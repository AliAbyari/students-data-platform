from __future__ import annotations

from datetime import date, timedelta

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from . import reference as ref
from .clickhouse import ClickHouseClient
from .jalali import PERSIAN_MONTHS, PERSIAN_WEEKDAYS, to_jalali
from .scd import MergeResult, assign_keys, in_filter, merge_type1, row_hash

DATE_RANGE = (date(2000, 1, 1), date(2030, 12, 31))


def load_dim_date(spark: SparkSession, ch: ClickHouseClient, version: int) -> int:
    start, end = DATE_RANGE
    expected = (end - start).days + 1
    if int(ch.scalar("SELECT count() FROM dim_date FINAL WHERE date_key > 0")) >= expected:
        return 0
    rows = []
    day = start
    while day <= end:
        jy, jm, jd = to_jalali(day)
        academic_year = day.year if day.month >= 9 else day.year - 1
        rows.append({
            "date_key": int(day.strftime("%Y%m%d")), "full_date": day.isoformat(), "day_of_month": day.day,
            "day_of_week": day.isoweekday(), "day_name": day.strftime("%A"), "month_number": day.month,
            "month_name": day.strftime("%B"), "quarter": (day.month - 1) // 3 + 1, "calendar_year": day.year,
            "year_month": day.year * 100 + day.month, "is_weekend": int(day.isoweekday() >= 6),
            "academic_year": academic_year, "academic_year_label": f"{academic_year}-{academic_year + 1}",
            "persian_date": f"{jy:04d}/{jm:02d}/{jd:02d}", "persian_year": jy, "persian_month": jm,
            "persian_month_name": PERSIAN_MONTHS[jm - 1], "persian_day": jd, "persian_year_month": jy * 100 + jm,
            "persian_weekday_name": PERSIAN_WEEKDAYS[day.isoweekday()], "row_version": version,
        })
        day += timedelta(days=1)
    return ch.insert_rows("dim_date", rows)


def prepare_departments(spark: SparkSession, departments: DataFrame) -> DataFrame:
    school = ref.lookup_frame(spark, ref.DEPARTMENT_SCHOOL,
                              ["department_code", "department_name_fa", "school_name", "school_name_fa"])
    return (departments.join(F.broadcast(school), "department_code", "left")
            .select("department_code", F.trim("department_name").alias("department_name"),
                    F.coalesce("department_name_fa", F.trim("department_name")).alias("department_name_fa"),
                    F.coalesce("school_name", F.lit("Unassigned")).alias("school_name"),
                    F.coalesce("school_name_fa", F.lit("نامشخص")).alias("school_name_fa"),
                    "_version", "_deleted", "_source"))


def _department_lookup(spark: SparkSession, ch: ClickHouseClient) -> DataFrame:
    return ch.read_dataframe(spark, "SELECT department_code, department_key, department_name, department_name_fa, "
                                    "school_name, school_name_fa FROM v_dim_department WHERE department_key > 0")


def prepare_courses(spark: SparkSession, ch: ClickHouseClient, courses: DataFrame) -> DataFrame:
    level = (F.floor(F.col("course_number") / 100) * 100).cast("int")
    return (courses.join(F.broadcast(_department_lookup(spark, ch)), "department_code", "left")
            .select("department_code", F.col("course_number").cast("int").alias("course_number"),
                    F.coalesce("department_key", F.lit(-1)).alias("department_key"),
                    F.concat_ws("-", "department_code", F.col("course_number").cast("string")).alias("course_code"),
                    F.trim("course_title").alias("course_title"),
                    F.trim("course_description").alias("course_description"),
                    F.col("credits").cast("decimal(3,1)").alias("credits"),
                    F.col("maximum_section_size").cast("int").alias("maximum_section_size"),
                    level.alias("course_level"),
                    F.when(level >= 500, "Graduate").when(level >= 300, F.concat(F.lit("Upper division "), level))
                     .otherwise(F.concat(F.lit("Lower division "), level)).alias("course_level_name"),
                    F.coalesce("department_name", F.lit("Unknown")).alias("department_name"),
                    F.coalesce("department_name_fa", F.lit("نامشخص")).alias("department_name_fa"),
                    F.coalesce("school_name", F.lit("Unknown")).alias("school_name"),
                    F.coalesce("school_name_fa", F.lit("نامشخص")).alias("school_name_fa"),
                    "_version", "_deleted", "_source"))


def prepare_degrees(spark: SparkSession, ch: ClickHouseClient, degrees: DataFrame, degree_types: DataFrame,
                    degree_levels: DataFrame) -> DataFrame:
    types = degree_types.select("degree_type_code", "degree_type_name", "degree_level_code")
    levels = degree_levels.select("degree_level_code", "degree_level_name")
    level_fa = ref.lookup_frame(spark, ref.DEGREE_LEVEL_FA, ["degree_level_code", "degree_level_name_fa"])
    return (degrees.join(types, "degree_type_code", "left").join(levels, "degree_level_code", "left")
            .join(F.broadcast(level_fa), "degree_level_code", "left")
            .join(F.broadcast(_department_lookup(spark, ch)), "department_code", "left")
            .select(F.col("degree_id").cast("int").alias("degree_id"),
                    F.coalesce("department_key", F.lit(-1)).alias("department_key"),
                    F.trim("degree_name").alias("degree_name"),
                    "degree_type_code", F.coalesce("degree_type_name", F.lit("Unknown")).alias("degree_type_name"),
                    F.coalesce("degree_level_code", F.lit("?")).alias("degree_level_code"),
                    F.coalesce("degree_level_name", F.lit("Unknown")).alias("degree_level_name"),
                    F.coalesce("degree_level_name_fa", F.lit("نامشخص")).alias("degree_level_name_fa"),
                    "department_code",
                    F.coalesce("department_name", F.lit("Unknown")).alias("department_name"),
                    F.coalesce("department_name_fa", F.lit("نامشخص")).alias("department_name_fa"),
                    F.coalesce("school_name", F.lit("Unknown")).alias("school_name"),
                    "_version", "_deleted", "_source"))


def prepare_class_standings(spark: SparkSession, standings: DataFrame, degree_levels: DataFrame) -> DataFrame:
    by_level = Window.partitionBy("degree_level_code").orderBy("required_credits", "class_standing_code")
    name_fa = ref.lookup_frame(spark, ref.CLASS_STANDING_FA, ["class_standing_code", "class_standing_name_fa"])
    return (standings.join(degree_levels.select("degree_level_code", "degree_level_name"), "degree_level_code", "left")
            .join(F.broadcast(name_fa), "class_standing_code", "left")
            .select("class_standing_code", F.trim("class_standing_name").alias("class_standing_name"),
                    F.coalesce("class_standing_name_fa", F.trim("class_standing_name")).alias("class_standing_name_fa"),
                    "degree_level_code", F.coalesce("degree_level_name", F.lit("Unknown")).alias("degree_level_name"),
                    F.row_number().over(by_level).alias("standing_order"),
                    F.col("required_credits").cast("int").alias("min_credits"),
                    F.coalesce(F.lead("required_credits").over(by_level) - 1, F.lit(999)).cast("int").alias("max_credits"),
                    "_version", "_deleted", "_source"))


def prepare_grades(spark: SparkSession, grades: DataFrame) -> DataFrame:
    decode = ref.lookup_frame(spark, ref.GRADE, ["grade_code", "grade_description", "grade_description_fa", "sort_order"])
    code = F.col("grade_code")
    return (grades.withColumnRenamed("grade", "grade_code").join(F.broadcast(decode), "grade_code", "left")
            .select("grade_code", F.coalesce("grade_description", code).alias("grade_description"),
                    F.coalesce("grade_description_fa", code).alias("grade_description_fa"),
                    F.col("points").cast("decimal(2,1)").alias("grade_points"),
                    F.col("include_in_gpa").cast("int").alias("include_in_gpa"),
                    code.isin("A", "B", "C", "D").cast("int").alias("is_passing"),
                    F.when(code.isin("A", "B", "C", "D"), "Pass").when(code == "F", "Fail")
                     .when(code == "W", "Withdrawn").when(code == "I", "Incomplete").otherwise("Other")
                     .alias("grade_category"),
                    F.coalesce("sort_order", F.lit(50)).alias("sort_order"),
                    "_version", "_deleted", "_source"))


def prepare_terms(spark: SparkSession, terms: DataFrame, sessions: DataFrame) -> DataFrame:
    decode = ref.lookup_frame(spark, ref.SESSION, ["session_code", "session_name_en", "session_name_fa", "session_order"])
    year = F.substring("term_code", -4, 4).cast("int")
    code = F.coalesce(F.when(F.trim("session_code") != "", F.trim("session_code")), F.substring("term_code", 1, 2))
    base = (terms.withColumn("calendar_year", year).withColumn("session_code", code)
            .join(sessions.select("session_code", "session_name"), "session_code", "left")
            .join(F.broadcast(decode), "session_code", "left"))
    start = (F.when(F.col("session_code") == "FA", F.make_date("calendar_year", F.lit(9), F.lit(1)))
              .when(F.col("session_code") == "SP", F.make_date("calendar_year", F.lit(1), F.lit(15)))
              .otherwise(F.make_date("calendar_year", F.lit(6), F.lit(1))))
    end = (F.when(F.col("session_code") == "FA", F.make_date("calendar_year", F.lit(12), F.lit(20)))
            .when(F.col("session_code") == "SP", F.make_date("calendar_year", F.lit(5), F.lit(15)))
            .otherwise(F.make_date("calendar_year", F.lit(8), F.lit(15))))
    academic = F.when(F.col("session_code") == "FA", F.col("calendar_year")).otherwise(F.col("calendar_year") - 1)
    session_name = F.coalesce("session_name_en", F.trim("session_name"), F.col("session_code"))
    return (base.withColumn("term_key", (F.col("calendar_year") * 10 + F.coalesce("session_order", F.lit(0))).cast("long"))
            .withColumn("term_start_date", start).withColumn("term_end_date", end)
            .select("term_key", "term_code", "session_code", session_name.alias("session_name"),
                    F.coalesce("session_name_fa", session_name).alias("session_name_fa"),
                    F.coalesce("session_order", F.lit(0)).alias("session_order"), "calendar_year",
                    academic.alias("academic_year"),
                    F.concat_ws("-", academic.cast("string"), (academic + 1).cast("string")).alias("academic_year_label"),
                    F.concat_ws(" ", session_name, F.col("calendar_year").cast("string")).alias("term_name"),
                    F.concat_ws(" ", F.coalesce("session_name_fa", session_name),
                                F.col("calendar_year").cast("string")).alias("term_name_fa"),
                    F.dense_rank().over(Window.orderBy("term_key")).alias("term_sequence"),
                    "term_start_date", "term_end_date",
                    F.date_format("term_start_date", "yyyyMMdd").cast("long").alias("term_start_date_key"),
                    F.col("year").cast("int").alias("source_year"),
                    "_version", "_deleted", "_source"))


def prepare_application_profiles(spark: SparkSession, version: int) -> DataFrame:
    rows = [(t, s, tn, tfa, sn, sfa, int(s == "A"), ts * 10 + ss)
            for t, (tn, tfa, ts) in ref.APPLICATION_TYPE.items()
            for s, (sn, sfa, ss) in ref.APPLICATION_STATUS.items()]
    frame = spark.createDataFrame(rows, ["application_type_code", "application_status_code", "application_type_name",
                                         "application_type_name_fa", "application_status_name",
                                         "application_status_name_fa", "is_admitted", "application_profile_key"])
    return frame.withColumn("_version", F.lit(version).cast("long")).withColumn("_deleted", F.lit(0)) \
                .withColumn("_source", F.lit("batch"))


def _person_columns(spark: SparkSession, frame: DataFrame) -> DataFrame:
    states = ref.lookup_frame(spark, ref.US_STATE, ["state_code", "state_name", "census_region"])
    genders = ref.lookup_frame(spark, ref.GENDER, ["gender", "gender_name", "gender_name_fa"])
    middle = F.when(F.trim("middle_name") != "", F.trim("middle_name"))
    return (frame.withColumnRenamed("state", "state_code")
            .join(F.broadcast(states), "state_code", "left")
            .join(F.broadcast(genders), "gender", "left")
            .withColumn("first_name", F.trim("first_name"))
            .withColumn("middle_name", F.coalesce(F.trim("middle_name"), F.lit("")))
            .withColumn("last_name", F.trim("last_name"))
            .withColumn("full_name", F.concat_ws(" ", "first_name", middle, "last_name"))
            .withColumn("gender_name", F.coalesce("gender_name", F.lit("Unknown")))
            .withColumn("gender_name_fa", F.coalesce("gender_name_fa", F.lit("نامشخص")))
            .withColumn("state_name", F.coalesce("state_name", F.lit("Unknown")))
            .withColumn("census_region", F.coalesce("census_region", F.lit("Unknown")))
            .withColumn("email", F.lower(F.trim("email"))))


APPLICANT_HASH = ["first_name", "middle_name", "last_name", "gender", "date_of_birth", "email", "telephone",
                  "street_address", "city", "state_code", "zip_code"]


def load_applicants(spark: SparkSession, ch: ClickHouseClient, applicants: DataFrame, *, batch_id: int,
                    full_snapshot: bool, snapshot_ms: int | None = None, ids: list[int] | None = None) -> MergeResult:
    prepared = _person_columns(spark, applicants).withColumn("applicant_id", F.col("applicant_id").cast("int"))
    return merge_type1(spark, ch, prepared, table="dim_applicant", key_column="applicant_key",
                       business_key=["applicant_id"], hash_columns=APPLICANT_HASH, batch_id=batch_id,
                       full_snapshot=full_snapshot, sequence="applicant_key_seq", snapshot_ms=snapshot_ms,
                       key_filter=in_filter("applicant_id", ids))


STUDENT_TYPE1 = ["applicant_id", "first_name", "middle_name", "last_name", "gender", "date_of_birth", "email",
                 "telephone", "street_address", "entry_term_code"]
STUDENT_TYPE2 = ["city", "state_code", "zip_code", "degree_id", "class_standing_code", "student_status_code"]
STUDENT_TYPE1_DERIVED = STUDENT_TYPE1 + ["full_name", "gender_name", "gender_name_fa", "birth_year", "cohort_year",
                                         "type1_hash"]


def prepare_students(spark: SparkSession, ch: ClickHouseClient, students: DataFrame,
                     emails: list[str] | None = None) -> DataFrame:
    degrees = ch.read_dataframe(spark, "SELECT degree_id, degree_key, degree_name, degree_level_name, department_code, "
                                       "department_name FROM v_dim_degree WHERE degree_key > 0")
    standings = ch.read_dataframe(spark, "SELECT class_standing_code, class_standing_key, class_standing_name "
                                         "FROM v_dim_class_standing WHERE class_standing_key > 0")
    where, params = in_filter("email", emails, "emails", "String")
    applicants = ch.read_dataframe(spark, "SELECT email, toString(date_of_birth) AS _dob, min(applicant_id) AS applicant_id "
                                          "FROM v_dim_applicant WHERE applicant_key > 0 AND date_of_birth IS NOT NULL "
                                          f"AND {where} GROUP BY email, _dob", params)
    status = ref.lookup_frame(spark, ref.STUDENT_STATUS,
                              ["student_status_code", "student_status_name", "student_status_name_fa"])

    frame = (_person_columns(spark, students)
             .withColumn("student_id", F.col("student_id").cast("int"))
             .withColumn("degree_id", F.coalesce(F.col("degree_pursued").cast("int"), F.lit(-1)))
             .withColumn("_has_standing", F.col("class_standing_code").isNotNull()
                         & (F.trim("class_standing_code") != ""))
             .withColumn("class_standing_code", F.when(F.col("_has_standing"), F.trim("class_standing_code"))
                                                 .otherwise(F.lit("NA")))
             .withColumn("student_status_code", F.col("student_status"))
             .withColumn("entry_term_code", F.col("enrollment_term"))
             .withColumn("_dob", F.date_format("date_of_birth", "yyyy-MM-dd")))
    frame = (frame.join(F.broadcast(degrees), "degree_id", "left")
             .join(F.broadcast(standings), "class_standing_code", "left")
             .join(F.broadcast(status), "student_status_code", "left")
             .join(applicants, ["email", "_dob"], "left"))
    return (frame
            .withColumn("birth_year", F.year("date_of_birth"))
            .withColumn("cohort_year", F.substring("entry_term_code", -4, 4).cast("int"))
            .withColumn("degree_key", F.coalesce("degree_key", F.lit(-1)))
            .withColumn("degree_name", F.coalesce("degree_name", F.lit("Unknown")))
            .withColumn("degree_level_name", F.coalesce("degree_level_name", F.lit("Unknown")))
            .withColumn("department_code", F.coalesce("department_code", F.lit("??")))
            .withColumn("department_name", F.coalesce("department_name", F.lit("Unknown")))
            .withColumn("class_standing_key", F.when(~F.col("_has_standing"), F.lit(-2))
                                               .otherwise(F.coalesce("class_standing_key", F.lit(-1))))
            .withColumn("class_standing_name", F.when(~F.col("_has_standing"), F.lit("Not applicable"))
                                                .otherwise(F.coalesce("class_standing_name", F.lit("Unknown"))))
            .withColumn("student_status_name", F.coalesce("student_status_name", F.lit("Unknown")))
            .withColumn("student_status_name_fa", F.coalesce("student_status_name_fa", F.lit("نامشخص")))
            .withColumn("type1_hash", row_hash(STUDENT_TYPE1))
            .withColumn("type2_hash", row_hash(STUDENT_TYPE2))
            .drop("_dob", "_has_standing"))


def load_students_scd2(spark: SparkSession, ch: ClickHouseClient, students: DataFrame, *, batch_id: int,
                       full_snapshot: bool, snapshot_ms: int | None = None,
                       ids: list[int] | None = None) -> MergeResult:
    result = MergeResult()
    where, params = in_filter("student_id", ids)
    current = ch.read_dataframe(
        spark,
        "SELECT student_key AS _key, student_id, type1_hash AS _t1, type2_hash AS _t2, toInt64(row_version) AS _ver, "
        "toInt64(toUnixTimestamp64Milli(valid_from)) AS _valid_from_ms, is_deleted AS _del "
        f"FROM dim_student FINAL WHERE is_current = 1 AND student_key > 0 AND {where}", params)

    joined = students.join(current, "student_id", "full_outer" if full_snapshot else "left").cache()
    fresh = joined.filter(F.col("_version").isNotNull()
                          & (F.col("_ver").isNull() | (F.col("_ver") < F.col("_version"))))
    alive = fresh.filter(F.col("_deleted") == 0)

    is_new = F.col("_key").isNull()
    type2 = F.col("_key").isNotNull() & ((F.col("_t2") != F.col("type2_hash")) | (F.col("_del") == 1))
    type1 = F.col("_key").isNotNull() & (F.col("_t2") == F.col("type2_hash")) & (F.col("_del") == 0) \
        & (F.col("_t1") != F.col("type1_hash"))

    versions = alive.filter(is_new | type2).withColumn(
        "change_reason", F.when(F.col("_key").isNull(), F.lit("new")).otherwise(F.lit("type2")))
    versions = assign_keys(versions, "student_key_seq", "student_key", ["student_id"]) \
        .withColumn("valid_from", F.timestamp_millis("_version"))
    overwrites = (alive.filter(type1).withColumn("student_key", F.col("_key"))
                  .withColumn("valid_from", F.timestamp_millis("_valid_from_ms"))
                  .withColumn("change_reason", F.lit("type1")))

    def finalize(frame: DataFrame) -> DataFrame:
        return (frame.withColumn("is_current", F.lit(1)).withColumn("is_deleted", F.lit(0))
                .withColumn("change_source", F.col("_source")).withColumn("batch_id", F.lit(batch_id).cast("long"))
                .withColumn("row_version", F.col("_version")))

    result.inserted = ch.insert_dataframe(finalize(versions), "dim_student")
    result.updated = ch.insert_dataframe(finalize(overwrites), "dim_student")

    expired = alive.filter(type2).select("_key", "_version")
    result.details["expired"] = expired.count()
    if result.details["expired"]:
        work_id = ch.stage_keys(expired, "_key", event_column="_version")
        ch.copy_rows("dim_student", "student_key", work_id, {
            "is_current": "toUInt8(0)",
            "valid_to": "fromUnixTimestamp64Milli(toInt64(w.event_ms))",
            "row_version": "w.event_ms",
        })

    touched = alive.filter(type2 | type1).filter(F.col("_t1") != F.col("type1_hash")) \
                   .select(F.col("student_id").alias("_key"), "_version")
    if touched.count():
        work_id = ch.stage_keys(touched, "_key", event_column="_version")
        _propagate_type1(ch, work_id)

    deleted = fresh.filter((F.col("_deleted") == 1) & F.col("_key").isNotNull() & (F.col("_del") == 0)) \
                   .select("_key", "_version")
    if full_snapshot and snapshot_ms is not None:
        vanished = joined.filter(F.col("_version").isNull() & F.col("_key").isNotNull() & (F.col("_del") == 0)
                                 & (F.col("_ver") < F.lit(snapshot_ms)))
        deleted = deleted.unionByName(vanished.select("_key", F.lit(snapshot_ms).cast("long").alias("_version")))
    result.deleted = deleted.count()
    if result.deleted:
        work_id = ch.stage_keys(deleted, "_key", event_column="_version")
        ch.copy_rows("dim_student", "student_key", work_id, {
            "is_deleted": "toUInt8(1)",
            "valid_to": "fromUnixTimestamp64Milli(toInt64(w.event_ms))",
            "row_version": "w.event_ms",
            "change_reason": "'deleted'",
        })
    joined.unpersist()
    return result


def _propagate_type1(ch: ClickHouseClient, work_id: str) -> None:
    columns = ch.table_columns("dim_student")
    overrides = {c: f"c.{c}" for c in STUDENT_TYPE1_DERIVED}
    overrides["row_version"] = "w.event_ms + 1"
    select = ", ".join(f"{overrides.get(col, 'h.' + col)} AS {col}" for col in columns)
    current_columns = ", ".join(["student_id"] + STUDENT_TYPE1_DERIVED)
    ch.execute(
        f"INSERT INTO dim_student ({', '.join(columns)}) "
        f"SELECT {select} FROM dim_student AS h FINAL "
        f"INNER JOIN (SELECT key_value, max(event_ms) AS event_ms FROM etl_work_keys WHERE work_id = {{w:String}} "
        f"            GROUP BY key_value) AS w ON w.key_value = h.student_id "
        f"INNER JOIN (SELECT {current_columns} FROM dim_student FINAL WHERE is_current = 1 AND student_id IN "
        f"            (SELECT key_value FROM etl_work_keys WHERE work_id = {{w:String}})) AS c "
        f"        ON c.student_id = h.student_id "
        f"WHERE h.is_current = 0 AND h.type1_hash != c.type1_hash",
        {"w": work_id})
