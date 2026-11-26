using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.WebUtilities;
using Microsoft.Extensions.Options;

namespace StudentsPortal.Server.Infrastructure;

public sealed class ClickHouseOptions
{
    public string Url { get; set; } = "http://clickhouse:8123";
    public string Database { get; set; } = "students_dw";
    public string User { get; set; } = "default";
    public string Password { get; set; } = "";
}

public sealed class ClickHouseException(string message) : Exception(message);

public sealed class ClickHouseClient(HttpClient http, IOptions<ClickHouseOptions> options)
{
    private static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
        NumberHandling = JsonNumberHandling.AllowReadingFromString,
    };

    private static readonly Dictionary<string, string?> Settings = new()
    {
        ["output_format_json_quote_64bit_integers"] = "0",
        ["output_format_json_quote_decimals"] = "0",
        ["date_time_output_format"] = "iso",
        ["readonly"] = "2",
        ["max_execution_time"] = "30",
    };

    public async Task<List<T>> QueryAsync<T>(string sql, IReadOnlyDictionary<string, object?>? parameters = null,
                                             CancellationToken ct = default)
    {
        var cfg = options.Value;
        var query = new Dictionary<string, string?>(Settings) { ["database"] = cfg.Database };
        if (parameters is not null)
        {
            foreach (var (name, value) in parameters)
            {
                query[$"param_{name}"] = Format(value);
            }
        }

        using var request = new HttpRequestMessage(HttpMethod.Post, QueryHelpers.AddQueryString(cfg.Url, query))
        {
            Content = new StringContent(sql + "\nFORMAT JSONEachRow", Encoding.UTF8, "text/plain"),
        };
        request.Headers.Add("X-ClickHouse-User", cfg.User);
        request.Headers.Add("X-ClickHouse-Key", cfg.Password);

        using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
        if (!response.IsSuccessStatusCode)
        {
            throw new ClickHouseException(await response.Content.ReadAsStringAsync(ct));
        }

        var rows = new List<T>();
        using var reader = new StreamReader(await response.Content.ReadAsStreamAsync(ct));
        while (await reader.ReadLineAsync(ct) is { } line)
        {
            if (line.Length > 0)
            {
                rows.Add(JsonSerializer.Deserialize<T>(line, Json)!);
            }
        }
        return rows;
    }

    public async Task<T?> SingleAsync<T>(string sql, IReadOnlyDictionary<string, object?>? parameters = null,
                                         CancellationToken ct = default)
        => (await QueryAsync<T>(sql, parameters, ct)).FirstOrDefault();

    private static string? Format(object? value) => value switch
    {
        null => "\\N",
        DateTime d => d.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture),
        IFormattable f => f.ToString(null, CultureInfo.InvariantCulture),
        _ => value.ToString(),
    };
}
