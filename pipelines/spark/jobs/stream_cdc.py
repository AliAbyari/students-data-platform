from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta, timezone

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (DateType, DoubleType, IntegerType, LongType, StringType, StructField, StructType)

from studentsdw import dimensions as dims
from studentsdw import facts
from studentsdw.clickhouse import ClickHouseClient
from studentsdw.control import start_batch
from studentsdw.session import build_session
from studentsdw.sources import snake

EPOCH = date(1970, 1, 1)
TECHNICAL = [StructField("_version", LongType()), StructField("_deleted", IntegerType()),
             StructField("_source", StringType())]


def _schema(*fields: tuple[str, object]) -> StructType:
    return StructType([StructField(name, kind) for name, kind in fields] + TECHNICAL)


S, I, D, F_ = StringType(), IntegerType(), DateType(), DoubleType()
SCHEMAS = {
    "Students": _schema(("student_id", I), ("first_name", S), ("middle_name", S), ("last_name", S), ("gender", S),
                        ("street_address", S), ("city", S), ("state", S), ("zip_code", S), ("telephone", S),
                        ("email", S), ("date_of_birth", D), ("degree_pursued", I), ("class_standing_code", S),
                        ("student_status", S), ("enrollment_term", S)),
    "Applicants": _schema(("applicant_id", I), ("first_name", S), ("middle_name", S), ("last_name", S), ("gender", S),
                          ("street_address", S), ("city", S), ("state", S), ("zip_code", S), ("telephone", S),
                          ("email", S), ("date_of_birth", D), ("application_received_date", D), ("entry_term", S),
                          ("application_type", S), ("gpa", S), ("sat_math_score", I), ("sat_reading_score", I),
                          ("sat_writing_score", I), ("essay_score", I), ("application_status", S),
                          ("admission_points", F_)),
    "CourseOfferings": _schema(("course_offering_id", I), ("department_code", S), ("course_number", I),
                               ("term_code", S), ("section", I), ("capacity", I)),
    "CourseEnrollments": _schema(("course_enrollment_id", I), ("course_offering_id", I), ("student_id", I),
                                 ("grade", S)),
}
PRIMARY_KEYS = {"Students": "student_id", "Applicants": "applicant_id", "CourseOfferings": "course_offering_id",
                "CourseEnrollments": "course_enrollment_id"}
DATE_COLUMNS = {"date_of_birth", "application_received_date"}


def _convert(value, column: str):
    if column in DATE_COLUMNS and isinstance(value, int):
        return EPOCH + timedelta(days=value)
    return value


def _image(envelope: dict, table: str) -> dict | None:
    deleted = envelope.get("op") == "d"
    image = envelope.get("before") if deleted else envelope.get("after")
    if image is None:
        return None
    row = {snake(k): _convert(v, snake(k)) for k, v in image.items()}
    row = {field.name: row.get(field.name) for field in SCHEMAS[table].fields}
    for field in SCHEMAS[table].fields:
        if isinstance(field.dataType, DoubleType) and isinstance(row[field.name], (int, str)):
            row[field.name] = float(row[field.name])
    row["_version"] = int(envelope["source"]["ts_ms"])
    row["_deleted"] = int(deleted)
    row["_source"] = "cdc"
    return row


class MicroBatchProcessor:
    def __init__(self, spark: SparkSession, ch: ClickHouseClient, stream_batch_id: int) -> None:
        self.spark, self.ch, self.batch_id = spark, ch, stream_batch_id

    def __call__(self, frame: DataFrame, micro_batch_id: int) -> None:
        started = time.monotonic()
        events = frame.select("topic", "partition", "offset", "timestamp", "value").collect()
        if not events:
            return

        latest: dict[str, dict] = {table: {} for table in SCHEMAS}
        telemetry = []
        for event in sorted(events, key=lambda e: (e["partition"], e["offset"])):
            if event["value"] is None:
                continue
            envelope = json.loads(event["value"])
            table = envelope.get("source", {}).get("table")
            if table not in SCHEMAS:
                continue
            row = _image(envelope, table)
            if row is None:
                continue
            key = row[PRIMARY_KEYS[table]]
            latest[table][key] = row
            source_ts = datetime.fromtimestamp(envelope["source"]["ts_ms"] / 1000, tz=timezone.utc)
            telemetry.append({"source_table": table, "operation": envelope.get("op", "?"), "business_key": str(key),
                              "source_ts": source_ts, "kafka_ts": event["timestamp"],
                              "kafka_partition": event["partition"], "kafka_offset": event["offset"]})

        applied = self._apply(latest)

        processed_at = datetime.now(timezone.utc)
        for item in telemetry:
            item["micro_batch_id"] = micro_batch_id
            item["processed_at"] = processed_at.isoformat()
            kafka_ts = item["kafka_ts"]
            if kafka_ts.tzinfo is None:
                kafka_ts = kafka_ts.replace(tzinfo=timezone.utc)
            item["end_to_end_ms"] = max(0, int((processed_at - item["source_ts"]).total_seconds() * 1000))
            item["source_ts"] = item["source_ts"].isoformat()
            item["kafka_ts"] = kafka_ts.isoformat()
        self.ch.insert_rows("cdc_event_log", telemetry)
        self.ch.insert_rows("cdc_micro_batch", [{
            "micro_batch_id": micro_batch_id, "processed_at": processed_at.isoformat(), "input_events": len(events),
            "applied_rows": applied, "duration_ms": int((time.monotonic() - started) * 1000)}])
        self.ch.clear_scratch()
        print(f"[cdc] micro-batch {micro_batch_id}: {len(events)} events, {applied} rows applied "
              f"in {time.monotonic() - started:.1f}s")

    def _frame(self, table: str, rows: dict) -> DataFrame:
        frame = self.spark.createDataFrame(list(rows.values()), SCHEMAS[table])
        if table == "Applicants":
            frame = frame.withColumn("gpa", F.col("gpa").cast("decimal(3,2)"))
        return frame

    def _apply(self, latest: dict[str, dict]) -> int:
        spark, ch, applied = self.spark, self.ch, 0
        common = dict(batch_id=self.batch_id, full_snapshot=False)

        if latest["Students"]:
            ids = list(latest["Students"])
            emails = sorted({(r["email"] or "").strip().lower() for r in latest["Students"].values()})
            prepared = dims.prepare_students(spark, ch, self._frame("Students", latest["Students"]), emails=emails)
            applied += dims.load_students_scd2(spark, ch, prepared, ids=ids, **common).written

        if latest["Applicants"]:
            ids = list(latest["Applicants"])
            frame = self._frame("Applicants", latest["Applicants"]).cache()
            applied += dims.load_applicants(spark, ch, frame, ids=ids, **common).written
            applied += facts.load_applications(spark, ch, frame, ids=ids, **common).written
            frame.unpersist()

        if latest["CourseOfferings"]:
            ids = list(latest["CourseOfferings"])
            applied += facts.load_course_offerings(spark, ch, self._frame("CourseOfferings", latest["CourseOfferings"]),
                                                   ids=ids, **common).written

        if latest["CourseEnrollments"]:
            rows = latest["CourseEnrollments"]
            applied += facts.load_enrollments(
                spark, ch, self._frame("CourseEnrollments", rows), ids=list(rows),
                offering_ids=sorted({r["course_offering_id"] for r in rows.values() if r["course_offering_id"]}),
                student_ids=sorted({r["student_id"] for r in rows.values() if r["student_id"]}), **common).written
        return applied


def main() -> None:
    spark = build_session("studentsdw-cdc-stream", {"spark.sql.streaming.stopGracefullyOnShutdown": "true"})
    ch = ClickHouseClient()
    stream_batch_id, _ = start_batch("cdc_stream")

    source = (spark.readStream.format("kafka")
              .option("kafka.bootstrap.servers", os.environ["KAFKA_BOOTSTRAP_SERVERS"])
              .option("subscribePattern", os.getenv("CDC_TOPIC_PATTERN", r"students\.Students\.dbo\..*"))
              .option("startingOffsets", "earliest")
              .option("failOnDataLoss", "false")
              .option("maxOffsetsPerTrigger", "20000")
              .load()
              .select("topic", "partition", "offset", "timestamp", F.col("value").cast("string").alias("value")))

    query = (source.writeStream
             .foreachBatch(MicroBatchProcessor(spark, ch, stream_batch_id))
             .option("checkpointLocation", os.getenv("CHECKPOINT_DIR", "/checkpoints/cdc"))
             .trigger(processingTime=f"{os.getenv('STREAM_TRIGGER_SECONDS', '5')} seconds")
             .start())
    print(f"[cdc] streaming started (lineage batch id {stream_batch_id})")
    query.awaitTermination()


if __name__ == "__main__":
    main()
