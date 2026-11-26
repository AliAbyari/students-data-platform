namespace StudentsPortal.Shared;

public sealed record PagedResult<T>(IReadOnlyList<T> Items, int Total, int Page, int PageSize)
{
    public int Pages => PageSize <= 0 ? 0 : (int)Math.Ceiling(Total / (double)PageSize);
}

public sealed record ApiError(string Code, string Message, IReadOnlyDictionary<string, string>? Fields = null);

public sealed record SavedId(int Id);

public sealed record Option(string Value, string Label, string? LabelFa = null);

public sealed record Lookups(
    IReadOnlyList<Option> Degrees,
    IReadOnlyList<Option> Terms,
    IReadOnlyList<Option> Departments,
    IReadOnlyList<Option> ClassStandings,
    IReadOnlyList<Option> Grades,
    IReadOnlyList<Option> Courses);

public static class Roles
{
    public const string Admin = "Admin";
    public const string User = "User";
}

public sealed record LoginRequest(string Username, string Password);

public sealed record LoginResponse(string Token, DateTimeOffset ExpiresAt, UserProfile User);

public sealed record UserProfile(
    int UserId, string Username, string FirstName, string LastName, string? Email, string Role,
    string PreferredLanguage, string PreferredTheme, DateTime CreatedAt, DateTime? LastLoginAt);

public sealed record UpdateProfileRequest(
    string FirstName, string LastName, string? Email, string PreferredLanguage, string PreferredTheme);

public sealed record ChangePasswordRequest(string CurrentPassword, string NewPassword);

public sealed record UserSummary(
    int UserId, string Username, string FirstName, string LastName, string? Email, string Role, bool IsActive,
    DateTime CreatedAt, DateTime? LastLoginAt);

public sealed record SaveUserRequest(
    string Username, string FirstName, string LastName, string? Email, string Role, bool IsActive, string? Password);

public sealed class StudentDto
{
    public int StudentId { get; set; }
    public string FirstName { get; set; } = "";
    public string MiddleName { get; set; } = "";
    public string LastName { get; set; } = "";
    public string Gender { get; set; } = "F";
    public DateTime? DateOfBirth { get; set; }
    public string Email { get; set; } = "";
    public string Telephone { get; set; } = "";
    public string StreetAddress { get; set; } = "";
    public string City { get; set; } = "";
    public string State { get; set; } = "";
    public string ZipCode { get; set; } = "";
    public int? DegreePursued { get; set; }
    public string? DegreeName { get; set; }
    public string? ClassStandingCode { get; set; }
    public string StudentStatus { get; set; } = "A";
    public string EnrollmentTerm { get; set; } = "";
}

public sealed class ApplicantDto
{
    public int ApplicantId { get; set; }
    public string FirstName { get; set; } = "";
    public string MiddleName { get; set; } = "";
    public string LastName { get; set; } = "";
    public string Gender { get; set; } = "F";
    public DateTime? DateOfBirth { get; set; }
    public string Email { get; set; } = "";
    public string Telephone { get; set; } = "";
    public string StreetAddress { get; set; } = "";
    public string City { get; set; } = "";
    public string State { get; set; } = "";
    public string ZipCode { get; set; } = "";
    public DateTime? ApplicationReceivedDate { get; set; }
    public string EntryTerm { get; set; } = "";
    public string ApplicationType { get; set; } = "U";
    public decimal? Gpa { get; set; }
    public int? SatMathScore { get; set; }
    public int? SatReadingScore { get; set; }
    public int? SatWritingScore { get; set; }
    public int? EssayScore { get; set; }
    public string ApplicationStatus { get; set; } = "N";
    public double? AdmissionPoints { get; set; }
}

public sealed class CourseOfferingDto
{
    public int CourseOfferingId { get; set; }
    public string DepartmentCode { get; set; } = "";
    public int CourseNumber { get; set; }
    public string? CourseTitle { get; set; }
    public string TermCode { get; set; } = "";
    public int Section { get; set; } = 1;
    public int Capacity { get; set; } = 30;
    public int Enrolled { get; set; }
}

public sealed class EnrollmentDto
{
    public int CourseEnrollmentId { get; set; }
    public int CourseOfferingId { get; set; }
    public int StudentId { get; set; }
    public string? StudentName { get; set; }
    public string? CourseCode { get; set; }
    public string? CourseTitle { get; set; }
    public string? TermCode { get; set; }
    public int? Section { get; set; }
    public string? Grade { get; set; }
}

public sealed record Kpis(long Total, long Active, long Graduated, long Withdrawn);

public sealed record LabelValue(string Label, string? LabelFa, double Value, double? Extra = null);

public sealed record Freshness(DateTime? LastBatchAt, long? LastBatchId, DateTime? LastCdcAt, long CdcEventsToday);

public sealed record Overview(
    Kpis Kpis,
    IReadOnlyList<LabelValue> CohortSizes,
    IReadOnlyList<LabelValue> TopDegrees,
    IReadOnlyList<LabelValue> EnrollmentByTerm,
    IReadOnlyList<LabelValue> GpaByDepartment,
    IReadOnlyList<LabelValue> GradeDistribution,
    IReadOnlyList<LabelValue> FillRateByDepartment,
    IReadOnlyList<LabelValue> AdmissionsByYear,
    IReadOnlyList<RecentStudent> RecentStudents,
    Freshness Freshness);

public sealed record RecentStudent(int StudentId, string FullName, string DegreeName, string StudentStatusCode,
                                   string ChangeSource);

public sealed record StudentVersion(
    long StudentKey, string FullName, string Email, string City, string StateCode, string DegreeName,
    string ClassStandingName, string StudentStatusCode, string StudentStatusName, string StudentStatusNameFa,
    DateTime ValidFrom, DateTime ValidTo, int IsCurrent, int IsDeleted, string ChangeReason, string ChangeSource,
    long BatchId);

public sealed record TermSummary(string TermCode, string TermName, string TermNameFa, long Courses, double Credits,
                                 double? Gpa);

public sealed record StudentInsight(
    int StudentId, IReadOnlyList<StudentVersion> Versions, IReadOnlyList<TermSummary> Terms, long Enrollments,
    double CreditsEarned, double? CumulativeGpa);

public sealed record CdcEvent(DateTime ProcessedAt, string SourceTable, string Operation, string BusinessKey,
                              long EndToEndMs);

public sealed record CdcTableStat(string SourceTable, long Events, double AvgLatencyMs, double P95LatencyMs);

public sealed record CdcMonitor(
    IReadOnlyList<CdcEvent> Recent, IReadOnlyList<CdcTableStat> Tables, IReadOnlyList<LabelValue> PerMinute,
    long EventsLastHour, double? MedianLatencyMs, double? P95LatencyMs);

public sealed record PipelineStep(string Step, string Status, long RowsWritten, long DurationMs);

public sealed record PipelineRun(long BatchId, string Pipeline, DateTime StartedAt, DateTime FinishedAt, bool HasFailure,
                                 long RowsWritten, IReadOnlyList<PipelineStep> Steps);

public sealed record DqResult(long BatchId, string RuleName, string TableName, string Severity, long FailedRows,
                              bool Passed, string Details);

public sealed record PipelineStatus(IReadOnlyList<PipelineRun> Runs, IReadOnlyList<DqResult> Quality,
                                    IReadOnlyDictionary<string, string> Links);
