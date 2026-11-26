using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Components;
using StudentsPortal.Shared;

namespace StudentsPortal.Client.Services;

public sealed class ApiException(string code, IReadOnlyDictionary<string, string>? fields = null) : Exception(code)
{
    public string Code { get; } = code;
    public IReadOnlyDictionary<string, string> Fields { get; } = fields ?? new Dictionary<string, string>();
}

public sealed class ApiClient(HttpClient http, Session session, NavigationManager nav)
{
    private static readonly JsonSerializerOptions Json = JsonSerializerOptions.Web;

    public Task<T> GetAsync<T>(string url) => SendAsync<T>(HttpMethod.Get, url, null);
    public Task<T> PostAsync<T>(string url, object body) => SendAsync<T>(HttpMethod.Post, url, body);
    public Task<T> PutAsync<T>(string url, object body) => SendAsync<T>(HttpMethod.Put, url, body);
    public Task DeleteAsync(string url) => SendAsync<object?>(HttpMethod.Delete, url, null);

    public static string Query(string path, params (string Key, object? Value)[] args)
    {
        var parts = args.Where(a => a.Value is not null && a.Value.ToString() != "")
                        .Select(a => $"{a.Key}={Uri.EscapeDataString(a.Value!.ToString()!)}");
        var query = string.Join("&", parts);
        return query.Length == 0 ? path : $"{path}?{query}";
    }

    private async Task<T> SendAsync<T>(HttpMethod method, string url, object? body)
    {
        using var request = new HttpRequestMessage(method, url);
        if (session.Token is not null)
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", session.Token);
        if (body is not null)
            request.Content = JsonContent.Create(body, body.GetType(), options: Json);

        HttpResponseMessage response;
        try
        {
            response = await http.SendAsync(request);
        }
        catch (HttpRequestException)
        {
            throw new ApiException("network");
        }

        using (response)
        {
            if (response.StatusCode == HttpStatusCode.Unauthorized && !url.EndsWith("/auth/login"))
            {
                await session.SignOutAsync();
                nav.NavigateTo("login", replace: true);
                throw new ApiException("invalid_credentials");
            }
            if (!response.IsSuccessStatusCode)
            {
                ApiError? error = null;
                try { error = await response.Content.ReadFromJsonAsync<ApiError>(Json); } catch (Exception) { }
                var code = error?.Code ?? response.StatusCode switch
                {
                    HttpStatusCode.Forbidden => "forbidden",
                    HttpStatusCode.NotFound => "not_found",
                    HttpStatusCode.TooManyRequests => "rate_limited",
                    _ => "unexpected",
                };
                throw new ApiException(code, error?.Fields);
            }
            if (response.StatusCode == HttpStatusCode.NoContent || typeof(T) == typeof(object))
                return default!;
            return (await response.Content.ReadFromJsonAsync<T>(Json))!;
        }
    }
}
