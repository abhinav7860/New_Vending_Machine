# Vending Machine EXE Distribution Package

## What You Have

✅ **VendingMachine.exe** - Standalone executable (no Python installation needed!)
✅ **All dependencies bundled** - Flask, Firebase, Serial communication, Voice recognition, etc.
✅ **External configuration** - Firebase credentials stay outside the executable

## Setup for Distribution

### Step 1: Prepare the Distribution Package

1. Navigate to `dist/` folder
2. You'll see `VendingMachine.exe` file
3. Create a new folder structure for distribution:

```
VendingMachine_Setup/
├── VendingMachine.exe
├── config/
│   └── README_CONFIG.txt
├── SETUP_INSTRUCTIONS.txt
└── REQUIREMENTS.txt
```

### Step 2: Setup Instructions for End Users

1. **Create config folder**
   - Create a folder named `config` in the same directory as the .exe
   
2. **Get Firebase Credentials**
   - Go to https://console.firebase.google.com/
   - Select your project
   - Click Settings (⚙️) → Service Accounts
   - Click "Generate New Private Key"
   - Save as `firebase_credentials.json` in the `config` folder

3. **Run the app**
   - Double-click `VendingMachine.exe`
   - Browser opens automatically at http://127.0.0.1:5000

### Step 3: Configuration Files

**Directory structure after setup:**
```
VendingMachine.exe
config/
├── firebase_credentials.json    ← User must add this
└── (other config files auto-generated)
logs/
static/
templates/
database.db
```

## For You (Developer)

To share this with others:

1. Zip the contents of `dist/` folder
2. Include the `BUILD_README.md` file
3. Send to users with instructions to:
   - Extract the zip
   - Create `config` folder
   - Add their own `firebase_credentials.json`

## Rebuilding the EXE

If you make changes to the app:

```bash
# Activate virtual environment
.venv\Scripts\activate.bat

# Run the build script
build_exe.bat
```

Or manually:
```bash
.venv\Scripts\pyinstaller.exe build_exe.spec --distpath ./dist --workpath ./build_temp
```

## Troubleshooting

**App won't start**
- Check that `config/firebase_credentials.json` exists
- Verify it's valid JSON
- Check internet connection

**"Port 5000 already in use"**
- Close other applications using that port
- Or run: `netstat -ano | findstr :5000` to find the process

**Missing features (e.g., voice, weight sensor)**
- Verify required hardware connected (microphone, ESP32)
- Check USB driver installations

## Size Information

- EXE file: ~200-250 MB (includes all Python dependencies)
- Config folder: ~5-10 KB (firebase_credentials.json)
- Runtime files: ~20-50 MB

## Advantages of This Approach

✅ Users don't need Python installed
✅ No "pip install" required
✅ Single executable = easy to distribute
✅ Firebase credentials separate = secure and configurable
✅ Updates easy - just replace .exe file

## Technical Details

- Built with PyInstaller 6.17.0
- Python 3.11.2
- All libraries statically linked except firebase_credentials.json
- Windows-only (built on Windows 10/11)

---

**Need to rebuild?** Run `build_exe.bat` after making code changes.
