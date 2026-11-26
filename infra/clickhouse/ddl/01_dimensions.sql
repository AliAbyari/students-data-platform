CREATE TABLE IF NOT EXISTS dim_date
(
    date_key             UInt32,
    full_date            Date,
    day_of_month         UInt8,
    day_of_week          UInt8,                 
    day_name             LowCardinality(String),
    month_number         UInt8,
    month_name           LowCardinality(String),
    quarter              UInt8,
    calendar_year        UInt16,
    year_month           UInt32,
    is_weekend           UInt8,
    academic_year        UInt16,                
    academic_year_label  String,
    persian_date         String,                
    persian_year         UInt16,
    persian_month        UInt8,
    persian_month_name   LowCardinality(String),
    persian_day          UInt8,
    persian_year_month   UInt32,
    persian_weekday_name LowCardinality(String),
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY date_key;

CREATE TABLE IF NOT EXISTS dim_term
(
    term_key             UInt32,                
    term_code            String,
    session_code         LowCardinality(String),
    session_name         LowCardinality(String),
    session_name_fa      LowCardinality(String),
    session_order        UInt8,
    calendar_year        UInt16,
    academic_year        UInt16,
    academic_year_label  String,
    term_name            String,
    term_name_fa         String,
    term_sequence        UInt16,
    term_start_date      Date,
    term_end_date        Date,
    term_start_date_key  UInt32,
    source_year          Int32,                
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    batch_id             UInt64,
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY term_key;

CREATE TABLE IF NOT EXISTS dim_department
(
    department_key       Int32,
    department_code      String,
    department_name      String,
    department_name_fa   String,
    school_name          LowCardinality(String),
    school_name_fa       LowCardinality(String),
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    batch_id             UInt64,
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY department_key;

CREATE TABLE IF NOT EXISTS dim_course
(
    course_key           Int32,
    department_code      String,
    course_number        Int32,
    department_key       Int32,
    course_code          String,                
    course_title         String,
    course_description   String,
    credits              Decimal(3, 1),
    maximum_section_size Nullable(Int32),
    course_level         Int32,                 
    course_level_name    LowCardinality(String),
    department_name      String,
    department_name_fa   String,
    school_name          LowCardinality(String),
    school_name_fa       LowCardinality(String),
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    batch_id             UInt64,
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY course_key;

CREATE TABLE IF NOT EXISTS dim_degree
(
    degree_key           Int32,
    degree_id            Int32,
    department_key       Int32,
    degree_name          String,
    degree_type_code     LowCardinality(String),
    degree_type_name     LowCardinality(String),
    degree_level_code    LowCardinality(String),
    degree_level_name    LowCardinality(String),
    degree_level_name_fa LowCardinality(String),
    department_code      String,
    department_name      String,
    department_name_fa   String,
    school_name          LowCardinality(String),
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    batch_id             UInt64,
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY degree_key;

CREATE TABLE IF NOT EXISTS dim_class_standing
(
    class_standing_key   Int32,
    class_standing_code  String,
    class_standing_name  String,
    class_standing_name_fa String,
    degree_level_code    LowCardinality(String),
    degree_level_name    LowCardinality(String),
    standing_order       UInt8,
    min_credits          Int32,
    max_credits          Int32,
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    batch_id             UInt64,
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY class_standing_key;

CREATE TABLE IF NOT EXISTS dim_grade
(
    grade_key            Int32,
    grade_code           String,
    grade_description    String,
    grade_description_fa String,
    grade_points         Nullable(Decimal(2, 1)),
    include_in_gpa       UInt8,
    is_passing           UInt8,
    grade_category       LowCardinality(String),
    sort_order           UInt8,
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    batch_id             UInt64,
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY grade_key;

CREATE TABLE IF NOT EXISTS dim_application_profile
(
    application_profile_key    Int32,
    application_type_code      String,
    application_status_code    String,
    application_type_name      LowCardinality(String),
    application_type_name_fa   LowCardinality(String),
    application_status_name    LowCardinality(String),
    application_status_name_fa LowCardinality(String),
    is_admitted                UInt8,
    row_hash                   Int64 DEFAULT 0,
    is_deleted                 UInt8 DEFAULT 0,
    batch_id                   UInt64 DEFAULT 0,
    row_version                UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY application_profile_key;

CREATE TABLE IF NOT EXISTS dim_applicant
(
    applicant_key        Int64,
    applicant_id         Int32,
    first_name           String,
    middle_name          String,
    last_name            String,
    full_name            String,
    gender               LowCardinality(String),
    gender_name          LowCardinality(String),
    gender_name_fa       LowCardinality(String),
    date_of_birth        Nullable(Date),
    email                String,
    telephone            String,
    street_address       String,
    city                 String,
    state_code           LowCardinality(String),
    state_name           LowCardinality(String),
    census_region        LowCardinality(String),
    zip_code             String,
    row_hash             Int64,
    is_deleted           UInt8 DEFAULT 0,
    change_source        LowCardinality(String),  
    batch_id             UInt64,
    row_version          UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY applicant_key;

CREATE TABLE IF NOT EXISTS dim_student
(
    student_key            Int64,
    student_id             Int32,
    applicant_id           Nullable(Int32),
    first_name             String,
    middle_name            String,
    last_name              String,
    full_name              String,
    gender                 LowCardinality(String),
    gender_name            LowCardinality(String),
    gender_name_fa         LowCardinality(String),
    date_of_birth          Nullable(Date),
    birth_year             Nullable(UInt16),
    email                  String,
    telephone              String,
    street_address         String,
    entry_term_code        String,
    cohort_year            Nullable(UInt16),
    city                   String,
    state_code             LowCardinality(String),
    zip_code               String,
    degree_id              Int32,
    class_standing_code    LowCardinality(String),
    student_status_code    LowCardinality(String),
    state_name             LowCardinality(String),
    census_region          LowCardinality(String),
    degree_key             Int32,
    degree_name            String,
    degree_level_name      LowCardinality(String),
    department_code        LowCardinality(String),
    department_name        String,
    class_standing_key     Int32,
    class_standing_name    LowCardinality(String),
    student_status_name    LowCardinality(String),
    student_status_name_fa LowCardinality(String),
    type1_hash             Int64,
    type2_hash             Int64,
    valid_from             DateTime64(3),
    valid_to               DateTime64(3) DEFAULT toDateTime64('2299-12-31 00:00:00', 3),
    is_current             UInt8,
    is_deleted             UInt8 DEFAULT 0,
    change_reason          LowCardinality(String),  
    change_source          LowCardinality(String), 
    batch_id               UInt64,
    row_version            UInt64
)
ENGINE = ReplacingMergeTree(row_version)
ORDER BY student_key;
