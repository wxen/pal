@echo off
chcp 65001 >nul
echo.
echo   Pal - AI Role-Playing Chat Framework
echo   Windows Installer
echo   =====================================
echo.

:: ── Python deps ──
echo [1/3] Installing Python dependencies...
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.10+.
    pause
    exit /b 1
)
python --version
python -m pip install --user -q textual flask requests python-dotenv Pillow 2>nul
echo   Dependencies installed.

:: ── Create directories ──
echo [2/3] Creating project structure...
if not exist "%~dp0ui" mkdir "%~dp0ui"
if not exist "%~dp0agent" mkdir "%~dp0agent"
if not exist "%~dp0file" mkdir "%~dp0file"
if not exist "%~dp0workspace" mkdir "%~dp0workspace"
echo   Directories ready.

:: ── Generate pal.bat launcher ──
echo [3/3] Generating pal.bat...
set "PROJECT_ROOT=%~dp0"
> "%USERPROFILE%\pal.bat" echo @echo off
>> "%USERPROFILE%\pal.bat" echo cd /d "%PROJECT_ROOT%" ^&^& python main.py %%*
echo   pal.bat generated in %%USERPROFILE%%

echo.
echo   =====================================
echo   Installation complete!
echo.
echo   CLI:            pal --help
echo   Create agent:   pal create mybot --wizard
echo   =====================================
echo.
pause
