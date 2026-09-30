@echo off
REM ===========================================================================
REM FreightIQ - start the FastAPI backend, then open the website.
REM
REM Previously this script only opened index.html, so the models and the API were
REM never running and the site silently used its built-in demo data.
REM
REM The API is optional: if uvicorn or the dependencies are missing, this script
REM says so and still opens the site, which then shows an "offline" notice in the
REM Model Status panel rather than failing.
REM ===========================================================================

setlocal
set "ROOT=%~dp0"
set "API_DIR=%ROOT%freight-intelligence-sih"
set "PORT=8000"

echo ============================================================
echo  FreightIQ Maritime Intelligence
echo ============================================================
echo.

REM --- Sanity checks -------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found on PATH. Install Python 3.10+ and try again.
    echo         The site will still open, but live model data will be unavailable.
    goto :opensite
)

if not exist "%API_DIR%\backend\main.py" (
    echo [WARN] Backend not found at %API_DIR%
    echo        Opening the site without live model data.
    goto :opensite
)

python -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo [WARN] FastAPI/uvicorn not installed. Starting without the backend.
    echo        To enable live model data, run:
    echo            pip install -r "%API_DIR%\requirements.txt"
    echo.
    goto :opensite
)

REM --- Check the models have been trained ---------------------------------
if not exist "%API_DIR%\models\artifacts\freight_metrics.json" (
    echo [WARN] Models do not look trained. Build them first with:
    echo            python "%API_DIR%\run_pipeline.py"
    echo.
)

REM --- Start the API in this window ---------------------------------------
echo Starting the API on http://127.0.0.1:%PORT% ...
echo Press Ctrl+C in this window to stop the server.
echo.
start "FreightIQ API" cmd /k "cd /d ""%API_DIR%"" && python -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT%"

REM Give the server a moment to bind before the page tries to reach it.
timeout /t 3 /nobreak >nul

:opensite
echo.
echo Opening the website...
start "" "%ROOT%index.html"
echo.
echo NOTE: browsers block API calls when a page is opened as a file:// URL.
echo       For the Live Model Status panel, serve over HTTP instead:
echo           powershell -File "%ROOT%serve.ps1"
echo       then open http://localhost:3000/
echo.
endlocal
