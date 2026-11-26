from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pytest

pytest.importorskip("pyspark")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spark", "jobs"))

import stream_cdc
from studentsdw import scd

pytestmark = pytest.mark.skipif(os.getenv("STUDENTSDW_TESTS") != "1",
                                reason="integration tests truncate tables; set STUDENTSDW_TESTS=1 on a disposable ClickHouse")


def _event(table, op, before, after, ts_ms, offset):
    value = {"before": before, "after": after, "op": op, "ts_ms": ts_ms + 5,
             "source": {"table": table, "ts_ms": ts_ms, "db": "Students", "schema": "dbo"}}
    return (f"students.Students.dbo.{table}", 0, offset, datetime.now(timezone.utc).replace(tzinfo=None), json.dumps(value))


def test_cdc_micro_batch(env_stream):
    spark, ch = env_stream
    student = {"StudentId": 8, "FirstName": "Ali", "MiddleName": "", "LastName": "Rezaei", "Gender": "M",
               "StreetAddress": "2 Oak", "City": "Austin", "State": "TX", "ZipCode": "73301", "Telephone": "555",
               "email": "ali@example.com", "DateOfBirth": 10957, "DegreePursued": 1, "ClassStandingCode": "U2",
               "StudentStatus": "A", "EnrollmentTerm": "FA2020"}
    graduated = dict(student, StudentStatus="G")
    enrollment = {"CourseEnrollmentId": 77, "CourseOfferingId": 500, "StudentId": 8, "Grade": None}
    graded = dict(enrollment, Grade="A")
    rows = [
        _event("Students", "u", student, graduated, 9_000_000_000_000, 1),
        _event("CourseEnrollments", "c", None, enrollment, 9_000_000_000_100, 2),
        _event("CourseEnrollments", "u", enrollment, graded, 9_000_000_000_200, 3),
    ]
    frame = spark.createDataFrame(rows, "topic string, partition int, offset long, timestamp timestamp, value string")
    stream_cdc.MicroBatchProcessor(spark, ch, stream_batch_id=99)(frame, 1)

    history = ch.query("SELECT student_status_code, is_current, change_source FROM v_dim_student_history "
                       "WHERE student_id = 8 ORDER BY valid_from")
    assert [h["student_status_code"] for h in history] == ["A", "G"]
    assert history[-1]["change_source"] == "cdc"
    fact = ch.query("SELECT grade_code, passed_count FROM rpt_enrollment WHERE course_enrollment_id = 77")
    assert fact == [{"grade_code": "A", "passed_count": 1}]
    assert ch.scalar("SELECT count() FROM cdc_event_log WHERE micro_batch_id = 1") == 3


@pytest.fixture(scope="module")
def env_stream():
    from pyspark.sql import SparkSession

    from studentsdw.clickhouse import ClickHouseClient

    scd.allocate_keys = lambda _seq, count: 50_000
    spark = SparkSession.builder.master("local[2]").config("spark.sql.session.timeZone", "UTC").getOrCreate()
    yield spark, ClickHouseClient()
