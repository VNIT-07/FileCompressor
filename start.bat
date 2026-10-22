@echo off
setlocal
cd /d "%~dp0"
title FileCompressor Studio

echo ========================================================
echo   Launching FileCompressor Studio...
echo ========================================================

:: Check for python command
where python >nul 2>nul
if %errorlevel% equ 0 (
    python server.py %*
    goto end
)

:: Check for py launcher
where py >nul 2>nul
if %errorlevel% equ 0 (
    py server.py %*
    goto end
)

:: Check for python3
where python3 >nul 2>nul
if %errorlevel% equ 0 (
    python3 server.py %*
    goto end
)

echo.
echo [ERROR] Python was not found in your system PATH.
echo Please install Python 3 from https://www.python.org/downloads/
echo and make sure to check "Add Python to PATH" during installation.
echo.
pause

:end
endlocal
