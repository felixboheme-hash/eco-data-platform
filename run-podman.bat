@echo off
REM Start/manage the eco-data-platform (ecology database + BI web page) Podman services.
REM Requires podman-compose (pip install podman-compose).
REM
REM Usage:
REM   run-podman.bat start        - build + start (db / etl / webapp)
REM   run-podman.bat logs         - follow logs of all services
REM   run-podman.bat stop         - stop and remove containers
REM   run-podman.bat reload-data  - re-run etl to reload data\*.csv (db/webapp unaffected)
REM
REM NOTE: keep this file pure ASCII. cmd.exe mis-parses multi-byte (Chinese) text,
REM even inside REM lines, and then runs fragments as commands.

setlocal

cd /d "%~dp0"

where podman-compose >nul 2>nul
if errorlevel 1 goto :no_compose

podman info >nul 2>nul
if errorlevel 1 goto :no_podman

if /I "%~1"=="start" goto :start
if /I "%~1"=="logs" goto :logs
if /I "%~1"=="stop" goto :stop
if /I "%~1"=="reload-data" goto :reload_data
goto :usage

:start
podman-compose up -d --build
if errorlevel 1 exit /b 1
echo.
echo Services started. Open http://localhost:8000 in your browser.
echo Use "run-podman.bat logs" to follow the logs.
exit /b 0

:logs
podman-compose logs -f
exit /b

:stop
podman-compose down
exit /b

:reload_data
echo Re-running ETL to reload data\*.csv into the database (db / webapp keep running)...
podman-compose run --rm etl
if errorlevel 1 exit /b 1
echo Done.
exit /b 0

:no_compose
echo Error: podman-compose is not installed or not found in PATH.
echo Install with: pip install podman-compose
exit /b 1

:no_podman
echo Error: cannot connect to Podman. Run "podman machine start" first.
exit /b 1

:usage
echo Usage: %~n0 [start^|logs^|stop^|reload-data]
exit /b 1
