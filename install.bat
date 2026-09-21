@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo ===============================================
echo   Local Voice Studio - Installation
echo ===============================================
echo.

cd /d "%~dp0"

REM --- 1. Check Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3.11 or 3.12 from python.org and re-run.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Found Python %PYVER%

REM --- 2. Create venv ---
if not exist ".venv\Scripts\python.exe" (
    echo [STEP] Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [OK] .venv already exists
)

set VENV_PY=.venv\Scripts\python.exe

REM --- 3. Upgrade pip ---
echo [STEP] Upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip

REM --- 4. Install PyTorch with CUDA 12.4 ---
echo [STEP] Installing PyTorch (CUDA 12.4 build) ...
"%VENV_PY%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
if errorlevel 1 (
    echo [WARN] CUDA 12.4 wheel failed, retrying with CPU-only PyTorch as a fallback ...
    "%VENV_PY%" -m pip install torch torchaudio
)

REM --- 5. Install remaining dependencies ---
echo [STEP] Installing dependencies from requirements.txt ...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. See output above.
    pause
    exit /b 1
)

REM --- 6. Check FFmpeg (system, optional - imageio-ffmpeg bundled binary is the fallback) ---
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [INFO] System FFmpeg not found on PATH - the bundled imageio-ffmpeg binary will be used instead.
) else (
    echo [OK] System FFmpeg found on PATH
)

REM --- 7. Prepare directories ---
echo [STEP] Preparing directories ...
for %%D in (models voices output cache logs) do (
    if not exist "%%D" mkdir "%%D"
)

REM --- 8. Hardware test ---
echo [STEP] Running environment/hardware test ...
"%VENV_PY%" tests\test_environment.py
if errorlevel 1 (
    echo [ERROR] Environment test failed - see messages above. Fix the issue and re-run install.bat.
    pause
    exit /b 1
)

echo.
echo ===============================================
echo   Installation complete. Run start.bat to launch the app.
echo   Voice Conversion (MODE 2 / Seed-VC) is installed separately -
echo   see INSTALL.md, section "Voice Conversion setup".
echo ===============================================
pause
