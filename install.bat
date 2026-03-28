@echo off
setlocal enabledelayedexpansion

:: AutoDoc installer for Windows
:: Usage: install.bat [target-directory]
:: Example: install.bat C:\Users\you\my-project

set "AUTODOC_DIR=%~dp0"
if "%~1"=="" (
    set "TARGET=%CD%"
) else (
    set "TARGET=%~1"
)

echo.
echo   AutoDoc installer
echo   =================
echo   Source : %AUTODOC_DIR%
echo   Target : %TARGET%
echo.

:: Verify target exists
if not exist "%TARGET%" (
    echo   ERROR: Target directory does not exist: %TARGET%
    exit /b 1
)

:: Create directories
if not exist "%TARGET%\.claude\commands"  mkdir "%TARGET%\.claude\commands"
if not exist "%TARGET%\Claude_Scripts"    mkdir "%TARGET%\Claude_Scripts"
if not exist "%TARGET%\docs"              mkdir "%TARGET%\docs"

:: Copy scripts
copy /Y "%AUTODOC_DIR%Claude_Scripts\log_activity.py"  "%TARGET%\Claude_Scripts\log_activity.py"  >nul
copy /Y "%AUTODOC_DIR%Claude_Scripts\daily_summary.py" "%TARGET%\Claude_Scripts\daily_summary.py" >nul
copy /Y "%AUTODOC_DIR%.claude\commands\summary.md"     "%TARGET%\.claude\commands\summary.md"     >nul

:: Copy config only if it doesn't exist
if not exist "%TARGET%\Claude_Scripts\autodoc.config.json" (
    copy /Y "%AUTODOC_DIR%Claude_Scripts\autodoc.config.json" "%TARGET%\Claude_Scripts\autodoc.config.json" >nul
    echo   Created : Claude_Scripts\autodoc.config.json
) else (
    echo   Skipped : Claude_Scripts\autodoc.config.json already exists ^(not overwritten^)
)

:: Create settings.local.json if it doesn't exist
set "SETTINGS=%TARGET%\.claude\settings.local.json"
if not exist "%SETTINGS%" (
    (
        echo {
        echo   "hooks": {
        echo     "Stop": [
        echo       {
        echo         "hooks": [
        echo           {
        echo             "type": "command",
        echo             "command": "python Claude_Scripts/log_activity.py",
        echo             "timeout": 15
        echo           }
        echo         ]
        echo       }
        echo     ]
        echo   }
        echo }
    ) > "%SETTINGS%"
    echo   Created : .claude\settings.local.json
) else (
    findstr /C:"log_activity.py" "%SETTINGS%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   Skipped : hook already present in settings.local.json
    ) else (
        echo.
        echo   WARNING: .claude\settings.local.json already exists.
        echo   Please add the following hook manually under hooks ^> Stop:
        echo.
        echo     {"type":"command","command":"python Claude_Scripts/log_activity.py","timeout":15}
        echo.
    )
)

echo.
echo   Done! AutoDoc is ready in: %TARGET%
echo.
echo   Next steps:
echo     1. Open the project in Claude Code
echo     2. Edit Claude_Scripts\autodoc.config.json to set your language ("es" or "en")
echo     3. Start coding -- entries appear in docs/YYYY-MM-DD.md automatically
echo     4. Type /summary at any time to generate the day summary
echo.
