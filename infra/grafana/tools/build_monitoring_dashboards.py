from pathlib import Path

from dashkit import (CH, UP_DOWN, Layout, bargauge, dashboard, gauge, override, override_regex, pie, prom,
                     prom_variable, sql, stat, state_timeline, steps, table, timeseries, write)

OUT = Path(__file__).resolve().parent.parent / "dashboards-monitoring"
TAGS = ["platform", "monitoring"]

ONESHOT = 'service=~".*-init|connect-register"'
LONG_RUNNING = 'service!~".*-init|connect-register"'

KAFKA_UP = ('(min(probe_success{service="Kafka broker"}) * clamp_max(max(kafka_brokers) or vector(0), 1)) '
            'or vector(0)')
CPU_PCT = '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[$__rate_interval])))'
MEM_PCT = '100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)'
DISK_PCT = '100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})'
CORES = 'count(node_cpu_seconds_total{mode="idle"})'

CONTAINER_STATE = (f'docker_container_running{{{LONG_RUNNING}}} * on(service, name) '
                   f'((3 - docker_container_healthy{{{LONG_RUNNING}}}) '
                   f'or on(service, name) (0 * docker_container_running{{{LONG_RUNNING}}} + 1))')
CONTAINER_STATE_MAP = [{"type": "value", "options": {
    "0": {"text": "STOPPED", "color": "red", "index": 0},
    "1": {"text": "RUNNING", "color": "blue", "index": 1},
    "2": {"text": "HEALTHY", "color": "green", "index": 2},
    "3": {"text": "UNHEALTHY", "color": "orange", "index": 3}}}]
RUNNING_MAP = [{"type": "value", "options": {
    "1": {"text": "RUNNING", "color": "green", "index": 0},
    "0": {"text": "NOT RUNNING", "color": "red", "index": 1}}}]
JOB_MAP = [{"type": "value", "options": {"0": {"text": "COMPLETED", "color": "green", "index": 0}}},
           {"type": "range", "options": {"from": 1, "to": 255, "result": {"text": "FAILED", "color": "red", "index": 1}}}]
LOAD_MAP = [{"type": "range", "options": {"from": 0, "to": 60, "result": {"text": "LIGHT", "color": "green", "index": 0}}},
            {"type": "range", "options": {"from": 60, "to": 85, "result": {"text": "BUSY", "color": "orange", "index": 1}}},
            {"type": "range", "options": {"from": 85, "to": 1000, "result": {"text": "HEAVY", "color": "red", "index": 2}}}]


def cpu_by(selector, legend="{{service}}"):
    return prom(f"sum by (service) (rate(docker_container_cpu_seconds_total{{{selector}}}[$__rate_interval])) * 100",
                legend)


def mem_by(selector, legend="{{service}}"):
    return prom(f"sum by (service) (docker_container_memory_working_set_bytes{{{selector}}})", legend)


L = Layout()
L.row("At a glance")
L.add(stat("Kafka", prom(KAFKA_UP), mappings=UP_DOWN, thresholds=steps("red", 1, "green"),
           description="UP when the broker port answers and the exporter sees at least one broker."), 4, 5)
L.add(stat("Debezium CDC connector", prom('probe_success{service="Debezium connector"}'), mappings=RUNNING_MAP,
           thresholds=steps("red", 1, "green"), no_value="NO DATA",
           description="Connector and all of its tasks report RUNNING on the Kafka Connect REST API."), 4, 5)
L.add(stat("Spark streaming", prom('probe_success{service="Spark streaming"}'), mappings=UP_DOWN,
           thresholds=steps("red", 1, "green"), no_value="NO DATA"), 4, 5)
L.add(stat("Services up", prom("sum(probe_success)"), color="#5b86f5", decimals=0), 3, 5)
L.add(stat("Services down", prom("count(probe_success == 0) or vector(0)"), thresholds=steps("green", 1, "red"),
           decimals=0), 3, 5)
L.add(stat("Firing alerts", prom('count(ALERTS{alertstate="firing"}) or vector(0)'),
           thresholds=steps("green", 1, "orange", 3, "red"), decimals=0), 3, 5)
L.add(stat("System load", prom(f'max(label_replace({CPU_PCT}, "r", "cpu", "", "") '
                               f'or label_replace(sum({MEM_PCT}), "r", "mem", "", ""))'),
           mappings=LOAD_MAP, thresholds=steps("green", 60, "orange", 85, "red"),
           description="Higher of host CPU % and memory %: LIGHT < 60, BUSY < 85, HEAVY above."), 3, 5)

L.row("Service probes")
for tier, title in (("streaming", "Streaming"), ("storage", "Storage"), ("batch|presentation", "Batch & presentation")):
    L.add(stat(title, prom(f'probe_success{{tier=~"{tier}"}}', "{{service}}"), mappings=UP_DOWN,
               thresholds=steps("red", 1, "green"), text_mode="value_and_name"), 8, 7)
L.add(state_timeline("Availability history", prom("probe_success", "{{service}}"), UP_DOWN,
                     description="Every 10 s each service is probed (HTTP health endpoint or TCP port)."), 24, 11)
L.add(bargauge("Availability in selected range", prom("sort(avg_over_time(probe_success[$__range]) * 100)",
                                                     "{{service}}", instant=True),
               unit="percent", mode="lcd", maximum=100, decimals=2, thresholds=steps("red", 95, "orange", 99, "green")),
      12, 10)
L.add(bargauge("Probe response time", prom("sort_desc(probe_duration_seconds)", "{{service}}", instant=True),
               unit="s", mode="gradient", thresholds=steps("green", 0.5, "orange", 2, "red"), decimals=3), 12, 10)

L.row("Containers")
L.add(stat("Container state", prom(CONTAINER_STATE, "{{service}}"), mappings=CONTAINER_STATE_MAP,
           thresholds=steps("red", 1, "blue", 2, "green", 3, "orange"), text_mode="value_and_name",
           description="HEALTHY / UNHEALTHY come from the Docker healthcheck; RUNNING means no healthcheck is defined."),
      24, 9)
L.add(stat("Init jobs", prom(f"docker_container_exit_code{{{ONESHOT}}}", "{{service}}"), mappings=JOB_MAP,
           thresholds=steps("green", 1, "red"), text_mode="value_and_name",
           description="One-shot jobs: restore + CDC setup, ClickHouse DDL, Airflow DB migration, connector registration."),
      8, 6)
L.add(bargauge("Restarts", prom(f"sort_desc(docker_container_restart_count{{{LONG_RUNNING}}})", "{{service}}",
                                instant=True),
               mode="basic", thresholds=steps("green", 1, "orange", 3, "red"), decimals=0), 8, 12)
L.add(bargauge("Uptime", prom(f"sort(time() - docker_container_started_at_seconds{{{LONG_RUNNING}}} "
                              f"and on(service, name) docker_container_running == 1)", "{{service}}", instant=True),
               unit="dtdurations", mode="gradient", thresholds=steps("orange", 300, "blue", 3600, "green"), decimals=0),
      8, 12)
L.add(table("Firing alerts", prom('ALERTS{alertstate="firing"}', instant=True, fmt="table"),
            no_value="No firing alerts",
            transformations=[{"id": "organize", "options": {
                "excludeByName": {"Time": True, "Value": True, "__name__": True, "alertstate": True, "job": True,
                                  "instance": True, "tier": True, "name": True},
                "indexByName": {"severity": 0, "alertname": 1, "service": 2}}}],
            overrides=[override("severity", custom_cellOptions={"type": "color-background"},
                                mappings=[{"type": "value", "options": {
                                    "critical": {"color": "red", "index": 0},
                                    "warning": {"color": "orange", "index": 1},
                                    "info": {"color": "blue", "index": 2}}}])]), 8, 6)

health = dashboard("platform-health", "Platform Health — Service Status", L, refresh="10s", time_from="now-3h",
                   tags=TAGS + ["health", "kafka"],
                   description="Up/down status of every service of the Students Data Platform.")

L = Layout()
L.row("Docker host (the Linux VM that runs the containers)")
L.add(stat("Status", prom(f'max(label_replace({CPU_PCT}, "r", "cpu", "", "") '
                          f'or label_replace(sum({MEM_PCT}), "r", "mem", "", ""))'),
           mappings=LOAD_MAP, thresholds=steps("green", 60, "orange", 85, "red")), 4, 6)
L.add(gauge("CPU", prom(CPU_PCT)), 4, 6)
L.add(gauge("Memory", prom(MEM_PCT)), 4, 6)
L.add(gauge("Disk /", prom(DISK_PCT), thresholds=steps("green", 75, "orange", 90, "red")), 4, 6)
L.add(gauge("Load per core (1m)", prom(f"node_load1 / scalar({CORES})"), unit="percentunit", maximum=2,
            thresholds=steps("green", 0.7, "orange", 1, "red"), decimals=2,
            description="1-minute load average divided by the number of cores; above 100% processes queue for CPU."),
      4, 6)
L.add(gauge("Swap", prom("100 * (1 - node_memory_SwapFree_bytes / node_memory_SwapTotal_bytes)"),
            thresholds=steps("green", 25, "orange", 60, "red"), no_value="no swap"), 4, 6)
L.add(stat("CPU cores", prom(CORES), color="#7c5ce0", decimals=0), 4, 3)
L.add(stat("Memory", prom("node_memory_MemTotal_bytes"), unit="bytes", color="#5b86f5"), 4, 3)
L.add(stat("Running containers", prom(f"sum(docker_container_running{{{LONG_RUNNING}}})"), color="#16a36a",
           decimals=0), 4, 3)
L.add(stat("Host uptime", prom("time() - node_boot_time_seconds"), unit="dtdurations", color="#d9772f"), 4, 3)
L.add(stat("Containers memory", prom("sum(docker_container_memory_working_set_bytes)"), unit="bytes",
           color="#e0559b"), 4, 3)
L.add(stat("Containers CPU", prom("sum(rate(docker_container_cpu_seconds_total[$__rate_interval])) * 100"),
           unit="percent", color="#0ea5a5", decimals=0, description="100% = one full CPU core."), 4, 3)

L.add(timeseries("CPU usage by mode", prom(
    'sum by (mode) (rate(node_cpu_seconds_total{mode!="idle"}[$__rate_interval])) '
    f'/ scalar({CORES}) * 100', "{{mode}}"), unit="percent", stack=True, fill=60, maximum=100), 12, 9)
L.add(timeseries("Memory", [prom("node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "used"),
                            prom("node_memory_MemAvailable_bytes", "available", ref="B")],
                 unit="bytes", stack=True, fill=50,
                 overrides=[override("used", color={"mode": "fixed", "fixedColor": "#e0559b"}),
                            override("available", color={"mode": "fixed", "fixedColor": "#16a36a"})]), 12, 9)
L.add(timeseries("Load average", [prom("node_load1", "1m"), prom("node_load5", "5m", ref="B"),
                                  prom("node_load15", "15m", ref="C"), prom(CORES, "cores", ref="D")],
                 decimals=2, fill=10,
                 overrides=[override("cores", color={"mode": "fixed", "fixedColor": "red"},
                                     custom_lineStyle={"fill": "dash", "dash": [10, 10]}, custom_fillOpacity=0)]), 8, 8)
L.add(timeseries("Pressure stall (PSI)", [
    prom("100 * rate(node_pressure_cpu_waiting_seconds_total[$__rate_interval])", "cpu"),
    prom("100 * rate(node_pressure_memory_waiting_seconds_total[$__rate_interval])", "memory", ref="B"),
    prom("100 * rate(node_pressure_io_waiting_seconds_total[$__rate_interval])", "io", ref="C")],
    unit="percent", fill=15,
    description="Share of time at least one task was waiting for CPU, memory or disk: the most direct 'is the system "
                "overloaded' signal."), 8, 8)
L.add(timeseries("Disk and network throughput", [
    prom("sum(rate(node_disk_read_bytes_total[$__rate_interval]))", "disk read"),
    prom("sum(rate(node_disk_written_bytes_total[$__rate_interval]))", "disk write", ref="B"),
    prom('sum(rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[$__rate_interval]))',
         "net in", ref="C"),
    prom('sum(rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[$__rate_interval]))',
         "net out", ref="D")],
    unit="Bps", fill=10, overrides=[override_regex(".*(write|out)", custom_transform="negative-Y")]), 8, 8)

L.row("Containers — who is using the resources?")
L.add(bargauge("CPU now (100% = 1 core)",
               prom("sort_desc(sum by (service) (rate(docker_container_cpu_seconds_total[2m])) * 100)",
                    "{{service}}", instant=True),
               unit="percent", mode="gradient", maximum=200, decimals=1,
               thresholds=steps("green", 50, "yellow", 100, "orange", 150, "red")), 8, 14)
L.add(bargauge("Memory now", prom("sort_desc(sum by (service) (docker_container_memory_working_set_bytes))",
                                  "{{service}}", instant=True),
               unit="bytes", mode="lcd", maximum=2 * 1024 ** 3,
               thresholds=steps("green", 512 * 1024 ** 2, "yellow", 1024 ** 3, "orange", 1536 * 1024 ** 2, "red")),
      8, 14)
L.add(pie("Memory share", prom("sum by (service) (docker_container_memory_working_set_bytes)", "{{service}}"),
          unit="bytes"), 8, 14)
L.add(timeseries("CPU by container", cpu_by('service=~"$service"'), unit="percent", stack=True, fill=40), 12, 10)
L.add(timeseries("Memory by container", mem_by('service=~"$service"'), unit="bytes", stack=True, fill=40), 12, 10)
L.add(timeseries("Network by container (in up / out down)", [
    prom('sum by (service) (rate(docker_container_network_receive_bytes_total{service=~"$service"}[$__rate_interval]))',
         "{{service}} in"),
    prom('sum by (service) (rate(docker_container_network_transmit_bytes_total{service=~"$service"}[$__rate_interval]))',
         "{{service}} out", ref="B")],
    unit="Bps", fill=10, legend_calcs=("mean", "max"), overrides=[override_regex(".* out", custom_transform="negative-Y")]),
    12, 10)
L.add(timeseries("Disk I/O by container (read up / write down)", [
    prom('sum by (service) (rate(docker_container_block_read_bytes_total{service=~"$service"}[$__rate_interval]))',
         "{{service}} read"),
    prom('sum by (service) (rate(docker_container_block_write_bytes_total{service=~"$service"}[$__rate_interval]))',
         "{{service}} write", ref="B")],
    unit="Bps", fill=10, legend_calcs=("mean", "max"),
    overrides=[override_regex(".* write", custom_transform="negative-Y")]), 12, 10)
L.add(bargauge("Threads / processes", prom("sort_desc(sum by (service) (docker_container_pids))", "{{service}}",
                                           instant=True),
               mode="basic", scheme="continuous-BlPu", decimals=0), 12, 10)
L.add(bargauge("CPU time consumed since start", prom("sort_desc(sum by (service) (docker_container_cpu_seconds_total))",
                                                     "{{service}}", instant=True),
               unit="s", mode="gradient", scheme="continuous-GrYlRd", decimals=0), 12, 10)

load = dashboard("system-load", "System Load — Host & Containers", L, refresh="15s", time_from="now-1h",
                 tags=TAGS + ["load"],
                 variables=[prom_variable("service", "Service", "label_values(docker_container_running, service)")],
                 description="CPU, memory, disk and network of the Docker host and of each container.")

L = Layout()
L.row("Broker")
L.add(stat("Kafka", prom(KAFKA_UP), mappings=UP_DOWN, thresholds=steps("red", 1, "green")), 4, 5)
L.add(stat("Brokers online", prom("max(kafka_brokers) or vector(0)"), thresholds=steps("red", 1, "green"),
           decimals=0), 4, 5)
L.add(stat("Topics", prom("count(kafka_topic_partitions)"), color="#5b86f5", decimals=0), 4, 5)
L.add(stat("Partitions", prom("sum(kafka_topic_partitions)"), color="#7c5ce0", decimals=0), 4, 5)
L.add(stat("Under-replicated partitions", prom("sum(kafka_topic_partition_under_replicated_partition) or vector(0)"),
           thresholds=steps("green", 1, "red"), decimals=0), 4, 5)
L.add(stat("Kafka uptime", prom('time() - max(docker_container_started_at_seconds{service="kafka"})'),
           unit="dtdurations", color="#d9772f"), 4, 5)
L.add(stat("CDC connector", prom('probe_success{service="Debezium connector"}'), mappings=RUNNING_MAP,
           thresholds=steps("red", 1, "green")), 4, 4)
L.add(stat("Kafka Connect", prom('probe_success{service="Kafka Connect"}'), mappings=UP_DOWN,
           thresholds=steps("red", 1, "green")), 4, 4)
L.add(stat("Spark streaming", prom('probe_success{service="Spark streaming"}'), mappings=UP_DOWN,
           thresholds=steps("red", 1, "green")), 4, 4)
L.add(stat("CDC messages (selected range)",
           prom('sum(increase(kafka_topic_partition_current_offset{topic=~"students[.].+"}[$__range]))', instant=True),
           color="#16a36a", decimals=0), 4, 4)
L.add(stat("Kafka restarts", prom('max(docker_container_restart_count{service="kafka"})'),
           thresholds=steps("green", 1, "orange", 3, "red"), decimals=0), 4, 4)
L.add(stat("Kafka memory", prom('sum(docker_container_memory_working_set_bytes{service="kafka"})'), unit="bytes",
           color="#e0559b"), 4, 4)

L.row("Throughput")
L.add(timeseries("CDC messages / s by topic",
                 prom('sum by (topic) (rate(kafka_topic_partition_current_offset{topic=~"students[.].+"}[$__rate_interval]))',
                      "{{topic}}"),
                 unit="short", draw="bars", fill=80, gradient="hue", decimals=2,
                 no_value="No CDC topics yet: Debezium creates a topic on the first change of each table."), 12, 9)
L.add(timeseries("All topics — messages / s",
                 prom('sum by (topic) (rate(kafka_topic_partition_current_offset[$__rate_interval]))', "{{topic}}"),
                 unit="short", stack=True, fill=35, decimals=2), 12, 9)
L.add(bargauge("Messages produced in selected range",
               prom('sort_desc(sum by (topic) (increase(kafka_topic_partition_current_offset[$__range])))', "{{topic}}",
                    instant=True),
               mode="gradient", scheme="continuous-BlYlRd", decimals=0), 8, 10)
L.add(bargauge("Messages retained per topic",
               prom("sort_desc(sum by (topic) (kafka_topic_partition_current_offset - kafka_topic_partition_oldest_offset))",
                    "{{topic}}", instant=True),
               mode="lcd", scheme="continuous-GrYlRd", decimals=0), 8, 10)
L.add(bargauge("Partitions per topic", prom("sort_desc(kafka_topic_partitions)", "{{topic}}", instant=True),
               mode="basic", scheme="continuous-BlPu", decimals=0), 8, 10)
L.add(timeseries("Consumer group lag", prom("sum by (consumergroup, topic) (kafka_consumergroup_lag)",
                                            "{{consumergroup}} / {{topic}}"),
                 unit="short", fill=20,
                 no_value="No consumer group commits offsets to Kafka (Spark keeps its offsets in the checkpoint).",
                 description="Only groups that commit offsets to Kafka appear here."), 12, 8)
L.add(timeseries("Warehouse side: CDC events / min (ClickHouse)", sql(
    "SELECT toStartOfMinute(processed_at) AS time, source_table, count() AS events FROM cdc_event_log "
    "WHERE $__timeFilter(processed_at) GROUP BY time, source_table ORDER BY time", timeseries=True),
    draw="bars", fill=80, gradient="hue", legend_calcs=("sum",),
    no_value="No change events in the selected range. Edit a record in the portal to generate one."), 12, 8)

L.row("Streaming services")
L.add(state_timeline("Streaming availability", prom('probe_success{tier="streaming"}', "{{service}}"), UP_DOWN),
      24, 7)
L.add(timeseries("CPU — streaming containers", cpu_by('service=~"kafka|connect|spark-streaming|kafka-ui|kafka-exporter"'),
                 unit="percent", fill=20), 8, 9)
L.add(timeseries("Memory — streaming containers",
                 mem_by('service=~"kafka|connect|spark-streaming|kafka-ui|kafka-exporter"'), unit="bytes", fill=20), 8, 9)
L.add(timeseries("Probe response time", prom('probe_duration_seconds{tier="streaming"}', "{{service}}"), unit="s",
                 fill=10), 8, 9)

kafka = dashboard("kafka-streaming", "Kafka & CDC Streaming", L, refresh="10s", time_from="now-1h",
                  tags=TAGS + ["kafka", "cdc"],
                  description="Kafka broker health, topic throughput and the Debezium -> Kafka -> Spark path.")

L = Layout()
L.row("ClickHouse (warehouse)")
L.add(stat("ClickHouse", prom('probe_success{service="ClickHouse"}'), mappings=UP_DOWN,
           thresholds=steps("red", 1, "green")), 4, 5)
L.add(stat("Uptime", prom("ClickHouseAsyncMetrics_Uptime"), unit="dtdurations", color="#d9772f"), 4, 5)
L.add(stat("Queries / s", prom("sum(rate(ClickHouseProfileEvents_Query[$__rate_interval]))"), unit="reqps",
           color="#5b86f5", decimals=2, graph=True), 4, 5)
L.add(stat("Memory in use", prom("ClickHouseMetrics_MemoryTracking"), unit="bytes", color="#e0559b", graph=True), 4, 5)
L.add(stat("Data on disk (MergeTree)", prom("ClickHouseAsyncMetrics_TotalBytesOfMergeTreeTables"), unit="bytes",
           color="#7c5ce0"), 4, 5)
L.add(gauge("Max parts per partition", prom("ClickHouseAsyncMetrics_MaxPartCountForPartition"), unit="short",
            maximum=300, decimals=0, thresholds=steps("green", 100, "orange", 250, "red"),
            description="Inserts are throttled at 300 parts per partition (parts_to_delay_insert)."), 4, 5)
L.add(timeseries("Queries / s", [
    prom("rate(ClickHouseProfileEvents_SelectQuery[$__rate_interval])", "select"),
    prom("rate(ClickHouseProfileEvents_InsertQuery[$__rate_interval])", "insert", ref="B"),
    prom("rate(ClickHouseProfileEvents_FailedQuery[$__rate_interval])", "failed", ref="C")],
    unit="reqps", fill=25, decimals=2,
    overrides=[override("failed", color={"mode": "fixed", "fixedColor": "red"})]), 8, 9)
L.add(timeseries("Rows / s", [
    prom("rate(ClickHouseProfileEvents_SelectedRows[$__rate_interval])", "read"),
    prom("rate(ClickHouseProfileEvents_InsertedRows[$__rate_interval])", "inserted", ref="B"),
    prom("rate(ClickHouseProfileEvents_MergedRows[$__rate_interval])", "merged", ref="C")],
    unit="short", fill=25), 8, 9)
L.add(timeseries("Memory, parts and merges", [
    prom("ClickHouseMetrics_MemoryTracking", "memory"),
    prom("ClickHouseMetrics_PartsActive", "active parts", ref="B"),
    prom("ClickHouseMetrics_Merge", "running merges", ref="C")],
    fill=15, overrides=[override("memory", unit="bytes"),
                        override_regex("active parts|running merges", custom_axisPlacement="right", unit="short")]),
    8, 9)

L.row("PostgreSQL (staging + Airflow metadata)")
L.add(stat("PostgreSQL", prom("pg_up"), mappings=UP_DOWN, thresholds=steps("red", 1, "green")), 4, 5)
L.add(gauge("Connections used", prom("100 * sum(pg_stat_database_numbackends) / sum(pg_settings_max_connections)"),
            thresholds=steps("green", 60, "orange", 85, "red")), 4, 5)
L.add(gauge("Cache hit ratio", prom("100 * sum(pg_stat_database_blks_hit) / "
                                    "(sum(pg_stat_database_blks_hit) + sum(pg_stat_database_blks_read))"),
            thresholds=steps("red", 90, "orange", 99, "green"), decimals=2), 4, 5)
L.add(stat("Transactions / s", prom('sum(rate(pg_stat_database_xact_commit[$__rate_interval]))'), unit="short",
           color="#5b86f5", decimals=1, graph=True), 4, 5)
L.add(stat("Deadlocks (range)", prom("sum(increase(pg_stat_database_deadlocks[$__range]))", instant=True),
           thresholds=steps("green", 1, "red"), decimals=0), 4, 5)
L.add(stat("Total size", prom("sum(pg_database_size_bytes)"), unit="bytes", color="#7c5ce0"), 4, 5)
L.add(timeseries("Transactions / s by database", [
    prom('sum by (datname) (rate(pg_stat_database_xact_commit{datname!~"template.*|"}[$__rate_interval]))',
         "{{datname}} commit"),
    prom('sum by (datname) (rate(pg_stat_database_xact_rollback{datname!~"template.*|"}[$__rate_interval]))',
         "{{datname}} rollback", ref="B")],
    unit="short", fill=20, decimals=2, overrides=[override_regex(".* rollback", custom_transform="negative-Y")]), 8, 9)
L.add(timeseries("Rows written / s", [
    prom("sum(rate(pg_stat_database_tup_inserted[$__rate_interval]))", "inserted"),
    prom("sum(rate(pg_stat_database_tup_updated[$__rate_interval]))", "updated", ref="B"),
    prom("sum(rate(pg_stat_database_tup_deleted[$__rate_interval]))", "deleted", ref="C")],
    unit="short", stack=True, fill=45), 8, 9)
L.add(timeseries("Sessions by state", prom('sum by (state) (pg_stat_activity_count)', "{{state}}"),
                 stack=True, fill=45, decimals=0), 8, 9)
L.add(bargauge("Database size", prom('sort_desc(pg_database_size_bytes{datname!~"template.*"})', "{{datname}}",
                                     instant=True),
               unit="bytes", mode="gradient", scheme="continuous-BlPu"), 12, 7)
L.add(bargauge("Locks by mode", prom("sort_desc(sum by (mode) (pg_locks_count))", "{{mode}}", instant=True),
               mode="lcd", scheme="continuous-GrYlRd", decimals=0), 12, 7)

L.row("SQL Server (operational source)")
L.add(stat("SQL Server", prom('probe_success{service="SQL Server"}'), mappings=UP_DOWN,
           thresholds=steps("red", 1, "green")), 4, 5)
L.add(stat("CPU", prom('sum(rate(docker_container_cpu_seconds_total{service="mssql"}[$__rate_interval])) * 100'),
           unit="percent", color="#0ea5a5", decimals=1, graph=True), 4, 5)
L.add(stat("Memory", prom('sum(docker_container_memory_working_set_bytes{service="mssql"})'), unit="bytes",
           color="#e0559b", graph=True), 4, 5)
L.add(stat("Disk written (range)",
           prom('sum(increase(docker_container_block_write_bytes_total{service="mssql"}[$__range]))', instant=True),
           unit="bytes", color="#d9772f"), 4, 5)
L.add(stat("TCP connect time", prom('probe_duration_seconds{service="SQL Server"}'), unit="s", decimals=3,
           thresholds=steps("green", 0.1, "orange", 1, "red")), 4, 5)
L.add(stat("Restarts", prom('max(docker_container_restart_count{service="mssql"})'),
           thresholds=steps("green", 1, "orange", 3, "red"), decimals=0), 4, 5)
L.add(timeseries("CPU — database containers", cpu_by('service=~"mssql|postgres|clickhouse"'), unit="percent",
                 fill=20), 12, 9)
L.add(timeseries("Memory — database containers", mem_by('service=~"mssql|postgres|clickhouse"'), unit="bytes",
                 fill=20), 12, 9)

databases = dashboard("platform-databases", "Databases — ClickHouse, PostgreSQL, SQL Server", L, refresh="15s",
                      time_from="now-1h", tags=TAGS + ["databases"],
                      description="Query load, memory, storage and connections of the three databases.")

for name, data in (("platform-health.json", health), ("system-load.json", load), ("kafka-streaming.json", kafka),
                   ("databases.json", databases)):
    write(OUT, name, data)
print("monitoring dashboards written to", OUT)
