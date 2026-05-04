@echo off
echo ========================================
echo Starting Debug MongoDB and Redis
echo ========================================
echo.
echo Usage: start_debug_services.bat [version]
echo   version: 2.0, 2.1, or 3.0 (default: use default ports)
echo.

set MONGODB_PORT=27017
set REDIS_PORT=6379
set PROJECT_NAME=ta-debug

if "%~1"=="2.0" (
    set MONGODB_PORT=27017
    set REDIS_PORT=6379
    set PROJECT_NAME=ta-v201
    echo Version: v2.0
) else if "%~1"=="2.1" (
    set MONGODB_PORT=27018
    set REDIS_PORT=6380
    set PROJECT_NAME=ta-v210
    echo Version: v2.1
) else if "%~1"=="3.0" (
    set MONGODB_PORT=27019
    set REDIS_PORT=6381
    set PROJECT_NAME=ta-v3
    echo Version: v3.0
) else if "%~1"=="" (
    echo No version specified, using default ports
) else (
    echo ERROR: Unknown version '%~1'. Use 2.0, 2.1, or 3.0
    pause
    exit /b 1
)

echo MongoDB port: %MONGODB_PORT%
echo Redis port: %REDIS_PORT%
echo Docker project: %PROJECT_NAME%
echo.

echo Checking Docker...
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker not running
    pause
    exit /b 1
)

echo Cleaning up existing containers for project %PROJECT_NAME%...
for /f "tokens=*" %%c in ('docker-compose -p %PROJECT_NAME% ps -q 2^>nul') do (
    docker stop %%c >nul 2>&1
    docker rm %%c >nul 2>&1
)

echo Starting MongoDB on port %MONGODB_PORT%...
docker run -d ^
    --name %PROJECT_NAME%-mongodb ^
    -p %MONGODB_PORT%:27017 ^
    -e MONGO_INITDB_ROOT_USERNAME=admin ^
    -e MONGO_INITDB_ROOT_PASSWORD=tradingagents123 ^
    -e MONGO_INITDB_DATABASE=tradingagents ^
    --restart unless-stopped ^
    mongo:4.4

if %errorlevel% equ 0 (
    echo [OK] MongoDB started successfully on port %MONGODB_PORT%
) else (
    echo [ERROR] MongoDB failed to start
)

echo Starting Redis on port %REDIS_PORT%...
docker run -d ^
    --name %PROJECT_NAME%-redis ^
    -p %REDIS_PORT%:6379 ^
    --restart unless-stopped ^
    redis:7-alpine redis-server --appendonly yes --requirepass tradingagents123

if %errorlevel% equ 0 (
    echo [OK] Redis started successfully on port %REDIS_PORT%
) else (
    echo [ERROR] Redis failed to start
)

echo Waiting 10 seconds for services to start...
timeout /t 10 /nobreak >nul

echo.
echo Service Status:
docker ps --filter "name=%PROJECT_NAME%" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ========================================
echo Debug Services Started!
echo ========================================
echo MongoDB: localhost:%MONGODB_PORT%
echo   Username: admin
echo   Password: tradingagents123
echo   Database: tradingagents
echo.
echo Redis: localhost:%REDIS_PORT%
echo   Password: tradingagents123
echo.
echo To stop services: docker stop %PROJECT_NAME%-mongodb %PROJECT_NAME%-redis
echo.

pause
