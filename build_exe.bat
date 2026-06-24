@echo off
setlocal enabledelayedexpansion

echo ======================================
echo  Building Vending Machine EXE
echo ======================================
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install PyInstaller if not already installed
echo Installing PyInstaller...
pip install pyinstaller --quiet

REM Build the executable
echo.
echo Building executable...
pyinstaller build_exe.spec --distpath ./dist --workpath ./build_temp

echo.
echo ======================================
echo Build Complete!
echo ======================================
echo.
echo Executable location: dist\VendingMachine\VendingMachine.exe
echo.
echo IMPORTANT: Before running the exe, create a 'config' folder in the same directory
echo and place your 'firebase_credentials.json' file inside:
echo.
echo   dist\VendingMachine\config\firebase_credentials.json
echo.
echo Instructions:
echo 1. Create folder: dist\VendingMachine\config
echo 2. Copy firebase_credentials.json to: dist\VendingMachine\config\
echo 3. Double-click dist\VendingMachine\VendingMachine.exe to run
echo.
pause
