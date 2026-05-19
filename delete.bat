@echo off
chcp 65001 >nul
set "PROJECT_ROOT=%~dp0"

echo.
echo   Pal - Uninstaller
echo   ==================
echo   This will remove:
echo     - %PROJECT_ROOT% (project directory^)
echo     - %%USERPROFILE%%\pal.bat (global command^)
echo.

set /p CONFIRM="  Are you sure? Type DELETE to confirm: "
if not "%CONFIRM%"=="DELETE" (
    echo   Cancelled.
    pause
    exit /b 0
)

echo.
echo [1/2] Removing global command...
del "%USERPROFILE%\pal.bat" 2>nul
echo   Command removed.

echo [2/2] Removing project directory...
cd /d "%USERPROFILE%"
rmdir /s /q "%PROJECT_ROOT%" 2>nul
echo   Project removed.

echo.
echo   Uninstallation complete.
echo   Python packages retained. Remove manually if desired.
pause
