from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .clickhouse import ClickHouseClient
from .control import pg_query


@dataclass(frozen=True)
class Rule:
    name: str
    table: str
    severity: str
    sql: str


RULES = [
    Rule("table_not_empty", "stg.students", "error", "SELECT CASE WHEN count(*) = 0 THEN 1 ELSE 0 END FROM stg.students"),
    Rule("table_not_empty", "stg.course_enrollments", "error",
         "SELECT CASE WHEN count(*) = 0 THEN 1 ELSE 0 END FROM stg.course_enrollments"),
    Rule("business_key_not_null", "stg.students", "error", "SELECT count(*) FROM stg.students WHERE student_id IS NULL"),
    Rule("business_key_unique", "stg.students", "error",
         "SELECT count(*) FROM (SELECT student_id FROM stg.students GROUP BY student_id HAVING count(*) > 1) d"),
    Rule("business_key_unique", "stg.course_enrollments", "error",
         "SELECT count(*) FROM (SELECT course_enrollment_id FROM stg.course_enrollments "
         "GROUP BY course_enrollment_id HAVING count(*) > 1) d"),
    Rule("orphan_student", "stg.course_enrollments", "warning",
         "SELECT count(*) FROM stg.course_enrollments e LEFT JOIN stg.students s USING (student_id) "
         "WHERE s.student_id IS NULL"),
    Rule("orphan_offering", "stg.course_enrollments", "warning",
         "SELECT count(*) FROM stg.course_enrollments e LEFT JOIN stg.course_offerings o USING (course_offering_id) "
         "WHERE o.course_offering_id IS NULL"),
    Rule("unknown_grade", "stg.course_enrollments", "warning",
         "SELECT count(*) FROM stg.course_enrollments e LEFT JOIN stg.grades g ON g.grade = e.grade "
         "WHERE e.grade IS NOT NULL AND g.grade IS NULL"),
    Rule("unknown_degree", "stg.students", "warning",
         "SELECT count(*) FROM stg.students s LEFT JOIN stg.degrees d ON d.degree_id = s.degree_pursued "
         "WHERE d.degree_id IS NULL"),
    Rule("invalid_status", "stg.students", "warning",
         "SELECT count(*) FROM stg.students WHERE student_status NOT IN ('A', 'G', 'W') OR student_status IS NULL"),
    Rule("missing_class_standing", "stg.students", "warning",
         "SELECT count(*) FROM stg.students WHERE class_standing_code IS NULL OR class_standing_code = ''"),
    Rule("gpa_out_of_range", "stg.applicants", "warning",
         "SELECT count(*) FROM stg.applicants WHERE gpa < 0 OR gpa > 4"),
    Rule("sat_out_of_range", "stg.applicants", "warning",
         "SELECT count(*) FROM stg.applicants WHERE sat_math_score NOT BETWEEN 200 AND 800 "
         "OR sat_reading_score NOT BETWEEN 200 AND 800 OR sat_writing_score NOT BETWEEN 200 AND 800"),
    Rule("capacity_positive", "stg.course_offerings", "warning",
         "SELECT count(*) FROM stg.course_offerings WHERE capacity <= 0"),
    Rule("term_year_consistent", "stg.terms", "warning",
         "SELECT count(*) FROM stg.terms WHERE year::text <> right(term_code, 4)"),
]


def run_rules(ch: ClickHouseClient, batch_id: int) -> list[dict]:
    results = []
    for rule in RULES:
        failed = int(pg_query(rule.sql)[0][0])
        results.append({
            "batch_id": batch_id, "checked_at": datetime.now(timezone.utc).isoformat(), "rule_name": rule.name,
            "table_name": rule.table, "severity": rule.severity, "failed_rows": failed, "passed": int(failed == 0),
            "details": rule.sql,
        })
    ch.insert_rows("dq_result", results)
    blocking = [r for r in results if r["severity"] == "error" and not r["passed"]]
    if blocking:
        names = ", ".join(f"{r['rule_name']}({r['table_name']})" for r in blocking)
        raise RuntimeError(f"Blocking data quality rules failed: {names}")
    return results


def reconcile(ch: ClickHouseClient, batch_id: int) -> list[dict]:
    pairs = [("stg.students", "v_dim_student", "student_id > 0"),
             ("stg.applicants", "v_fact_application", "1"),
             ("stg.course_offerings", "v_fact_course_offering", "1"),
             ("stg.course_enrollments", "v_fact_enrollment", "1")]
    results = []
    for staging, warehouse, where in pairs:
        source_rows = int(pg_query(f"SELECT count(*) FROM {staging}")[0][0])
        dw_rows = int(ch.scalar(f"SELECT count() FROM {warehouse} WHERE {where}"))
        diff = abs(source_rows - dw_rows)
        results.append({
            "batch_id": batch_id, "checked_at": datetime.now(timezone.utc).isoformat(),
            "rule_name": "reconcile_row_count", "table_name": warehouse,
            "severity": "warning", "failed_rows": diff, "passed": int(diff == 0),
            "details": f"staging={source_rows} warehouse={dw_rows}",
        })
    ch.insert_rows("dq_result", results)
    return results
