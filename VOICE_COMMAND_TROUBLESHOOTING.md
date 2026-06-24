# Voice Command Troubleshooting Guide

## Issues Fixed ✅

### 1. Missing Dependency: `pyttsx3`
- **Problem**: Code tried to use `pyttsx3` but it wasn't in `requirements.txt`
- **Fixed**: Added `pyttsx3==2.90` to requirements.txt
- **Impact**: Text-to-speech announcements now work

### 2. Better Error Handling
- **Problem**: Generic error messages made debugging difficult
- **Fixed**: 
  - Separate error handling for microphone issues (OSError)
  - Distinguish between "couldn't understand" vs "connection error"
  - Added helpful installation instructions
- **Impact**: Users see specific error reasons instead of generic failures

### 3. Internet Connection Dependency
- **Problem**: Voice recognition uses Google Speech API which requires internet
- **Fixed**: Added clear error message when connection fails
- **What to check**: Ensure machine has internet access

---

## Troubleshooting Checklist

### ❌ "Voice commands disabled" or "Speech recognition not available"
**Causes & Solutions:**

1. **PyAudio not installed** (most common on Windows)
   ```bash
   # First, ensure you have Visual Studio C++ build tools
   # Then try:
   pip install PyAudio==0.2.14
   ```
   
   If that fails:
   ```bash
   # Alternative: Use pre-compiled wheel
   pip install pipwin
   pipwin install PyAudio
   ```

2. **SpeechRecognition not installed**
   ```bash
   pip install SpeechRecognition==3.10.0
   ```

3. **Microphone not connected or in use**
   - Check Windows Sound Settings
   - Ensure no other app is using the microphone
   - Try: Settings → Privacy & Security → Microphone

4. **Reinstall all dependencies**
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```

### ❌ "Could not understand" (constantly)
**Causes & Solutions:**

1. **Microphone too quiet**
   - Speak louder and closer to microphone
   - Check microphone volume in Windows Sound Settings

2. **Too much background noise**
   - Reduce ambient noise (fan, music, etc.)
   - Code does `adjust_for_ambient_noise` but may need quieter environment

3. **Speaking too fast/unclearly**
   - Speak slower and enunciate clearly
   - Say product number clearly: "One", "Two", "Three", "Four"

### ❌ "Connection error" or timeout
**Causes & Solutions:**

1. **No internet connection**
   - Check WiFi/Ethernet connection
   - Open browser and verify internet works
   - Google Speech API requires live internet

2. **Google API rate limited**
   - Wait a few minutes before trying again
   - Or reduce rapid voice command attempts

3. **Firewall blocking**
   - Check Windows Firewall settings
   - May need to allow Python through firewall

### ❌ Voice bot starts but doesn't listen
**Causes & Solutions:**

1. **Bot not started via API**
   - In web interface, click "Start Voice Bot"
   - Check status shows "bot_running: true"

2. **Listening timeout**
   - Code waits 5 seconds for audio input
   - Speak within 5 seconds of "listening..."

---

## How Voice Commands Work

```
1. User clicks "Start Voice Bot" in web interface
2. Global flag: bot_running = True
3. listen_for_commands() thread:
   - Listens to microphone (5 second timeout)
   - Sends audio to Google Speech API
   - Converts audio to text
   - Extracts product number from text
   - Triggers door open mechanism
4. Loop repeats until "Stop Voice Bot" clicked
```

## Test Voice System

### Step 1: Check Dependencies
```bash
python -c "import speech_recognition; print('✓ SpeechRecognition OK')"
python -c "import pyaudio; print('✓ PyAudio OK')"
python -c "import pyttsx3; print('✓ pyttsx3 OK')"
```

### Step 2: Test Microphone Access
```bash
python -c "import speech_recognition as sr; m = sr.Microphone(); print(f'✓ Microphone OK: {m}')"
```

### Step 3: Check Internet
```bash
ping google.com
```

### Step 4: Run App and Test
1. Start app: `python app.py`
2. Open browser: `http://localhost:5000`
3. Click "Start Voice Bot"
4. Say: "Open product 1" or just "1"
5. Check browser console for voice messages

---

## Installation for Fresh Setup

```bash
# Clean install
pip uninstall -y SpeechRecognition PyAudio pyttsx3
pip install -r requirements.txt

# If PyAudio fails on Windows, use:
pip install pipwin
pipwin install PyAudio

# Verify
python -c "import speech_recognition, pyaudio, pyttsx3; print('All voice dependencies OK')"
```

---

## Debug Logging

Check console output for voice-related messages:
- `[VOICE] Voice system ready` - System initialized
- `[VOICE] Voice system active, listening` - Waiting for audio
- `[VOICE] API Error` - Internet/API issue
- `[BOT] Could not understand` - Audio captured but not recognized
- `[BOT] Processing...` - Product detected, door opening

---

## Common Product Phrases

Voice recognition accepts:
- **Numbers**: "1", "2", "3", "4", "one", "two", "three", "four"
- **Product names**: Say full product name if stored in database
- **Commands**: "list products", "stop", "cancel", "back", "exit", "quit"

---

## Notes

- **Google API Requirements**: Requires active internet connection
- **Timeout**: 5 seconds to start speaking, 4 seconds max speech duration
- **Language**: English only (can be modified in code)
- **Accuracy**: ~85-90% in quiet environments

