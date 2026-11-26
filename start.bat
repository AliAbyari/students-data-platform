@echo off

setlocal EnableExtensions EnableDelayedExpansion
title Students Data Platform

set "HERE=%~dp0"
if "%HERE:~0,2%"=="\\" (
    for /f "tokens=1,2,* delims=\" %%A in ("%HERE%") do (
        if /i "%%A"=="wsl.localhost" set "DISTRO=%%B" & set "REST=%%C"
        if /i "%%A"=="wsl$" set "DISTRO=%%B" & set "REST=%%C"
    )
    set "LINUXDIR=/!REST:\=/!"
    if not defined DISTRO (
        echo [ERROR] Network folders are not supported. Copy the project to a local drive.
        goto :fail
    )
    echo [setup] The project is inside WSL ^(!DISTRO!^); running start.sh there ...
    wsl.exe -d !DISTRO! --cd "!LINUXDIR!" -- bash ./start.sh
    if errorlevel 1 goto :fail
    endlocal
    exit /b 0
)
cd /d "%HERE%"

echo.
echo   Students Data Platform
echo   SQL Server ^> Airflow + Spark ^> PostgreSQL ^> ClickHouse  ^|  Debezium ^> Kafka ^> Spark Streaming
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker was not found. Install Docker Desktop ^(WSL 2 backend^) and run this script again:
    echo         https://www.docker.com/products/docker-desktop/
    start "" "https://www.docker.com/products/docker-desktop/"
    goto :fail
)
docker info >nul 2>&1
if not errorlevel 1 goto :dockerready
set "DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if exist "%DESKTOP%" (
    echo [setup] Starting Docker Desktop ...
    start "" "%DESKTOP%"
)
set /a waited=0
:waitdocker
ping -n 4 127.0.0.1 >nul
docker info >nul 2>&1
if not errorlevel 1 goto :dockerready
set /a waited+=1
if !waited! LSS 60 goto :waitdocker
echo [ERROR] Docker Desktop is not running. Start it and run this script again.
goto :fail
:dockerready
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose v2 is required. Update Docker Desktop.
    goto :fail
)
for /f "tokens=*" %%T in ('docker info --format "{{.OSType}}"') do set "OSTYPE=%%T"
if /i not "!OSTYPE!"=="linux" (
    echo [ERROR] Docker is running Windows containers. Right-click the Docker icon and choose
    echo         "Switch to Linux containers", then run this script again.
    goto :fail
)

if not exist "data\Students.bak" (
    
    if exist "data\Students.bak.tar.gz.001" (
        echo [setup] Unpacking the Students database backup ...
        set "PARTS="
        for /f "delims=" %%F in ('dir /b /on "data\Students.bak.tar.gz.0*"') do set "PARTS=!PARTS!+"data\%%F""
        copy /b !PARTS:~1! "%TEMP%\Students.bak.tar.gz" >nul
        tar -xzf "%TEMP%\Students.bak.tar.gz" -C data
        if errorlevel 1 (
            del "%TEMP%\Students.bak.tar.gz" >nul 2>&1
            echo [ERROR] The backup could not be unpacked. Windows 10 1803 or later is required ^(tar.exe^).
            goto :fail
        )
        del "%TEMP%\Students.bak.tar.gz" >nul 2>&1
    ) else if exist "..\Students.bak" (
        echo [setup] Copying ..\Students.bak to data\Students.bak
        copy /y "..\Students.bak" "data\Students.bak" >nul
    ) else (
        echo [ERROR] The backup parts data\Students.bak.tar.gz.* are missing. Clone the full repository again.
        goto :fail
    )
)

if not exist ".env" (
    echo [setup] Creating .env from .env.example
    copy /y ".env.example" ".env" >nul
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"
set "BATCH_SCHEDULE="
if not defined PORT_PORTAL set "PORT_PORTAL=9080"
if not defined PORT_PROMETHEUS set "PORT_PROMETHEUS=9091"

if not defined DOCKERHUB_MIRROR set "DOCKERHUB_MIRROR=auto"
if /i "!DOCKERHUB_MIRROR!"=="auto" (
    set "CODE=000"
    for /f %%C in ('curl -s -o nul -w "%%{http_code}" --max-time 10 https://registry-1.docker.io/v2/ 2^>nul') do set "CODE=%%C"
    if "!CODE!"=="401" (set "DOCKERHUB_MIRROR=docker.io") else if "!CODE!"=="200" (set "DOCKERHUB_MIRROR=docker.io") else (set "DOCKERHUB_MIRROR=docker.arvancloud.ir")
)
echo [setup] Docker Hub images from: !DOCKERHUB_MIRROR!

for /f "tokens=*" %%M in ('docker info --format "{{.MemTotal}}"') do set "MEM=%%M"
set /a MEM_GB=!MEM:~0,-9! 2>nul
if defined MEM_GB if !MEM_GB! LSS 7 (
    echo [warning] Docker has about !MEM_GB! GB of memory. 8 GB or more is recommended
    echo           ^(%%UserProfile%%\.wslconfig: [wsl2] memory=10GB, then run: wsl --shutdown^).
)

set "RUNNING="
for /f %%I in ('docker compose ps -q 2^>nul') do set "RUNNING=1"
if not defined RUNNING (
    set "BUSY="
    for %%P in (%PORT_PORTAL% %PORT_AIRFLOW% %PORT_GRAFANA% %PORT_KAFKA_UI% %PORT_CONNECT% %PORT_CLICKHOUSE_HTTP% %PORT_SQLSERVER% %PORT_POSTGRES% %PORT_PROMETHEUS%) do (
        netstat -ano -p tcp | findstr /r /c:"127.0.0.1:%%P .*LISTENING" /c:"0.0.0.0:%%P .*LISTENING" /c:"\[::\]:%%P .*LISTENING" >nul && set "BUSY=!BUSY! %%P"
    )
    if defined BUSY (
        echo [ERROR] These ports are already in use:!BUSY!. Free them or change the PORT_* values in .env.
        goto :fail
    )
)

echo.
echo [1/4] Downloading images (first run: about 5-10 minutes, depending on the connection) ...
title Students Data Platform - downloading images
set /a attempt=0
:pull
set /a attempt+=1
docker compose pull --ignore-buildable
if errorlevel 1 (
    if !attempt! GEQ 5 (
        echo [ERROR] Images could not be downloaded. Set DOCKERHUB_MIRROR in .env.
        goto :fail
    )
    echo [retry] download attempt !attempt! failed, trying again in 10 seconds ...
    ping -n 11 127.0.0.1 >nul
    goto :pull
)

echo.
echo [2/4] Building the platform images (first run: about 5-10 minutes; later runs use the cache) ...
title Students Data Platform - building images
set /a attempt=0
:build
set /a attempt+=1
docker compose build
if errorlevel 1 (
    if !attempt! GEQ 5 goto :fail
    echo [retry] build attempt !attempt! failed, trying again in 10 seconds ...
    ping -n 11 127.0.0.1 >nul
    goto :build
)

echo.
echo [3/4] Starting the services ...
title Students Data Platform - starting services
docker compose up -d
if errorlevel 1 goto :fail

echo.
echo [4/4] Waiting until every service is ready (first run: SQL Server restores the database, about 2-5 minutes) ...
title Students Data Platform - waiting for services
set /a tries=0
:wait
set /a tries+=1
curl -fs "http://localhost:%PORT_PORTAL%/health" >nul 2>&1
if not errorlevel 1 goto :ready
if !tries! GEQ 180 (
    echo [ERROR] The portal did not become healthy in time. Inspect: docker compose logs portal mssql-init
    goto :fail
)
set /a show=tries %% 2
if !show! EQU 1 call :status
ping -n 6 127.0.0.1 >nul
goto :wait

:status
set /a secs=(tries-1)*5, mm=secs/60, ss=secs%%60
set "SS=0!ss!"
set "SS=!SS:~-2!"
set /a total=0, done=0
set "PENDING="
for /f "tokens=1-3" %%a in ('docker compose ps -a --format "{{.Service}} {{.State}} {{.Health}}" 2^>nul') do (
    set /a total+=1
    set "ok="
    if /i "%%b"=="running" if /i not "%%c"=="starting" if /i not "%%c"=="unhealthy" set "ok=1"
    set "SVC=%%a"
    if /i "%%b"=="exited" if not "!SVC:init=!!SVC:register=!"=="!SVC!!SVC!" set "ok=1"
    if defined ok (set /a done+=1) else (set "PENDING=!PENDING! %%a")
)
if defined PENDING (
    echo   [!mm!:!SS!] !done!/!total! services ready - starting:!PENDING!
) else (
    echo   [!mm!:!SS!] !done!/!total! services ready - waiting for the portal
)
title Students Data Platform - !done!/!total! services ready
exit /b 0

:ready
title Students Data Platform - running
echo.
echo [done] Platform is up. Opening the portal in your browser ...
echo.
echo   Students Portal (Blazor PWA)  http://localhost:%PORT_PORTAL%     user: %PORTAL_ADMIN_USER%  password: %PORTAL_ADMIN_PASSWORD%
echo   Airflow                       http://localhost:%PORT_AIRFLOW%     user: %AIRFLOW_ADMIN_USER%  password: %AIRFLOW_ADMIN_PASSWORD%
echo   Grafana                       http://localhost:%PORT_GRAFANA%     user: %GRAFANA_ADMIN_USER%  password: %GRAFANA_ADMIN_PASSWORD%
echo   Kafka UI                      http://localhost:%PORT_KAFKA_UI%
echo   Prometheus                    http://localhost:%PORT_PROMETHEUS%
echo   ClickHouse HTTP               http://localhost:%PORT_CLICKHOUSE_HTTP%
echo   SQL Server                    localhost,%PORT_SQLSERVER%   (sa / see .env)
echo.
echo   The initial warehouse load runs automatically in Airflow (DAG students_batch_scd)
echo   and takes a few minutes; the dashboard fills in when it finishes.
echo.
start "" "http://localhost:%PORT_PORTAL%"
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
