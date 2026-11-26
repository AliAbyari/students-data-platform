CREATE TABLE IF NOT EXISTS fact_enrollment
(
    course_enrollment_id Int32,
    term_key             UInt32,
    term_start_date_key  UInt32,
    student_key          Int64,
    course_key           Int32,
    department_key       Int32,
    degree_key           Int32,
    class_standing_key   Int32,
    grade_key            Int32,
    course_offering_id   Int32,
    section_number       Int32,
    enrollment_count     UInt8,
    credits_attempted    Decimal(4, 1),
    credits_earned       Decimal(4, 1),
    gpa_credits          Decimal(4, 1),
    quality_points       Decimal(5, 1),
    passed_count         UInt8,
    failed_count         UInt8,
    withdrawn_count      UInt8,
    graded_count         UInt8,
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    change_source        LowCardinality(String),
    batch_id             UInt64,
    row_version          UInt64,
    loaded_at            DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY course_enrollment_id;

CREATE TABLE IF NOT EXISTS fact_application
(
    applicant_id            Int32,
    applicant_key           Int64,
    application_date_key    UInt32,
    entry_term_key          UInt32,
    application_profile_key Int32,
    student_key             Int64,
    application_count       UInt8,
    admitted_count          UInt8,
    denied_count            UInt8,
    enrolled_count          UInt8,
    high_school_gpa         Nullable(Decimal(3, 2)),
    sat_math_score          Nullable(Int32),
    sat_reading_score       Nullable(Int32),
    sat_writing_score       Nullable(Int32),
    sat_total_score         Nullable(Int32),
    essay_score             Nullable(Int32),
    admission_points        Nullable(Float64),
    age_at_application      Nullable(UInt8),
    lead_time_days          Nullable(Int32),
    row_hash                Int64,
    is_deleted              UInt8 DEFAULT 0,
    change_source           LowCardinality(String),
    batch_id                UInt64,
    row_version             UInt64,
    loaded_at               DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY applicant_id;

CREATE TABLE IF NOT EXISTS fact_course_offering
(
    course_offering_id   Int32,
    term_key             UInt32,
    term_start_date_key  UInt32,
    course_key           Int32,
    department_key       Int32,
    section_number       Int32,
    section_count        UInt8,
    capacity             Int32,
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    change_source        LowCardinality(String),
    batch_id             UInt64,
    row_version          UInt64,
    loaded_at            DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY course_offering_id;
