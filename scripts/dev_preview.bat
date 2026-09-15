@echo off
setlocal
rem Double-click launcher for scripts/dev_preview.py.
rem Resolves the repository from this file's own location: no absolute paths.
for %%I in ("%~dp0..") do set "REPO=%%~fI"
set "PY=%REPO%\.venv\Scripts\python.exe"
if not exist "%PY%" (
echo [ERROR] Virtual environment interpreter not found:
echo         %PY%
echo.
echo Create the project virtual environment first; see docs\PROJECT_ONBOARDING.md.
echo.
pause
exit /b 1
)
"%PY%" "%REPO%\scripts\dev_preview.py" %*
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%
