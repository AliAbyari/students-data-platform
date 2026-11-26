using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using StudentsPortal.Client;
using StudentsPortal.Client.Services;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

builder.Services.AddScoped(_ => new HttpClient { BaseAddress = new Uri(builder.HostEnvironment.BaseAddress) });
builder.Services.AddSingleton<I18n>();
builder.Services.AddSingleton<Toasts>();
builder.Services.AddScoped<Session>();
builder.Services.AddScoped<AuthenticationStateProvider>(sp => sp.GetRequiredService<Session>());
builder.Services.AddScoped<ApiClient>();
builder.Services.AddAuthorizationCore();
builder.Services.AddCascadingAuthenticationState();

var host = builder.Build();
await host.Services.GetRequiredService<Session>().InitializeAsync();
await host.RunAsync();
