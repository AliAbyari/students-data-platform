CREATE DATABASE airflow;

CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS control;

CREATE SEQUENCE IF NOT EXISTS control.batch_id_seq START 1;

CREATE SEQUENCE IF NOT EXISTS control.student_key_seq   START 1;
CREATE SEQUENCE IF NOT EXISTS control.applicant_key_seq START 1;
CREATE SEQUENCE IF NOT EXISTS control.reference_key_seq START 1;

CREATE TABLE IF NOT EXISTS control.etl_batch (
    batch_id        bigint      PRIMARY KEY,
    pipeline        text        NOT NULL,
    snapshot_ms     bigint      NOT NULL,
    status          text        NOT NULL DEFAULT 'running',
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    message         text
);

CREATE TABLE IF NOT EXISTS control.extract_log (
    batch_id    bigint      NOT NULL REFERENCES control.etl_batch (batch_id),
    table_name  text        NOT NULL,
    row_count   bigint      NOT NULL,
    duration_ms bigint      NOT NULL,
    loaded_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, table_name)
);

CREATE TABLE IF NOT EXISTS stg.students (
    student_id int, first_name text, middle_name text, last_name text, gender text,
    street_address text, city text, state text, zip_code text, telephone text, email text,
    date_of_birth date, degree_pursued int, class_standing_code text, student_status text,
    enrollment_term text, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.applicants (
    applicant_id int, first_name text, middle_name text, last_name text, gender text,
    street_address text, city text, state text, zip_code text, telephone text, email text,
    date_of_birth date, application_received_date date, entry_term text, application_type text,
    gpa numeric(3, 2), sat_math_score int, sat_reading_score int, sat_writing_score int,
    essay_score int, application_status text, admission_points double precision,
    _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.course_enrollments (
    course_enrollment_id int, course_offering_id int, student_id int, grade text,
    _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.course_offerings (
    course_offering_id int, department_code text, course_number int, term_code text,
    section int, capacity int, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.courses (
    department_code text, course_number int, course_title text, course_description text,
    credits numeric(3, 1), maximum_section_size int, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.departments (
    department_code text, department_name text, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.degrees (
    degree_id int, department_code text, degree_type_code text, degree_name text,
    _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.degree_types (
    degree_type_code text, degree_type_name text, degree_level_code text,
    _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.degree_levels (
    degree_level_code text, degree_level_name text, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.class_standings (
    class_standing_code text, class_standing_name text, degree_level_code text,
    required_credits int, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.grades (
    grade text, points numeric(2, 1), include_in_gpa boolean, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.terms (
    term_code text, session_code text, year int, _batch_id bigint, _extracted_at timestamptz);

CREATE TABLE IF NOT EXISTS stg.sessions (
    session_code text, session_name text, _batch_id bigint, _extracted_at timestamptz);
