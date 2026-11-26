using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.JSInterop;
using StudentsPortal.Shared;

namespace StudentsPortal.Client.Services;

public sealed class Session(IJSRuntime js, I18n i18n) : AuthenticationStateProvider
{
    private const string TokenKey = "sp.token";
    private const string UserKey = "sp.user";
    private static readonly AuthenticationState Anonymous = new(new ClaimsPrincipal(new ClaimsIdentity()));

    public string? Token { get; private set; }
    public UserProfile? User { get; private set; }
    public bool IsAdmin => User?.Role == Roles.Admin;
    public string Theme { get; private set; } = "light";
    public bool Remember { get; private set; } = true;

    public bool JustSignedIn { get; set; }

    public async Task InitializeAsync()
    {
        Theme = await js.InvokeAsync<string?>("portal.storage.get", "sp.theme") ?? "light";
        i18n.SetLanguage(await js.InvokeAsync<string?>("portal.storage.get", "sp.lang") ?? "fa");
        Token = await js.InvokeAsync<string?>("portal.storage.get", TokenKey);
        Remember = !await js.InvokeAsync<bool>("portal.storage.isTemporary", TokenKey);
        var user = await js.InvokeAsync<string?>("portal.storage.get", UserKey);
        if (Token is not null && user is not null)
        {
            try
            {
                User = JsonSerializer.Deserialize<UserProfile>(user, JsonSerializerOptions.Web);
            }
            catch (JsonException)
            {
                Token = null;
            }
        }
        await ApplyDocumentAsync();
    }

    public Task SignInAsync(LoginResponse response) => SignInAsync(response, Remember, null, null);

    public async Task SignInAsync(LoginResponse response, bool remember, string? language, string? theme)
    {
        Remember = remember;
        Token = response.Token;
        await js.InvokeVoidAsync("portal.storage.set", TokenKey, response.Token, !remember);
        await UpdateUserAsync(response.User);
        await SetThemeAsync(theme ?? response.User.PreferredTheme);
        await SetLanguageAsync(language ?? response.User.PreferredLanguage);
        NotifyAuthenticationStateChanged(Task.FromResult(BuildState()));
    }

    public async Task UpdateUserAsync(UserProfile user)
    {
        User = user;
        await js.InvokeVoidAsync("portal.storage.set", UserKey, JsonSerializer.Serialize(user, JsonSerializerOptions.Web), !Remember);
        NotifyAuthenticationStateChanged(Task.FromResult(BuildState()));
    }

    public async Task SignOutAsync()
    {
        Token = null;
        User = null;
        await js.InvokeVoidAsync("portal.storage.remove", TokenKey);
        await js.InvokeVoidAsync("portal.storage.remove", UserKey);
        NotifyAuthenticationStateChanged(Task.FromResult(Anonymous));
    }

    public async Task SetThemeAsync(string theme)
    {
        Theme = theme == "dark" ? "dark" : "light";
        await js.InvokeVoidAsync("portal.storage.set", "sp.theme", Theme);
        await ApplyDocumentAsync();
    }

    public async Task SetLanguageAsync(string language)
    {
        i18n.SetLanguage(language);
        await js.InvokeVoidAsync("portal.storage.set", "sp.lang", i18n.Language);
        await ApplyDocumentAsync();
    }

    private ValueTask ApplyDocumentAsync()
        => js.InvokeVoidAsync("portal.applyDocument", i18n.Language, i18n.Dir, Theme, i18n["app_name"]);

    public override Task<AuthenticationState> GetAuthenticationStateAsync() => Task.FromResult(BuildState());

    private AuthenticationState BuildState()
    {
        if (Token is null || User is null || IsExpired(Token)) return Anonymous;
        var identity = new ClaimsIdentity(
        [
            new Claim(ClaimTypes.NameIdentifier, User.UserId.ToString()),
            new Claim(ClaimTypes.Name, User.Username),
            new Claim(ClaimTypes.Role, User.Role),
        ], "jwt");
        return new AuthenticationState(new ClaimsPrincipal(identity));
    }

    private static bool IsExpired(string token)
    {
        try
        {
            var payload = token.Split('.')[1].Replace('-', '+').Replace('_', '/');
            payload = payload.PadRight(payload.Length + (4 - payload.Length % 4) % 4, '=');
            using var doc = JsonDocument.Parse(Convert.FromBase64String(payload));
            return doc.RootElement.TryGetProperty("exp", out var exp)
                   && DateTimeOffset.FromUnixTimeSeconds(exp.GetInt64()) <= DateTimeOffset.UtcNow;
        }
        catch (Exception)
        {
            return true;
        }
    }
}
