@echo off
setlocal

title Install LLM Gateway Requirements

echo ============================================================
echo   LLM GATEWAY - DEPENDENCY INSTALLATION AND SETUP
echo ============================================================
echo.

cd /d "%~dp0"

rem 1. Check Python installation
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in your PATH!
    echo Please install Python 3.12 or newer from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version
echo.

rem 2. Create virtual environment if not present
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Creating virtual environment in .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo [2/4] Existing virtual environment found: .venv
)
echo.

rem 3. Upgrade pip and install requirements
echo [3/4] Installing dependencies from requirements.txt...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install one or more dependencies!
    pause
    exit /b 1
)
echo Dependencies installed successfully.
echo.

rem 4. Setup .env from .env.example if missing
echo [4/4] Checking environment configuration .env...
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo Created .env from .env.example with safe defaults.
    )
) else (
    echo Existing .env found.
)

echo.
echo ============================================================
echo   SETUP COMPLETED SUCCESSFULLY!
echo ============================================================
echo You can now start the LLM Gateway by running:
echo   run_gateway.bat
echo.
pause
