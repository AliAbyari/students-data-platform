using System.Data;
using Microsoft.Data.SqlClient;

namespace StudentsPortal.Server.Infrastructure;

public sealed class Database(IConfiguration configuration)
{
    private readonly string students = configuration.GetConnectionString("Students")
        ?? throw new InvalidOperationException("ConnectionStrings:Students is not configured.");
    private readonly string portal = configuration.GetConnectionString("Portal")
        ?? throw new InvalidOperationException("ConnectionStrings:Portal is not configured.");

    public IDbConnection Students() => new SqlConnection(students);

    public IDbConnection Portal() => new SqlConnection(portal);
}

public static class SqlErrors
{
    public const int ForeignKeyViolation = 547;
    public const int UniqueViolation = 2627;
    public const int UniqueIndexViolation = 2601;

    public static bool Is(this SqlException exception, params int[] numbers)
        => exception.Errors.Cast<SqlError>().Any(e => numbers.Contains(e.Number));
}
