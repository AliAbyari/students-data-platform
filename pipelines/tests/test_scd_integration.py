from __future__ import annotations

import itertools
import os
import uuid
from datetime import date

import pytest

pytest.importorskip("pyspark")

from pyspark.sql import functions as F

from studentsdw import dimensions as dims, facts, scd
from studentsdw.clickhouse import ClickHouseClient
from studentsdw.scd import merge_type1

pytestmark = pytest.mark.skipif(os.getenv("STUDENTSDW_TESTS") != "1",
                                reason="integration tests truncate tables; set STUDENTSDW_TESTS=1 on a disposable ClickHouse")

_counter = itertools.count(1000)


def _allocate(_sequence: str, count: int) -> int:
    first = next(_counter)
    for _ in range(count - 1):
        next(_counter)
    return first


@pytest.fixture(scope="module")
def env():
    from pyspark.sql import SparkSession

    scd.allocate_keys = _allocate
    spark = (SparkSession.builder.master("local[2]").appName("studentsdw-tests")
             .config("spark.sql.session.timeZone", "UTC").config("spark.sql.shuffle.partitions", "2")
             .getOrCreate())
    ch = ClickHouseClient()
    for table in ("dim_student", "dim_degree", "dim_class_standing", "dim_department", "dim_course", "dim_grade",
                  "dim_term", "dim_applicant", "fact_enrollment", "fact_course_offering", "etl_work_keys"):
        ch.execute(f"TRUNCATE TABLE {table}")
    yield spark, ch
    spark.stop()


def _tech(frame, version, deleted=0, source="batch"):
    return (frame.withColumn("_version", F.lit(version).cast("long")).withColumn("_deleted", F.lit(deleted))
            .withColumn("_source", F.lit(source)))


STUDENT_COLUMNS = ["student_id", "first_name", "middle_name", "last_name", "gender", "street_address", "city", "state",
                   "zip_code", "telephone", "email", "date_of_birth", "degree_pursued", "class_standing_code",
                   "student_status", "enrollment_term"]


def _students(spark, rows, version, deleted=0, source="batch"):
    return _tech(spark.createDataFrame(rows, STUDENT_COLUMNS), version, deleted, source)


def _seed_reference(spark, ch, version):
    departments = _tech(spark.createDataFrame([("CS", "Computer Science")], ["department_code", "department_name"]),
                        version)
    merge_type1(spark, ch, dims.prepare_departments(spark, departments), table="dim_department",
                key_column="department_key", business_key=["department_code"], sequence="reference_key_seq",
                hash_columns=["department_name"], batch_id=1, full_snapshot=True, snapshot_ms=version)
    degrees = _tech(spark.createDataFrame([(1, "CS", "BS", "Bachelor of Science in Computer Science")],
                                          ["degree_id", "department_code", "degree_type_code", "degree_name"]), version)
    types = _tech(spark.createDataFrame([("BS", "Bachelor of Science", "U")],
                                        ["degree_type_code", "degree_type_name", "degree_level_code"]), version)
    levels = _tech(spark.createDataFrame([("U", "Undergraduate")], ["degree_level_code", "degree_level_name"]), version)
    merge_type1(spark, ch, dims.prepare_degrees(spark, ch, degrees, types, levels), table="dim_degree",
                key_column="degree_key", business_key=["degree_id"], sequence="reference_key_seq",
                hash_columns=["degree_name"], batch_id=1, full_snapshot=True, snapshot_ms=version)
    standings = _tech(spark.createDataFrame([("U1", "Freshman", "U", 0), ("U2", "Sophomore", "U", 30)],
                                            ["class_standing_code", "class_standing_name", "degree_level_code",
                                             "required_credits"]), version)
    merge_type1(spark, ch, dims.prepare_class_standings(spark, standings, levels), table="dim_class_standing",
                key_column="class_standing_key", business_key=["class_standing_code"], sequence="reference_key_seq",
                hash_columns=["class_standing_name", "max_credits"], batch_id=1, full_snapshot=True,
                snapshot_ms=version)


def _history(ch, student_id):
    return ch.query("SELECT student_key, city, first_name, is_current, is_deleted, change_reason, "
                    "toUnixTimestamp64Milli(valid_to) AS valid_to_ms FROM v_dim_student_history "
                    "WHERE student_id = {id:Int32} ORDER BY valid_from, student_key", {"id": student_id})


def test_student_scd2_lifecycle(env):
    spark, ch = env
    _seed_reference(spark, ch, 1_000)
    dob = date(2001, 5, 4)
    base = (7, "Sara", "", "Ahmadi", "F", "1 Main St", "Austin", "TX", "73301", "555", "sara@example.com", dob, 1,
            "U1", "A", "FA2020")

    prepared = dims.prepare_students(spark, ch, _students(spark, [base], 2_000))
    result = dims.load_students_scd2(spark, ch, prepared, batch_id=1, full_snapshot=True, snapshot_ms=2_000)
    assert result.inserted == 1
    history = _history(ch, 7)
    assert len(history) == 1 and history[0]["is_current"] == 1 and history[0]["change_reason"] == "new"

    prepared = dims.prepare_students(spark, ch, _students(spark, [base], 2_000))
    assert dims.load_students_scd2(spark, ch, prepared, batch_id=1, full_snapshot=True, snapshot_ms=2_000).written == 0

    moved = list(base)
    moved[6] = "Dallas"
    prepared = dims.prepare_students(spark, ch, _students(spark, [tuple(moved)], 3_000, source="cdc"))
    dims.load_students_scd2(spark, ch, prepared, batch_id=2, full_snapshot=False, ids=[7])
    history = _history(ch, 7)
    assert [h["city"] for h in history] == ["Austin", "Dallas"]
    assert [h["is_current"] for h in history] == [0, 1]
    assert history[0]["valid_to_ms"] == 3_000

    prepared = dims.prepare_students(spark, ch, _students(spark, [base], 2_500))
    assert dims.load_students_scd2(spark, ch, prepared, batch_id=3, full_snapshot=True, snapshot_ms=2_500).written == 0

    renamed = list(moved)
    renamed[1] = "Sarah"
    prepared = dims.prepare_students(spark, ch, _students(spark, [tuple(renamed)], 4_000, source="cdc"))
    dims.load_students_scd2(spark, ch, prepared, batch_id=4, full_snapshot=False, ids=[7])
    history = _history(ch, 7)
    assert len(history) == 2
    assert {h["first_name"] for h in history} == {"Sarah"}

    prepared = dims.prepare_students(spark, ch, _students(spark, [tuple(renamed)], 5_000, deleted=1, source="cdc"))
    dims.load_students_scd2(spark, ch, prepared, batch_id=5, full_snapshot=False, ids=[7])
    assert ch.scalar("SELECT count() FROM v_dim_student WHERE student_id = 7") == 0


def test_enrollment_incremental(env):
    spark, ch = env
    version = 10_000
    courses = _tech(spark.createDataFrame([("CS", 101, "Intro", "Intro to CS", 3.0, 30)],
                                          ["department_code", "course_number", "course_title", "course_description",
                                           "credits", "maximum_section_size"]), version)
    merge_type1(spark, ch, dims.prepare_courses(spark, ch, courses), table="dim_course", key_column="course_key",
                business_key=["department_code", "course_number"], sequence="reference_key_seq",
                hash_columns=["course_title"], batch_id=1, full_snapshot=True, snapshot_ms=version)
    grades = _tech(spark.createDataFrame([("A", 4.0, True), ("F", 0.0, True), ("W", None, False)],
                                         "grade string, points double, include_in_gpa boolean"), version)
    merge_type1(spark, ch, dims.prepare_grades(spark, grades), table="dim_grade", key_column="grade_key",
                business_key=["grade_code"], sequence="reference_key_seq", hash_columns=["grade_description"],
                batch_id=1, full_snapshot=True, snapshot_ms=version)
    terms = _tech(spark.createDataFrame([("FA2020", "FA", 2020)], ["term_code", "session_code", "year"]), version)
    sessions = _tech(spark.createDataFrame([("FA", "Fall")], ["session_code", "session_name"]), version)
    merge_type1(spark, ch, dims.prepare_terms(spark, terms, sessions), table="dim_term", key_column="term_key",
                business_key=["term_code"], hash_columns=["term_name"], batch_id=1, full_snapshot=True,
                snapshot_ms=version)
    assert ch.scalar("SELECT term_key FROM v_dim_term WHERE term_code = 'FA2020'") == 20203

    dob = date(2000, 1, 1)
    prepared = dims.prepare_students(spark, ch, _students(spark, [
        (8, "Ali", "", "Rezaei", "M", "2 Oak", "Austin", "TX", "73301", "555", "ali@example.com", dob, 1, "U2", "A",
         "FA2020")], version))
    dims.load_students_scd2(spark, ch, prepared, batch_id=1, full_snapshot=False)

    offerings = _tech(spark.createDataFrame([(500, "CS", 101, "FA2020", 1, 30)],
                                            ["course_offering_id", "department_code", "course_number", "term_code",
                                             "section", "capacity"]), version)
    facts.load_course_offerings(spark, ch, offerings, batch_id=1, full_snapshot=True, snapshot_ms=version)

    schema = "course_enrollment_id int, course_offering_id int, student_id int, grade string"
    rows = [(1, 500, 8, "A"), (2, 500, 8, None), (3, 500, 999, "F")]
    result = facts.load_enrollments(spark, ch, _tech(spark.createDataFrame(rows, schema), version + 1),
                                    batch_id=1, full_snapshot=True, snapshot_ms=version + 1)
    assert result.inserted == 3
    fact = {r["course_enrollment_id"]: r for r in ch.query(
        "SELECT course_enrollment_id, student_key, grade_key, toFloat64(quality_points) AS qp, passed_count, "
        "term_key FROM v_fact_enrollment ORDER BY course_enrollment_id")}
    assert fact[1]["qp"] == 12.0 and fact[1]["passed_count"] == 1 and fact[1]["term_key"] == 20203
    assert fact[2]["grade_key"] == -2
    assert fact[3]["student_key"] == -1

    rows = [(1, 500, 8, "A"), (2, 500, 8, "F"), (3, 500, 999, "F")]
    result = facts.load_enrollments(spark, ch, _tech(spark.createDataFrame(rows, schema), version + 2),
                                    batch_id=2, full_snapshot=True, snapshot_ms=version + 2)
    assert result.inserted == 1

    rows = [(1, 500, 8, "A"), (2, 500, 8, "F")]
    result = facts.load_enrollments(spark, ch, _tech(spark.createDataFrame(rows, schema), version + 3),
                                    batch_id=3, full_snapshot=True, snapshot_ms=version + 3)
    assert result.deleted == 1
    assert ch.scalar("SELECT count() FROM v_fact_enrollment") == 2
    assert ch.scalar("SELECT count() FROM rpt_course_offering_fill WHERE course_offering_id = 500 AND enrolled = 2") == 1


def test_work_keys_are_isolated(env):
    _, ch = env
    work = uuid.uuid4().hex
    ch.insert_rows("etl_work_keys", [{"work_id": work, "key_value": 1, "event_ms": 1}])
    assert ch.scalar("SELECT count() FROM etl_work_keys WHERE work_id = {w:String}", {"w": work}) == 1
