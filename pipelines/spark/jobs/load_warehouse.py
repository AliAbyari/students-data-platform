from __future__ import annotations

import argparse

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from studentsdw import dimensions as dims
from studentsdw import facts
from studentsdw.clickhouse import ClickHouseClient
from studentsdw.config import Postgres
from studentsdw.control import StepLog
from studentsdw.scd import merge_type1
from studentsdw.session import build_session


class Staging:
    def __init__(self, spark: SparkSession, snapshot_ms: int) -> None:
        self.spark, self.snapshot_ms, self.cfg = spark, snapshot_ms, Postgres()

    def table(self, name: str) -> DataFrame:
        frame = self.spark.read.jdbc(self.cfg.jdbc_url, f"stg.{name}", properties={
            "user": self.cfg.user, "password": self.cfg.password, "driver": "org.postgresql.Driver",
            "fetchsize": "20000"})
        return (frame.drop("_batch_id", "_extracted_at")
                .withColumn("_version", F.lit(self.snapshot_ms).cast("long"))
                .withColumn("_deleted", F.lit(0))
                .withColumn("_source", F.lit("batch")))


def load_dimensions(spark: SparkSession, ch: ClickHouseClient, stg: Staging, batch_id: int, snapshot_ms: int) -> None:
    common = dict(batch_id=batch_id, full_snapshot=True, snapshot_ms=snapshot_ms)

    def step(name: str):
        return StepLog(ch, batch_id, "batch_scd", f"dim.{name}")

    with step("date") as s:
        s.rows_written = dims.load_dim_date(spark, ch, snapshot_ms)

    with step("department") as s:
        s.rows_written = merge_type1(
            spark, ch, dims.prepare_departments(spark, stg.table("departments")), table="dim_department",
            key_column="department_key", business_key=["department_code"], sequence="reference_key_seq",
            hash_columns=["department_name", "department_name_fa", "school_name", "school_name_fa"], **common).written

    with step("course") as s:
        s.rows_written = merge_type1(
            spark, ch, dims.prepare_courses(spark, ch, stg.table("courses")), table="dim_course",
            key_column="course_key", business_key=["department_code", "course_number"], sequence="reference_key_seq",
            hash_columns=["department_key", "course_title", "course_description", "credits", "maximum_section_size",
                          "department_name", "department_name_fa", "school_name"], **common).written

    with step("degree") as s:
        prepared = dims.prepare_degrees(spark, ch, stg.table("degrees"), stg.table("degree_types"),
                                        stg.table("degree_levels"))
        s.rows_written = merge_type1(
            spark, ch, prepared, table="dim_degree", key_column="degree_key", business_key=["degree_id"],
            sequence="reference_key_seq",
            hash_columns=["department_key", "degree_name", "degree_type_code", "degree_type_name", "degree_level_code",
                          "degree_level_name", "department_name", "school_name"], **common).written

    with step("class_standing") as s:
        prepared = dims.prepare_class_standings(spark, stg.table("class_standings"), stg.table("degree_levels"))
        s.rows_written = merge_type1(
            spark, ch, prepared, table="dim_class_standing", key_column="class_standing_key",
            business_key=["class_standing_code"], sequence="reference_key_seq",
            hash_columns=["class_standing_name", "class_standing_name_fa", "degree_level_code", "degree_level_name",
                          "standing_order", "min_credits", "max_credits"], **common).written

    with step("grade") as s:
        s.rows_written = merge_type1(
            spark, ch, dims.prepare_grades(spark, stg.table("grades")), table="dim_grade", key_column="grade_key",
            business_key=["grade_code"], sequence="reference_key_seq",
            hash_columns=["grade_description", "grade_description_fa", "grade_points", "include_in_gpa", "is_passing",
                          "grade_category", "sort_order"], **common).written

    with step("term") as s:
        s.rows_written = merge_type1(
            spark, ch, dims.prepare_terms(spark, stg.table("terms"), stg.table("sessions")), table="dim_term",
            key_column="term_key", business_key=["term_code"],
            hash_columns=["term_key", "session_code", "session_name", "term_name", "term_sequence", "term_start_date",
                          "term_end_date", "source_year"], **common).written

    with step("application_profile") as s:
        s.rows_written = merge_type1(
            spark, ch, dims.prepare_application_profiles(spark, snapshot_ms), table="dim_application_profile",
            key_column="application_profile_key", business_key=["application_type_code", "application_status_code"],
            hash_columns=["application_type_name", "application_type_name_fa", "application_status_name",
                          "application_status_name_fa", "is_admitted"], **common).written

    with step("applicant") as s:
        result = dims.load_applicants(spark, ch, stg.table("applicants"), **common)
        s.rows_written = result.written
        s.message = f"inserted={result.inserted} updated={result.updated} deleted={result.deleted}"

    with step("student_scd2") as s:
        prepared = dims.prepare_students(spark, ch, stg.table("students"))
        result = dims.load_students_scd2(spark, ch, prepared, **common)
        s.rows_written = result.written
        s.message = (f"new_versions={result.inserted} type1_overwrites={result.updated} "
                     f"expired={result.details.get('expired', 0)} deleted={result.deleted}")


def load_facts(spark: SparkSession, ch: ClickHouseClient, stg: Staging, batch_id: int, snapshot_ms: int) -> None:
    common = dict(batch_id=batch_id, full_snapshot=True, snapshot_ms=snapshot_ms)
    for name, loader, table in (("course_offering", facts.load_course_offerings, "course_offerings"),
                                ("enrollment", facts.load_enrollments, "course_enrollments"),
                                ("application", facts.load_applications, "applicants")):
        with StepLog(ch, batch_id, "batch_scd", f"fact.{name}") as s:
            result = loader(spark, ch, stg.table(table), **common)
            s.rows_written = result.written
            s.message = f"upserted={result.inserted} deleted={result.deleted}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--snapshot-ms", type=int, required=True)
    parser.add_argument("--stage", choices=["dimensions", "facts"], required=True)
    args = parser.parse_args()

    spark = build_session(f"studentsdw-load-{args.stage}")
    ch = ClickHouseClient()
    stg = Staging(spark, args.snapshot_ms)
    try:
        if args.stage == "dimensions":
            load_dimensions(spark, ch, stg, args.batch_id, args.snapshot_ms)
        else:
            load_facts(spark, ch, stg, args.batch_id, args.snapshot_ms)
    finally:
        ch.clear_scratch()
        spark.stop()


if __name__ == "__main__":
    main()
