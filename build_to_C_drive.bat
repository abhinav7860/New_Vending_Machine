@echo off
REM Build SenseMart v1 EXE to C:\SenseMart_V1
REM This script builds the application and places all dependencies at C:\SenseMart_V1

echo ======================================
echo Building SenseMart Vending Machine v1.0
echo ======================================

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Create output directories
if not exist "C:\SenseMart_V1" mkdir C:\SenseMart_V1
if not exist "C:\SenseMart_V1\config" mkdir C:\SenseMart_V1\config
if not exist "C:\SenseMart_V1\dist" mkdir C:\SenseMart_V1\dist
if not exist "C:\SenseMart_V1\build" mkdir C:\SenseMart_V1\build

REM Copy Firebase credentials to C:\SenseMart_V1\config
echo Copying Firebase credentials...
copy "firebase_credentials.json" "C:\SenseMart_V1\config\firebase_credentials.json" /Y

REM Build the executable with PyInstaller
echo Building executable...
pyinstaller --onedir --console ^
    --name SenseMart_V1 ^
    --distpath "C:\SenseMart_V1\dist" ^
    --workpath "C:\SenseMart_V1\build" ^
    --specpath "C:\SenseMart_V1" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "logs;logs" ^
    --add-data "firebase_credentials.json;." ^
    --hidden-import=flask ^
    --hidden-import=werkzeug ^
    --hidden-import=jinja2 ^
    --hidden-import=serial ^
    --hidden-import=firebase_admin ^
    --hidden-import=pyaudio ^
    app.py

if %errorlevel% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo ======================================
echo Build Complete!
echo Output location: C:\SenseMart_V1\dist\SenseMart_V1
echo Firebase credentials: C:\SenseMart_V1\config\firebase_credentials.json
echo ======================================
pause
