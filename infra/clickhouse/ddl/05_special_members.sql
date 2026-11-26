INSERT INTO dim_date (date_key, full_date, day_of_month, day_of_week, day_name, month_number, month_name, quarter,
                      calendar_year, year_month, is_weekend, academic_year, academic_year_label, persian_date,
                      persian_year, persian_month, persian_month_name, persian_day, persian_year_month,
                      persian_weekday_name, row_version)
VALUES (0, '1970-01-01', 0, 0, 'Unknown', 0, 'Unknown', 0, 0, 0, 0, 0, 'Unknown', 'Unknown', 0, 0, 'نامشخص', 0, 0, 'نامشخص', 0);

INSERT INTO dim_term (term_key, term_code, session_code, session_name, session_name_fa, session_order, calendar_year,
                      academic_year, academic_year_label, term_name, term_name_fa, term_sequence, term_start_date,
                      term_end_date, term_start_date_key, source_year, row_hash, batch_id, row_version)
VALUES (0, 'UNK', 'NA', 'Unknown', 'نامشخص', 0, 0, 0, 'Unknown', 'Unknown', 'نامشخص', 0, '1970-01-01', '1970-01-01', 0, 0, 0, 0, 0);

INSERT INTO dim_department (department_key, department_code, department_name, department_name_fa, school_name,
                            school_name_fa, row_hash, batch_id, row_version)
VALUES (-1, '??', 'Unknown', 'نامشخص', 'Unknown', 'نامشخص', 0, 0, 0);

INSERT INTO dim_course (course_key, department_code, course_number, department_key, course_code, course_title,
                        course_description, credits, maximum_section_size, course_level, course_level_name,
                        department_name, department_name_fa, school_name, school_name_fa, row_hash, batch_id, row_version)
VALUES (-1, '??', 0, -1, 'UNKNOWN', 'Unknown', 'Unknown', 0, NULL, 0, 'Unknown', 'Unknown', 'نامشخص', 'Unknown', 'نامشخص', 0, 0, 0);

INSERT INTO dim_degree (degree_key, degree_id, department_key, degree_name, degree_type_code, degree_type_name,
                        degree_level_code, degree_level_name, degree_level_name_fa, department_code, department_name,
                        department_name_fa, school_name, row_hash, batch_id, row_version)
VALUES (-1, -1, -1, 'Unknown', '?', 'Unknown', '?', 'Unknown', 'نامشخص', '??', 'Unknown', 'نامشخص', 'Unknown', 0, 0, 0);

INSERT INTO dim_class_standing (class_standing_key, class_standing_code, class_standing_name, class_standing_name_fa,
                                degree_level_code, degree_level_name, standing_order, min_credits, max_credits,
                                row_hash, batch_id, row_version)
VALUES (-1, '??', 'Unknown', 'نامشخص', '?', 'Unknown', 0, 0, 0, 0, 0, 0),
       (-2, 'NA', 'Not applicable', 'ثبت نشده', '?', 'Not applicable', 0, 0, 0, 0, 0, 0);

INSERT INTO dim_grade (grade_key, grade_code, grade_description, grade_description_fa, grade_points, include_in_gpa,
                       is_passing, grade_category, sort_order, row_hash, batch_id, row_version)
VALUES (-1, '??', 'Unknown', 'نامشخص', NULL, 0, 0, 'Unknown', 99, 0, 0, 0),
       (-2, 'NG', 'Not graded', 'بدون نمره', NULL, 0, 0, 'Not graded', 98, 0, 0, 0);

INSERT INTO dim_application_profile (application_profile_key, application_type_code, application_status_code,
                                     application_type_name, application_type_name_fa, application_status_name,
                                     application_status_name_fa, is_admitted, row_version)
VALUES (-1, '?', '?', 'Unknown', 'نامشخص', 'Unknown', 'نامشخص', 0, 0);

INSERT INTO dim_applicant (applicant_key, applicant_id, first_name, middle_name, last_name, full_name, gender,
                           gender_name, gender_name_fa, date_of_birth, email, telephone, street_address, city,
                           state_code, state_name, census_region, zip_code, row_hash, change_source, batch_id, row_version)
VALUES (-1, -1, 'Unknown', '', 'Unknown', 'Unknown', '?', 'Unknown', 'نامشخص', NULL, '', '', '', '', '??',
        'Unknown', 'Unknown', '', 0, 'seed', 0, 0);

INSERT INTO dim_student (student_key, student_id, applicant_id, first_name, middle_name, last_name, full_name, gender,
                         gender_name, gender_name_fa, date_of_birth, birth_year, email, telephone, street_address,
                         entry_term_code, cohort_year, city, state_code, zip_code, degree_id, class_standing_code,
                         student_status_code, state_name, census_region, degree_key, degree_name, degree_level_name,
                         department_code, department_name, class_standing_key, class_standing_name,
                         student_status_name, student_status_name_fa, type1_hash, type2_hash, valid_from, is_current,
                         change_reason, change_source, batch_id, row_version)
VALUES (-1, -1, NULL, 'Unknown', '', 'Unknown', 'Unknown', '?', 'Unknown', 'نامشخص', NULL, NULL, '', '', '', 'UNK', NULL,
        '', '??', '', -1, '??', '?', 'Unknown', 'Unknown', -1, 'Unknown', 'Unknown', '??', 'Unknown', -1, 'Unknown',
        'Unknown', 'نامشخص', 0, 0, '1970-01-01 00:00:00', 1, 'seed', 'seed', 0, 0),
       (-2, -2, NULL, 'Not applicable', '', 'Not applicable', 'Not applicable', '?', 'Not applicable', 'ندارد', NULL,
        NULL, '', '', '', 'UNK', NULL, '', '??', '', -1, 'NA', '?', 'Not applicable', 'Not applicable', -1,
        'Not applicable', 'Not applicable', '??', 'Not applicable', -2, 'Not applicable', 'Not applicable', 'ندارد',
        0, 0, '1970-01-01 00:00:00', 1, 'seed', 'seed', 0, 0);
