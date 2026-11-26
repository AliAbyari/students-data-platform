using StudentsPortal.Server.Infrastructure;
using StudentsPortal.Shared;

namespace StudentsPortal.Server.Endpoints;

public static class AnalyticsEndpoints
{
    private const string PopulationFilter =
        "student_key > 0 " +
        "AND ({degree:Nullable(Int32)} IS NULL OR degree_id = {degree:Nullable(Int32)}) " +
        "AND ({term:Nullable(String)} IS NULL OR entry_term_code = {term:Nullable(String)})";

    public static void MapAnalyticsEndpoints(this IEndpointRouteBuilder app)
    {
        var api = app.MapGroup("/api/analytics").RequireAuthorization();
        api.MapGet("/overview", Overview);
        api.MapGet("/students/{id:int}", StudentInsight);
        api.MapGet("/cdc", CdcMonitor);
        api.MapGet("/pipeline", Pipeline);
    }

    private static async Task<IResult> Overview(ClickHouseClient ch, int? degree, string? term, CancellationToken ct)
    {
        var p = new Dictionary<string, object?> { ["degree"] = degree, ["term"] = string.IsNullOrWhiteSpace(term) ? null : term };
        var scope = degree is null && p["term"] is null
            ? ""
            : $"AND f.student_key IN (SELECT student_key FROM dim_student WHERE student_id IN " +
              $"(SELECT student_id FROM v_dim_student WHERE {PopulationFilter}))";

        var kpis = ch.SingleAsync<Kpis>(
            "SELECT count() AS total, countIf(student_status_code = 'A') AS active, " +
            "countIf(student_status_code = 'G') AS graduated, countIf(student_status_code = 'W') AS withdrawn " +
            $"FROM v_dim_student WHERE {PopulationFilter}", p, ct);
        var cohorts = ch.QueryAsync<LabelValue>(
            "SELECT toString(cohort_year) AS label, CAST(NULL, 'Nullable(String)') AS label_fa, toFloat64(count()) AS value " +
            $"FROM v_dim_student WHERE {PopulationFilter} AND cohort_year IS NOT NULL " +
            "GROUP BY cohort_year ORDER BY cohort_year", p, ct);
        var degrees = ch.QueryAsync<LabelValue>(
            "SELECT degree_name AS label, CAST(NULL, 'Nullable(String)') AS label_fa, toFloat64(count()) AS value " +
            $"FROM v_dim_student WHERE {PopulationFilter} GROUP BY degree_name ORDER BY value DESC LIMIT 6", p, ct);
        var byTerm = ch.QueryAsync<LabelValue>(
            "SELECT any(t.term_name) AS label, any(t.term_name_fa) AS label_fa, toFloat64(sum(f.enrollment_count)) AS value " +
            "FROM v_fact_enrollment AS f INNER JOIN v_dim_term AS t ON t.term_key = f.term_key " +
            $"WHERE f.term_key > 0 {scope} GROUP BY f.term_key ORDER BY f.term_key", p, ct);
        var gpa = ch.QueryAsync<LabelValue>(
            "SELECT d.department_name AS label, d.department_name_fa AS label_fa, " +
            "round(toFloat64(sum(f.quality_points)) / nullIf(toFloat64(sum(f.gpa_credits)), 0), 2) AS value, " +
            "toFloat64(sum(f.enrollment_count)) AS extra " +
            "FROM v_fact_enrollment AS f INNER JOIN v_dim_department AS d ON d.department_key = f.department_key " +
            $"WHERE f.department_key > 0 {scope} GROUP BY d.department_name, d.department_name_fa " +
            "HAVING value IS NOT NULL ORDER BY value DESC", p, ct);
        var grades = ch.QueryAsync<LabelValue>(
            "SELECT g.grade_code AS label, any(g.grade_description_fa) AS label_fa, toFloat64(count()) AS value " +
            "FROM v_fact_enrollment AS f INNER JOIN v_dim_grade AS g ON g.grade_key = f.grade_key " +
            $"WHERE 1 {scope} GROUP BY g.grade_code, g.sort_order ORDER BY g.sort_order", p, ct);
        var fill = ch.QueryAsync<LabelValue>(
            "SELECT department_name AS label, any(department_name_fa) AS label_fa, " +
            "round(100 * sum(enrolled) / nullIf(sum(capacity), 0), 1) AS value, toFloat64(sum(capacity)) AS extra " +
            "FROM rpt_course_offering_fill WHERE department_name != '' GROUP BY department_name " +
            "HAVING value IS NOT NULL ORDER BY value DESC", null, ct);
        var admissions = ch.QueryAsync<LabelValue>(
            "SELECT toString(calendar_year) AS label, CAST(NULL, 'Nullable(String)') AS label_fa, " +
            "toFloat64(sum(application_count)) AS value, toFloat64(sum(admitted_count)) AS extra " +
            "FROM rpt_admissions WHERE calendar_year > 0 GROUP BY calendar_year ORDER BY calendar_year", null, ct);
        var recent = ch.QueryAsync<RecentStudent>(
            "SELECT student_id, full_name, degree_name, student_status_code, change_source " +
            $"FROM v_dim_student WHERE {PopulationFilter} ORDER BY row_version DESC, student_id DESC LIMIT 7", p, ct);
        var freshness = ch.SingleAsync<Freshness>(
            "SELECT (SELECT max(run_finished_at) FROM rpt_pipeline_runs WHERE pipeline = 'batch_scd' AND has_failure = 0) " +
            "         AS last_batch_at, " +
            "       (SELECT max(batch_id) FROM rpt_pipeline_runs WHERE pipeline = 'batch_scd' AND has_failure = 0) " +
            "         AS last_batch_id, " +
            "       (SELECT max(processed_at) FROM cdc_event_log) AS last_cdc_at, " +
            "       (SELECT count() FROM cdc_event_log WHERE processed_at >= today()) AS cdc_events_today", null, ct);

        await Task.WhenAll(kpis, cohorts, degrees, byTerm, gpa, grades, fill, admissions, recent, freshness);
        var lastBatch = freshness.Result;
        return Results.Ok(new Overview(
            kpis.Result ?? new Kpis(0, 0, 0, 0), cohorts.Result, degrees.Result, byTerm.Result, gpa.Result,
            grades.Result, fill.Result, admissions.Result, recent.Result,
            lastBatch is null ? new Freshness(null, null, null, 0)
                              : lastBatch with { LastBatchAt = Real(lastBatch.LastBatchAt), LastCdcAt = Real(lastBatch.LastCdcAt),
                                                 LastBatchId = lastBatch.LastBatchId is > 0 ? lastBatch.LastBatchId : null }));
    }

    private static async Task<IResult> StudentInsight(int id, ClickHouseClient ch, CancellationToken ct)
    {
        var p = new Dictionary<string, object?> { ["id"] = id };
        var versions = ch.QueryAsync<StudentVersion>(
            "SELECT student_key, full_name, email, city, state_code, degree_name, class_standing_name, " +
            "student_status_code, student_status_name, student_status_name_fa, valid_from, valid_to, is_current, " +
            "is_deleted, change_reason, change_source, toInt64(batch_id) AS batch_id " +
            "FROM v_dim_student_history WHERE student_id = {id:Int32} ORDER BY valid_from, student_key", p, ct);
        var terms = ch.QueryAsync<TermSummary>(
            "SELECT t.term_code AS term_code, any(t.term_name) AS term_name, any(t.term_name_fa) AS term_name_fa, " +
            "toInt64(count()) AS courses, toFloat64(sum(f.credits_earned)) AS credits, " +
            "round(toFloat64(sum(f.quality_points)) / nullIf(toFloat64(sum(f.gpa_credits)), 0), 2) AS gpa " +
            "FROM v_fact_enrollment AS f INNER JOIN v_dim_term AS t ON t.term_key = f.term_key " +
            "WHERE f.student_key IN (SELECT student_key FROM dim_student WHERE student_id = {id:Int32}) " +
            "GROUP BY t.term_code, t.term_key ORDER BY t.term_key", p, ct);
        var totals = ch.SingleAsync<TranscriptTotals>(
            "SELECT toInt64(count()) AS enrollments, toFloat64(sum(credits_earned)) AS credits_earned, " +
            "round(toFloat64(sum(quality_points)) / nullIf(toFloat64(sum(gpa_credits)), 0), 2) AS gpa " +
            "FROM v_fact_enrollment WHERE student_key IN (SELECT student_key FROM dim_student WHERE student_id = {id:Int32})",
            p, ct);
        await Task.WhenAll(versions, terms, totals);
        var t = totals.Result ?? new TranscriptTotals(0, 0, null);
        return Results.Ok(new StudentInsight(id, versions.Result, terms.Result, t.Enrollments, t.CreditsEarned, t.Gpa));
    }

    private sealed record TranscriptTotals(long Enrollments, double CreditsEarned, double? Gpa);

    private static async Task<IResult> CdcMonitor(ClickHouseClient ch, CancellationToken ct)
    {
        var recent = ch.QueryAsync<CdcEvent>(
            "SELECT processed_at, source_table, operation, business_key, toInt64(end_to_end_ms) AS end_to_end_ms " +
            "FROM cdc_event_log ORDER BY processed_at DESC, kafka_offset DESC LIMIT 25", null, ct);
        var tables = ch.QueryAsync<CdcTableStat>(
            "SELECT source_table, toInt64(count()) AS events, round(avg(end_to_end_ms)) AS avg_latency_ms, " +
            "round(quantile(0.95)(end_to_end_ms)) AS p95_latency_ms FROM cdc_event_log " +
            "WHERE processed_at > now() - INTERVAL 1 DAY GROUP BY source_table ORDER BY events DESC", null, ct);
        var perMinute = ch.QueryAsync<LabelValue>(
            "SELECT formatDateTime(m, '%H:%i') AS label, CAST(NULL, 'Nullable(String)') AS label_fa, toFloat64(c) AS value, " +
            "toFloat64(a) AS extra FROM (" +
            "  SELECT toDateTime(toStartOfMinute(processed_at)) AS m, count() AS c, avg(end_to_end_ms) AS a " +
            "  FROM cdc_event_log WHERE processed_at > now() - INTERVAL 30 MINUTE GROUP BY m " +
            "  ORDER BY m WITH FILL FROM toStartOfMinute(now() - INTERVAL 29 MINUTE) TO toStartOfMinute(now()) + 60 STEP 60" +
            ") ORDER BY m", null, ct);
        var summary = ch.SingleAsync<CdcSummary>(
            "SELECT toInt64(count()) AS events, if(count() = 0, NULL, quantile(0.5)(end_to_end_ms)) AS median, " +
            "if(count() = 0, NULL, quantile(0.95)(end_to_end_ms)) AS p95 " +
            "FROM cdc_event_log WHERE processed_at > now() - INTERVAL 1 HOUR", null, ct);
        await Task.WhenAll(recent, tables, perMinute, summary);
        var s = summary.Result ?? new CdcSummary(0, null, null);
        return Results.Ok(new CdcMonitor(recent.Result, tables.Result, perMinute.Result, s.Events, s.Median, s.P95));
    }

    private sealed record CdcSummary(long Events, double? Median, double? P95);

    private sealed record RunRow(long BatchId, string Pipeline, DateTime RunStartedAt, DateTime RunFinishedAt,
                                 bool HasFailure, long TotalRowsWritten, string[] StepNames, string[] StepStatuses,
                                 long[] StepRows, long[] StepDurations);

    private static async Task<IResult> Pipeline(ClickHouseClient ch, IConfiguration config, CancellationToken ct)
    {
        var runs = ch.QueryAsync<RunRow>(
            "SELECT toInt64(batch_id) AS batch_id, pipeline, run_started_at, run_finished_at, " +
            "toBool(has_failure) AS has_failure, toInt64(total_rows_written) AS total_rows_written, " +
            "arrayMap(x -> tupleElement(x, 2), steps) AS step_names, " +
            "arrayMap(x -> tupleElement(x, 3), steps) AS step_statuses, " +
            "arrayMap(x -> toInt64(tupleElement(x, 4)), steps) AS step_rows, " +
            "arrayMap(x -> toInt64(tupleElement(x, 5)), steps) AS step_durations " +
            "FROM rpt_pipeline_runs ORDER BY run_started_at DESC LIMIT 12", null, ct);
        var quality = ch.QueryAsync<DqResult>(
            "SELECT toInt64(batch_id) AS batch_id, rule_name, table_name, severity, toInt64(failed_rows) AS failed_rows, " +
            "toBool(passed) AS passed, details FROM dq_result " +
            "WHERE batch_id = (SELECT max(batch_id) FROM dq_result) ORDER BY passed, severity, rule_name", null, ct);
        await Task.WhenAll(runs, quality);

        var mapped = runs.Result.Select(r => new PipelineRun(
            r.BatchId, r.Pipeline, r.RunStartedAt, r.RunFinishedAt, r.HasFailure, r.TotalRowsWritten,
            r.StepNames.Select((name, i) => new PipelineStep(name, r.StepStatuses[i], r.StepRows[i], r.StepDurations[i]))
                       .ToList())).ToList();
        var links = config.GetSection("Links").GetChildren().ToDictionary(c => c.Key, c => c.Value ?? "");
        return Results.Ok(new PipelineStatus(mapped, quality.Result, links));
    }

    private static DateTime? Real(DateTime? value) => value is { Year: > 1971 } ? value : null;
}
