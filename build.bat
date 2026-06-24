@echo off
REM Build Vending Machine EXE with PyInstaller
REM This script builds a standalone Windows executable

echo Building Vending Machine EXE...
echo This may take 5-10 minutes on first build...

pyinstaller --onefile ^
  --windowed ^
  --add-data "templates:templates" ^
  --add-data "static:static" ^
  --add-data "firebase_credentials.json:." ^
  --add-data "database.db:." ^
  --hidden-import=flask ^
  --hidden-import=sqlite3 ^
  --hidden-import=serial ^
  --hidden-import=requests ^
  --hidden-import=jinja2 ^
  --hidden-import=werkzeug ^
  --name VendingMachine ^
  app.py

echo.
echo ============================================================
if exist dist\VendingMachine.exe (
    echo BUILD SUCCESSFUL!
    echo.
    echo Your EXE is ready: dist\VendingMachine.exe
    echo.
    echo NEXT STEPS:
    echo 1. Copy the entire 'dist' folder to your deployment location
    echo 2. Make sure these files are in the same folder as VendingMachine.exe:
    echo    - database.db
    echo    - firebase_credentials.json
    echo    - templates\ folder
    echo    - static\ folder
    echo    - logs\ folder (auto-created if missing)
    echo.
    echo 3. Double-click VendingMachine.exe to run!
) else (
    echo BUILD FAILED! Check the error messages above.
)
echo ============================================================
pause
