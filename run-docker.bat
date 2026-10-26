@echo off
REM Start/manage the eco-data-platform (ecology database + BI web page) Docker services.
REM
REM Usage:
REM   run-docker.bat start        - build + start (db / etl / webapp)
REM   run-docker.bat logs         - follow logs of all services
REM   run-docker.bat stop         - stop and remove containers
REM   run-docker.bat reload-data  - re-run etl to reload data\*.csv (db/webapp unaffected)
REM
REM NOTE: keep this file pure ASCII. cmd.exe mis-parses multi-byte (Chinese) text,
REM even inside REM lines, and then runs fragments as commands.

setlocal

cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 goto :no_docker

docker info >nul 2>nul
if errorlevel 1 goto :no_daemon

if /I "%~1"=="start" goto :start
if /I "%~1"=="logs" goto :logs
if /I "%~1"=="stop" goto :stop
if /I "%~1"=="reload-data" goto :reload_data
goto :usage

:start
docker compose up -d --build
if errorlevel 1 exit /b 1
echo.
echo Services started. Open http://localhost:8000 in your browser.
echo Use "run-docker.bat logs" to follow the logs.
exit /b 0

:logs
docker compose logs -f
exit /b

:stop
docker compose down
exit /b

:reload_data
echo Re-running ETL to reload data\*.csv into the database (db / webapp keep running)...
docker compose run --rm etl
if errorlevel 1 exit /b 1
echo Done.
exit /b 0

:no_docker
echo Error: docker is not installed or not found in PATH.
exit /b 1

:no_daemon
echo Error: cannot connect to the Docker daemon. Please start Docker Desktop first.
exit /b 1

:usage
echo Usage: %~n0 [start^|logs^|stop^|reload-data]
exit /b 1
