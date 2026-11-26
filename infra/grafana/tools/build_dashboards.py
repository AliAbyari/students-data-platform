import json
from pathlib import Path

import dashkit as dk
from dashkit import override, sql, steps

DS = {"type": "grafana-clickhouse-datasource", "uid": "clickhouse-dw"}
OUT = Path(__file__).resolve().parent.parent / "dashboards"


def target(sql, timeseries=False):
    return {"datasource": DS, "editorType": "sql", "format": 0 if timeseries else 1,
            "queryType": "timeseries" if timeseries else "table", "rawSql": sql, "refId": "A"}


def panel(pid, title, kind, sql, x, y, w, h, timeseries=False, unit=None, decimals=None, options=None,
          description=None, minimum=None, maximum=None, no_value=None):
    defaults = {}
    if no_value:
        defaults["noValue"] = no_value
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    if unit:
        defaults["unit"] = unit
    if decimals is not None:
        defaults["decimals"] = decimals
    p = {"id": pid, "title": title, "type": kind, "datasource": DS, "targets": [target(sql, timeseries)],
         "gridPos": {"x": x, "y": y, "w": w, "h": h}, "fieldConfig": {"defaults": defaults, "overrides": []},
         "options": options or {}}
    if description:
        p["description"] = description
    return p


def stat(pid, title, sql, x, y, w=6, h=4, unit=None, color="blue", no_value=None, description=None):
    p = panel(pid, title, "stat", sql, x, y, w, h, unit=unit or "locale", description=description, no_value=no_value,
              options={"colorMode": "background", "graphMode": "none", "justifyMode": "center",
                       "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}})
    p["fieldConfig"]["defaults"]["color"] = {"mode": "fixed", "fixedColor": color}
    return p


def bar(pid, title, sql, x, y, w, h, horizontal=False, unit=None, decimals=None, minimum=None, maximum=None):
    return panel(pid, title, "barchart", sql, x, y, w, h, unit=unit, decimals=decimals, minimum=minimum, maximum=maximum,
                 options={"orientation": "horizontal" if horizontal else "auto",
                          "showValue": "always" if horizontal else "never",
                          "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
                          "xTickLabelRotation": 0 if horizontal else -45})


def table(pid, title, sql, x, y, w, h, unit=None):
    return panel(pid, title, "table", sql, x, y, w, h, unit=unit, options={"showHeader": True, "cellHeight": "sm"})


def dashboard(uid, title, panels, refresh, time_from="now-6h", tags=()):
    return {"uid": uid, "title": title, "tags": ["platform", *tags], "timezone": "browser", "schemaVersion": 39,
            "version": 1, "editable": False, "refresh": refresh, "time": {"from": time_from, "to": "now"},
            "panels": panels, "templating": {"list": []}, "annotations": {"list": []}, "links": dk.PLATFORM_LINKS}


overview = dashboard("students-dw-overview", "Students DW — Overview", [
    stat(1, "Total students", "SELECT count() FROM v_dim_student WHERE student_key > 0", 0, 0, color="#5b86f5"),
    stat(2, "Active", "SELECT countIf(student_status_code = 'A') FROM v_dim_student WHERE student_key > 0", 6, 0, color="#16a36a"),
    stat(3, "Graduated", "SELECT countIf(student_status_code = 'G') FROM v_dim_student WHERE student_key > 0", 12, 0, color="#7c5ce0"),
    stat(4, "Withdrawn", "SELECT countIf(student_status_code = 'W') FROM v_dim_student WHERE student_key > 0", 18, 0, color="#d9772f"),
    bar(5, "Course enrollments by term",
        "SELECT any(t.term_name) AS term, sum(f.enrollment_count) AS enrollments FROM v_fact_enrollment AS f "
        "INNER JOIN v_dim_term AS t ON t.term_key = f.term_key WHERE f.term_key > 0 GROUP BY f.term_key ORDER BY f.term_key",
        0, 4, 16, 9, unit="short"),
    bar(6, "GPA by department",
        "SELECT d.department_name AS department, round(toFloat64(sum(f.quality_points)) / nullIf(toFloat64(sum(f.gpa_credits)), 0), 2) AS gpa "
        "FROM v_fact_enrollment AS f INNER JOIN v_dim_department AS d ON d.department_key = f.department_key "
        "GROUP BY department ORDER BY gpa DESC", 16, 4, 8, 9, horizontal=True, decimals=2, minimum=0, maximum=4),
    bar(7, "Seat fill rate by department (%)",
        "SELECT department_name AS department, round(100 * sum(enrolled) / nullIf(sum(capacity), 0), 1) AS fill_rate "
        "FROM rpt_course_offering_fill WHERE department_name != '' GROUP BY department ORDER BY fill_rate DESC",
        0, 13, 8, 9, horizontal=True, unit="percent", decimals=1, minimum=0, maximum=100),
    bar(8, "Applications vs admissions by entry year",
        "SELECT toString(calendar_year) AS year, sum(application_count) AS applications, sum(admitted_count) AS admitted, "
        "sum(enrolled_count) AS enrolled FROM rpt_admissions WHERE calendar_year > 0 GROUP BY calendar_year ORDER BY calendar_year",
        8, 13, 16, 9),
    panel(9, "Grade distribution", "piechart",
          "SELECT g.grade_code AS grade, count() AS enrollments FROM v_fact_enrollment AS f "
          "INNER JOIN v_dim_grade AS g ON g.grade_key = f.grade_key GROUP BY grade ORDER BY grade",
          0, 22, 8, 9, unit="locale", options={"pieType": "donut", "reduceOptions": {"calcs": ["lastNotNull"], "values": True},
                                "legend": {"showLegend": True, "displayMode": "table", "placement": "right", "values": ["value", "percent"]}}),
    table(10, "Students by census region and status",
          "SELECT census_region AS region, countIf(student_status_code = 'A') AS active, "
          "countIf(student_status_code = 'G') AS graduated, countIf(student_status_code = 'W') AS withdrawn, count() AS total "
          "FROM v_dim_student WHERE student_key > 0 GROUP BY region ORDER BY total DESC", 8, 22, 16, 9, unit="locale"),
], refresh="1m", tags=["students", "warehouse"])

IDLE = "No change events in the selected range. Edit a record in the portal to generate one."

operations = dashboard("students-dw-operations", "Students DW — CDC & Pipelines", [
    stat(1, "CDC events (selected range)", "SELECT count() FROM cdc_event_log WHERE $__timeFilter(processed_at)", 0, 0, color="#5b86f5"),
    stat(2, "Median latency (last 100 events)",
         "SELECT quantile(0.5)(end_to_end_ms) FROM (SELECT end_to_end_ms FROM cdc_event_log "
         "ORDER BY processed_at DESC LIMIT 100) HAVING count() > 0",
         6, 0, unit="ms", color="#16a36a", no_value="—",
         description="Commit in SQL Server to row in ClickHouse, over the latest 100 change events."),
    stat(3, "p95 latency (last 100 events)",
         "SELECT quantile(0.95)(end_to_end_ms) FROM (SELECT end_to_end_ms FROM cdc_event_log "
         "ORDER BY processed_at DESC LIMIT 100) HAVING count() > 0",
         12, 0, unit="ms", color="#7c5ce0", no_value="—",
         description="Commit in SQL Server to row in ClickHouse, over the latest 100 change events."),
    stat(4, "Last successful batch",
         "SELECT toUnixTimestamp64Milli(max(run_finished_at)) FROM rpt_pipeline_runs "
         "WHERE pipeline = 'batch_scd' AND has_failure = 0 AND arrayExists(s -> s.2 = 'fact.application', steps) "
         "HAVING count() > 0",
         18, 0, unit="dateTimeFromNow", color="#d9772f", no_value="—"),
    panel(5, "CDC events per minute by table", "timeseries",
          "SELECT toStartOfMinute(processed_at) AS time, source_table, count() AS events FROM cdc_event_log "
          "WHERE $__timeFilter(processed_at) GROUP BY time, source_table ORDER BY time",
          0, 4, 12, 9, timeseries=True, no_value=IDLE,
          options={"legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"}}),
    panel(6, "End-to-end latency (commit to warehouse)", "timeseries",
          "SELECT toStartOfMinute(processed_at) AS time, avg(end_to_end_ms) AS avg_ms, quantile(0.95)(end_to_end_ms) AS p95_ms "
          "FROM cdc_event_log WHERE $__timeFilter(processed_at) GROUP BY time ORDER BY time",
          12, 4, 12, 9, timeseries=True, unit="ms", no_value=IDLE),
    table(7, "Recent change events",
          "SELECT processed_at, source_table, operation, business_key, end_to_end_ms FROM cdc_event_log "
          "ORDER BY processed_at DESC LIMIT 50", 0, 13, 12, 10),
    table(8, "Batch runs",
          "SELECT batch_id, pipeline, run_started_at, run_finished_at, has_failure, total_rows_written "
          "FROM rpt_pipeline_runs ORDER BY run_started_at DESC LIMIT 20", 12, 13, 12, 10),
    table(9, "Data quality — latest batch",
          "SELECT rule_name, table_name, severity, failed_rows, passed FROM dq_result "
          "WHERE batch_id = (SELECT max(batch_id) FROM dq_result) ORDER BY passed, severity, rule_name", 0, 23, 24, 9),
], refresh="10s", time_from="now-24h", tags=["students", "cdc", "operations"])

GRADE_COLORS = {"A": "#16a36a", "B": "#5b86f5", "C": "#f2c744", "D": "#ff8c3a", "F": "#e5484d", "W": "#a1a1aa"}
GPA = "round(toFloat64(sum(quality_points)) / nullIf(toFloat64(sum(gpa_credits)), 0), 2)"
L = dk.Layout()
L.row("Key figures")
L.add(dk.stat("Enrollments", sql("SELECT sum(enrollment_count) FROM v_fact_enrollment"), unit="short", color="#5b86f5"),
      4, 4)
L.add(dk.stat("Students", sql("SELECT count() FROM v_dim_student WHERE student_key > 0"), unit="short",
              color="#7c5ce0"), 4, 4)
L.add(dk.stat("Courses", sql("SELECT count() FROM v_dim_course WHERE course_key > 0"), color="#0ea5a5"), 4, 4)
L.add(dk.stat("Departments", sql("SELECT count() FROM v_dim_department WHERE department_key > 0"), color="#d9772f"),
      4, 4)
L.add(dk.stat("Applications", sql("SELECT sum(application_count) FROM v_fact_application"), unit="short",
              color="#e0559b"), 4, 4)
L.add(dk.stat("Credits earned", sql("SELECT sum(credits_earned) FROM v_fact_enrollment"), unit="short",
              color="#16a36a"), 4, 4)
L.add(dk.gauge("Overall GPA", sql(f"SELECT {GPA} FROM v_fact_enrollment"), unit="none", maximum=4, decimals=2,
               thresholds=steps("red", 2, "orange", 2.7, "yellow", 3.2, "green")), 6, 7)
L.add(dk.gauge("Admission rate", sql("SELECT round(100 * sum(admitted_count) / nullIf(sum(application_count), 0), 1) "
                                     "FROM v_fact_application"),
               thresholds=steps("purple", 30, "blue", 60, "green"),
               description="Admitted applicants / all applications."), 6, 7)
L.add(dk.gauge("Yield", sql("SELECT round(100 * sum(enrolled_count) / nullIf(sum(admitted_count), 0), 1) "
                            "FROM v_fact_application"),
               thresholds=steps("red", 25, "orange", 40, "green"), description="Enrolled / admitted applicants."),
      6, 7)
L.add(dk.bargauge("Admissions funnel", sql(
    "SELECT sum(application_count) AS Applications, sum(admitted_count) AS Admitted, sum(enrolled_count) AS Enrolled "
    "FROM v_fact_application"), unit="short", mode="gradient",
    overrides=[override("Applications", color=dk.fixed("#5b86f5")), override("Admitted", color=dk.fixed("#7c5ce0")),
               override("Enrolled", color=dk.fixed("#16a36a"))]), 6, 7)

L.row("Academic performance")
L.add(dk.pie("Grade distribution", sql(
    "SELECT " + ", ".join(f"sumIf(f.enrollment_count, g.grade_code = '{c}') AS {c}" for c in GRADE_COLORS) +
    " FROM v_fact_enrollment AS f INNER JOIN v_dim_grade AS g ON g.grade_key = f.grade_key"),
    overrides=[override(c, color=dk.fixed(col)) for c, col in GRADE_COLORS.items()]), 8, 9)
L.add(dk.bargauge("GPA by school", sql(
    f"SELECT school_name AS school, {GPA} AS gpa FROM rpt_enrollment WHERE school_name != '' "
    "GROUP BY school ORDER BY gpa DESC"), values=True, unit="none", mode="gradient", minimum=2, maximum=4,
    decimals=2, scheme="continuous-RdYlGr"), 8, 9)
L.add(dk.bargauge("Top 10 courses by enrollment", sql(
    "SELECT concat(c.course_code, '  ', c.course_title) AS course, sum(f.enrollment_count) AS enrollments "
    "FROM v_fact_enrollment AS f INNER JOIN v_dim_course AS c ON c.course_key = f.course_key "
    "GROUP BY course ORDER BY enrollments DESC LIMIT 10"), values=True, unit="short", mode="lcd",
    scheme="continuous-BlPu"), 8, 9)
L.add(dk.barchart("Enrollments per year by school", sql(
    "SELECT toString(calendar_year) AS year, school_name AS school, sum(enrollment_count) AS enrollments "
    "FROM rpt_enrollment WHERE calendar_year > 0 GROUP BY year, school ORDER BY year"),
    stack=True, unit="short", show_value="never",
    transformations=[{"id": "groupingToMatrix", "options": {"rowField": "year", "columnField": "school",
                                                            "valueField": "enrollments", "emptyValue": "zero"}}]),
    16, 10)
L.add(dk.bargauge("Students by class standing", sql(
    "SELECT class_standing_name AS standing, sum(enrollment_count) AS enrollments FROM rpt_enrollment "
    "WHERE class_standing_name != '' GROUP BY standing ORDER BY enrollments DESC"), values=True, unit="short",
    mode="gradient", scheme="continuous-GrYlRd"), 8, 10)
L.add(dk.table("Enrollment heat map — department × year", sql(
    "SELECT department_name AS department, toString(calendar_year) AS year, sum(enrollment_count) AS enrollments "
    "FROM rpt_enrollment WHERE calendar_year > 0 AND department_name != '' GROUP BY department, year ORDER BY year"),
    unit="short", cell="color-background", scheme="continuous-BlYlRd",
    transformations=[{"id": "groupingToMatrix", "options": {"rowField": "department", "columnField": "year",
                                                            "valueField": "enrollments", "emptyValue": "zero"}}],
    overrides=[override("department\\year", custom_cellOptions={"type": "auto"}, custom_width=160)]), 24, 10)

L.row("Admissions & demographics")
L.add(dk.barchart("Admission rate by entry year (%)", sql(
    "SELECT toString(calendar_year) AS year, round(100 * sum(admitted_count) / nullIf(sum(application_count), 0), 1) "
    "AS admission_rate FROM rpt_admissions WHERE calendar_year > 0 GROUP BY year ORDER BY year"),
    unit="percent", decimals=1, scheme="continuous-RdYlGr", show_value="always"), 12, 9)
L.add(dk.barchart("SAT score distribution", sql(
    "SELECT toString(intDiv(sat_total_score, 100) * 100) AS sat, count() AS applicants FROM rpt_admissions "
    "WHERE sat_total_score > 0 GROUP BY sat ORDER BY sat"), unit="short", scheme="continuous-BlPu",
    show_value="never"), 12, 9)
L.add(dk.pie("Students by gender", sql(
    "SELECT countIf(gender = 'F') AS Female, countIf(gender = 'M') AS Male FROM v_dim_student WHERE student_key > 0"),
    overrides=[override("Female", color=dk.fixed("#e0559b")), override("Male", color=dk.fixed("#5b86f5"))]), 8, 9)
L.add(dk.pie("Applicants by census region", sql(
    "SELECT census_region AS region, sum(application_count) AS applications FROM rpt_admissions "
    "WHERE census_region != '' GROUP BY region ORDER BY applications DESC"), values=True), 8, 9)
L.add(dk.bargauge("Average high-school GPA by entry year", sql(
    "SELECT toString(calendar_year) AS year, round(avg(high_school_gpa), 2) AS hs_gpa FROM rpt_admissions "
    "WHERE calendar_year > 0 AND high_school_gpa > 0 GROUP BY year ORDER BY year"), values=True, unit="none",
    mode="lcd", minimum=2.5, maximum=4, decimals=2, scheme="continuous-YlBl"), 8, 9)

insights = dk.dashboard("students-dw-insights", "Students DW — Insights", L, refresh="5m", time_from="now-6h",
                        tags=["students", "warehouse", "kpi"],
                        description="Colourful academic and admissions KPIs from the ClickHouse warehouse.")

PARTS = "FROM system.parts WHERE active AND database = currentDatabase()"
QLOG = "FROM system.query_log WHERE $__timeFilter(event_time)"
L = dk.Layout()
L.row("Storage")
L.add(dk.stat("Tables", sql("SELECT count() FROM system.tables WHERE database = currentDatabase() "
                            "AND engine LIKE '%MergeTree%'"), color="#5b86f5"), 4, 4)
L.add(dk.stat("Rows", sql(f"SELECT sum(rows) {PARTS}"), unit="short", color="#7c5ce0"), 4, 4)
L.add(dk.stat("Size on disk", sql(f"SELECT sum(bytes_on_disk) {PARTS}"), unit="bytes", color="#e0559b"), 4, 4)
L.add(dk.stat("Compression ratio", sql(f"SELECT round(sum(data_uncompressed_bytes) / sum(data_compressed_bytes), 1) "
                                       f"{PARTS}"), unit="x", decimals=1, color="#16a36a"), 4, 4)
L.add(dk.stat("Queries (range)", sql(f"SELECT count() {QLOG} AND type = 'QueryFinish'"), unit="short",
              color="#0ea5a5"), 4, 4)
L.add(dk.stat("Failed queries (range)", sql(f"SELECT count() {QLOG} AND type IN ('ExceptionBeforeStart', "
                                            "'ExceptionWhileProcessing')"),
              thresholds=steps("green", 1, "orange", 10, "red")), 4, 4)
L.add(dk.bargauge("Size on disk by table", sql(f"SELECT table, sum(bytes_on_disk) AS size {PARTS} GROUP BY table "
                                               "ORDER BY size DESC"),
                  values=True, unit="bytes", mode="gradient", scheme="continuous-BlPu"), 12, 11)
L.add(dk.table("Tables", sql(
    "SELECT table, sum(rows) AS rows, sum(bytes_on_disk) AS size, count() AS parts, "
    "round(sum(data_uncompressed_bytes) / sum(data_compressed_bytes), 1) AS ratio, max(modification_time) AS last_write "
    f"{PARTS} GROUP BY table ORDER BY size DESC"),
    sort_by=("size", True),
    overrides=[override("size", unit="bytes", custom_cellOptions={"type": "gauge", "mode": "gradient"},
                        color={"mode": "continuous-BlPu"}),
               override("rows", unit="short"),
               override("parts", custom_cellOptions={"type": "color-background"},
                        thresholds=steps("green", 20, "orange", 100, "red"), color={"mode": "thresholds"}),
               override("ratio", unit="x")]), 12, 11)

L.row("Query activity")
L.add(dk.timeseries("Queries per minute by kind", sql(
    f"SELECT toStartOfMinute(event_time) AS time, query_kind, count() AS queries {QLOG} AND type = 'QueryFinish' "
    "GROUP BY time, query_kind ORDER BY time", timeseries=True), draw="bars", fill=80, stack=True,
    legend_calcs=("sum",)), 12, 9)
L.add(dk.timeseries("Query duration", sql(
    f"SELECT toStartOfMinute(event_time) AS time, quantile(0.5)(query_duration_ms) AS p50, "
    f"quantile(0.95)(query_duration_ms) AS p95, max(query_duration_ms) AS max {QLOG} AND type = 'QueryFinish' "
    "GROUP BY time ORDER BY time", timeseries=True), unit="ms", fill=15,
    overrides=[override("max", color=dk.fixed("red")), override("p95", color=dk.fixed("orange")),
               override("p50", color=dk.fixed("green"))]), 12, 9)
L.add(dk.timeseries("Rows read and memory per minute", sql(
    f"SELECT toStartOfMinute(event_time) AS time, sum(read_rows) AS rows_read, max(memory_usage) AS peak_memory "
    f"{QLOG} AND type = 'QueryFinish' GROUP BY time ORDER BY time", timeseries=True), fill=20,
    overrides=[override("peak_memory", unit="bytes", custom_axisPlacement="right"),
               override("rows_read", unit="short")]), 12, 9)
L.add(dk.pie("Queries by user", sql(f"SELECT user, count() AS queries {QLOG} AND type = 'QueryFinish' GROUP BY user"),
             values=True), 6, 9)
L.add(dk.pie("Queries by kind", sql(f"SELECT query_kind, count() AS queries {QLOG} AND type = 'QueryFinish' "
                                    "GROUP BY query_kind"), values=True), 6, 9)
L.add(dk.table("Slowest queries (selected range)", sql(
    "SELECT event_time, user, query_duration_ms AS duration_ms, read_rows, memory_usage AS memory, "
    f"substring(replaceRegexpAll(query, '\\\\s+', ' '), 1, 160) AS query {QLOG} AND type = 'QueryFinish' "
    "ORDER BY query_duration_ms DESC LIMIT 15"),
    overrides=[override("duration_ms", unit="ms", custom_cellOptions={"type": "color-background"},
                        thresholds=steps("green", 500, "orange", 2000, "red"), color={"mode": "thresholds"}),
               override("memory", unit="bytes"), override("read_rows", unit="short")]), 24, 9)
L.add(dk.table("Recent errors", sql(
    "SELECT event_time, user, exception_code AS code, substring(exception, 1, 200) AS error, "
    f"substring(replaceRegexpAll(query, '\\\\s+', ' '), 1, 120) AS query {QLOG} AND exception != '' "
    "ORDER BY event_time DESC LIMIT 20"), no_value="No failed queries in the selected range",
    overrides=[override("code", custom_cellOptions={"type": "color-background"}, color=dk.fixed("red"))]), 24, 8)

internals = dk.dashboard("clickhouse-internals", "ClickHouse — Warehouse Internals", L, refresh="30s",
                         time_from="now-3h", tags=["warehouse", "clickhouse", "operations"],
                         description="Table sizes, parts, compression and query activity from ClickHouse system tables.")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "dw-overview.json").write_text(json.dumps(overview, indent=2, ensure_ascii=False))
(OUT / "cdc-operations.json").write_text(json.dumps(operations, indent=2, ensure_ascii=False))
dk.write(OUT, "dw-insights.json", insights)
dk.write(OUT, "clickhouse-internals.json", internals)
print("dashboards written to", OUT)
