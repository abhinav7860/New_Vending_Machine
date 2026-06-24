# Vending Machine Project (Flask + SQLite + ESP32 Serial Reader)

## What is included
- `app.py` : Flask web application (user + admin UI)
- `serial_reader.py` : Background script to read weight data from ESP32 over serial and update DB
- `init_db.py` : Initialize the SQLite database with sample products and admin user
- `templates/` : HTML templates (index, admin login, admin panel, update)
- `static/style.css` : Basic styling
- `esp32_example/esp32_weight_example.ino` : Example ESP32 Arduino code to send weight values over serial
- `requirements.txt` : Python dependencies

## Quick Start (Linux/macOS/Windows WSL)
1. Create a Python virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows PowerShell: .\venv\Scripts\Activate.ps1
   ```
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize the database:
   ```bash
   python init_db.py
   ```
4. In one terminal, run the Flask app:
   ```bash
   export FLASK_APP=app.py
   flask run
   ```
   Or directly:
   ```bash
   python app.py
   ```
   Default: http://127.0.0.1:5000

5. In another terminal, run the serial reader to get weight updates from ESP32:
   ```bash
   python serial_reader.py
   ```
   Edit `serial_reader.py` to set the correct serial port (e.g., COM3 on Windows or /dev/ttyUSB0 on Linux).

## Admin Login
- username: `admin`
- password: `admin123`

## Notes
- The serial reader expects raw numeric weight values (one per line) from the ESP32.
- The provided logic maps weight updates to the `weight` field for product id 1 as an example.
- You can expand mapping logic in `serial_reader.py` to detect which product moved based on sensor setup.