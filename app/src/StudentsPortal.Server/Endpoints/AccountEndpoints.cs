using System.Security.Claims;
using Dapper;
using StudentsPortal.Server.Infrastructure;
using StudentsPortal.Shared;

namespace StudentsPortal.Server.Endpoints;

public static class AccountEndpoints
{
    public static void MapAccountEndpoints(this IEndpointRouteBuilder app)
    {
        var auth = app.MapGroup("/api/auth");

        auth.MapPost("/login", async (LoginRequest request, AccountService accounts) =>
        {
            var user = await accounts.FindByUsernameAsync(request.Username.Trim());
            if (user is null || !user.IsActive || !accounts.VerifyPassword(user, request.Password))
            {
                return Results.Json(new ApiError("invalid_credentials", "Invalid username or password."),
                                    statusCode: StatusCodes.Status401Unauthorized);
            }
            var response = await accounts.SignInAsync(user);
            await accounts.LogActivityAsync(user.UserId, "login", "session", null);
            return Results.Ok(response);
        }).AllowAnonymous().RequireRateLimiting("login");

        auth.MapPost("/logout", async (ClaimsPrincipal principal, AccountService accounts) =>
        {
            await accounts.RevokeSessionsAsync(principal.UserId());
            return Results.NoContent();
        }).RequireAuthorization();

        auth.MapGet("/me", async (ClaimsPrincipal principal, AccountService accounts) =>
            await accounts.FindAsync(principal.UserId()) is { } user ? Results.Ok(user.ToProfile()) : Results.Unauthorized())
            .RequireAuthorization();

        var profile = app.MapGroup("/api/profile").RequireAuthorization();

        profile.MapPut("/", async (UpdateProfileRequest request, ClaimsPrincipal principal, Database db,
                                   AccountService accounts) =>
        {
            var errors = Validation.Profile(request);
            if (errors.Count > 0) return Validation.Problem(errors);
            using var conn = db.Portal();
            await conn.ExecuteAsync(
                "UPDATE app.Users SET FirstName = @FirstName, LastName = @LastName, Email = @Email, " +
                "PreferredLanguage = @PreferredLanguage, PreferredTheme = @PreferredTheme WHERE UserId = @id",
                new { request.FirstName, request.LastName, Email = Validation.NullIfEmpty(request.Email),
                      request.PreferredLanguage, request.PreferredTheme, id = principal.UserId() });
            return Results.Ok((await accounts.FindAsync(principal.UserId()))!.ToProfile());
        });

        profile.MapPut("/password", async (ChangePasswordRequest request, ClaimsPrincipal principal, Database db,
                                           AccountService accounts) =>
        {
            var user = await accounts.FindAsync(principal.UserId());
            if (user is null) return Results.Unauthorized();
            if (!accounts.VerifyPassword(user, request.CurrentPassword))
                return Validation.Problem(new() { ["currentPassword"] = "wrong_password" });
            if (!Validation.IsStrongPassword(request.NewPassword))
                return Validation.Problem(new() { ["newPassword"] = "weak_password" });
            using (var conn = db.Portal())
            {
                await conn.ExecuteAsync("UPDATE app.Users SET PasswordHash = @hash WHERE UserId = @id",
                    new { hash = accounts.HashPassword(user, request.NewPassword), id = user.UserId });
            }
            return Results.Ok(await accounts.SignInAsync(user));
        });

        var users = app.MapGroup("/api/users").RequireAuthorization(policy => policy.RequireRole(Roles.Admin));

        users.MapGet("/", async (AccountService accounts) =>
            Results.Ok((await accounts.ListAsync()).Select(u => u.ToSummary())));

        users.MapPost("/", async (SaveUserRequest request, Database db, AccountService accounts,
                                  ClaimsPrincipal principal) =>
        {
            var errors = Validation.User(request, requirePassword: true);
            if (errors.Count > 0) return Validation.Problem(errors);
            if (await accounts.FindByUsernameAsync(request.Username.Trim()) is not null)
                return Validation.Problem(new() { ["username"] = "duplicate" });
            var user = new UserRecord { Username = request.Username.Trim() };
            using var conn = db.Portal();
            var id = await conn.ExecuteScalarAsync<int>(
                "INSERT INTO app.Users (Username, PasswordHash, FirstName, LastName, Email, [Role], IsActive) " +
                "OUTPUT INSERTED.UserId VALUES (@Username, @hash, @FirstName, @LastName, @Email, @Role, @IsActive)",
                new { Username = user.Username, hash = accounts.HashPassword(user, request.Password!), request.FirstName,
                      request.LastName, Email = Validation.NullIfEmpty(request.Email), request.Role, request.IsActive });
            await accounts.LogActivityAsync(principal.UserId(), "insert", "user", id.ToString());
            return Results.Ok((await accounts.FindAsync(id))!.ToSummary());
        });

        users.MapPut("/{id:int}", async (int id, SaveUserRequest request, Database db, AccountService accounts,
                                         ClaimsPrincipal principal) =>
        {
            var errors = Validation.User(request, requirePassword: false);
            if (errors.Count > 0) return Validation.Problem(errors);
            var user = await accounts.FindAsync(id);
            if (user is null) return Results.NotFound();
            if (id == principal.UserId() && (!request.IsActive || request.Role != Roles.Admin))
                return Validation.Problem(new() { ["role"] = "cannot_demote_self" });
            using var conn = db.Portal();
            await conn.ExecuteAsync(
                "UPDATE app.Users SET FirstName = @FirstName, LastName = @LastName, Email = @Email, [Role] = @Role, " +
                "IsActive = @IsActive WHERE UserId = @id",
                new { request.FirstName, request.LastName, Email = Validation.NullIfEmpty(request.Email), request.Role,
                      request.IsActive, id });
            if (!string.IsNullOrEmpty(request.Password))
            {
                if (!Validation.IsStrongPassword(request.Password))
                    return Validation.Problem(new() { ["password"] = "weak_password" });
                await conn.ExecuteAsync("UPDATE app.Users SET PasswordHash = @hash WHERE UserId = @id",
                    new { hash = accounts.HashPassword(user, request.Password), id });
            }
            if (!request.IsActive || !string.IsNullOrEmpty(request.Password) || request.Role != user.Role)
                await accounts.RevokeSessionsAsync(id);
            await accounts.LogActivityAsync(principal.UserId(), "update", "user", id.ToString());
            return Results.Ok((await accounts.FindAsync(id))!.ToSummary());
        });
    }
}
