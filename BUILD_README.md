# Vending Machine - Standalone Executable

This folder contains the Vending Machine application as a standalone executable.

## Quick Start

### Prerequisites
- Windows 10/11
- Internet connection (for Firebase)

### Setup Instructions

1. **Create config folder**
   - Create a new folder named `config` in the same directory as `VendingMachine.exe`

2. **Add Firebase credentials**
   - Get your `firebase_credentials.json` from Firebase Console
   - Place it in the `config` folder

   Example structure:
   ```
   VendingMachine/
   ├── VendingMachine.exe
   ├── config/
   │   └── firebase_credentials.json
   └── ... (other files)
   ```

3. **Run the application**
   - Double-click `VendingMachine.exe`
   - The app will open in your browser at `http://127.0.0.1:5000`

## Getting Firebase Credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to **Project Settings** > **Service Accounts**
4. Click **Generate New Private Key**
5. Save the downloaded JSON file as `firebase_credentials.json` in the `config` folder

## Troubleshooting

**"firebase_credentials.json not found"**
- Ensure the `config` folder exists in the same directory as the executable
- Verify the filename is exactly `firebase_credentials.json`
- Check that the file is valid JSON

**Port 5000 already in use**
- Close other applications using port 5000
- Or modify `app.py` to use a different port

**App crashes on startup**
- Check the console window for error messages
- Ensure Firebase credentials are valid
- Verify internet connection for Firebase access

## Distribution

When distributing this executable to others:
1. Include all files in the `dist/VendingMachine` folder
2. Include a copy of this README
3. Provide them with the `firebase_credentials.json` file (or instructions to get their own)
4. They should place `firebase_credentials.json` in the `config` folder

## Features

- Web-based vending machine interface
- Real-time Firebase integration
- Product management
- Transaction logging
- Voice commands (with microphone)
- Weight verification (with ESP32)
- Admin panel
- Analytics dashboard

## System Requirements

- Windows 7+ (tested on Windows 10/11)
- 4GB RAM minimum
- 50MB free disk space
- USB port for ESP32 (optional, for weight sensor)

## Support

For issues or questions, contact the development team or check the project repository.
