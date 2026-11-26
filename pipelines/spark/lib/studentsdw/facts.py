from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .clickhouse import ClickHouseClient
from .scd import MergeResult, in_filter, merge_fact


def _terms(spark: SparkSession, ch: ClickHouseClient) -> DataFrame:
    return ch.read_dataframe(spark, "SELECT term_code, toInt64(term_key) AS term_key, "
                                    "toInt64(term_start_date_key) AS term_start_date_key, "
                                    "toString(term_start_date) AS term_start FROM v_dim_term WHERE term_key > 0")


OFFERING_HASH = ["term_key", "term_start_date_key", "course_key", "department_key", "section_number", "capacity"]


def load_course_offerings(spark: SparkSession, ch: ClickHouseClient, offerings: DataFrame, *, batch_id: int,
                          full_snapshot: bool, snapshot_ms: int | None = None,
                          ids: list[int] | None = None) -> MergeResult:
    courses = ch.read_dataframe(spark, "SELECT department_code, course_number, course_key, department_key "
                                       "FROM v_dim_course WHERE course_key > 0")
    frame = (offerings.withColumn("course_number", F.col("course_number").cast("int"))
             .join(F.broadcast(courses), ["department_code", "course_number"], "left")
             .join(F.broadcast(_terms(spark, ch)), "term_code", "left")
             .select(F.col("course_offering_id").cast("int").alias("course_offering_id"),
                     F.coalesce("term_key", F.lit(0)).alias("term_key"),
                     F.coalesce("term_start_date_key", F.lit(0)).alias("term_start_date_key"),
                     F.coalesce("course_key", F.lit(-1)).alias("course_key"),
                     F.coalesce("department_key", F.lit(-1)).alias("department_key"),
                     F.col("section").cast("int").alias("section_number"),
                     F.lit(1).alias("section_count"),
                     F.col("capacity").cast("int").alias("capacity"),
                     "_version", "_deleted", "_source"))
    return merge_fact(spark, ch, frame, table="fact_course_offering", id_column="course_offering_id",
                      hash_columns=OFFERING_HASH, batch_id=batch_id, full_snapshot=full_snapshot,
                      snapshot_ms=snapshot_ms, id_filter=in_filter("course_offering_id", ids))


ENROLLMENT_HASH = ["term_key", "term_start_date_key", "student_key", "course_key", "department_key", "degree_key",
                   "class_standing_key", "grade_key", "course_offering_id", "section_number"]


def load_enrollments(spark: SparkSession, ch: ClickHouseClient, enrollments: DataFrame, *, batch_id: int,
                     full_snapshot: bool, snapshot_ms: int | None = None, ids: list[int] | None = None,
                     offering_ids: list[int] | None = None, student_ids: list[int] | None = None) -> MergeResult:
    where_o, params_o = in_filter("course_offering_id", offering_ids)
    offerings = ch.read_dataframe(spark, "SELECT course_offering_id, toInt64(term_key) AS term_key, "
                                         "toInt64(term_start_date_key) AS term_start_date_key, course_key, "
                                         f"department_key, section_number FROM v_fact_course_offering WHERE {where_o}",
                                  params_o)
    credits = ch.read_dataframe(spark, "SELECT course_key, toFloat64(credits) AS credits FROM v_dim_course")
    where_s, params_s = in_filter("student_id", student_ids)
    students = ch.read_dataframe(spark, "SELECT student_id, student_key, degree_key, class_standing_key "
                                        f"FROM v_dim_student WHERE student_key > 0 AND {where_s}", params_s)
    grades = ch.read_dataframe(spark, "SELECT grade_code, grade_key, toFloat64(ifNull(grade_points, 0)) AS points, "
                                      "include_in_gpa, is_passing, grade_category FROM v_dim_grade WHERE grade_key > 0")

    graded = F.col("grade").isNotNull() & (F.trim("grade") != "")
    frame = (enrollments
             .withColumn("course_offering_id", F.col("course_offering_id").cast("int"))
             .withColumn("student_id", F.col("student_id").cast("int"))
             .withColumn("grade_code", F.when(graded, F.trim("grade")))
             .join(offerings, "course_offering_id", "left")
             .join(F.broadcast(credits), "course_key", "left")
             .join(students, "student_id", "left")
             .join(F.broadcast(grades), "grade_code", "left"))

    credit = F.coalesce("credits", F.lit(0.0))
    passed = F.coalesce("is_passing", F.lit(0)) == 1
    in_gpa = F.coalesce("include_in_gpa", F.lit(0)) == 1
    frame = frame.select(
        F.col("course_enrollment_id").cast("int").alias("course_enrollment_id"),
        F.coalesce("term_key", F.lit(0)).alias("term_key"),
        F.coalesce("term_start_date_key", F.lit(0)).alias("term_start_date_key"),
        F.coalesce("student_key", F.lit(-1)).cast("long").alias("student_key"),
        F.coalesce("course_key", F.lit(-1)).alias("course_key"),
        F.coalesce("department_key", F.lit(-1)).alias("department_key"),
        F.coalesce("degree_key", F.lit(-1)).alias("degree_key"),
        F.coalesce("class_standing_key", F.lit(-1)).alias("class_standing_key"),
        F.when(F.col("grade_code").isNull(), F.lit(-2)).otherwise(F.coalesce("grade_key", F.lit(-1))).alias("grade_key"),
        "course_offering_id",
        F.coalesce("section_number", F.lit(0)).alias("section_number"),
        F.lit(1).alias("enrollment_count"),
        credit.cast("decimal(4,1)").alias("credits_attempted"),
        F.when(passed, credit).otherwise(0.0).cast("decimal(4,1)").alias("credits_earned"),
        F.when(in_gpa, credit).otherwise(0.0).cast("decimal(4,1)").alias("gpa_credits"),
        F.when(in_gpa, credit * F.col("points")).otherwise(0.0).cast("decimal(5,1)").alias("quality_points"),
        passed.cast("int").alias("passed_count"),
        (F.col("grade_category") == "Fail").cast("int").alias("failed_count"),
        (F.col("grade_category") == "Withdrawn").cast("int").alias("withdrawn_count"),
        F.col("grade_code").isNotNull().cast("int").alias("graded_count"),
        "_version", "_deleted", "_source")
    frame = frame.fillna(0, subset=["failed_count", "withdrawn_count"])
    return merge_fact(spark, ch, frame, table="fact_enrollment", id_column="course_enrollment_id",
                      hash_columns=ENROLLMENT_HASH + ["credits_attempted"], batch_id=batch_id,
                      full_snapshot=full_snapshot, snapshot_ms=snapshot_ms,
                      preserve=["student_key", "degree_key", "class_standing_key"],
                      id_filter=in_filter("course_enrollment_id", ids))


APPLICATION_HASH = ["applicant_key", "application_date_key", "entry_term_key", "application_profile_key", "student_key",
                    "high_school_gpa", "sat_math_score", "sat_reading_score", "sat_writing_score", "essay_score",
                    "admission_points"]


def load_applications(spark: SparkSession, ch: ClickHouseClient, applicants: DataFrame, *, batch_id: int,
                      full_snapshot: bool, snapshot_ms: int | None = None,
                      ids: list[int] | None = None) -> MergeResult:
    where, params = in_filter("applicant_id", ids)
    keys = ch.read_dataframe(spark, f"SELECT applicant_id, applicant_key FROM v_dim_applicant WHERE applicant_key > 0 "
                                    f"AND {where}", params)
    profiles = ch.read_dataframe(spark, "SELECT application_type_code, application_status_code, application_profile_key "
                                        "FROM v_dim_application_profile WHERE application_profile_key > 0")
    matches = ch.read_dataframe(spark, "SELECT email, toString(date_of_birth) AS _dob, min(student_key) AS _matched "
                                       "FROM v_dim_student WHERE student_key > 0 AND date_of_birth IS NOT NULL "
                                       "GROUP BY email, _dob")

    sat_parts = [F.col("sat_math_score"), F.col("sat_reading_score"), F.col("sat_writing_score")]
    admitted = F.col("application_status") == "A"
    frame = (applicants
             .withColumn("applicant_id", F.col("applicant_id").cast("int"))
             .withColumn("email", F.lower(F.trim("email")))
             .withColumn("_dob", F.date_format("date_of_birth", "yyyy-MM-dd"))
             .withColumnRenamed("application_type", "application_type_code")
             .withColumn("application_status_code", F.col("application_status"))
             .join(keys, "applicant_id", "left")
             .join(F.broadcast(profiles), ["application_type_code", "application_status_code"], "left")
             .join(F.broadcast(_terms(spark, ch)).withColumnRenamed("term_code", "entry_term"), "entry_term", "left")
             .join(matches, ["email", "_dob"], "left"))
    frame = frame.select(
        "applicant_id",
        F.coalesce("applicant_key", F.lit(-1)).cast("long").alias("applicant_key"),
        F.coalesce(F.date_format("application_received_date", "yyyyMMdd").cast("long"), F.lit(0)).alias("application_date_key"),
        F.coalesce("term_key", F.lit(0)).alias("entry_term_key"),
        F.coalesce("application_profile_key", F.lit(-1)).alias("application_profile_key"),
        F.coalesce("_matched", F.lit(-2)).cast("long").alias("student_key"),
        F.lit(1).alias("application_count"),
        admitted.cast("int").alias("admitted_count"),
        (F.col("application_status") == "D").cast("int").alias("denied_count"),
        (admitted & F.col("_matched").isNotNull()).cast("int").alias("enrolled_count"),
        F.col("gpa").cast("decimal(3,2)").alias("high_school_gpa"),
        F.col("sat_math_score").cast("int").alias("sat_math_score"),
        F.col("sat_reading_score").cast("int").alias("sat_reading_score"),
        F.col("sat_writing_score").cast("int").alias("sat_writing_score"),
        (sat_parts[0] + sat_parts[1] + sat_parts[2]).cast("int").alias("sat_total_score"),
        F.col("essay_score").cast("int").alias("essay_score"),
        F.col("admission_points").cast("double").alias("admission_points"),
        F.floor(F.months_between("application_received_date", "date_of_birth") / 12).cast("int").alias("age_at_application"),
        F.datediff(F.to_date("term_start"), "application_received_date").alias("lead_time_days"),
        "_version", "_deleted", "_source")
    return merge_fact(spark, ch, frame, table="fact_application", id_column="applicant_id",
                      hash_columns=APPLICATION_HASH, batch_id=batch_id, full_snapshot=full_snapshot,
                      snapshot_ms=snapshot_ms, id_filter=in_filter("applicant_id", ids))
