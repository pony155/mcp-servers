@echo off
setlocal

set "DISTRIBUTION=Debian"
set "START_DIRECTORY="

if not "%~1"=="" set "DISTRIBUTION=%~1"
if not "%~2"=="" set "START_DIRECTORY=%~2"

where wsl.exe >nul 2>nul
if errorlevel 1 (
    echo Error: wsl.exe was not found. Install Windows Subsystem for Linux before running this script.
    exit /b 1
)

echo Entering WSL %DISTRIBUTION% bash...

if defined START_DIRECTORY (
    wsl.exe -d %DISTRIBUTION% --cd "%START_DIRECTORY%"
) else (
    wsl.exe -d %DISTRIBUTION%
)

set "WSL_STATUS=%ERRORLEVEL%"
if not "%WSL_STATUS%"=="0" (
    echo Error: Failed to enter WSL distribution "%DISTRIBUTION%".
    echo If it is not installed, install it with: wsl --install -d %DISTRIBUTION%
)

exit /b %WSL_STATUS%
