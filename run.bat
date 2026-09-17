@echo off
REM sApkAnalyzer Launcher for Windows
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py %*
    goto end
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py -3 main.py %*
    goto end
)

echo Error: Python not found! Please install Python 3 from python.org.
pause

:end
