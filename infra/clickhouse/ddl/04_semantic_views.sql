CREATE OR REPLACE VIEW v_dim_date AS SELECT * FROM dim_date FINAL;
CREATE OR REPLACE VIEW v_dim_term AS SELECT * FROM dim_term FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_dim_department AS SELECT * FROM dim_department FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_dim_course AS SELECT * FROM dim_course FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_dim_degree AS SELECT * FROM dim_degree FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_dim_class_standing AS SELECT * FROM dim_class_standing FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_dim_grade AS SELECT * FROM dim_grade FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_dim_application_profile AS SELECT * FROM dim_application_profile FINAL;
CREATE OR REPLACE VIEW v_dim_applicant AS SELECT * FROM dim_applicant FINAL WHERE is_deleted = 0;

CREATE OR REPLACE VIEW v_dim_student_history AS SELECT * FROM dim_student FINAL;
CREATE OR REPLACE VIEW v_dim_student AS
SELECT * FROM dim_student FINAL WHERE is_current = 1 AND is_deleted = 0;

CREATE OR REPLACE VIEW v_fact_enrollment AS SELECT * FROM fact_enrollment FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_fact_application AS SELECT * FROM fact_application FINAL WHERE is_deleted = 0;
CREATE OR REPLACE VIEW v_fact_course_offering AS SELECT * FROM fact_course_offering FINAL WHERE is_deleted = 0;

CREATE OR REPLACE VIEW rpt_enrollment AS
SELECT
    f.course_enrollment_id AS course_enrollment_id,
    f.course_offering_id AS course_offering_id,
    f.section_number AS section_number,
    t.term_key AS term_key, t.term_code AS term_code, t.term_name AS term_name, t.term_name_fa AS term_name_fa, t.calendar_year AS calendar_year, t.academic_year_label AS academic_year_label,
    t.session_code AS session_code, t.session_name AS session_name, t.session_name_fa AS session_name_fa,
    c.course_code AS course_code, c.course_title AS course_title, c.course_level AS course_level, c.credits AS credits,
    d.department_code AS department_code, d.department_name AS department_name, d.department_name_fa AS department_name_fa, d.school_name AS school_name, d.school_name_fa AS school_name_fa,
    g.degree_id AS degree_id, g.degree_name AS degree_name, g.degree_level_name AS degree_level_name,
    cs.class_standing_code AS class_standing_code, cs.class_standing_name AS class_standing_name,
    gr.grade_code AS grade_code, gr.grade_category AS grade_category,
    s.student_id AS student_id, s.full_name AS student_name, s.state_code AS state_code, s.census_region AS census_region, s.gender AS gender,
    f.enrollment_count AS enrollment_count, f.credits_attempted AS credits_attempted, f.credits_earned AS credits_earned, f.gpa_credits AS gpa_credits, f.quality_points AS quality_points,
    f.passed_count AS passed_count, f.failed_count AS failed_count, f.withdrawn_count AS withdrawn_count, f.graded_count AS graded_count,
    f.change_source AS change_source, f.loaded_at AS loaded_at
FROM v_fact_enrollment AS f
LEFT JOIN v_dim_term           AS t  ON t.term_key = f.term_key
LEFT JOIN v_dim_course         AS c  ON c.course_key = f.course_key
LEFT JOIN v_dim_department     AS d  ON d.department_key = f.department_key
LEFT JOIN v_dim_degree         AS g  ON g.degree_key = f.degree_key
LEFT JOIN v_dim_class_standing AS cs ON cs.class_standing_key = f.class_standing_key
LEFT JOIN v_dim_grade          AS gr ON gr.grade_key = f.grade_key
LEFT JOIN v_dim_student_history AS s ON s.student_key = f.student_key;

CREATE OR REPLACE VIEW rpt_course_offering_fill AS
SELECT
    o.course_offering_id AS course_offering_id,
    o.section_number AS section_number,
    t.term_key AS term_key, t.term_code AS term_code, t.term_name AS term_name, t.term_name_fa AS term_name_fa, t.calendar_year AS calendar_year,
    c.course_code AS course_code, c.course_title AS course_title,
    d.department_code AS department_code, d.department_name AS department_name, d.department_name_fa AS department_name_fa,
    o.capacity AS capacity,
    ifNull(e.enrolled, 0)                                AS enrolled,
    ifNull(e.passed, 0)                                  AS passed,
    ifNull(e.withdrawn, 0)                               AS withdrawn,
    toInt64(o.capacity) - toInt64(ifNull(e.enrolled, 0)) AS seats_remaining,
    if(ifNull(e.enrolled, 0) > o.capacity, 1, 0)         AS is_over_capacity
FROM v_fact_course_offering AS o
LEFT JOIN
(
    SELECT course_offering_id,
           sum(enrollment_count) AS enrolled,
           sum(passed_count)     AS passed,
           sum(withdrawn_count)  AS withdrawn
    FROM v_fact_enrollment
    GROUP BY course_offering_id
) AS e ON e.course_offering_id = o.course_offering_id
LEFT JOIN v_dim_term       AS t ON t.term_key = o.term_key
LEFT JOIN v_dim_course     AS c ON c.course_key = o.course_key
LEFT JOIN v_dim_department AS d ON d.department_key = o.department_key;

CREATE OR REPLACE VIEW rpt_admissions AS
SELECT
    t.term_key AS term_key, t.term_code AS term_code, t.term_name AS term_name, t.term_name_fa AS term_name_fa, t.calendar_year AS calendar_year,
    p.application_type_code AS application_type_code, p.application_type_name AS application_type_name, p.application_type_name_fa AS application_type_name_fa,
    a.state_code AS state_code, a.census_region AS census_region, a.gender AS gender,
    f.application_count AS application_count, f.admitted_count AS admitted_count, f.denied_count AS denied_count, f.enrolled_count AS enrolled_count,
    f.high_school_gpa AS high_school_gpa, f.sat_total_score AS sat_total_score, f.admission_points AS admission_points, f.age_at_application AS age_at_application, f.lead_time_days AS lead_time_days
FROM v_fact_application AS f
LEFT JOIN v_dim_term                AS t ON t.term_key = f.entry_term_key
LEFT JOIN v_dim_application_profile AS p ON p.application_profile_key = f.application_profile_key
LEFT JOIN v_dim_applicant           AS a ON a.applicant_key = f.applicant_key;

CREATE OR REPLACE VIEW rpt_pipeline_runs AS
SELECT
    batch_id,
    pipeline,
    min(l.started_at)                                              AS run_started_at,
    max(l.finished_at)                                             AS run_finished_at,
    toUInt8(countIf(l.status = 'failed') > 0)                      AS has_failure,
    sum(l.rows_written)                                            AS total_rows_written,
    arraySort(groupArray((l.started_at, l.step, l.status, l.rows_written, l.duration_ms))) AS steps
FROM etl_step_log AS l
GROUP BY batch_id, pipeline;
