@echo off
REM FMU Gateway - Local Development Startup Script
echo ======================================================================
echo FMU GATEWAY - LOCAL SERVER
echo ======================================================================
echo.

REM Navigate to project directory
cd /d "%~dp0"

REM Set environment variables for local development
set DATABASE_URL=sqlite:///./local.db
set STRIPE_ENABLED=false
set REDIS_URL=
set REQUIRE_AUTH=false

echo Starting local FMU Gateway...
echo Server will be available at: http://localhost:8000
echo Health check at: http://localhost:8000/health
echo API docs at: http://localhost:8000/docs
echo.
echo NOTE: Authentication is DISABLED for local development
echo.
echo Press CTRL+C to stop the server
echo.

REM Start uvicorn
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause

