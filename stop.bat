@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "HERE=%~dp0"
if "%HERE:~0,2%"=="\\" (
    for /f "tokens=1,2,* delims=\" %%A in ("%HERE%") do (
        if /i "%%A"=="wsl.localhost" set "DISTRO=%%B" & set "REST=%%C"
        if /i "%%A"=="wsl$" set "DISTRO=%%B" & set "REST=%%C"
    )
    set "LINUXDIR=/!REST:\=/!"
    wsl.exe -d !DISTRO! --cd "!LINUXDIR!" -- bash ./stop.sh %*
    endlocal
    exit /b
)
cd /d "%HERE%"
if /i "%~1"=="--reset" (
    docker compose down -v
) else (
    docker compose down
)
endlocal
