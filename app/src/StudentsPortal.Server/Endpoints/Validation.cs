using System.Text.RegularExpressions;
using StudentsPortal.Shared;

namespace StudentsPortal.Server.Endpoints;

public static partial class Validation
{
    public static IResult Problem(Dictionary<string, string> errors)
        => Results.Json(new ApiError("validation", "One or more fields are invalid.", errors),
                        statusCode: StatusCodes.Status400BadRequest);

    public static IResult Conflict(string code, string message)
        => Results.Json(new ApiError(code, message), statusCode: StatusCodes.Status409Conflict);

    public static string? NullIfEmpty(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    public static bool IsStrongPassword(string? password) => password is { Length: >= 10 and <= 128 };

    public static Dictionary<string, string> Profile(UpdateProfileRequest r)
    {
        var e = new Dictionary<string, string>();
        Required(e, "firstName", r.FirstName, 64);
        Required(e, "lastName", r.LastName, 64);
        Email(e, "email", r.Email, optional: true);
        if (r.PreferredLanguage is not ("fa" or "en")) e["preferredLanguage"] = "invalid";
        if (r.PreferredTheme is not ("dark" or "light")) e["preferredTheme"] = "invalid";
        return e;
    }

    public static Dictionary<string, string> User(SaveUserRequest r, bool requirePassword)
    {
        var e = new Dictionary<string, string>();
        Required(e, "username", r.Username, 64);
        Required(e, "firstName", r.FirstName, 64);
        Required(e, "lastName", r.LastName, 64);
        Email(e, "email", r.Email, optional: true);
        if (r.Role is not (Roles.Admin or Roles.User)) e["role"] = "invalid";
        if (requirePassword && !IsStrongPassword(r.Password)) e["password"] = "weak_password";
        return e;
    }

    public static Dictionary<string, string> Person(string firstName, string middleName, string lastName, string gender,
        DateTime? dateOfBirth, string email, string telephone, string street, string city, string state, string zip)
    {
        var e = new Dictionary<string, string>();
        Required(e, "firstName", firstName, 40);
        Optional(e, "middleName", middleName, 40);
        Required(e, "lastName", lastName, 40);
        if (gender is not ("M" or "F")) e["gender"] = "invalid";
        if (dateOfBirth is null) e["dateOfBirth"] = "required";
        else if (dateOfBirth > DateTime.Today.AddYears(-14) || dateOfBirth < new DateTime(1900, 1, 1))
            e["dateOfBirth"] = "out_of_range";
        Email(e, "email", email, optional: false);
        Required(e, "telephone", telephone, 20);
        Required(e, "streetAddress", street, 50);
        Required(e, "city", city, 30);
        if (string.IsNullOrWhiteSpace(state) || !StateCode().IsMatch(state)) e["state"] = "invalid";
        if (string.IsNullOrWhiteSpace(zip) || !ZipCode().IsMatch(zip)) e["zipCode"] = "invalid";
        return e;
    }

    public static Dictionary<string, string> Student(StudentDto s)
    {
        var e = Person(s.FirstName, s.MiddleName, s.LastName, s.Gender, s.DateOfBirth, s.Email, s.Telephone,
                       s.StreetAddress, s.City, s.State, s.ZipCode);
        if (s.DegreePursued is null) e["degreePursued"] = "required";
        if (s.StudentStatus is not ("A" or "G" or "W")) e["studentStatus"] = "invalid";
        if (string.IsNullOrWhiteSpace(s.EnrollmentTerm)) e["enrollmentTerm"] = "required";
        return e;
    }

    public static Dictionary<string, string> Applicant(ApplicantDto a)
    {
        var e = Person(a.FirstName, a.MiddleName, a.LastName, a.Gender, a.DateOfBirth, a.Email, a.Telephone,
                       a.StreetAddress, a.City, a.State, a.ZipCode);
        if (a.ApplicationReceivedDate is null) e["applicationReceivedDate"] = "required";
        if (string.IsNullOrWhiteSpace(a.EntryTerm)) e["entryTerm"] = "required";
        if (a.ApplicationType is not ("U" or "G" or "T" or "I")) e["applicationType"] = "invalid";
        if (a.ApplicationStatus is not ("A" or "D" or "N")) e["applicationStatus"] = "invalid";
        if (a.Gpa is < 0 or > 4) e["gpa"] = "out_of_range";
        foreach (var (field, score) in new[] { ("satMathScore", a.SatMathScore), ("satReadingScore", a.SatReadingScore),
                                               ("satWritingScore", a.SatWritingScore) })
            if (score is < 200 or > 800) e[field] = "out_of_range";
        return e;
    }

    public static Dictionary<string, string> Offering(CourseOfferingDto o)
    {
        var e = new Dictionary<string, string>();
        if (string.IsNullOrWhiteSpace(o.DepartmentCode)) e["departmentCode"] = "required";
        if (o.CourseNumber is < 9 or > 1000) e["courseNumber"] = "out_of_range";
        if (string.IsNullOrWhiteSpace(o.TermCode)) e["termCode"] = "required";
        if (o.Section is < 1 or > 99) e["section"] = "out_of_range";
        if (o.Capacity is <= 0 or >= 1000) e["capacity"] = "out_of_range";
        return e;
    }

    private static void Required(Dictionary<string, string> e, string field, string? value, int max)
    {
        if (string.IsNullOrWhiteSpace(value)) e[field] = "required";
        else if (value.Trim().Length > max) e[field] = "too_long";
    }

    private static void Optional(Dictionary<string, string> e, string field, string? value, int max)
    {
        if (value is not null && value.Trim().Length > max) e[field] = "too_long";
    }

    private static void Email(Dictionary<string, string> e, string field, string? value, bool optional)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            if (!optional) e[field] = "required";
        }
        else if (value.Length > 80 || !EmailPattern().IsMatch(value)) e[field] = "invalid";
    }

    [GeneratedRegex(@"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    private static partial Regex EmailPattern();

    [GeneratedRegex("^[A-Z]{2}$")]
    private static partial Regex StateCode();

    [GeneratedRegex(@"^\d{5}$")]
    private static partial Regex ZipCode();
}
