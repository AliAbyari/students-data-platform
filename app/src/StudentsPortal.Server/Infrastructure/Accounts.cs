using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Dapper;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;
using StudentsPortal.Shared;

namespace StudentsPortal.Server.Infrastructure;

public sealed class JwtOptions
{
    public string Key { get; set; } = "";
    public string Issuer { get; set; } = "students-portal";
    public int LifetimeHours { get; set; } = 10;
}

public sealed class UserRecord
{
    public int UserId { get; set; }
    public string Username { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public string FirstName { get; set; } = "";
    public string LastName { get; set; } = "";
    public string? Email { get; set; }
    public string Role { get; set; } = Roles.User;
    public bool IsActive { get; set; }
    public string PreferredLanguage { get; set; } = "fa";
    public string PreferredTheme { get; set; } = "light";
    public Guid SessionStamp { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? LastLoginAt { get; set; }

    public UserProfile ToProfile() => new(UserId, Username, FirstName, LastName, Email, Role, PreferredLanguage,
                                          PreferredTheme, CreatedAt, LastLoginAt);

    public UserSummary ToSummary() => new(UserId, Username, FirstName, LastName, Email, Role, IsActive, CreatedAt,
                                          LastLoginAt);
}

public sealed class AccountService(Database db, IMemoryCache cache, IOptions<JwtOptions> jwt)
{
    public const string SessionClaim = "sst";
    private const string Columns = "UserId, Username, PasswordHash, FirstName, LastName, Email, [Role], IsActive, " +
                                   "PreferredLanguage, PreferredTheme, SessionStamp, CreatedAt, LastLoginAt";
    private readonly PasswordHasher<UserRecord> hasher = new();

    public async Task<UserRecord?> FindAsync(int userId)
    {
        using var conn = db.Portal();
        return await conn.QuerySingleOrDefaultAsync<UserRecord>(
            $"SELECT {Columns} FROM app.Users WHERE UserId = @userId", new { userId });
    }

    public async Task<UserRecord?> FindByUsernameAsync(string username)
    {
        using var conn = db.Portal();
        return await conn.QuerySingleOrDefaultAsync<UserRecord>(
            $"SELECT {Columns} FROM app.Users WHERE Username = @username", new { username });
    }

    public async Task<IReadOnlyList<UserRecord>> ListAsync()
    {
        using var conn = db.Portal();
        return (await conn.QueryAsync<UserRecord>($"SELECT {Columns} FROM app.Users ORDER BY UserId")).ToList();
    }

    public bool VerifyPassword(UserRecord user, string password)
        => hasher.VerifyHashedPassword(user, user.PasswordHash, password) != PasswordVerificationResult.Failed;

    public string HashPassword(UserRecord user, string password) => hasher.HashPassword(user, password);

    public async Task<LoginResponse> SignInAsync(UserRecord user)
    {
        var stamp = Guid.NewGuid();
        using (var conn = db.Portal())
        {
            await conn.ExecuteAsync(
                "UPDATE app.Users SET SessionStamp = @stamp, LastLoginAt = SYSUTCDATETIME() WHERE UserId = @id",
                new { stamp, id = user.UserId });
        }
        cache.Remove(CacheKey(user.UserId));
        user.SessionStamp = stamp;
        user.LastLoginAt = DateTime.UtcNow;

        var options = jwt.Value;
        var expires = DateTimeOffset.UtcNow.AddHours(options.LifetimeHours);
        var claims = new[]
        {
            new Claim(JwtRegisteredClaimNames.Sub, user.UserId.ToString()),
            new Claim(ClaimTypes.NameIdentifier, user.UserId.ToString()),
            new Claim(ClaimTypes.Name, user.Username),
            new Claim(ClaimTypes.GivenName, user.FirstName),
            new Claim(ClaimTypes.Surname, user.LastName),
            new Claim(ClaimTypes.Role, user.Role),
            new Claim(SessionClaim, stamp.ToString("N")),
        };
        var token = new JwtSecurityToken(options.Issuer, options.Issuer, claims, expires: expires.UtcDateTime,
            signingCredentials: new SigningCredentials(SigningKey(options), SecurityAlgorithms.HmacSha256));
        return new LoginResponse(new JwtSecurityTokenHandler().WriteToken(token), expires, user.ToProfile());
    }

    public async Task RevokeSessionsAsync(int userId)
    {
        using var conn = db.Portal();
        await conn.ExecuteAsync("UPDATE app.Users SET SessionStamp = NEWID() WHERE UserId = @userId", new { userId });
        cache.Remove(CacheKey(userId));
    }

    public async Task<bool> IsSessionValidAsync(int userId, string stamp)
    {
        var current = await cache.GetOrCreateAsync(CacheKey(userId), async entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds(30);
            var user = await FindAsync(userId);
            return user is { IsActive: true } ? user.SessionStamp.ToString("N") : null;
        });
        return current is not null && string.Equals(current, stamp, StringComparison.Ordinal);
    }

    public async Task EnsureAdminAsync(string username, string password, ILogger logger)
    {
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                if (await FindByUsernameAsync(username) is not null)
                {
                    return;
                }
                var user = new UserRecord { Username = username, FirstName = "System", LastName = "Administrator",
                                            Role = Roles.Admin, IsActive = true };
                user.PasswordHash = HashPassword(user, password);
                using var conn = db.Portal();
                await conn.ExecuteAsync(
                    "INSERT INTO app.Users (Username, PasswordHash, FirstName, LastName, [Role], IsActive) " +
                    "VALUES (@Username, @PasswordHash, @FirstName, @LastName, @Role, 1)", user);
                logger.LogInformation("Seeded administrator account {Username}", username);
                return;
            }
            catch (Exception ex) when (attempt < 60)
            {
                logger.LogWarning("Account store not reachable yet ({Message}); retrying", ex.Message);
                await Task.Delay(TimeSpan.FromSeconds(5));
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Administrator account could not be seeded");
                return;
            }
        }
    }

    public async Task LogActivityAsync(int? userId, string action, string entity, string? key)
    {
        using var conn = db.Portal();
        await conn.ExecuteAsync(
            "INSERT INTO app.ActivityLog (UserId, Action, Entity, EntityKey) VALUES (@userId, @action, @entity, @key)",
            new { userId, action, entity, key });
    }

    public static SymmetricSecurityKey SigningKey(JwtOptions options)
        => new(Encoding.UTF8.GetBytes(options.Key.PadRight(64, '0')));

    private static string CacheKey(int userId) => $"session:{userId}";
}

public static class ClaimsExtensions
{
    public static int UserId(this ClaimsPrincipal principal)
        => int.TryParse(principal.FindFirstValue(ClaimTypes.NameIdentifier), out var id) ? id : 0;
}
