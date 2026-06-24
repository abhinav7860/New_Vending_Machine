@echo off
REM Vending Machine EXE Verification Script
REM This script verifies that all required files are in place

echo.
echo ===============================================
echo Vending Machine EXE Verification
echo ===============================================
echo.

REM Check if main exe exists
if exist "dist\VendingMachine\VendingMachine.exe" (
    echo [OK] Main executable found: dist\VendingMachine\VendingMachine.exe
) else (
    echo [ERROR] Main executable NOT found!
    pause
    exit /b 1
)

REM Check for templates
if exist "dist\VendingMachine\templates" (
    echo [OK] Templates folder found
) else (
    echo [ERROR] Templates folder NOT found!
)

REM Check for static files
if exist "dist\VendingMachine\static" (
    echo [OK] Static files folder found
) else (
    echo [ERROR] Static files folder NOT found!
)

REM Check for logs folder
if exist "dist\VendingMachine\logs" (
    echo [OK] Logs folder found
) else (
    echo [ERROR] Logs folder NOT found!
)

REM Check for python dll
if exist "dist\VendingMachine\python311.dll" (
    echo [OK] Python runtime DLL found
) else (
    echo [WARNING] Python runtime DLL not found (might be OK if using different bundling)
)

echo.
echo ===============================================
echo Verification Complete!
echo ===============================================
echo.
echo To run the application, execute:
echo   RUN_VENDING_MACHINE.bat
echo.
pause
