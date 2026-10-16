@echo off
setlocal

title LLM Gateway Server

echo ============================================================
echo   STARTING LLM GATEWAY (PRODUCTION-GRADE SERVER)
echo ============================================================
echo.

cd /d "%~dp0"

rem Check if virtual environment exists; if not, automatically setup
if not exist ".venv\Scripts\python.exe" (
    echo [NOTICE] Virtual environment .venv not found. Auto-running setup...
    call install_requirements.bat
    if errorlevel 1 (
        echo [ERROR] Setup failed!
        pause
        exit /b 1
    )
)

rem Create .env from template if missing
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo Notice: Created initial .env configuration from .env.example.
    )
)

echo Gateway Server Configuration:
echo   - Base URL:      http://localhost:8000
echo   - API Docs:      http://localhost:8000/docs
echo   - Health Check:  http://localhost:8000/health
echo   - Stats:         http://localhost:8000/stats
echo   - Providers:     http://localhost:8000/providers
echo.
echo Press CTRL+C to stop the gateway server.
echo ============================================================
echo.

call .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

if errorlevel 1 (
    echo.
    echo [NOTICE] Gateway server exited with error.
    pause
)
