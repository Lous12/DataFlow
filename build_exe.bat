@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo DataFlow v2 - ONEFILE build
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo [ERROR] Python not found.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating venv...
    %PY% -m venv .venv
    if errorlevel 1 goto :error
)

echo [2/4] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto :error

echo [3/4] Cleaning...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist DataFlow.spec del /q DataFlow.spec

echo [4/4] Building one-file EXE...
".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onefile ^
    --name DataFlow ^
    main.py

if errorlevel 1 goto :error

echo.
echo ========================================
echo BUILD COMPLETE
echo EXE: %CD%\dist\DataFlow.exe
echo ========================================
pause
exit /b 0

:error
echo.
echo BUILD FAILED
echo Copy the error text from this window.
pause
exit /b 1
