@echo off
REM Vending Machine Application Launcher
REM This batch file launches the built VendingMachine.exe application
REM The application will:
REM - Verify ESP32 connection
REM - Open a web browser to http://127.0.0.1:5000
REM - Properly shutdown when the browser is closed

echo Starting Vending Machine Application...
echo.
echo Flask server is starting. Your browser will open automatically.
echo The application will listen on http://127.0.0.1:5000
echo.
echo To stop the application, close the browser window or press Ctrl+C in this terminal.
echo.

REM Get the directory where this batch file is located
cd /d "%~dp0"

REM Run the VendingMachine exe
.\dist\VendingMachine\VendingMachine.exe

pause
