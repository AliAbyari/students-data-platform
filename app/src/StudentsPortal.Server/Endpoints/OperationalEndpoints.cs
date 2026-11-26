using System.Security.Claims;
using Dapper;
using Microsoft.Data.SqlClient;
using StudentsPortal.Server.Infrastructure;
using StudentsPortal.Shared;

namespace StudentsPortal.Server.Endpoints;

public static class OperationalEndpoints
{
    private const int MaxPageSize = 100;

    private static readonly Dictionary<string, string> DepartmentFa = new()
    {
        ["BE"] = "مهندسی پزشکی", ["CE"] = "مهندسی عمران", ["CM"] = "مهندسی شیمی", ["EE"] = "مهندسی برق",
        ["ME"] = "مهندسی مکانیک", ["MG"] = "مدیریت مهندسی", ["CH"] = "شیمی", ["CS"] = "علوم کامپیوتر",
        ["MA"] = "ریاضی", ["PH"] = "فیزیک", ["LA"] = "علوم انسانی",
    };

    private sealed class OptionRow
    {
        public string Value { get; set; } = "";
        public string Label { get; set; } = "";
        public string? LabelFa { get; set; }
        public Option ToOption() => new(Value, Label, LabelFa);
    }

    public static void MapOperationalEndpoints(this IEndpointRouteBuilder app)
    {
        var api = app.MapGroup("/api").RequireAuthorization();
        var admin = new Action<Microsoft.AspNetCore.Authorization.AuthorizationPolicyBuilder>(p => p.RequireRole(Roles.Admin));

        api.MapGet("/lookups", GetLookups);

        api.MapGet("/students", ListStudents);
        api.MapGet("/students/{id:int}", async (int id, Database db) =>
        {
            using var conn = db.Students();
            var student = await conn.QuerySingleOrDefaultAsync<StudentDto>(StudentSelect + " WHERE s.StudentId = @id", new { id });
            return student is null ? Results.NotFound() : Results.Ok(student);
        });
        api.MapPost("/students", SaveStudent).RequireAuthorization(admin);
        api.MapPut("/students/{id:int}", SaveStudent).RequireAuthorization(admin);
        api.MapDelete("/students/{id:int}", (int id, Database db, AccountService accounts, ClaimsPrincipal user) =>
            Delete(db, accounts, user, "student", id,
                "SET XACT_ABORT ON; BEGIN TRANSACTION; DELETE FROM dbo.StudentProfiles WHERE StudentId = @id; " +
                "DELETE FROM dbo.Students WHERE StudentId = @id; COMMIT TRANSACTION;"))
           .RequireAuthorization(admin);

        api.MapGet("/applicants", ListApplicants);
        api.MapGet("/applicants/{id:int}", async (int id, Database db) =>
        {
            using var conn = db.Students();
            var applicant = await conn.QuerySingleOrDefaultAsync<ApplicantDto>(ApplicantSelect + " WHERE ApplicantId = @id",
                                                                               new { id });
            return applicant is null ? Results.NotFound() : Results.Ok(applicant);
        });
        api.MapPost("/applicants", SaveApplicant).RequireAuthorization(admin);
        api.MapPut("/applicants/{id:int}", SaveApplicant).RequireAuthorization(admin);
        api.MapDelete("/applicants/{id:int}", (int id, Database db, AccountService accounts, ClaimsPrincipal user) =>
            Delete(db, accounts, user, "applicant", id, "DELETE FROM dbo.Applicants WHERE ApplicantId = @id"))
           .RequireAuthorization(admin);

        api.MapGet("/offerings", ListOfferings);
        api.MapPost("/offerings", SaveOffering).RequireAuthorization(admin);
        api.MapPut("/offerings/{id:int}", SaveOffering).RequireAuthorization(admin);
        api.MapDelete("/offerings/{id:int}", (int id, Database db, AccountService accounts, ClaimsPrincipal user) =>
            Delete(db, accounts, user, "offering", id, "DELETE FROM dbo.CourseOfferings WHERE CourseOfferingId = @id"))
           .RequireAuthorization(admin);

        api.MapGet("/enrollments", ListEnrollments);
        api.MapPost("/enrollments", SaveEnrollment).RequireAuthorization(admin);
        api.MapPut("/enrollments/{id:int}", SaveEnrollment).RequireAuthorization(admin);
        api.MapDelete("/enrollments/{id:int}", (int id, Database db, AccountService accounts, ClaimsPrincipal user) =>
            Delete(db, accounts, user, "enrollment", id, "DELETE FROM dbo.CourseEnrollments WHERE CourseEnrollmentId = @id"))
           .RequireAuthorization(admin);
    }

    private static async Task<IResult> GetLookups(Database db)
    {
        using var conn = db.Students();
        using var grid = await conn.QueryMultipleAsync("""
            SELECT CAST(DegreeId AS varchar(10)) AS Value, DegreeName AS Label FROM dbo.Degrees ORDER BY DegreeName;
            SELECT TermCode AS Value,
                   CASE SessionCode WHEN 'FA' THEN 'Fall ' WHEN 'SP' THEN 'Spring ' ELSE 'Summer ' END + RIGHT(TermCode, 4) AS Label,
                   CASE SessionCode WHEN 'FA' THEN N'پاییز ' WHEN 'SP' THEN N'بهار ' ELSE N'تابستان ' END + RIGHT(TermCode, 4) AS LabelFa
            FROM dbo.Terms
            ORDER BY RIGHT(TermCode, 4) DESC, CASE SessionCode WHEN 'FA' THEN 3 WHEN 'SU' THEN 2 ELSE 1 END DESC;
            SELECT DepartmentCode AS Value, DepartmentName AS Label FROM dbo.Departments ORDER BY DepartmentName;
            SELECT ClassStandingCode AS Value, ClassStandingName AS Label FROM dbo.ClassStandings ORDER BY ClassStandingCode;
            SELECT Grade AS Value, Grade AS Label FROM dbo.Grades ORDER BY Grade;
            SELECT DepartmentCode + '|' + CAST(CourseNumber AS varchar(10)) AS Value,
                   DepartmentCode + '-' + CAST(CourseNumber AS varchar(10)) + '  ' + CourseTitle AS Label
            FROM dbo.Courses ORDER BY DepartmentCode, CourseNumber;
            """);
        var degrees = (await grid.ReadAsync<OptionRow>()).Select(o => o.ToOption()).ToList();
        var terms = (await grid.ReadAsync<OptionRow>()).Select(o => o.ToOption()).ToList();
        var departments = (await grid.ReadAsync<OptionRow>())
            .Select(o => new Option(o.Value, o.Label, DepartmentFa.GetValueOrDefault(o.Value))).ToList();
        var standings = (await grid.ReadAsync<OptionRow>()).Select(o => o.ToOption()).ToList();
        var grades = (await grid.ReadAsync<OptionRow>()).Select(o => o.ToOption()).ToList();
        var courses = (await grid.ReadAsync<OptionRow>()).Select(o => o.ToOption()).ToList();
        return Results.Ok(new Lookups(degrees, terms, departments, standings, grades, courses));
    }

    private const string StudentSelect = """
        SELECT s.StudentId, s.FirstName, s.MiddleName, s.LastName, s.Gender, s.DateOfBirth, s.email AS Email,
               s.Telephone, s.StreetAddress, s.City, s.State, s.ZipCode, s.DegreePursued, d.DegreeName,
               s.ClassStandingCode, s.StudentStatus, s.EnrollmentTerm
        FROM dbo.Students AS s
        LEFT JOIN dbo.Degrees AS d ON d.DegreeId = s.DegreePursued
        """;

    private static async Task<IResult> ListStudents(Database db, string? search, string? status, int? degree,
                                                    string? term, int page = 1, int pageSize = 20)
    {
        var (skip, take) = Paging(ref page, ref pageSize);
        const string where = """
             WHERE (@search IS NULL OR s.StudentId = @searchId OR s.LastName LIKE @like OR s.FirstName LIKE @like
                    OR s.email LIKE @like)
               AND (@status IS NULL OR s.StudentStatus = @status)
               AND (@degree IS NULL OR s.DegreePursued = @degree)
               AND (@term IS NULL OR s.EnrollmentTerm = @term)
            """;
        var args = SearchArgs(search, new { status = Validation.NullIfEmpty(status), degree, term = Validation.NullIfEmpty(term), skip, take });
        using var conn = db.Students();
        using var grid = await conn.QueryMultipleAsync(
            $"{StudentSelect} {where} ORDER BY s.StudentId DESC OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY; " +
            $"SELECT COUNT(*) FROM dbo.Students AS s {where};", args);
        var items = (await grid.ReadAsync<StudentDto>()).ToList();
        var total = await grid.ReadSingleAsync<int>();
        return Results.Ok(new PagedResult<StudentDto>(items, total, page, pageSize));
    }

    private static async Task<IResult> SaveStudent(int? id, StudentDto s, Database db, AccountService accounts,
                                                   ClaimsPrincipal user)
    {
        Normalize(s);
        var errors = Validation.Student(s);
        if (errors.Count > 0) return Validation.Problem(errors);
        var args = new { s.FirstName, s.MiddleName, s.LastName, s.Gender, s.DateOfBirth, s.Email, s.Telephone,
                         s.StreetAddress, s.City, s.State, s.ZipCode, s.DegreePursued,
                         ClassStandingCode = Validation.NullIfEmpty(s.ClassStandingCode), s.StudentStatus,
                         s.EnrollmentTerm, id };
        return await Execute(accounts, user, "student", id, async () =>
        {
            using var conn = db.Students();
            if (id is null)
            {
                return await conn.ExecuteScalarAsync<int>("""
                    INSERT INTO dbo.Students (FirstName, MiddleName, LastName, Gender, StreetAddress, City, State, ZipCode,
                                              Telephone, email, DateOfBirth, DegreePursued, ClassStandingCode,
                                              StudentStatus, EnrollmentTerm)
                    OUTPUT INSERTED.StudentId
                    VALUES (@FirstName, @MiddleName, @LastName, @Gender, @StreetAddress, @City, @State, @ZipCode,
                            @Telephone, @Email, @DateOfBirth, @DegreePursued, @ClassStandingCode, @StudentStatus,
                            @EnrollmentTerm)
                    """, args);
            }
            var affected = await conn.ExecuteAsync("""
                UPDATE dbo.Students SET FirstName = @FirstName, MiddleName = @MiddleName, LastName = @LastName,
                       Gender = @Gender, StreetAddress = @StreetAddress, City = @City, State = @State, ZipCode = @ZipCode,
                       Telephone = @Telephone, email = @Email, DateOfBirth = @DateOfBirth, DegreePursued = @DegreePursued,
                       ClassStandingCode = @ClassStandingCode, StudentStatus = @StudentStatus,
                       EnrollmentTerm = @EnrollmentTerm
                WHERE StudentId = @id
                """, args);
            return affected == 0 ? null : id;
        });
    }

    private const string ApplicantSelect = """
        SELECT ApplicantId, FirstName, MiddleName, LastName, Gender, DateOfBirth, Email, Telephone, StreetAddress, City,
               State, ZipCode, ApplicationReceivedDate, EntryTerm, ApplicationType, Gpa, SatMathScore, SatReadingScore,
               SatWritingScore, EssayScore, ApplicationStatus, AdmissionPoints
        FROM dbo.Applicants
        """;

    private static async Task<IResult> ListApplicants(Database db, string? search, string? status, string? term,
                                                      int page = 1, int pageSize = 20)
    {
        var (skip, take) = Paging(ref page, ref pageSize);
        const string where = """
             WHERE (@search IS NULL OR ApplicantId = @searchId OR LastName LIKE @like OR FirstName LIKE @like
                    OR Email LIKE @like)
               AND (@status IS NULL OR ApplicationStatus = @status)
               AND (@term IS NULL OR EntryTerm = @term)
            """;
        var args = SearchArgs(search, new { status = Validation.NullIfEmpty(status), term = Validation.NullIfEmpty(term), skip, take });
        using var conn = db.Students();
        using var grid = await conn.QueryMultipleAsync(
            $"{ApplicantSelect} {where} ORDER BY ApplicantId DESC OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY; " +
            $"SELECT COUNT(*) FROM dbo.Applicants {where};", args);
        var items = (await grid.ReadAsync<ApplicantDto>()).ToList();
        var total = await grid.ReadSingleAsync<int>();
        return Results.Ok(new PagedResult<ApplicantDto>(items, total, page, pageSize));
    }

    private static async Task<IResult> SaveApplicant(int? id, ApplicantDto a, Database db, AccountService accounts,
                                                     ClaimsPrincipal user)
    {
        a.FirstName = a.FirstName.Trim(); a.LastName = a.LastName.Trim(); a.MiddleName = a.MiddleName?.Trim() ?? "";
        a.Email = a.Email.Trim(); a.State = a.State.Trim().ToUpperInvariant();
        var errors = Validation.Applicant(a);
        if (errors.Count > 0) return Validation.Problem(errors);
        var args = new { a.FirstName, a.MiddleName, a.LastName, a.Gender, a.StreetAddress, a.City, a.State, a.ZipCode,
                         a.Telephone, a.Email, a.DateOfBirth, a.ApplicationReceivedDate, a.EntryTerm, a.ApplicationType,
                         a.Gpa, a.SatMathScore, a.SatReadingScore, a.SatWritingScore, a.EssayScore,
                         a.ApplicationStatus, a.AdmissionPoints, id };
        return await Execute(accounts, user, "applicant", id, async () =>
        {
            using var conn = db.Students();
            if (id is null)
            {
                return await conn.ExecuteScalarAsync<int>("""
                    INSERT INTO dbo.Applicants (FirstName, MiddleName, LastName, Gender, StreetAddress, City, State, ZipCode,
                           Telephone, Email, DateOfBirth, ApplicationReceivedDate, EntryTerm, ApplicationType, Gpa,
                           SatMathScore, SatReadingScore, SatWritingScore, EssayScore, ApplicationStatus, AdmissionPoints)
                    OUTPUT INSERTED.ApplicantId
                    VALUES (@FirstName, @MiddleName, @LastName, @Gender, @StreetAddress, @City, @State, @ZipCode,
                           @Telephone, @Email, @DateOfBirth, @ApplicationReceivedDate, @EntryTerm, @ApplicationType, @Gpa,
                           @SatMathScore, @SatReadingScore, @SatWritingScore, @EssayScore, @ApplicationStatus,
                           @AdmissionPoints)
                    """, args);
            }
            var affected = await conn.ExecuteAsync("""
                UPDATE dbo.Applicants SET FirstName = @FirstName, MiddleName = @MiddleName, LastName = @LastName,
                       Gender = @Gender, StreetAddress = @StreetAddress, City = @City, State = @State, ZipCode = @ZipCode,
                       Telephone = @Telephone, Email = @Email, DateOfBirth = @DateOfBirth,
                       ApplicationReceivedDate = @ApplicationReceivedDate, EntryTerm = @EntryTerm,
                       ApplicationType = @ApplicationType, Gpa = @Gpa, SatMathScore = @SatMathScore,
                       SatReadingScore = @SatReadingScore, SatWritingScore = @SatWritingScore, EssayScore = @EssayScore,
                       ApplicationStatus = @ApplicationStatus, AdmissionPoints = @AdmissionPoints
                WHERE ApplicantId = @id
                """, args);
            return affected == 0 ? null : id;
        });
    }

    private static async Task<IResult> ListOfferings(Database db, ClickHouseClient warehouse, string? search,
                                                     string? term, string? department, int page = 1, int pageSize = 20)
    {
        var (skip, take) = Paging(ref page, ref pageSize);
        const string where = """
             WHERE (@search IS NULL OR o.CourseOfferingId = @searchId OR CAST(o.CourseNumber AS varchar(10)) = @search
                    OR c.CourseTitle LIKE '%' + @search + '%')
               AND (@term IS NULL OR o.TermCode = @term)
               AND (@department IS NULL OR o.DepartmentCode = @department)
            """;
        var args = SearchArgs(search, new { term = Validation.NullIfEmpty(term), department = Validation.NullIfEmpty(department), skip, take });
        using var conn = db.Students();
        using var grid = await conn.QueryMultipleAsync($"""
            SELECT o.CourseOfferingId, o.DepartmentCode, o.CourseNumber, c.CourseTitle, o.TermCode, o.Section, o.Capacity
            FROM dbo.CourseOfferings AS o
            LEFT JOIN dbo.Courses AS c ON c.DepartmentCode = o.DepartmentCode AND c.CourseNumber = o.CourseNumber
            {where}
            ORDER BY o.CourseOfferingId DESC OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
            SELECT COUNT(*) FROM dbo.CourseOfferings AS o
            LEFT JOIN dbo.Courses AS c ON c.DepartmentCode = o.DepartmentCode AND c.CourseNumber = o.CourseNumber
            {where};
            """, args);
        var items = (await grid.ReadAsync<CourseOfferingDto>()).ToList();
        var total = await grid.ReadSingleAsync<int>();

        if (items.Count > 0)
        {
            try
            {
                var ids = "[" + string.Join(",", items.Select(i => i.CourseOfferingId)) + "]";
                var fill = await warehouse.QueryAsync<OfferingFill>(
                    "SELECT course_offering_id, toInt64(enrolled) AS enrolled FROM rpt_course_offering_fill " +
                    "WHERE course_offering_id IN {ids:Array(Int32)}",
                    new Dictionary<string, object?> { ["ids"] = ids });
                var lookup = fill.ToDictionary(f => f.CourseOfferingId, f => f.Enrolled);
                foreach (var item in items) item.Enrolled = (int)lookup.GetValueOrDefault(item.CourseOfferingId);
            }
            catch (Exception)
            {
            }
        }
        return Results.Ok(new PagedResult<CourseOfferingDto>(items, total, page, pageSize));
    }

    private sealed record OfferingFill(int CourseOfferingId, long Enrolled);

    private static async Task<IResult> SaveOffering(int? id, CourseOfferingDto o, Database db, AccountService accounts,
                                                    ClaimsPrincipal user)
    {
        var errors = Validation.Offering(o);
        if (errors.Count > 0) return Validation.Problem(errors);
        var args = new { o.DepartmentCode, o.CourseNumber, o.TermCode, o.Section, o.Capacity, id };
        return await Execute(accounts, user, "offering", id, async () =>
        {
            using var conn = db.Students();
            if (id is null)
            {
                return await conn.ExecuteScalarAsync<int>("""
                    INSERT INTO dbo.CourseOfferings (DepartmentCode, CourseNumber, TermCode, Section, Capacity)
                    OUTPUT INSERTED.CourseOfferingId
                    VALUES (@DepartmentCode, @CourseNumber, @TermCode, @Section, @Capacity)
                    """, args);
            }
            var affected = await conn.ExecuteAsync("""
                UPDATE dbo.CourseOfferings SET DepartmentCode = @DepartmentCode, CourseNumber = @CourseNumber,
                       TermCode = @TermCode, Section = @Section, Capacity = @Capacity
                WHERE CourseOfferingId = @id
                """, args);
            return affected == 0 ? null : id;
        });
    }

    private static async Task<IResult> ListEnrollments(Database db, int? studentId, int? offeringId, int page = 1,
                                                       int pageSize = 20)
    {
        var (skip, take) = Paging(ref page, ref pageSize);
        const string where = " WHERE (@studentId IS NULL OR e.StudentId = @studentId) " +
                             "AND (@offeringId IS NULL OR e.CourseOfferingId = @offeringId)";
        using var conn = db.Students();
        using var grid = await conn.QueryMultipleAsync($"""
            SELECT e.CourseEnrollmentId, e.CourseOfferingId, e.StudentId,
                   s.FirstName + ' ' + s.LastName AS StudentName,
                   o.DepartmentCode + '-' + CAST(o.CourseNumber AS varchar(10)) AS CourseCode, c.CourseTitle,
                   o.TermCode, o.Section, e.Grade
            FROM dbo.CourseEnrollments AS e
            LEFT JOIN dbo.Students AS s ON s.StudentId = e.StudentId
            LEFT JOIN dbo.CourseOfferings AS o ON o.CourseOfferingId = e.CourseOfferingId
            LEFT JOIN dbo.Courses AS c ON c.DepartmentCode = o.DepartmentCode AND c.CourseNumber = o.CourseNumber
            {where}
            ORDER BY e.CourseEnrollmentId DESC OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
            SELECT COUNT(*) FROM dbo.CourseEnrollments AS e {where};
            """, new { studentId, offeringId, skip, take });
        var items = (await grid.ReadAsync<EnrollmentDto>()).ToList();
        var total = await grid.ReadSingleAsync<int>();
        return Results.Ok(new PagedResult<EnrollmentDto>(items, total, page, pageSize));
    }

    private static async Task<IResult> SaveEnrollment(int? id, EnrollmentDto e, Database db, AccountService accounts,
                                                      ClaimsPrincipal user)
    {
        var errors = new Dictionary<string, string>();
        if (e.StudentId <= 0) errors["studentId"] = "required";
        if (e.CourseOfferingId <= 0) errors["courseOfferingId"] = "required";
        var grade = Validation.NullIfEmpty(e.Grade);
        if (grade is not null && grade is not ("A" or "B" or "C" or "D" or "F" or "W")) errors["grade"] = "invalid";
        if (errors.Count > 0) return Validation.Problem(errors);
        var args = new { e.StudentId, e.CourseOfferingId, grade, id };
        return await Execute(accounts, user, "enrollment", id, async () =>
        {
            using var conn = db.Students();
            if (id is null)
            {
                return await conn.ExecuteScalarAsync<int>("""
                    INSERT INTO dbo.CourseEnrollments (CourseOfferingId, StudentId, Grade)
                    OUTPUT INSERTED.CourseEnrollmentId VALUES (@CourseOfferingId, @StudentId, @grade)
                    """, args);
            }
            var affected = await conn.ExecuteAsync("""
                UPDATE dbo.CourseEnrollments SET CourseOfferingId = @CourseOfferingId, StudentId = @StudentId,
                       Grade = @grade
                WHERE CourseEnrollmentId = @id
                """, args);
            return affected == 0 ? null : id;
        });
    }

    private static (int Skip, int Take) Paging(ref int page, ref int pageSize)
    {
        page = Math.Max(1, page);
        pageSize = Math.Clamp(pageSize, 1, MaxPageSize);
        return ((page - 1) * pageSize, pageSize);
    }

    private static DynamicParameters SearchArgs(string? search, object extra)
    {
        var term = Validation.NullIfEmpty(search);
        var args = new DynamicParameters(extra);
        args.Add("search", term);
        args.Add("searchId", int.TryParse(term, out var id) ? id : -1);
        args.Add("like", term is null ? null : term.Replace("[", "[[]").Replace("%", "[%]").Replace("_", "[_]") + "%");
        return args;
    }

    private static void Normalize(StudentDto s)
    {
        s.FirstName = s.FirstName.Trim();
        s.MiddleName = s.MiddleName?.Trim() ?? "";
        s.LastName = s.LastName.Trim();
        s.Email = s.Email.Trim();
        s.State = s.State.Trim().ToUpperInvariant();
    }

    private static async Task<IResult> Execute(AccountService accounts, ClaimsPrincipal user, string entity, int? id,
                                               Func<Task<int?>> action)
    {
        try
        {
            var key = await action();
            if (key is null) return Results.NotFound();
            await accounts.LogActivityAsync(user.UserId(), id is null ? "insert" : "update", entity, key.ToString());
            return Results.Ok(new { id = key });
        }
        catch (SqlException ex) when (ex.Is(SqlErrors.ForeignKeyViolation) && ex.Message.Contains("FOREIGN KEY"))
        {
            return Validation.Conflict("reference_missing", "A referenced record does not exist.");
        }
        catch (SqlException ex) when (ex.Is(SqlErrors.UniqueViolation, SqlErrors.UniqueIndexViolation))
        {
            return Validation.Conflict("duplicate", "A record with the same key already exists.");
        }
        catch (SqlException ex) when (ex.Class == 16)
        {
            return Validation.Conflict("constraint", ex.Message);
        }
    }

    private static async Task<IResult> Delete(Database db, AccountService accounts, ClaimsPrincipal user, string entity,
                                              int id, string sql)
    {
        try
        {
            using var conn = db.Students();
            var affected = await conn.ExecuteAsync(sql, new { id });
            if (affected == 0) return Results.NotFound();
            await accounts.LogActivityAsync(user.UserId(), "delete", entity, id.ToString());
            return Results.NoContent();
        }
        catch (SqlException ex) when (ex.Is(SqlErrors.ForeignKeyViolation))
        {
            return Validation.Conflict("has_dependents", "The record is referenced by other records.");
        }
    }
}
