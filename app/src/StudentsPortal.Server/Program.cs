using System.Globalization;
using System.Security.Claims;
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.IdentityModel.Tokens;
using StudentsPortal.Server.Endpoints;
using StudentsPortal.Server.Infrastructure;
using StudentsPortal.Shared;

var builder = WebApplication.CreateBuilder(args);
CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;

builder.Services.Configure<JwtOptions>(builder.Configuration.GetSection("Jwt"));
builder.Services.Configure<ClickHouseOptions>(builder.Configuration.GetSection("ClickHouse"));
builder.Services.AddMemoryCache();
builder.Services.AddSingleton<Database>();
builder.Services.AddSingleton<AccountService>();
builder.Services.AddHttpClient<ClickHouseClient>(client => client.Timeout = TimeSpan.FromSeconds(60));
builder.Services.AddProblemDetails();

var jwt = builder.Configuration.GetSection("Jwt").Get<JwtOptions>() ?? new JwtOptions();
if (jwt.Key.Length < 32)
{
    throw new InvalidOperationException("Jwt:Key must be at least 32 characters.");
}

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(options =>
{
    options.MapInboundClaims = false;
    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidIssuer = jwt.Issuer,
        ValidAudience = jwt.Issuer,
        IssuerSigningKey = AccountService.SigningKey(jwt),
        NameClaimType = ClaimTypes.Name,
        RoleClaimType = ClaimTypes.Role,
        ClockSkew = TimeSpan.FromMinutes(1),
    };
    options.Events = new JwtBearerEvents
    {
        OnTokenValidated = async context =>
        {
            var accounts = context.HttpContext.RequestServices.GetRequiredService<AccountService>();
            var principal = context.Principal!;
            var stamp = principal.FindFirstValue(AccountService.SessionClaim);
            if (stamp is null || !await accounts.IsSessionValidAsync(principal.UserId(), stamp))
            {
                context.Fail("Session is no longer active.");
            }
        },
    };
});
builder.Services.AddAuthorization();

builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    options.AddPolicy("login", context => RateLimitPartition.GetFixedWindowLimiter(
        context.Connection.RemoteIpAddress?.ToString() ?? "anonymous",
        _ => new FixedWindowRateLimiterOptions { PermitLimit = 10, Window = TimeSpan.FromMinutes(1) }));
});

var app = builder.Build();

app.UseExceptionHandler(handler => handler.Run(async context =>
{
    var error = context.Features.Get<IExceptionHandlerFeature>()?.Error;
    var (status, code) = error switch
    {
        ClickHouseException => (StatusCodes.Status503ServiceUnavailable, "warehouse_unavailable"),
        Microsoft.Data.SqlClient.SqlException => (StatusCodes.Status503ServiceUnavailable, "source_unavailable"),
        HttpRequestException => (StatusCodes.Status503ServiceUnavailable, "warehouse_unavailable"),
        _ => (StatusCodes.Status500InternalServerError, "unexpected"),
    };
    app.Logger.LogError(error, "Request failed: {Path}", context.Request.Path);
    context.Response.StatusCode = status;
    await context.Response.WriteAsJsonAsync(new ApiError(code, "The request could not be completed."));
}));

app.UseBlazorFrameworkFiles();
app.UseStaticFiles();
app.UseRateLimiter();
app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/health", () => Results.Ok(new { status = "ok" })).AllowAnonymous();
app.MapAccountEndpoints();
app.MapOperationalEndpoints();
app.MapAnalyticsEndpoints();
app.MapGet("/api/platform/links", (IConfiguration config) =>
    Results.Ok(config.GetSection("Links").GetChildren().ToDictionary(c => c.Key, c => c.Value)))
   .RequireAuthorization();
app.MapFallbackToFile("index.html");

var seed = app.Configuration.GetSection("Seed");
var adminPassword = seed["AdminPassword"] ?? throw new InvalidOperationException("Seed:AdminPassword is required.");
app.Lifetime.ApplicationStarted.Register(() => _ = Task.Run(() =>
    app.Services.GetRequiredService<AccountService>().EnsureAdminAsync(seed["AdminUser"] ?? "admin", adminPassword, app.Logger)));

app.Run();
