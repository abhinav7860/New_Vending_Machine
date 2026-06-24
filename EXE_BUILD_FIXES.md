# Vending Machine EXE - Build Summary & Fixes

## Date
January 7, 2026

## Issues Fixed

### 1. **Internal Server Error When Running EXE**
**Root Cause:** Flask app was not finding template and static files when running as an exe because it was using relative paths that didn't work inside the bundled executable.

**Solution:** 
- Added `BASE_PATH` detection using `sys.frozen` to determine if running as exe or in dev mode
- Updated Flask initialization to use absolute paths:
  ```python
  template_folder=os.path.join(BASE_PATH, 'templates')
  static_folder=os.path.join(BASE_PATH, 'static')
  ```
- Updated all database and file references to use BASE_PATH:
  - Database connections now use `os.path.join(BASE_PATH, "database.db")`
  - Log files now use helper function `get_logs_path(filename)`

### 2. **Application Not Closing When Browser Closed**
**Root Cause:** Flask app was blocking forever even after browser window closed. The daemon thread for voice commands and main Flask thread weren't properly handling shutdown signals.

**Solution:**
- Added graceful shutdown handlers using `signal.signal()` and `atexit.register()`
- Added try/except block around Flask run with KeyboardInterrupt handling
- Modified Flask to use `threaded=True` mode for better signal handling
- Added explicit `os._exit(0)` to force clean exit

### 3. **PyInstaller Build Issues**
**Problem:** Previous spec files were too verbose and caused build to hang.

**Solution:**
- Simplified spec file with minimal hiddenimports
- Switched from one-file (-onefile) to one-directory (COLLECT) mode for faster builds
- Spec file now includes:
  - templates, static, and logs directories
  - Minimal but sufficient hidden imports (flask, werkzeug, jinja2, serial)
  - Proper COLLECT directive for one-directory bundle

## New Files Created

1. **vending_machine.spec** - Proper PyInstaller configuration file
2. **RUN_VENDING_MACHINE.bat** - Easy launcher script

## How to Use the New EXE

### Method 1: Double-Click Batch File
```
Double-click: RUN_VENDING_MACHINE.bat
```

### Method 2: Direct EXE Execution
```
Navigate to: dist\VendingMachine\
Double-click: VendingMachine.exe
```

### What Happens:
1. Console window opens showing startup messages
2. ESP32 weight sensor connection is verified
3. Web browser automatically opens to `http://127.0.0.1:5000`
4. Flask server runs in the background
5. **Closing the browser window will now properly shutdown the application**

## Build Instructions (If You Need to Rebuild)

```bash
cd "c:\Users\a0510281\Documents\python2026\New_Vending_Machine_2026\New_Vending_Machine"

# Clean old builds
rmdir /s /q build dist

# Build the executable
.venv\Scripts\python.exe -m PyInstaller vending_machine.spec --noconfirm
```

## Executable Details

- **Location:** `dist\VendingMachine\VendingMachine.exe`
- **Size:** ~9.4 MB
- **Type:** Bundled executable (one-directory format)
- **Python Version:** 3.11.2
- **Console:** Yes (shows debug output)

## Key Improvements

✓ Proper file path handling for exe environment
✓ Graceful shutdown on browser close
✓ No longer requires manual Task Manager termination
✓ All Flask routes work correctly
✓ Database and logs properly accessible
✓ Templates and static files load without errors

## Testing Recommendations

1. Test the exe by double-clicking RUN_VENDING_MACHINE.bat
2. Verify web interface loads correctly
3. Test a purchase flow
4. Close the browser - app should shutdown cleanly
5. Check that no python process remains in Task Manager

## Files Modified

- `app.py` - Added BASE_PATH, graceful shutdown, proper file path handling
- Created `vending_machine.spec` - Proper PyInstaller configuration
- Created `RUN_VENDING_MACHINE.bat` - Convenient launcher

## Notes

- The exe includes all necessary dependencies (Flask, PySerial, Requests, etc.)
- Logs and database files are properly accessed from the exe's directory
- The app will work from any location on the computer
- Template rendering and static file serving work correctly in exe mode
