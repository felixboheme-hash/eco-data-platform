@echo off
chcp 65001 >nul
REM 啟動/管理 eco-data-platform（生態資料庫 + BI網頁）的 Docker 容器服務。
REM
REM 用法：
REM   run-docker.bat start        rem 建置 + 啟動（db / etl / webapp 三個服務）
REM   run-docker.bat logs         rem 追蹤所有服務的 log
REM   run-docker.bat stop         rem 停止並移除容器
REM   run-docker.bat reload-data  rem 重新執行 etl，把 data\*.csv 重新匯入資料庫（不影響 db/webapp）

setlocal

cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo Error: docker is not installed or not found in PATH.
    exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
    echo Error: 無法連線到 Docker daemon，請先啟動 Docker Desktop 後再執行。
    exit /b 1
)

set ACTION=%1

if "%ACTION%"=="" (
    echo Usage: %~n0 [start^|logs^|stop^|reload-data]
    exit /b 1
)

if /I "%ACTION%"=="start" (
    docker compose up -d --build
    echo.
    echo 服務已啟動。瀏覽器開啟 http://localhost:8000 查看BI網頁。
    echo 用 "run-docker.bat logs" 追蹤 log。
    goto :eof
)

if /I "%ACTION%"=="logs" (
    docker compose logs -f
    goto :eof
)

if /I "%ACTION%"=="stop" (
    docker compose down
    goto :eof
)

if /I "%ACTION%"=="reload-data" (
    echo 重新執行 ETL，將 data\*.csv 匯入資料庫（db / webapp 不受影響）...
    docker compose run --rm etl
    echo 完成。
    goto :eof
)

echo Usage: %~n0 [start^|logs^|stop^|reload-data]
exit /b 1
