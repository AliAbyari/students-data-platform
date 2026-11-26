CREATE TABLE IF NOT EXISTS etl_step_log
(
    batch_id      UInt64,
    pipeline      LowCardinality(String),
    step          LowCardinality(String),
    status        LowCardinality(String),
    rows_read     UInt64,
    rows_written  UInt64,
    started_at    DateTime64(3),
    finished_at   DateTime64(3),
    duration_ms   UInt64 MATERIALIZED toUInt64(greatest(0, dateDiff('millisecond', started_at, finished_at))),
    message       String
)
ENGINE = MergeTree
ORDER BY (started_at, batch_id)
TTL toDateTime(started_at) + INTERVAL 180 DAY;

CREATE TABLE IF NOT EXISTS dq_result
(
    batch_id      UInt64,
    checked_at    DateTime64(3),
    rule_name     LowCardinality(String),
    table_name    LowCardinality(String),
    severity      LowCardinality(String),
    failed_rows   UInt64,
    passed        UInt8,
    details       String
)
ENGINE = MergeTree
ORDER BY (checked_at, batch_id)
TTL toDateTime(checked_at) + INTERVAL 180 DAY;

CREATE TABLE IF NOT EXISTS cdc_event_log
(
    micro_batch_id  UInt64,
    source_table    LowCardinality(String),
    operation       LowCardinality(String),
    business_key    String,
    source_ts       DateTime64(3),
    kafka_ts        DateTime64(3),
    processed_at    DateTime64(3),
    end_to_end_ms   UInt32,
    kafka_partition UInt16,
    kafka_offset    UInt64
)
ENGINE = MergeTree
ORDER BY (processed_at, source_table)
TTL toDateTime(processed_at) + INTERVAL 30 DAY;

CREATE TABLE IF NOT EXISTS cdc_micro_batch
(
    micro_batch_id  UInt64,
    processed_at    DateTime64(3),
    input_events    UInt32,
    applied_rows    UInt32,
    duration_ms     UInt32
)
ENGINE = MergeTree
ORDER BY processed_at
TTL toDateTime(processed_at) + INTERVAL 30 DAY;

CREATE TABLE IF NOT EXISTS etl_work_keys
(
    work_id     String,
    key_value   Int64,
    event_ms    UInt64,
    created_at  DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (work_id, key_value)
TTL created_at + INTERVAL 1 DAY;
