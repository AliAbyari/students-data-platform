FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY StudentsPortal.slnx ./
COPY src/StudentsPortal.Shared/StudentsPortal.Shared.csproj src/StudentsPortal.Shared/
COPY src/StudentsPortal.Client/StudentsPortal.Client.csproj src/StudentsPortal.Client/
COPY src/StudentsPortal.Server/StudentsPortal.Server.csproj src/StudentsPortal.Server/
RUN dotnet restore src/StudentsPortal.Server/StudentsPortal.Server.csproj
COPY src/ src/
RUN dotnet publish src/StudentsPortal.Server/StudentsPortal.Server.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl libicu-dev \
 && rm -rf /var/lib/apt/lists/*
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false \
    ASPNETCORE_URLS=http://+:8080
WORKDIR /app
COPY --from=build /app .
USER app
EXPOSE 8080
ENTRYPOINT ["dotnet", "StudentsPortal.Server.dll"]
