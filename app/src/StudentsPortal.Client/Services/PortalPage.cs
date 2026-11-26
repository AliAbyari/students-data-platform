using Microsoft.AspNetCore.Components;
using StudentsPortal.Shared;

namespace StudentsPortal.Client.Services;

public abstract class PortalPage : ComponentBase, IDisposable
{
    [Inject] protected I18n L { get; set; } = default!;
    [Inject] protected ApiClient Api { get; set; } = default!;
    [Inject] protected Toasts Toasts { get; set; } = default!;
    [Inject] protected Session Session { get; set; } = default!;
    [Inject] protected NavigationManager Nav { get; set; } = default!;

    protected bool IsAdmin => Session.IsAdmin;
    protected Dictionary<string, string> Errors { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    protected bool Busy { get; set; }

    protected override void OnInitialized() => L.Changed += OnLanguageChanged;

    private void OnLanguageChanged() => InvokeAsync(StateHasChanged);

    protected string? FieldError(string field) => Errors.TryGetValue(field, out var code) ? L.Error(code) : null;

    protected async Task<bool> RunAsync(Func<Task> action, string? successKey = null)
    {
        Busy = true;
        Errors = new(StringComparer.OrdinalIgnoreCase);
        try
        {
            await action();
            if (successKey is not null) Toasts.Success(L[successKey]);
            return true;
        }
        catch (ApiException ex)
        {
            foreach (var (field, code) in ex.Fields) Errors[field] = code;
            Toasts.Error(L.Error(ex.Code));
            return false;
        }
        finally
        {
            Busy = false;
            StateHasChanged();
        }
    }

    protected static Lookups? CachedLookups;

    protected async Task<Lookups> LookupsAsync()
        => CachedLookups ??= await Api.GetAsync<Lookups>("api/lookups");

    public virtual void Dispose()
    {
        L.Changed -= OnLanguageChanged;
        GC.SuppressFinalize(this);
    }
}
