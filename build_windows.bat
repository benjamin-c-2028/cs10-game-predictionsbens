@echo off
setlocal

cd /d "%~dp0"

set "APP_NAME=Bitcoin-Up-or-Down-Arcade"
set "ENTRY_FILE=game.py"
set "PYTHON_CMD=py -3"

where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3 not found. Install Python 3 first if you want to build the EXE yourself.
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

%PYTHON_CMD% -m venv .venv-build
if errorlevel 1 exit /b 1

call .venv-build\Scripts\activate.bat
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --add-data "asset-game;asset-game" ^
    --collect-all arcade ^
    --collect-all pyglet ^
    "%ENTRY_FILE%"
if errorlevel 1 exit /b 1

echo.
echo Built dist\%APP_NAME%.exe
