namespace StudentsPortal.Client.Services;

public sealed record Toast(Guid Id, string Message, string Kind);

public sealed class Toasts
{
    private readonly List<Toast> items = [];
    public IReadOnlyList<Toast> Items => items;
    public event Action? Changed;

    public void Success(string message) => Show(message, "success");
    public void Error(string message) => Show(message, "error");
    public void Info(string message) => Show(message, "info");

    public void Dismiss(Guid id)
    {
        items.RemoveAll(t => t.Id == id);
        Changed?.Invoke();
    }

    private void Show(string message, string kind)
    {
        var toast = new Toast(Guid.NewGuid(), message, kind);
        items.Add(toast);
        Changed?.Invoke();
        _ = Task.Delay(kind == "error" ? 7000 : 4500).ContinueWith(_ => Dismiss(toast.Id));
    }
}
