# -*- coding: utf-8 -*-
import threading
import webbrowser
import time
import datetime
import sys
import io
import os
import signal

# Fix console encoding issues on Windows
if sys.platform == 'win32':
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Determine base paths for file resources (works in both dev and exe)
if getattr(sys, 'frozen', False):
    # Running as exe - separate paths for assets vs writable data
    exe_dir = os.path.dirname(sys.executable)  # C:\SenseMart_V1\app
    BUNDLE_PATH = sys._MEIPASS  # Assets (templates, static) from bundle
    DATA_PATH = sys._MEIPASS  # Will be overridden if external data dir found
    
    # Try to find writable data directory in these locations (in order)
    possible_data_dirs = [
        os.getenv('SENSEMART_DATA_DIR'),  # Environment variable
        os.path.normpath(os.path.join(exe_dir, '..', 'data')),  # Sibling data folder: C:\SenseMart_V1\data
        'C:\\SenseMart_V1\\data',  # Standard installation path
        os.path.expanduser('~\\SenseMart_V1\\data'),  # User home
    ]
    
    # Debug: Print checked paths
    print(f"[DEBUG] EXE location: {exe_dir}")
    print(f"[DEBUG] Bundle location (BUNDLE_PATH): {BUNDLE_PATH}")
    
    for data_dir in possible_data_dirs:
        if data_dir:
            print(f"[DEBUG] Checking for data directory: {data_dir}")
            if os.path.isdir(data_dir):
                # Found a writable data directory, use it for logs and database
                DATA_PATH = data_dir
                print(f"[CONFIG] ✓ Using external data directory: {data_dir}")
                break
            else:
                print(f"[DEBUG] Not found or not a directory")
    
    if DATA_PATH == BUNDLE_PATH:
        print(f"[WARNING] Could not find external data directory, using bundle: {DATA_PATH}")
    else:
        # Copy bundled files to external data directory on first run
        bundled_db = os.path.join(BUNDLE_PATH, 'database.db')
        external_db = os.path.join(DATA_PATH, 'database.db')
        if os.path.exists(bundled_db) and (not os.path.exists(external_db) or os.path.getsize(external_db) == 0):
            try:
                import shutil
                shutil.copy2(bundled_db, external_db)
                print(f"[CONFIG] ✓ Copied database from bundle to {external_db}")
            except Exception as e:
                print(f"[WARNING] Failed to copy database: {e}")
        
        # Ensure logs directory exists
        logs_dir = os.path.join(DATA_PATH, 'logs')
        if not os.path.isdir(logs_dir):
            try:
                os.makedirs(logs_dir, exist_ok=True)
                print(f"[CONFIG] ✓ Created logs directory: {logs_dir}")
            except Exception as e:
                print(f"[WARNING] Failed to create logs directory: {e}")
    
    # For templates and static files, always use bundle path
    BASE_PATH = BUNDLE_PATH
    # For logs and database, use the external data path
    DATA_BASE = DATA_PATH
else:
    # Running in dev mode
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    DATA_BASE = BASE_PATH  # Same location in dev mode

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
import sqlite3
from werkzeug.security import check_password_hash
import json
import os
import requests
import base64
import re

try:
    import sys
    import serial.serialutil
    # Patch ALL constants and classes from serialutil into serial module
    serial_module = sys.modules['serial']
    for attr in dir(serial.serialutil):
        if attr.isupper() or attr == 'SerialBase':  # Constants and base class
            setattr(serial_module, attr, getattr(serial.serialutil, attr))
    from serial.serialwin32 import Serial as Win32Serial
    PYSERIAL_AVAILABLE = True
except (ImportError, AttributeError):
    try:
        from serial.serialposix import Serial as PosixSerial
        PYSERIAL_AVAILABLE = True
    except ImportError:
        PYSERIAL_AVAILABLE = False
        Win32Serial = None
        PosixSerial = None

# Try to import AWS SNS for SMS alerts
try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    print("[WARNING] boto3 not available - SMS via AWS SNS disabled")

# Serial connection for weight sensor
SERIAL_PORT = 'COM6'
SERIAL_BAUD = 115200
serial_connection = None

def get_available_com_ports():
    """Get list of available COM ports"""
    available_ports = []
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        for port in ports:
            available_ports.append({
                'port': port.device,
                'description': port.description
            })
    except Exception as e:
        print(f"[INFO] Could not enumerate COM ports: {e}")
    
    # Always include COM6 as default
    if 'COM6' not in [p['port'] for p in available_ports]:
        available_ports.insert(0, {'port': 'COM6', 'description': 'COM6 (Default Weight Sensor)'})
    
    return available_ports

# Product weights mapping (slot -> weight in grams)
# These are defaults/fallbacks - actual weights come from Admin Panel (database)
PRODUCT_WEIGHTS = {
    1: 50,   # Slot 1 - 50g (fallback, use admin panel to set actual weight)
    2: 50,   # Slot 2 - 50g (fallback, use admin panel to set actual weight)
    3: 50,   # Slot 3 - 50g (fallback, use admin panel to set actual weight)
    4: 50    # Slot 4 - 50g (fallback, use admin panel to set actual weight)
}

# Weight tolerance (grams) - ±3g around expected weight (default)
WEIGHT_TOLERANCE = 3

# ESP32 connection status (global flag)
esp32_connected = False

# Mock mode for testing (set MOCK_WEIGHT_SENSOR=true to use simulated weights)
MOCK_WEIGHT_SENSOR = os.getenv('MOCK_WEIGHT_SENSOR', 'false').lower() == 'true'
if MOCK_WEIGHT_SENSOR:
    print("[WEIGHT SENSOR] [MOCK] MOCK MODE ENABLED - Using simulated weights")
    esp32_connected = True  # In mock mode, pretend ESP32 is always connected

# Mock weight tracking
MOCK_WEIGHTS = {1: 1000, 2: 950, 3: 850, 4: 750}  # Initial mock weights

def load_weight_tolerance_from_db():
    """Load weight tolerance from database settings table"""
    global WEIGHT_TOLERANCE
    try:
        db_path = os.path.join(DATA_BASE, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Check if settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if cursor.fetchone():
            # Try to get weight_tolerance setting
            cursor.execute("SELECT value FROM settings WHERE key='weight_tolerance'")
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    WEIGHT_TOLERANCE = int(row[0])
                    print(f"[SETTINGS] Loaded weight tolerance from database: +/-{WEIGHT_TOLERANCE}g")
                except (ValueError, TypeError):
                    print(f"[SETTINGS] Invalid weight tolerance in DB, using default: +/-{WEIGHT_TOLERANCE}g")
        conn.close()
    except Exception as e:
        print(f"[SETTINGS] Could not load weight tolerance from DB: {e}")

def save_weight_tolerance_to_db(tolerance):
    """Save weight tolerance to database settings table"""
    try:
        db_path = os.path.join(DATA_BASE, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Create settings table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert or update weight_tolerance
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES ('weight_tolerance', ?, CURRENT_TIMESTAMP)
        """, (str(tolerance),))
        conn.commit()
        conn.close()
        print(f"[SETTINGS] Saved weight tolerance to database: +/-{tolerance}g")
    except Exception as e:
        print(f"[SETTINGS] Could not save weight tolerance to DB: {e}")

# Load settings from database on startup
load_weight_tolerance_from_db()


def init_serial_connection():
    """Initialize serial connection to ESP32 on COM6"""
    global serial_connection
    if not PYSERIAL_AVAILABLE or Win32Serial is None:
        print("[WEIGHT SENSOR] pyserial not installed - weight verification disabled")
        return False
    try:
        print(f"[WEIGHT SENSOR] Attempting to connect to {SERIAL_PORT} at {SERIAL_BAUD} baud...")
        # Disable hardware flow control (rtscts, xonxoff) to prevent reset issues
        serial_connection = Win32Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2, dsrdtr=False, rtscts=False, xonxoff=False)
        
        # CRITICAL FIX: Set DTR and RTS lines to prevent ESP32 reset on connection
        serial_connection.dtr = False  
        serial_connection.rts = False
        
        print("[WEIGHT SENSOR] [WAIT] Waiting 2 seconds for ESP32 to stabilize...")
        time.sleep(2)  # Give ESP32 time to fully initialize after connection
        print(f"[WEIGHT SENSOR] [OK] Successfully connected to {SERIAL_PORT} at {SERIAL_BAUD} baud")
        
        # Verify ESP32 is responding with ID
        print("[WEIGHT SENSOR] [SEARCH] Verifying ESP32 is present...")
        serial_connection.reset_input_buffer()
        time.sleep(0.2)
        serial_connection.write(b'ID\r\n')
        time.sleep(0.5)
        
        response = b''
        if serial_connection.in_waiting:
            response = serial_connection.read(serial_connection.in_waiting)
            response_str = response.decode('utf-8', errors='ignore').strip()
            print(f"[WEIGHT SENSOR] ESP32 Response: {response_str}")
            if 'ESP' in response_str.upper():
                print(f"[WEIGHT SENSOR] [OK] ESP32 verified: {response_str}")
                return True
        
        print("[WEIGHT SENSOR] [WARNING] No ID response from ESP32, but connection open - continuing...")
        return True
        
    except PermissionError as e:
        print(f"[WEIGHT SENSOR] [ERROR] PERMISSION DENIED on {SERIAL_PORT}")
        print(f"[WEIGHT SENSOR] [WARNING] COM port is in use by another application")
        print(f"[WEIGHT SENSOR] Solutions:")
        print(f"   1. Close Arduino IDE, PuTTY, or any Terminal windows")
        print(f"   2. Unplug and replug the ESP32")
        print(f"   3. Restart the Vending Machine app")
        print(f"[WEIGHT SENSOR] App will continue in mock mode...")
        return False
    except Exception as e:
        print(f"[WEIGHT SENSOR] [ERROR] Could not connect to {SERIAL_PORT} at {SERIAL_BAUD} baud: {e}")
        print(f"[WEIGHT SENSOR] Error type: {type(e).__name__}")
        return False





def send_esp_command(command):
    """
    Send command to ESP32 via serial (non-blocking)
    Examples: LED1ON, LED1OFF, BUZZON, BUZZOFF
    Runs in background - ignores response/errors
    """
    global serial_connection
    
    def send_in_background():
        try:
            if MOCK_WEIGHT_SENSOR:
                print(f"[ESP COMMAND] [MOCK] Would send: {command}")
                return
            
            if serial_connection is None or not serial_connection.is_open:
                print(f"[ESP COMMAND] Serial not available for command: {command}")
                return
            
            # Send command to ESP (fire and forget)
            cmd = f"{command}\r\n".encode()
            print(f"[ESP COMMAND] Sending: {command}")
            serial_connection.write(cmd)
            # Don't wait for response - ESP may not respond to non-GET commands
            
        except Exception as e:
            print(f"[ESP COMMAND] {command} - Error (ignored): {e}")
    
    # Send in background thread so it doesn't block main flow
    threading.Thread(target=send_in_background, daemon=True).start()


def get_weight_reading():
    """
    Get weight reading from ESP32 via serial
    Format: B10070B20070B30070B40070 or b10950b20900b30450b40050
    Returns: {1: 950, 2: 900, 3: 450, 4: 50}
    """
    global serial_connection, MOCK_WEIGHTS, MOCK_WEIGHT_SENSOR
    
    # MOCK MODE - Returns simulated weights for testing
    if MOCK_WEIGHT_SENSOR:
        # Simulate weight change by decreasing a bin weight by 50-100g
        import random
        mock_result = dict(MOCK_WEIGHTS)
        # Randomly reduce one bin to simulate product removal
        slot = random.randint(1, 4)
        if mock_result[slot] > 100:
            mock_result[slot] -= random.randint(50, 100)
        print(f"[WEIGHT SENSOR] [MOCK] Simulated weights (slot {slot} reduced): {mock_result}")
        return mock_result

    try:
        if serial_connection is None:
            success = init_serial_connection()
            if not success:
                print("[WEIGHT SENSOR] [WARNING] Failed to initialize serial connection")
                return None
        
        if serial_connection is None or not serial_connection.is_open:
            print("[WEIGHT SENSOR] [WARNING] Serial connection not open")
            return None
        
        # Clear buffer BEFORE sending command
        serial_connection.reset_input_buffer()
        time.sleep(0.3)
        
        # Send GET command
        print("[WEIGHT SENSOR] [SEND] Sending GET command...")
        serial_connection.write(b'GET\r\n')
        time.sleep(0.5)  # Wait for ESP32 to process and respond
        
        # Read response - be more patient
        response = b''
        attempts = 0
        max_attempts = 10  # Try up to 1 second total
        
        while attempts < max_attempts:
            if serial_connection.in_waiting > 0:
                chunk = serial_connection.read(serial_connection.in_waiting)
                response += chunk
                print(f"[WEIGHT SENSOR] [RECEIVE] Received ({len(chunk)} bytes): {chunk}")
                time.sleep(0.1)
            else:
                attempts += 1
                time.sleep(0.1)
        
        if not response:
            print("[WEIGHT SENSOR] [WARNING] No response from sensor after GET command")
            return None
        
        # Parse response: B10070B20070B30070B40070 or b10950b20900b30450b40050
        response_str = response.decode('utf-8', errors='ignore').strip().lower()
        print(f"[WEIGHT SENSOR] 📊 Raw response: {response_str}")
        weights = {}
        
        # Parse format: b1<weight>b2<weight>b3<weight>b4<weight>
        # Weight can be 3-4 digits (decimal)
        pattern = r'b(\d)(\d{3,4})'
        matches = re.findall(pattern, response_str)
        
        if matches:
            for slot_str, weight_str in matches:
                try:
                    slot = int(slot_str)
                    weight = int(weight_str)
                    weights[slot] = weight
                    print(f"[WEIGHT SENSOR] ✓ Slot {slot}: {weight}g")
                except Exception as parse_err:
                    print(f"[WEIGHT SENSOR] [WARNING] Parse error on 'b{slot_str}{weight_str}': {parse_err}")
                    continue
        
        if weights:
            print(f"[WEIGHT SENSOR] [OK] Weights received: {weights}")
            return weights
        
        print(f"[WEIGHT SENSOR] [WARNING] Could not parse weights from: {response_str}")
        return None
            
    except Exception as e:
        print(f"[WEIGHT SENSOR] [WARNING] Error reading weight: {e}")
        import traceback
        traceback.print_exc()
        return None

# Try to import text-to-speech for voice announcements
try:
    import pyttsx3
    TTS_AVAILABLE = True
    tts_engine = pyttsx3.init()
    tts_engine.setProperty('rate', 150)
except ImportError:
    TTS_AVAILABLE = False
    print("[WARNING] pyttsx3 not available - voice announcements disabled")

# Try to import PDF generation library
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from io import BytesIO
    import qrcode
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("[WARNING] reportlab not available - PDF receipts disabled")

# Try to import speech recognition, but make it optional
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    print("[WARNING] SpeechRecognition not available - voice commands disabled")

# Global flag to control bot start/stop
bot_running = False
bot_thread = None

# Firebase imports
try:
    from firebase_config import get_firestore_db
    from firebase_db import (
        init_firebase_db, get_all_products, get_product_by_id, 
        update_product_stock, update_product, save_chat_message, 
        log_transaction, log_purchase, log_stock_update, update_current_stock
    )
    FIREBASE_ENABLED = init_firebase_db()
    if FIREBASE_ENABLED:
        print("[INFO] Firebase integration enabled!")
except Exception as e:
    print(f"[WARNING] Firebase not available: {e}")
    FIREBASE_ENABLED = False

# Local logging imports
from local_logs import (
    log_purchase_local, log_stock_update_local, log_transaction_local,
    update_stock_status_local, check_consecutive_sales_and_update_price
)


app = Flask(__name__, 
            template_folder=os.path.join(BASE_PATH, 'templates'),
            static_folder=os.path.join(BASE_PATH, 'static'))
app.secret_key = "supersecretkey"

# Configure file uploads
UPLOAD_FOLDER = os.path.join(BASE_PATH, 'static', 'product_images')
QR_FOLDER = os.path.join(BASE_PATH, 'static', 'qr_codes')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# =============== PATH HELPERS ===============

def get_logs_path(filename):
    """Get absolute path for log files - uses external data directory"""
    logs_dir = os.path.join(DATA_BASE, 'logs')
    # Ensure logs directory exists
    if not os.path.isdir(logs_dir):
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except Exception as e:
            print(f"[WARNING] Failed to create logs directory: {e}")
    return os.path.join(logs_dir, filename)

# =============== DEMAND-BASED PRICING ===============

def get_consecutive_purchases(product_id):
    """Get consecutive purchase count for a product in current session"""
    if 'purchase_history' not in session:
        session['purchase_history'] = []
    
    # Count consecutive purchases of this product from the end of history
    count = 0
    for purchase in reversed(session['purchase_history']):
        if purchase == str(product_id):
            count += 1
        else:
            break
    
    return count


def calculate_dynamic_price(product_id, base_price):
    """
    Calculate price with demand-based pricing
    If customer buys same product 3 times, 4th+ purchase gets 10% markup
    Returns rounded price (no decimals)
    """
    consecutive_count = get_consecutive_purchases(product_id)
    
    # If 4th or more consecutive purchase, apply 10% markup
    if consecutive_count >= 3:
        # Apply 10% markup
        dynamic_price = base_price * 1.10
        # Round to nearest integer
        return int(round(dynamic_price))
    
    # Otherwise return original rounded price
    return int(round(base_price))


def track_purchase(product_id):
    """Track a purchase in session history for demand-based pricing"""
    if 'purchase_history' not in session:
        session['purchase_history'] = []
    
    session['purchase_history'].append(str(product_id))
    session.modified = True


def get_best_selling_product():
    """Get the product ID with the most sales from transaction logs"""
    try:
        from local_logs import get_transaction_logs_local
        transactions = get_transaction_logs_local()
        
        if not transactions:
            return None
        
        # Count sales by product_id (only 'sold' transactions)
        sales_count = {}
        for txn in transactions:
            if txn.get('transaction_type') == 'sold':
                product_id = str(txn.get('product_id', ''))
                if product_id:
                    sales_count[product_id] = sales_count.get(product_id, 0) + txn.get('quantity', 1)
        
        # Find the product with most sales
        if sales_count:
            best_product = max(sales_count, key=sales_count.get)
            return int(best_product) if best_product else None
    except Exception as e:
        print(f"[INFO] Could not get best-selling product: {e}")
    
    return None

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global chat log for voice bot messages
chat_messages = []
MAX_MESSAGES = 50


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Helper function to add messages to chat log
def add_chat_message(msg):
    global chat_messages
    chat_messages.append(msg)
    if len(chat_messages) > MAX_MESSAGES:
        chat_messages.pop(0)
    
    # Chat logging to Firebase disabled - only transaction logs are saved


# ==================== API ENDPOINTS FOR SETTINGS ====================
@app.route("/api/com_ports")
def get_com_ports():
    """API endpoint to get available COM ports"""
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    ports = get_available_com_ports()
    return jsonify({'ports': ports, 'current': SERIAL_PORT})


@app.route("/api/update_serial_port/<port>", methods=['POST'])
def update_serial_port(port):
    """Update the serial port for weight sensor"""
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    global SERIAL_PORT, serial_connection
    SERIAL_PORT = port
    serial_connection = None  # Reset connection to force reconnect
    print(f"[SERIAL] Serial port updated to {port}")
    return jsonify({'success': True, 'message': f'Serial port updated to {port}'})


@app.route("/api/esp/connect", methods=['POST'])
def esp_connect():
    """
    Test ESP32 connection - Send ID and verify response contains "ESP"
    Used by admin panel to test connection after port selection
    STRICT MODE: Only succeeds if ESP32 responds with valid ESPVM or similar
    """
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    global esp32_connected
    
    # Get the selected COM port from request
    data = request.get_json()
    selected_port = data.get('port') if data else None
    
    if not selected_port:
        return jsonify({
            'success': False,
            'message': 'No COM port specified',
            'connected': False
        }), 400
    
    print("\n" + "="*60)
    print(f"[ADMIN TEST] Testing ESP32 on {selected_port} (STRICT MODE)...")
    print("="*60)
    
    temp_serial = None
    
    try:
        # Try to open the selected serial port (don't use global connection)
        print(f"[ADMIN TEST] [CONNECT] Attempting to connect to {selected_port} at {SERIAL_BAUD} baud...")
        try:
            temp_serial = Win32Serial(selected_port, SERIAL_BAUD, timeout=2, dsrdtr=False, rtscts=False, xonxoff=False)
            temp_serial.dtr = False
            temp_serial.rts = False
            time.sleep(0.5)
            print(f"[ADMIN TEST] [OK] Port {selected_port} opened successfully")
        except Exception as e:
            print(f"[ADMIN TEST] [ERROR] Could not open port {selected_port}: {e}")
            esp32_connected = False
            return jsonify({
                'success': False,
                'message': f'Could not open port {selected_port}. Port may be in use or invalid.',
                'connected': False
            }), 400
        
        if temp_serial is None or not temp_serial.is_open:
            print(f"[ADMIN TEST] [ERROR] Serial connection not open after initialization")
            esp32_connected = False
            return jsonify({
                'success': False,
                'message': 'Serial connection failed to open',
                'connected': False
            }), 400
        
        # Send ID command to verify ESP32 responds
        print(f"[ADMIN TEST] [SEND] Sending ID command to {selected_port}...")
        temp_serial.reset_input_buffer()
        time.sleep(0.2)
        temp_serial.write(b'ID\r\n')
        time.sleep(0.8)  # Wait longer for response
        
        # Read response from ESP32
        id_response = b''
        if temp_serial.in_waiting > 0:
            id_response = temp_serial.read(temp_serial.in_waiting)
        
        if not id_response:
            print(f"[ADMIN TEST] [ERROR] No response from {selected_port} (timeout waiting for ID response)")
            esp32_connected = False
            temp_serial.close()
            return jsonify({
                'success': False,
                'message': 'No response from ESP32. Check that device is powered on and COM port is correct.',
                'connected': False
            }), 400
        
        response_str = id_response.decode('utf-8', errors='ignore').strip()
        print(f"[ADMIN TEST] [RECEIVE] Received from {selected_port}: {response_str}")
        
        # Validate response contains ESP
        if 'ESP' not in response_str.upper():
            print(f"[ADMIN TEST] [ERROR] Invalid response from {selected_port}: '{response_str}' (expected response to contain 'ESP')")
            esp32_connected = False
            temp_serial.close()
            return jsonify({
                'success': False,
                'message': f'Invalid response from device: "{response_str}". This may not be an ESP32.',
                'connected': False
            }), 400
        
        # Success! Valid ESP32 response - now set this port as the active one
        print(f"[ADMIN TEST] [OK] ESP32 VERIFIED on {selected_port}! Response: {response_str}")
        
        # Update global SERIAL_PORT and close temporary connection
        global SERIAL_PORT, serial_connection
        SERIAL_PORT = selected_port
        
        # Close the temporary test connection
        if temp_serial and temp_serial.is_open:
            temp_serial.close()
        
        # Reset global connection to force reconnect with new port
        serial_connection = None
        
        esp32_connected = True
        
        return jsonify({
            'success': True,
            'message': f'[OK] Connected successfully to {selected_port}! Device: {response_str}',
            'connected': True,
            'device_id': response_str,
            'port': selected_port
        })
    
    except Exception as e:
        print(f"[ADMIN TEST] [ERROR] Unexpected error: {e}")
        esp32_connected = False
        if temp_serial and temp_serial.is_open:
            temp_serial.close()
        return jsonify({
            'success': False,
            'message': f'Connection error: {str(e)}',
            'connected': False
        }), 400


@app.route("/api/esp/status")
def esp_status():
    """Get ESP32 connection status"""
    global esp32_connected
    return jsonify({
        'connected': esp32_connected,
        'port': SERIAL_PORT,
        'status': 'Connected' if esp32_connected else 'Not Connected'
    })


@app.route("/api/esp/command", methods=['POST'])
def esp_command():
    """Send command to ESP32 (LED, BUZZ, etc.)"""
    data = request.get_json()
    command = data.get('command') if data else None
    
    if not command:
        return jsonify({'success': False, 'message': 'No command specified'}), 400
    
    # Validate command format (safety check)
    valid_commands = ['LED1ON', 'LED1OFF', 'LED2ON', 'LED2OFF', 'LED3ON', 'LED3OFF', 
                      'LED4ON', 'LED4OFF', 'BUZZON', 'BUZZOFF']
    
    if command not in valid_commands:
        print(f"[API] Invalid ESP32 command rejected: {command}")
        return jsonify({'success': False, 'message': 'Invalid command'}), 400
    
    # Send command in background (non-blocking)
    send_esp_command(command)
    
    return jsonify({
        'success': True,
        'message': f'Command sent: {command}',
        'command': command
    })


@app.route("/api/bot/start", methods=['POST'])
def bot_start():
    """Start the voice bot"""
    global bot_running
    bot_running = True
    print("[BOT] Voice bot started via API")
    add_chat_message("[BOT] Voice bot started! Say a product number or name (1, 2, 3, or 4)")
    return jsonify({
        'success': True,
        'message': 'Voice bot started',
        'bot_running': bot_running
    })


@app.route("/api/bot/stop", methods=['POST'])
def bot_stop():
    """Stop the voice bot"""
    global bot_running
    bot_running = False
    print("[BOT] Voice bot stopped via API")
    add_chat_message("[BOT] Voice bot stopped")
    return jsonify({
        'success': True,
        'message': 'Voice bot stopped',
        'bot_running': bot_running
    })


@app.route("/api/bot/status", methods=['GET'])
def bot_status():
    """Get voice bot status"""
    global bot_running
    return jsonify({
        'bot_running': bot_running,
        'sr_available': SR_AVAILABLE
    })


@app.route("/api/settings/weight-tolerance", methods=['GET', 'POST'])
def weight_tolerance_setting():
    """Get or update weight tolerance setting"""
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    global WEIGHT_TOLERANCE
    
    if request.method == 'GET':
        # Return current tolerance
        return jsonify({
            'tolerance': WEIGHT_TOLERANCE,
            'unit': 'grams',
            'description': f'±{WEIGHT_TOLERANCE}g around expected product weight'
        })
    
    elif request.method == 'POST':
        # Update tolerance
        data = request.get_json()
        tolerance = data.get('tolerance') if data else None
        
        if tolerance is None:
            return jsonify({'success': False, 'message': 'Tolerance value not provided'}), 400
        
        try:
            tolerance = int(tolerance)
            if tolerance < 1 or tolerance > 50:
                return jsonify({
                    'success': False, 
                    'message': 'Tolerance must be between 1g and 50g'
                }), 400
            
            WEIGHT_TOLERANCE = tolerance
            # Save to database for persistence
            save_weight_tolerance_to_db(tolerance)
            print(f"[SETTINGS] Weight tolerance updated to ±{tolerance}g and saved to database")
            
            return jsonify({
                'success': True,
                'message': f'Weight tolerance updated to ±{tolerance}g',
                'tolerance': tolerance
            })
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Invalid tolerance value'
            }), 400


@app.route("/api/test_weight_sensor", methods=['GET'])
def test_weight_sensor():
    """Test ESP32 weight sensor connection and reading"""
    print("\n" + "="*60)
    print("[TEST] Testing weight sensor connection...")
    print("="*60)
    
    weights = get_weight_reading()
    
    if weights:
        return jsonify({
            'success': True,
            'message': 'Weight sensor working!',
            'weights': weights
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to read from weight sensor',
            'current_port': SERIAL_PORT,
            'current_baud': SERIAL_BAUD
        }), 500


# Global variable to store previous weights for home screen monitoring
HOME_SCREEN_LAST_WEIGHTS = {}

@app.route("/api/check_sensor_home", methods=['GET'])
def check_sensor_home():
    """
    Check weight sensors on home screen and detect if products are taken
    This runs every 10 seconds in the background
    Returns products that have been taken with HSTXN transaction IDs
    """
    global HOME_SCREEN_LAST_WEIGHTS
    
    print("\n[HOME SCREEN SENSOR] Checking weight sensors...")
    
    # Get current weights
    current_weights = get_weight_reading()
    
    if not current_weights:
        print("[HOME SCREEN SENSOR] [WARNING] Could not read weights")
        return jsonify({
            'success': False,
            'message': 'Weight sensor unavailable',
            'products_taken': []
        })
    
    print(f"[HOME SCREEN SENSOR] Current weights: {current_weights}")
    print(f"[HOME SCREEN SENSOR] Last weights: {HOME_SCREEN_LAST_WEIGHTS}")
    
    products_taken = []
    
    # Compare with last weights to detect changes
    for slot in [1, 2, 3, 4]:
        # Use integer keys consistently (get_weight_reading returns int keys)
        current_weight = current_weights.get(slot, 0)
        last_weight = HOME_SCREEN_LAST_WEIGHTS.get(slot, 0)
        
        if last_weight > 0:  # Only check if we have a baseline
            weight_diff = last_weight - current_weight
            
            # If weight decreased, assume product was taken (threshold: > 30g)
            if weight_diff > 30:
                print(f"[HOME SCREEN SENSOR] [DETECT] Slot {slot}: Weight decreased by {weight_diff}g")
                
                # Get product info from this slot
                try:
                    conn = get_db_connection()
                    product = conn.execute("SELECT id, name, price, stock, weight FROM products WHERE id = ?", (slot,)).fetchone()
                    conn.close()
                    
                    if product:
                        product_dict = dict(product)
                        product_id = product_dict['id']
                        product_name = product_dict['name']
                        old_stock = product_dict['stock']
                        
                        # Calculate quantity taken based on weight difference
                        product_weight = int(product_dict.get('weight', 50))
                        quantity_taken = max(1, weight_diff // product_weight)
                        
                        # Update stock in database
                        new_stock = max(0, old_stock - quantity_taken)
                        conn = get_db_connection()
                        conn.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
                        conn.commit()
                        conn.close()
                        
                        # Generate HSTXN transaction ID (Home Screen Transaction)
                        transaction_id = f"HSTXN_{int(time.time() * 1000)}"
                        price = float(product_dict.get('price', 0))
                        
                        # Log the transaction locally (log_transaction_local already imported at module level)
                        log_transaction_local(
                            str(product_id),
                            product_name,
                            "purchase",
                            quantity=quantity_taken,
                            final_stock=new_stock,
                            transaction_type="sold",
                            price=price,
                            transaction_id=transaction_id
                        )
                        
                        print(f"[HOME SCREEN SENSOR] [LOG] Transaction {transaction_id}: {product_name} x{quantity_taken}, Stock: {old_stock} → {new_stock}")
                        
                        products_taken.append({
                            'product_id': product_id,
                            'name': product_name,
                            'quantity': quantity_taken,
                            'new_stock': new_stock,
                            'transaction_id': transaction_id,
                            'weight_diff': weight_diff
                        })
                    else:
                        print(f"[HOME SCREEN SENSOR] [WARNING] No product found for slot {slot}")
                except Exception as e:
                    print(f"[HOME SCREEN SENSOR] [ERROR] Failed to process product from slot {slot}: {e}")
                    import traceback
                    traceback.print_exc()
    
    # Update the baseline weights (use .update() to avoid race conditions)
    HOME_SCREEN_LAST_WEIGHTS.update(current_weights)
    
    return jsonify({
        'success': True,
        'current_weights': current_weights,
        'products_taken': products_taken,
        'timestamp': datetime.datetime.now().isoformat()
    })


# ==================== SMS ALERT FUNCTION ====================
def send_stock_alert_sms(product_name, current_stock, phone_number=None):
    """
    Send SMS alert via AWS SNS (100 FREE SMS per month!)
    
    Setup:
    1. Create AWS account: https://aws.amazon.com/
    2. Create IAM user with SNS permissions
    3. Get Access Key ID and Secret Access Key
    4. Set environment variables:
       - AWS_ACCESS_KEY_ID
       - AWS_SECRET_ACCESS_KEY
       - AWS_REGION (ap-south-1 for India)
       - ALERT_PHONE_NUMBER (+917025530975)
    
    Args:
        product_name: Name of the product
        current_stock: Current stock level
        phone_number: Phone number to send SMS to (optional)
    
    Returns:
        True if SMS sent successfully, False otherwise
    """
    if not AWS_AVAILABLE:
        print("[SMS ALERT] [WARNING] AWS SDK not installed. Install with: pip install boto3")
        log_sms_alert(product_name, current_stock, phone_number or '7025530975')
        return False
    
    try:
        # Get AWS credentials from environment
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_REGION', 'ap-south-1')
        
        if not access_key or not secret_key:
            print("[SMS ALERT] [WARNING] AWS credentials not configured.")
            print("   Set environment variables:")
            print("   - AWS_ACCESS_KEY_ID")
            print("   - AWS_SECRET_ACCESS_KEY")
            print("   - AWS_REGION (default: ap-south-1)")
            log_sms_alert(product_name, current_stock, phone_number or '7025530975')
            return False
        
        # Get phone number
        if phone_number is None:
            phone_number = os.getenv('ALERT_PHONE_NUMBER', '+917025530975')
        
        # Ensure phone number has + prefix
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        # Message
        message = f"STOCK ALERT: {product_name} stock is now {current_stock} units (below 50). Please restock soon!"
        
        # Create SNS client
        sns_client = boto3.client(
            'sns',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Send SMS
        response = sns_client.publish(
            PhoneNumber=phone_number,
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SmsType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
        
        print(f"[SMS ALERT] [OK] Stock alert sent for {product_name} (Stock: {current_stock}) to {phone_number}")
        print(f"   Message ID: {response['MessageId']}")
        return True
        
    except Exception as e:
        print(f"[SMS ALERT ERROR] [ERROR] {str(e)}")
        # Log as fallback
        phone_num = phone_number if phone_number else '7025530975'
        log_sms_alert(product_name, current_stock, phone_num)
        return False



def log_sms_alert(product_name, current_stock, phone_number):
    """Log SMS alert to file as fallback when API fails"""
    try:
        os_path = os.path.join('logs', 'sms_alerts.json')
        os.makedirs(os.path.dirname(os_path), exist_ok=True)
        
        alert_record = {
            'timestamp': datetime.datetime.now().isoformat(),
            'product': product_name,
            'stock': current_stock,
            'phone': phone_number,
            'status': 'logged'
        }
        
        # Append to log file
        with open(os_path, 'a') as f:
            f.write(json.dumps(alert_record) + '\n')
        
        print(f"[SMS LOG] [LOG] Alert logged to file: {product_name}")
    except Exception as e:
        print(f"[SMS LOG ERROR] Could not write to log file: {e}")





# ==================== END SMS ALERT FUNCTION ====================


# ------------------ DB CONNECTION ------------------
def get_db_connection():
    db_path = os.path.join(DATA_BASE, "database.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------ SEARCH ENDPOINT (FOR AUTOCOMPLETE) ------------------
@app.route("/search")
def search():
    """Search products by name (for autocomplete)"""
    query = request.args.get("q", "").strip().lower()
    
    if not query or len(query) < 1:
        return jsonify([])
    
    try:
        if FIREBASE_ENABLED:
            products = get_all_products()
            
            # Check SQLite product count
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM products")
                sqlite_count = cursor.fetchone()[0]
                conn.close()
            except:
                sqlite_count = 0
            
            # Check if Firebase products have required fields (name, price)
            has_required_fields = (products and 
                                  all(product.get('name') and product.get('price') for product in products))
            
            # If Firebase is empty, has fewer products than SQLite, or missing required fields, fall back to SQLite
            if not products or len(products) < sqlite_count or not has_required_fields:
                reason = "empty" if not products else "fewer products" if len(products) < sqlite_count else "missing required fields"
                print(f"[INFO] Firebase products {reason}, using SQLite in search")
                conn = get_db_connection()
                products = conn.execute("SELECT id, name, price, stock, image FROM products").fetchall()
                conn.close()
                products = [dict(p) for p in products]
            else:
                # Also fetch image data from SQLite to merge
                try:
                    conn = get_db_connection()
                    sqlite_products = conn.execute("SELECT id, image FROM products").fetchall()
                    conn.close()
                    
                    # Create a dict of images from SQLite
                    image_map = {str(row[0]): row[1] for row in sqlite_products}
                    
                    # Merge image data into Firebase products
                    for product in products:
                        product_id = str(product.get('id'))
                        if product_id in image_map and not product.get('image'):
                            product['image'] = image_map[product_id]
                except Exception as e:
                    print(f"[WARNING] Failed to merge image data in search: {e}")
        else:
            conn = get_db_connection()
            products = conn.execute("SELECT id, name, price, stock, image FROM products").fetchall()
            conn.close()
            products = [dict(p) for p in products]
        
        # Filter products that start with the query
        results = []
        for product in products:
            if product and product.get('name', '').lower().startswith(query):
                results.append({
                    'id': product.get('id'),
                    'name': product.get('name'),
                    'price': product.get('price'),
                    'stock': product.get('stock'),
                    'image': product.get('image')
                })
        
        return jsonify(results[:10])  # Return max 10 results
    
    except Exception as e:
        print(f"[ERROR] Search error: {e}")
        return jsonify([])


# ------------------ CHAT LOG ENDPOINT ------------------
@app.route("/chat_log")
def chat_log():
    return jsonify(chat_messages)


@app.route("/logs")
def view_logs():
    """Display all logs"""
    from local_logs import get_purchase_logs_local, get_stock_logs_local, get_transaction_logs_local, get_stock_status_local
    
    purchases = get_purchase_logs_local()
    stocks = get_stock_logs_local()
    transactions = get_transaction_logs_local()
    status = get_stock_status_local()
    
    return render_template("logs.html", 
                         purchases=purchases, 
                         stocks=stocks, 
                         transactions=transactions,
                         status=status)


# ------------------ HOME PAGE ------------------
@app.route("/")
def index():
    # Clear purchases on home page return
    if 'purchases' in session:
        session.pop('purchases', None)
    
    products = None
    
    if FIREBASE_ENABLED:
        # Fetch from Firebase
        products = get_all_products()
        
        # Check SQLite product count
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products")
            sqlite_count = cursor.fetchone()[0]
            conn.close()
        except:
            sqlite_count = 0
        
        # Check if Firebase products have required fields (name, price)
        has_required_fields = (products and 
                              all(product.get('name') and product.get('price') for product in products))
        
        # If Firebase is empty, has fewer products than SQLite, or missing required fields, fall back to SQLite
        if not products or len(products) < sqlite_count or not has_required_fields:
            reason = "empty" if not products else "fewer products" if len(products) < sqlite_count else "missing required fields"
            print(f"[INFO] Firebase products {reason}, using SQLite")
            conn = get_db_connection()
            products = conn.execute("SELECT * FROM products").fetchall()
            conn.close()
            products = [dict(p) for p in products]
        else:
            # Also fetch image data from SQLite to merge
            # This ensures images are displayed even if Firebase doesn't have them
            try:
                conn = get_db_connection()
                sqlite_products = conn.execute("SELECT id, image FROM products").fetchall()
                conn.close()
                
                # Create a dict of images from SQLite
                image_map = {str(row[0]): row[1] for row in sqlite_products}
                
                # Merge image data into Firebase products
                for product in products:
                    product_id = str(product.get('id'))
                    if product_id in image_map and not product.get('image'):
                        product['image'] = image_map[product_id]
                
                print("[INFO] Merged image data from SQLite into Firebase products")
            except Exception as e:
                print(f"[WARNING] Failed to merge image data: {e}")
    else:
        # Fallback to SQLite
        conn = get_db_connection()
        products = conn.execute("SELECT * FROM products").fetchall()
        conn.close()
        # Convert to dictionaries for consistent template rendering
        products = [dict(p) for p in products]
    
    # =============== APPLY DEMAND-BASED PRICING ===============
    # Calculate dynamic prices for all products based on session purchase history
    best_seller_id = get_best_selling_product()
    
    for product in products:
        product_id = product.get('id')
        original_price = float(product.get('price', 0))
        dynamic_price = calculate_dynamic_price(product_id, original_price)
        consecutive_purchases = get_consecutive_purchases(product_id)
        
        # Store both original and dynamic prices
        product['original_price'] = original_price
        product['price'] = dynamic_price
        product['consecutive_purchases'] = consecutive_purchases
        product['is_surge_priced'] = (consecutive_purchases >= 3)
        
        # Mark best-selling product
        product['is_best_seller'] = (product_id == best_seller_id)
    
    return render_template("index.html", products=products)


# ------------------ BUY PRODUCT ------------------
@app.route("/buy/<int:id>")
def buy(id):
    if FIREBASE_ENABLED:
        item = get_product_by_id(str(id))
        # Fall back to SQLite if Firebase returns None or missing required fields
        if item is None or not item.get('name') or not item.get('price'):
            conn = get_db_connection()
            item = conn.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
            conn.close()
            if item:
                item = dict(item)
    else:
        conn = get_db_connection()
        item = conn.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
        conn.close()
        if item:
            item = dict(item)

    if item is None:
        flash("Product not found!", "danger")
        return redirect(url_for("index"))

    door_number = id  # Each product has a door number based on ID
    
    # =============== DEMAND-BASED PRICING ===============
    original_price = float(item['price'])
    dynamic_price = calculate_dynamic_price(id, original_price)
    consecutive_purchases = get_consecutive_purchases(id)
    
    # Store both original and dynamic price in item
    item['original_price'] = original_price
    item['price'] = dynamic_price
    item['consecutive_purchases'] = consecutive_purchases
    item['is_surge_priced'] = (consecutive_purchases >= 3)
    
    if consecutive_purchases >= 3:
        surge_info = f" [SURGE: Rs{dynamic_price} instead of Rs{int(original_price)}]"
        print(f"[PRICING] DEMAND-BASED: {item['name']} - {consecutive_purchases}th+ consecutive purchase - Applying 10% markup{surge_info}")
    else:
        print(f"[PRICING] Regular pricing: {item['name']} - Rs{dynamic_price} (consecutive purchases: {consecutive_purchases})")
    
    print(f"[PAYMENT] Payment initiated for product {item['name']} (Door {door_number})")
    add_chat_message(f"[SYSTEM] Product selected: {item['name']}")

    if item["stock"] > 0:
        # [WARNING] DO NOT REDUCE STOCK HERE - Wait for weight verification
        # Stock will only be reduced after weight verification succeeds
        print(f"[PAYMENT] Proceeding to weight verification for product {item['name']}")
        message = f"Click TAKE PRODUCT to start weight-based verification..."
        add_chat_message(f"[SYSTEM] Ready for weight verification")
    else:
        message = f"{item['name']} is OUT OF STOCK!"
        add_chat_message(f"[MACHINE] {item['name']} is OUT OF STOCK!")

    return render_template("buy.html", item=item, message=message, door_number=door_number)

@app.route("/api/weight/initial/<int:product_id>")
def get_initial_weight(product_id):
    """Get initial weight reading before purchase"""
    global serial_connection
    
    # In MOCK mode, skip serial connection - just get weights directly
    if not MOCK_WEIGHT_SENSOR:
        # Ensure connection is open
        if serial_connection is None:
            success = init_serial_connection()
            if not success:
                print("[WEIGHT] [ERROR] Could not initialize serial connection for initial weight")
                return jsonify({'success': False, 'error': 'Weight sensor not available'}), 500
    
    weights = get_weight_reading()
    if weights:
        print(f"[WEIGHT INITIAL] [OK] Initial weights captured: {weights}")
        return jsonify({
            'success': True,
            'weights': weights,
            'product_id': product_id,
            'timestamp': datetime.datetime.now().isoformat()
        })
    
    print("[WEIGHT INITIAL] [ERROR] Could not read initial weight")
    return jsonify({'success': False, 'error': 'Could not read weight'}), 500


@app.route("/api/weight/verify/<int:product_id>", methods=['POST'])
def verify_weight_change(product_id):
    """Verify weight change after product is dispensed"""
    data = request.get_json()
    initial_weights = data.get('initial_weights', {})
    transaction_id = data.get('transaction_id', f"TXN_{int(time.time() * 1000)}")
    
    print(f"\n{'='*60}")
    print(f"[WEIGHT VERIFY] Starting verification for product {product_id}")
    print(f"[WEIGHT VERIFY] Transaction ID: {transaction_id}")
    print(f"[WEIGHT VERIFY] Initial weights received: {initial_weights}")
    print(f"{'='*60}")
    
    # Get final weight reading
    # First check if final_weights were provided in the request (for testing or offline mode)
    final_weights = data.get('final_weights')
    if not final_weights:
        final_weights = get_weight_reading()
    
    print(f"[WEIGHT VERIFY] Final weights received: {final_weights}")
    
    # If weight sensor not available, auto-pass (weight sensor optional)
    sensor_unavailable = not final_weights
    if sensor_unavailable:
        print(f"[WEIGHT VERIFY] [!] WARNING: Could not read final weight - Weight sensor unavailable!")
        print(f"[WEIGHT VERIFY] [OK] AUTO-PASSING verification (weight sensor optional)")
        print(f"{'='*60}\n")
        weight_verified = True
        weight_diff = 0
        expected_weight = 0
    else:
        # Check weight change - NOW WITH MULTI-BIN DETECTION
        product_slot = product_id  # Assuming product_id corresponds to slot
        # Try both int and str keys
        initial_weight = initial_weights.get(product_slot, initial_weights.get(str(product_slot), 0))
        final_weight = final_weights.get(product_slot, final_weights.get(str(product_slot), 0))
        weight_diff = initial_weight - final_weight
        
        # Get expected weight from database/Firebase (entered by admin)
        # Always prioritize database over Firebase for most accurate data
        expected_weight = 50  # Default fallback
        try:
            # ALWAYS check SQLite first as primary source
            conn = get_db_connection()
            result = conn.execute("SELECT weight FROM products WHERE id = ?", (product_id,)).fetchone()
            conn.close()
            
            if result and result[0]:
                expected_weight = int(result[0])
                print(f"[WEIGHT VERIFY] [DATA] Fetched weight from SQLite: {expected_weight}g for product {product_id}")
            else:
                print(f"[WEIGHT VERIFY] [!] No weight in SQLite for product {product_id}, trying Firebase...")
                if FIREBASE_ENABLED:
                    product_data = get_product_by_id(str(product_id))
                    if product_data and product_data.get('weight'):
                        expected_weight = int(product_data.get('weight', 50))
                        print(f"[WEIGHT VERIFY] [DATA] Fetched weight from Firebase: {expected_weight}g for product {product_id}")
        except Exception as e:
            print(f"[WEIGHT VERIFY] [!] Could not fetch product weight from DB: {e}, using default 50g")
            expected_weight = PRODUCT_WEIGHTS.get(product_slot, 50)
        
        tolerance = WEIGHT_TOLERANCE  # ±Xg tolerance around expected weight
        
        print(f"[WEIGHT VERIFY] Slot {product_slot}: Initial={initial_weight}g, Final={final_weight}g, Diff={weight_diff}g")
        print(f"[WEIGHT VERIFY] Expected weight per product: {expected_weight}g ±{tolerance}g")
        
        # MULTI-BIN DETECTION: Check all bins for weight changes
        print(f"[WEIGHT VERIFY] ===== MULTI-BIN DETECTION =====\"")
        print(f"[WEIGHT VERIFY] Initial weights all bins: {initial_weights}")
        print(f"[WEIGHT VERIFY] Final weights all bins: {final_weights}")
        
        # Calculate weight delta for all bins
        total_weight_delta = 0
        other_bin_deltas = {}
        target_bin_delta = 0
        
        for slot in [1, 2, 3, 4]:
            initial = initial_weights.get(slot, initial_weights.get(str(slot), 0))
            final = final_weights.get(slot, final_weights.get(str(slot), 0))
            delta = initial - final
            
            if delta > 0:
                total_weight_delta += delta
                if slot == product_slot:
                    target_bin_delta = delta
                else:
                    other_bin_deltas[slot] = delta
                    print(f"[WEIGHT VERIFY] [DELTA] OTHER BIN DELTA: Slot {slot} lost {delta}g (user may have taken from bin {slot} too)")
        
        if other_bin_deltas:
            print(f"[WEIGHT VERIFY] [!] Multi-bin detection: Products taken from bins: {product_slot} + {list(other_bin_deltas.keys())}")
            weight_diff = total_weight_delta  # Use total weight delta instead of just target bin
            print(f"[WEIGHT VERIFY] Using TOTAL weight delta: {weight_diff}g (target bin: {target_bin_delta}g + other bins: {sum(other_bin_deltas.values())}g)")
        
        print(f"[WEIGHT VERIFY] ===== END MULTI-BIN DETECTION =====\"")
        
        # Calculate quantity of products taken
        # Allow tolerance for each product (e.g., if taking 2x60g products, expect 120g but allow ±10g per product = ±20g total)
        quantity = round(weight_diff / expected_weight) if expected_weight > 0 else 1
        
        # If multiple bins affected, allow up to 8 products (2 per bin × 4 bins)
        # Otherwise limit to 1-4 products (single bin max)
        if other_bin_deltas:
            quantity = max(1, min(quantity, 8))  # Multi-bin: allow up to 8 products
            print(f"[WEIGHT VERIFY] Multi-bin detected: allowing up to 8 products")
        else:
            quantity = max(1, min(quantity, 4))  # Single bin: limit to 4 products max
        
        # Calculate expected range for detected quantity
        expected_range_min = (expected_weight - tolerance) * quantity
        expected_range_max = (expected_weight + tolerance) * quantity
        
        print(f"[WEIGHT VERIFY] Detected quantity: {quantity} product(s)")
        print(f"[WEIGHT VERIFY] Expected range for {quantity} product(s): {expected_range_min}g - {expected_range_max}g")
        
        # Check if weight diff matches the detected quantity
        weight_verified = expected_range_min <= weight_diff <= expected_range_max
        
        if weight_verified:
            print(f"[WEIGHT VERIFY] [PASS] - {quantity} product(s) taken! Weight change: {weight_diff}g")
            print(f"{'='*60}\n")
        else:
            print(f"[WEIGHT VERIFY] [FAIL] - Weight change: {weight_diff}g does not match any expected quantity")
            print(f"[WEIGHT VERIFY] DEBUG - Expected 1x: {expected_weight-tolerance}g-{expected_weight+tolerance}g, 2x: {(expected_weight-tolerance)*2}g-{(expected_weight+tolerance)*2}g, 3x: {(expected_weight-tolerance)*3}g-{(expected_weight+tolerance)*3}g")
            print(f"{'='*60}\n")
            return jsonify({
                'success': True,
                'verified': False,
                'quantity': 0,
                'quantity_text': 'No products detected',
                'weight_diff': weight_diff,
                'expected_weight': expected_weight,
                'message': f'[FAIL] No products detected. Weight change ({weight_diff}g) does not match expected ranges. Check that products were taken from door.'
            })
    
    # [OK] WEIGHT VERIFIED - NOW REDUCE STOCK AND LOG TRANSACTION
    if weight_verified:
        try:
            # Get product details for the target bin
            if FIREBASE_ENABLED:
                item = get_product_by_id(str(product_id))
                # If Firebase returns None or missing required fields, fall back to SQLite
                if item is None or not item.get('name') or not item.get('price'):
                    conn = get_db_connection()
                    item = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
                    conn.close()
                    if item:
                        item = dict(item)
            else:
                conn = get_db_connection()
                item = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
                conn.close()
                if item:
                    item = dict(item)
            
            if item:
                old_stock = item.get('stock', 0)
                product_name = item.get('name', f'Product {product_id}')
                price = item.get('price', 0)
                
                # MULTI-BIN AMOUNT CALCULATION: If multiple bins accessed, sum prices from all bins
                total_amount = 0
                target_bin_products = 0  # Track products from target bin
                bin_stock_updates = {}   # Track stock updates for all bins
                
                if other_bin_deltas:
                    # Multiple bins accessed - need to charge for all of them
                    print(f"[MULTI-BIN BILLING] Calculating prices for multiple bins...")
                    print(f"[MULTI-BIN STOCK] Preparing stock reductions for multiple bins...")
                    
                    # Price and stock for target bin
                    target_bin_products = max(1, round(target_bin_delta / expected_weight)) if expected_weight > 0 else 1
                    target_bin_amount = price * target_bin_products
                    total_amount += target_bin_amount
                    bin_stock_updates[product_id] = target_bin_products  # Will reduce target bin by this amount
                    print(f"[MULTI-BIN BILLING] Bin {product_id}: {target_bin_products} product(s) × ${price:.2f} = ${target_bin_amount:.2f}")
                    print(f"[MULTI-BIN STOCK] Bin {product_id}: Will reduce stock by {target_bin_products}")
                    
                    # Prices and stock for other bins
                    for other_bin in other_bin_deltas.keys():
                        try:
                            if FIREBASE_ENABLED:
                                other_item = get_product_by_id(str(other_bin))
                                # If Firebase returns None or missing required fields, fall back to SQLite
                                if other_item is None or not other_item.get('name') or not other_item.get('price'):
                                    conn = get_db_connection()
                                    other_item = conn.execute("SELECT * FROM products WHERE id = ?", (other_bin,)).fetchone()
                                    conn.close()
                                    if other_item:
                                        other_item = dict(other_item)
                            else:
                                conn = get_db_connection()
                                other_item = conn.execute("SELECT * FROM products WHERE id = ?", (other_bin,)).fetchone()
                                conn.close()
                                if other_item:
                                    other_item = dict(other_item)
                            
                            if other_item:
                                other_price = float(other_item.get('price', 0))
                                other_bin_products = max(1, round(other_bin_deltas[other_bin] / expected_weight)) if expected_weight > 0 else 1
                                other_bin_amount = other_price * other_bin_products
                                total_amount += other_bin_amount
                                bin_stock_updates[other_bin] = other_bin_products  # Will reduce other bin by this amount
                                print(f"[MULTI-BIN BILLING] Bin {other_bin}: {other_bin_products} product(s) × ${other_price:.2f} = ${other_bin_amount:.2f}")
                                print(f"[MULTI-BIN STOCK] Bin {other_bin}: Will reduce stock by {other_bin_products}")
                            else:
                                print(f"[MULTI-BIN BILLING] WARNING: Bin {other_bin} not found, charging default price")
                                other_bin_products = max(1, round(other_bin_deltas[other_bin] / expected_weight)) if expected_weight > 0 else 1
                                other_bin_amount = price * other_bin_products
                                total_amount += other_bin_amount
                                bin_stock_updates[other_bin] = other_bin_products
                        except Exception as e:
                            print(f"[MULTI-BIN BILLING] Exception fetching price for bin {other_bin}: {e}, using ${price:.2f}")
                            other_bin_products = max(1, round(other_bin_deltas[other_bin] / expected_weight)) if expected_weight > 0 else 1
                            other_bin_amount = price * other_bin_products
                            total_amount += other_bin_amount
                            bin_stock_updates[other_bin] = other_bin_products
                    
                    print(f"[MULTI-BIN BILLING] [OK] TOTAL AMOUNT: ${total_amount:.2f} (from {len(other_bin_deltas) + 1} bins)")
                else:
                    # Single bin - use simple calculation
                    total_amount = price * quantity
                    target_bin_products = quantity
                    bin_stock_updates[product_id] = quantity
                
                # Determine image path
                image_path = f"/static/captures/capture_{transaction_id}.jpg"
                
                # UPDATE STOCK FOR ALL AFFECTED BINS
                print(f"[MULTI-BIN STOCK] ===== UPDATING STOCK FOR ALL BINS =====")
                for bin_id, reduce_by in bin_stock_updates.items():
                    try:
                        if FIREBASE_ENABLED:
                            bin_item = get_product_by_id(str(bin_id))
                            # If Firebase returns None, fall back to SQLite
                            if bin_item is None:
                                conn = get_db_connection()
                                bin_item = conn.execute("SELECT * FROM products WHERE id = ?", (bin_id,)).fetchone()
                                conn.close()
                                if bin_item:
                                    bin_item = dict(bin_item)
                            
                            if bin_item:
                                bin_old_stock = bin_item.get('stock', 0)
                                bin_new_stock = max(0, bin_old_stock - reduce_by)
                                update_product_stock(str(bin_id), bin_new_stock)
                                log_stock_update(str(bin_id), bin_item.get('name', f'Product {bin_id}'), bin_old_stock, bin_new_stock, reason="SOLD")
                                print(f"[MULTI-BIN STOCK] [OK] Bin {bin_id}: {bin_old_stock} -> {bin_new_stock} (reduced by {reduce_by})")
                        else:
                            conn = get_db_connection()
                            bin_row = conn.execute("SELECT stock, name FROM products WHERE id = ?", (bin_id,)).fetchone()
                            if bin_row:
                                bin_old_stock = bin_row[0]
                                bin_name = bin_row[1]
                                bin_new_stock = max(0, bin_old_stock - reduce_by)
                                conn.execute("UPDATE products SET stock = ? WHERE id = ?", (bin_new_stock, bin_id))
                                conn.commit()
                                log_stock_update(str(bin_id), bin_name, bin_old_stock, bin_new_stock, reason="SOLD")
                                print(f"[MULTI-BIN STOCK] [OK] Bin {bin_id}: {bin_old_stock} -> {bin_new_stock} (reduced by {reduce_by})")
                            conn.close()
                    except Exception as e:
                        print(f"[MULTI-BIN STOCK] [ERROR] Error updating stock for bin {bin_id}: {e}")
                
                print(f"[MULTI-BIN STOCK] ===== END STOCK UPDATE =====")
                
                # Use target bin's new stock for logging (for primary product)
                new_stock = bin_stock_updates.get(product_id, quantity)
                if FIREBASE_ENABLED:
                    target_item = get_product_by_id(str(product_id))
                    if target_item:
                        new_stock = target_item.get('stock', 0)
                else:
                    conn = get_db_connection()
                    result = conn.execute("SELECT stock FROM products WHERE id = ?", (product_id,)).fetchone()
                    conn.close()
                    if result:
                        new_stock = result[0]
                
                # Log all transactions with image path and transaction ID
                log_purchase_local(str(product_id), product_name, price, quantity=quantity)
                log_stock_update_local(str(product_id), product_name, old_stock, new_stock, reason="SOLD")
                
                # Also log to Firebase
                if FIREBASE_ENABLED:
                    log_purchase(str(product_id), product_name, price, quantity=quantity)
                    log_stock_update(str(product_id), product_name, old_stock, new_stock, reason="SOLD")
                
                # Log transaction for target bin
                log_transaction_local(str(product_id), product_name, "purchase", quantity=target_bin_products if target_bin_products > 0 else quantity, final_stock=new_stock, transaction_type="sold", price=float(price), transaction_id=transaction_id, image_path=image_path)
                
                # If multi-bin purchase, log each bin as separate transaction with same timestamp
                if other_bin_deltas:
                    timestamp = datetime.datetime.now().isoformat()
                    for other_bin in sorted(other_bin_deltas.keys()):
                        try:
                            if FIREBASE_ENABLED:
                                other_item = get_product_by_id(str(other_bin))
                                # If Firebase returns None or missing required fields, fall back to SQLite
                                if other_item is None or not other_item.get('name') or not other_item.get('price'):
                                    conn = get_db_connection()
                                    other_item = conn.execute("SELECT * FROM products WHERE id = ?", (other_bin,)).fetchone()
                                    conn.close()
                                    if other_item:
                                        other_item = dict(other_item)
                            else:
                                conn = get_db_connection()
                                other_item = conn.execute("SELECT * FROM products WHERE id = ?", (other_bin,)).fetchone()
                                conn.close()
                                if other_item:
                                    other_item = dict(other_item)
                            
                            if other_item:
                                other_name = other_item.get('name', f'Product {other_bin}')
                                other_bin_qty = bin_stock_updates.get(other_bin, 1)
                                other_bin_new_stock = other_item.get('stock', 0) if FIREBASE_ENABLED else (get_db_connection().execute("SELECT stock FROM products WHERE id = ?", (other_bin,)).fetchone()[0] if get_db_connection() else 0)
                                
                                # Log each other bin purchase with same transaction ID but same timestamp
                                log_transaction_local(str(other_bin), other_name, "purchase", quantity=other_bin_qty, final_stock=other_bin_new_stock, transaction_type="sold", price=float(other_item.get('price', 0)), transaction_id=transaction_id, image_path=image_path)
                        except Exception as e:
                            print(f"[MULTI-BIN LOGGING] Could not log transaction for bin {other_bin}: {e}")
                
                # Also log to Firebase if enabled - log target bin first, then other bins with same timestamp
                if FIREBASE_ENABLED:
                    log_transaction(str(product_id), product_name, transaction_id=transaction_id, quantity=target_bin_products if target_bin_products > 0 else quantity)
                    
                    if other_bin_deltas:
                        for other_bin in sorted(other_bin_deltas.keys()):
                            try:
                                other_item = get_product_by_id(str(other_bin))
                                # If Firebase returns None or missing required fields, fall back to SQLite
                                if other_item is None or not other_item.get('name') or not other_item.get('price'):
                                    conn = get_db_connection()
                                    other_item = conn.execute("SELECT * FROM products WHERE id = ?", (other_bin,)).fetchone()
                                    conn.close()
                                    if other_item:
                                        other_item = dict(other_item)
                                
                                if other_item:
                                    other_name = other_item.get('name', f'Product {other_bin}')
                                    other_bin_qty = bin_stock_updates.get(other_bin, 1)
                                    log_transaction(str(other_bin), other_name, transaction_id=transaction_id, quantity=other_bin_qty)
                            except Exception as e:
                                print(f"[MULTI-BIN FIREBASE LOGGING] Could not log transaction for bin {other_bin}: {e}")
                
                update_stock_status_local(str(product_id), new_stock)

                
                # Send stock alert SMS if stock is low
                if new_stock < 50:
                    send_stock_alert_sms(product_name, new_stock)
                
                # Check for consecutive sales price increase
                check_consecutive_sales_and_update_price(str(product_id), price)
                
                # Log purchase with multi-bin info if applicable
                if quantity == 1:
                    msg = f"[PURCHASE COMPLETE] Product {product_id} ({product_name}) sold. Stock: {old_stock} → {new_stock}"
                else:
                    if other_bin_deltas:
                        msg = f"[PURCHASE COMPLETE] {quantity}x products from MULTIPLE BINS (Bin {product_id} + Bins {list(other_bin_deltas.keys())}) sold! Total: ${total_amount:.2f}. Stock: {old_stock} → {new_stock}"
                    else:
                        msg = f"[PURCHASE COMPLETE] {quantity}x Product {product_id} ({product_name}) sold! Total: ${total_amount:.2f}. Stock: {old_stock} → {new_stock}"
                
                print(msg)
                
                # =============== TRACK PURCHASE FOR DEMAND-BASED PRICING ===============
                track_purchase(product_id)
                if other_bin_deltas:
                    for other_bin in other_bin_deltas.keys():
                        track_purchase(other_bin)
                
                # More detailed message for multi-bin purchases
                if other_bin_deltas:
                    add_chat_message(f"[MACHINE] 🎯 MULTI-BIN PURCHASE: {quantity} products from bins {[product_id] + list(other_bin_deltas.keys())}! Total: ${total_amount:.2f}")
                else:
                    add_chat_message(f"[MACHINE] {quantity}x {product_name} purchased! Total: ${total_amount:.2f}. Stock: {new_stock}")
                
                # Build bins_info for display
                bins_info = f"Bin {product_id}"
                
                # Build items list for receipt
                items_list = []
                
                if other_bin_deltas:
                    other_bins_list = ', '.join([f"Bin {b}" for b in sorted(other_bin_deltas.keys())])
                    bins_info = f"Bin {product_id} + {other_bins_list}"
                    
                    # Add target bin item
                    items_list.append({
                        'name': product_name,
                        'count': target_bin_products,
                        'price': price
                    })
                    
                    # Add other bin items
                    for other_bin in sorted(other_bin_deltas.keys()):
                        try:
                            if FIREBASE_ENABLED:
                                other_item = get_product_by_id(str(other_bin))
                                # If Firebase returns None or missing required fields, fall back to SQLite
                                if other_item is None or not other_item.get('name') or not other_item.get('price'):
                                    conn = get_db_connection()
                                    other_item = conn.execute("SELECT * FROM products WHERE id = ?", (other_bin,)).fetchone()
                                    conn.close()
                                    if other_item:
                                        other_item = dict(other_item)
                            else:
                                conn = get_db_connection()
                                other_item = conn.execute("SELECT * FROM products WHERE id = ?", (other_bin,)).fetchone()
                                conn.close()
                                if other_item:
                                    other_item = dict(other_item)
                            
                            if other_item:
                                other_name = other_item.get('name', f'Product {other_bin}')
                                other_price = other_item.get('price', 0)
                                other_count = bin_stock_updates.get(other_bin, 1)
                                items_list.append({
                                    'name': other_name,
                                    'count': other_count,
                                    'price': other_price
                                })
                        except Exception as e:
                            print(f"[ERROR] Failed to get details for bin {other_bin}: {e}")
                else:
                    # Single bin - just add the one item
                    items_list.append({
                        'name': product_name,
                        'count': quantity,
                        'price': price
                    })
                
                return jsonify({
                    'success': True,
                    'verified': True,
                    'quantity': quantity,
                    'quantity_text': f'{quantity} product(s)',
                    'weight_diff': weight_diff,
                    'expected_weight': expected_weight,
                    'price': price,
                    'total_amount': total_amount,
                    'new_stock': new_stock,
                    'transaction_id': transaction_id,
                    'image_path': image_path,
                    'bins_info': bins_info,
                    'is_multi_bin': bool(other_bin_deltas),
                    'items_list': items_list,
                    'message': f'[OK] {quantity} product(s) taken! Total amount: ${total_amount:.2f}'
                })
            else:
                print(f"[ERROR] Product {product_id} not found for stock reduction")
                return jsonify({
                    'success': True,
                    'verified': True,
                    'weight_diff': weight_diff,
                    'expected_weight': expected_weight,
                    'message': 'Weight verified but product not found for stock update.'
                }), 400
        except Exception as e:
            print(f"[ERROR] Failed to update stock for product {product_id}: {e}")
            return jsonify({
                'success': True,
                'verified': True,
                'weight_diff': weight_diff,
                'expected_weight': expected_weight,
                'message': f'Weight verified but failed to update stock: {str(e)}'
            }), 500


@app.route("/open_door/<int:door_number>")
def open_door(door_number):
    """Open the vending machine door for the specified product with voice and auto-close"""
    print(f"\n{'='*50}")
    print(f"[DOOR CONTROL] [DOOR] OPENING DOOR {door_number}")
    print(f"[DOOR CONTROL] Timestamp: {datetime.datetime.now()}")
    print(f"{'='*50}\n")
    
    # Track purchase in session
    if 'purchases' not in session:
        session['purchases'] = []
    
    # Get product details for the purchase record
    try:
        if FIREBASE_ENABLED:
            item = get_product_by_id(str(door_number))
        else:
            conn = get_db_connection()
            item = conn.execute("SELECT * FROM products WHERE id = ?", (door_number,)).fetchone()
            conn.close()
            if item:
                item = dict(item)
        
        if item:
            session['purchases'].append({
                'id': door_number,
                'name': item.get('name', f'Product {door_number}'),
                'price': float(item.get('price', 0)),
                'timestamp': datetime.datetime.now().isoformat()
            })
            session.modified = True
    except Exception as e:
        print(f"[INFO] Could not track purchase: {e}")
    
    # Voice announcement
    if TTS_AVAILABLE:
        def announce_door():
            try:
                message = f"Door {door_number} is now open. Please collect your product."
                tts_engine.say(message)
                tts_engine.runAndWait()
            except Exception as e:
                print(f"[TTS ERROR] {e}")
        
        # Run voice in background thread to not block response
        threading.Thread(target=announce_door, daemon=True).start()
    
    # Auto-close door after 30 seconds
    def auto_close_door():
        time.sleep(30)
        print(f"\n[DOOR CONTROL] [DOOR] AUTO-CLOSING DOOR {door_number} (30s timeout)")
        print(f"[DOOR CONTROL] Timestamp: {datetime.datetime.now()}\n")
        add_chat_message(f"[SYSTEM] ⏰ Door {door_number} auto-closed after 30 seconds")
    
    threading.Thread(target=auto_close_door, daemon=True).start()
    
    add_chat_message(f"[MACHINE] [DOOR] Door {door_number} opened! Please collect your product. (Auto-closes in 2 min)")
    return render_template("open_door.html", door_number=door_number, purchases=session.get('purchases', []))


# ------------------ TRANSACTION RECEIPT ------------------
@app.route("/transaction_receipt")
def transaction_receipt():
    """Display items taken and provide go-back button"""
    # Get the items list from the most recent transaction or session
    items_list = session.get('last_items', [])
    total_amount = session.get('last_amount', 0)
    transaction_id = session.get('last_transaction_id', '')
    
    return render_template("transaction_receipt.html", 
                         items_list=items_list,
                         total_amount=total_amount,
                         transaction_id=transaction_id)


# ------------------ ADMIN LOGIN ------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admin WHERE username=?",
                             (username,)).fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            flash("Incorrect username or password!", "danger")

    return render_template("admin.html")



# ------------------ ADMIN PANEL ------------------
@app.route("/admin_panel")
def admin_panel():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if FIREBASE_ENABLED:
        products = get_all_products()
        
        # Check SQLite product count
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products")
            sqlite_count = cursor.fetchone()[0]
            conn.close()
        except:
            sqlite_count = 0
        
        # Check if Firebase products have required fields (name, price)
        has_required_fields = (products and 
                              all(product.get('name') and product.get('price') for product in products))
        
        # If Firebase is empty, has fewer products than SQLite, or missing required fields, fall back to SQLite
        if not products or len(products) < sqlite_count or not has_required_fields:
            reason = "empty" if not products else "fewer products" if len(products) < sqlite_count else "missing required fields"
            print(f"[INFO] Firebase products {reason}, using SQLite in admin_panel")
            conn = get_db_connection()
            products = conn.execute("SELECT * FROM products").fetchall()
            conn.close()
            products = [dict(p) for p in products]
        else:
            # Merge image data from SQLite
            try:
                conn = get_db_connection()
                sqlite_products = conn.execute("SELECT id, image FROM products").fetchall()
                conn.close()
                
                image_map = {str(row[0]): row[1] for row in sqlite_products}
                for product in products:
                    product_id = str(product.get('id'))
                    if product_id in image_map and not product.get('image'):
                        product['image'] = image_map[product_id]
            except Exception as e:
                print(f"[WARNING] Failed to merge image data in admin panel: {e}")
    else:
        conn = get_db_connection()
        products = conn.execute("SELECT * FROM products").fetchall()
        conn.close()
        products = [dict(p) for p in products]

    return render_template("admin_panel.html", products=products)



# ------------------ UPDATE PRODUCT ------------------
@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if FIREBASE_ENABLED:
        product = get_product_by_id(str(id))
        
        # If Firebase returns None or missing required fields, fall back to SQLite
        if product is None or not product.get('name') or not product.get('price'):
            conn = get_db_connection()
            product = conn.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
            conn.close()
            if product:
                product = dict(product)
        else:
            # Get image from SQLite as backup/sync
            try:
                conn = get_db_connection()
                sqlite_product = conn.execute("SELECT image FROM products WHERE id = ?", (id,)).fetchone()
                conn.close()
                if sqlite_product and sqlite_product[0]:
                    if not product or not product.get('image'):
                        if product:
                            product['image'] = sqlite_product[0]
                        else:
                            product = {'id': id, 'image': sqlite_product[0]}
            except Exception as e:
                print(f"[WARNING] Failed to fetch image from SQLite: {e}")
    else:
        conn = get_db_connection()
        product = conn.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
        conn.close()
        if product:
            product = dict(product)

    if product is None:
        flash("Product not found!", "danger")
        return redirect(url_for("admin_panel"))

    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        stock = request.form.get("stock")
        weight = request.form.get("weight")
        old_stock = product.get('stock', 0)
        image_filename = product.get('image') or None  # Keep existing image by default, handle None case
        
        print(f"[UPDATE PRODUCT] Initial image_filename: {image_filename}")

        # Convert weight to int (with default 50g)
        try:
            weight = int(weight) if weight else 50
        except (ValueError, TypeError):
            weight = 50
        
        print(f"[UPDATE PRODUCT] Product ID: {id}, Weight submitted: {request.form.get('weight')}, Converted: {weight}")  # DEBUG
        print(f"[UPDATE PRODUCT] Request files keys: {list(request.files.keys())}")
        print(f"[UPDATE PRODUCT] Request form keys: {list(request.form.keys())}")

        # Handle image upload
        image_upload_attempted = False
        upload_success = False
        upload_error = None
        
        if 'image' in request.files:
            image_upload_attempted = True
            file = request.files['image']
            print(f"[IMAGE UPLOAD] File object: {file}")
            print(f"[IMAGE UPLOAD] File filename: '{file.filename}'" if file else "[IMAGE UPLOAD] No file object")
            print(f"[IMAGE UPLOAD] Upload folder: {app.config['UPLOAD_FOLDER']}")
            print(f"[IMAGE UPLOAD] Folder exists: {os.path.exists(app.config['UPLOAD_FOLDER'])}")
            
            if file and file.filename and file.filename != '' and allowed_file(file.filename):
                try:
                    print(f"[IMAGE UPLOAD] File passed validation. Processing...")
                    
                    # Generate new filename FIRST
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    timestamp = int(time.time())
                    filename = f"product_{id}_{timestamp}.{ext}"  # Don't use secure_filename yet
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    print(f"[IMAGE UPLOAD] Generated filename: {filename}")
                    print(f"[IMAGE UPLOAD] Full filepath: {filepath}")
                    
                    # Save new image FIRST (before deleting old one)
                    print(f"[IMAGE UPLOAD] Attempting to save file...")
                    file.save(filepath)
                    
                    # Verify file was saved
                    if os.path.exists(filepath):
                        file_size = os.path.getsize(filepath)
                        print(f"[IMAGE UPLOAD] [OK] File saved successfully! Size: {file_size} bytes")
                        print(f"[IMAGE UPLOAD] File exists at path: {filepath}")
                        
                        # NOW delete old image since new one is safe
                        if image_filename and image_filename != 'default.png':
                            old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                            print(f"[IMAGE UPLOAD] Attempting to delete old image: {image_filename}")
                            if os.path.exists(old_image_path):
                                try:
                                    os.remove(old_image_path)
                                    print(f"[IMAGE UPLOAD] [OK] Old image deleted: {image_filename}")
                                except Exception as del_err:
                                    print(f"[IMAGE UPLOAD] [WARNING] Failed to delete old image: {del_err}")
                            else:
                                print(f"[IMAGE UPLOAD] ℹ️ Old image file not found at: {old_image_path}")
                        
                        # Update image_filename to new one
                        image_filename = filename
                        upload_success = True
                        print(f"[IMAGE UPLOAD] [OK] image_filename updated to: {image_filename}")
                    else:
                        upload_error = "File was not saved properly to disk"
                        print(f"[IMAGE UPLOAD] [ERROR] File NOT found after save! Path: {filepath}")
                        print(f"[IMAGE UPLOAD] Directory contents: {os.listdir(app.config['UPLOAD_FOLDER'])}")
                except Exception as e:
                    import traceback
                    upload_error = f"Upload error: {str(e)}"
                    print(f"[IMAGE UPLOAD] [ERROR] Exception occurred: {e}")
                    print(f"[IMAGE UPLOAD] Traceback:\n{traceback.format_exc()}")
            else:
                if file and file.filename:
                    upload_error = f"Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WebP"
                print(f"[IMAGE UPLOAD] [WARNING] File validation failed:")
                print(f"  - file exists: {bool(file)}")
                print(f"  - filename: {file.filename if file else 'N/A'}")
                print(f"  - filename not empty: {file.filename != '' if file else 'N/A'}")
                if file and file.filename:
                    print(f"  - allowed_file result: {allowed_file(file.filename)}")
        else:
            print(f"[IMAGE UPLOAD] ℹ️ 'image' not in request.files")
        
        print(f"[UPDATE PRODUCT] Final image_filename to save: '{image_filename}'")

        # CRITICAL FIX: Only update image in database if upload was successful!
        # This prevents database pointing to non-existent files
        image_to_save = image_filename
        if image_upload_attempted and not upload_success:
            # If image upload was attempted but failed, keep the old image
            image_to_save = product.get('image')
            print(f"[UPDATE PRODUCT] Image upload failed, reverting to old image: '{image_to_save}'")

        if FIREBASE_ENABLED:
            update_product(str(id), name, price, stock, image=image_to_save, weight=weight)
            print(f"[INFO] Firebase product {id} updated with image: {image_to_save} and weight: {weight}g")
            
            # IMPORTANT: Also update SQLite to keep image synchronized
            # This ensures images persist even if Firebase is used
            try:
                conn = get_db_connection()
                print(f"[DEBUG] Updating SQLite: image_filename='{image_to_save}'")
                conn.execute("UPDATE products SET name=?, price=?, stock=?, weight=?, image=? WHERE id=?",
                             (name, price, stock, weight, image_to_save, id))
                conn.commit()
                print(f"[DEBUG] SQLite UPDATE executed successfully")
                conn.close()
                print(f"[INFO] [OK] SQLite synced for product {id} with image: {image_to_save} and weight: {weight}g")
            except Exception as e:
                print(f"[WARNING] Failed to sync to SQLite: {e}")
                import traceback
                print(f"[ERROR] Traceback: {traceback.format_exc()}")
        else:
            conn = get_db_connection()
            print(f"[DEBUG] Updating SQLite (no Firebase): image_filename='{image_to_save}'")
            conn.execute("UPDATE products SET name=?, price=?, stock=?, weight=?, image=? WHERE id=?",
                         (name, price, stock, weight, image_to_save, id))
            conn.commit()
            print(f"[DEBUG] SQLite UPDATE executed successfully")
            conn.close()
            print(f"[INFO] [OK] SQLite product {id} updated with image: {image_to_save} and weight: {weight}g")

        # Log stock change if quantity changed
        new_stock = int(stock)
        if new_stock != old_stock:
            quantity_change = new_stock - old_stock
            reason = "RESTOCKED" if quantity_change > 0 else "STOCK_REDUCED"
            log_stock_update_local(str(id), name, old_stock, new_stock, reason=reason)
            update_stock_status_local(str(id), new_stock)
            
            # Also log to Firebase
            if FIREBASE_ENABLED:
                log_stock_update(str(id), name, old_stock, new_stock, reason=reason)
                update_current_stock(str(id), new_stock)
            
            # Log transaction for stock addition
            if quantity_change > 0:
                log_transaction_local(str(id), name, "admin_restock", quantity=quantity_change, final_stock=new_stock, transaction_type="added", price=float(price))
                # Also log to Firebase
                if FIREBASE_ENABLED:
                    log_transaction(str(id), name, "admin_restock", quantity=quantity_change, final_stock=new_stock, transaction_type="added", price=float(price))
            else:
                log_transaction_local(str(id), name, "admin_adjustment", quantity=abs(quantity_change), final_stock=new_stock, transaction_type="sold", price=float(price))
                # Also log to Firebase
                if FIREBASE_ENABLED:
                    log_transaction(str(id), name, "admin_adjustment", quantity=abs(quantity_change), final_stock=new_stock, transaction_type="sold", price=float(price))
        
        # Log price change if price changed
        old_price = float(product.get('price', 0))
        new_price = float(price)
        if new_price != old_price:
            print(f"[PRODUCT UPDATE] Price changed: {old_price} → {new_price}")
            log_transaction_local(str(id), name, "admin_price_change", quantity=1, final_stock=new_stock, transaction_type="price_update", price=new_price)
            if FIREBASE_ENABLED:
                log_transaction(str(id), name, "admin_price_change", quantity=1, final_stock=new_stock, transaction_type="price_update", price=new_price)
        
        # Log name change if name changed
        old_name = product.get('name', '')
        if old_name != name and old_name.strip():  # Only log if name actually changed
            print(f"[PRODUCT UPDATE] Name changed: {old_name} → {name}")
            log_transaction_local(str(id), f"{old_name} → {name}", "admin_name_change", quantity=1, final_stock=new_stock, transaction_type="name_update", price=float(price))
            if FIREBASE_ENABLED:
                log_transaction(str(id), f"{old_name} → {name}", "admin_name_change", quantity=1, final_stock=new_stock, transaction_type="name_update", price=float(price))
        
        # Log weight change if weight changed
        old_weight = int(product.get('weight', 50))
        new_weight = int(weight)
        if new_weight != old_weight:
            print(f"[PRODUCT UPDATE] Weight changed: {old_weight}g → {new_weight}g")
            log_transaction_local(str(id), name, "admin_weight_change", quantity=1, final_stock=new_stock, transaction_type="weight_update", price=float(price))
            if FIREBASE_ENABLED:
                log_transaction(str(id), name, "admin_weight_change", quantity=1, final_stock=new_stock, transaction_type="weight_update", price=float(price))

        # Verify the update was saved to database
        try:
            if FIREBASE_ENABLED:
                verify_product = get_product_by_id(str(id))
                firebase_image = verify_product.get('image', '') if verify_product else 'NOT_FOUND'
                print(f"[VERIFY] Firebase product {id} image after update: '{firebase_image}'")
            
            conn = get_db_connection()
            verify_row = conn.execute("SELECT image FROM products WHERE id = ?", (id,)).fetchone()
            sqlite_image = verify_row[0] if verify_row else 'NOT_FOUND'
            conn.close()
            print(f"[VERIFY] SQLite product {id} image after update: '{sqlite_image}'")
            
            if sqlite_image == image_to_save:
                print(f"[VERIFY] [OK] Image successfully saved to database: {image_to_save}")
            else:
                print(f"[VERIFY] [ERROR] WARNING: Image mismatch! Expected: {image_to_save}, Got: {sqlite_image}")
        except Exception as e:
            print(f"[VERIFY] Error verifying update: {e}")

        # Generate appropriate message
        message = "Product updated successfully!"
        if image_upload_attempted:
            if upload_success:
                message = "[OK] Product updated and image uploaded successfully!"
            elif upload_error:
                message = f"[WARNING] Product updated, but image upload failed: {upload_error}"
        
        # Commented out flash message - user doesn't need notification about changes
        # flash(message, "success" if upload_success or not image_upload_attempted else "warning")
        return redirect(url_for("admin_panel"))

    return render_template("update.html", product=product)



# ------------------ LOGOUT ------------------
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))



# ------------------ VOICE COMMAND SYSTEM ------------------

def build_dynamic_name_mapping():
    """Build product name to ID mapping from database (supports dynamic name changes)"""
    name_mapping = {}
    
    # Always include fallback hardcoded names as base
    fallback = {
        "apple": 1, "apples": 1,
        "orange": 2, "oranges": 2,
        "mango": 3, "mangos": 3,
        "banana": 4, "bananas": 4,
        "chocolate": 1, "chocolates": 1,
        "cookies": 2, "cookie": 2,
        "ball": 3, "balls": 3,
        "clock": 4, "clocks": 4
    }
    name_mapping.update(fallback)
    
    try:
        if FIREBASE_ENABLED:
            try:
                products = get_all_products()
                print(f"[VOICE] Loaded {len(products)} products from Firebase")
            except Exception as e:
                print(f"[VOICE] Firebase error: {e}, using local database instead")
                products = None
        else:
            products = None
        
        # If Firebase failed or disabled, try local database
        if products is None:
            try:
                conn = get_db_connection()
                products = conn.execute("SELECT id, name FROM products").fetchall()
                conn.close()
                products = [dict(p) for p in products]
                print(f"[VOICE] Loaded {len(products)} products from SQLite database")
            except Exception as e:
                print(f"[VOICE] Database error: {e}, using fallback names")
                return fallback
        
        # Build mapping: product name (lowercase) -> product id
        for product in products:
            if product:
                product_name = str(product.get('name', '')).lower().strip()
                product_id = int(product.get('id', 0))
                
                if product_name and product_id > 0:
                    # Add singular form
                    name_mapping[product_name] = product_id
                    
                    # Add plural form (append 's' if not already ending with 's')
                    if not product_name.endswith('s'):
                        name_mapping[product_name + 's'] = product_id
        
        print(f"[VOICE] Final name mapping: {name_mapping}")
        return name_mapping
    
    except Exception as e:
        print(f"[WARNING] Unexpected error in build_dynamic_name_mapping: {e}")
        print(f"[WARNING] Using fallback mapping")
        return fallback


def extract_number(text):
    if not text:
        return None

    text = text.lower().strip()

    # Get dynamic product name mapping from database
    name_mapping = build_dynamic_name_mapping()
    print(f"[VOICE] Name mapping in extract_number: {name_mapping}")

    # Direct digit mapping
    digit_mapping = {
        "1": 1, "one": 1, "won": 1, "uno": 1,
        "2": 2, "two": 2, "to": 2, "too": 2, "do": 2, "tu": 2,
        "3": 3, "three": 3, "tree": 3, "tri": 3,
        "4": 4, "four": 4, "for": 4, "fore": 4
    }

    # First try exact product name match
    for name, product_id in name_mapping.items():
        if name == text or text == name:
            print(f"[VOICE] ✓ Exact match: '{text}' = '{name}' → Product {product_id}")
            return product_id
    
    # Try word-by-word matching for names and numbers
    words = text.split()
    for word in words:
        # Remove punctuation from word
        word_clean = word.strip('.,!?')
        
        # Check product names (exact match)
        if word_clean in name_mapping:
            print(f"[VOICE] ✓ Word match: '{word_clean}' → Product {name_mapping[word_clean]}")
            return name_mapping[word_clean]
        
        # Check digit names
        if word_clean in digit_mapping:
            print(f"[VOICE] ✓ Digit match: '{word_clean}' → Product {digit_mapping[word_clean]}")
            return digit_mapping[word_clean]
        
        # Try single digit
        if word_clean.isdigit() and len(word_clean) == 1:
            num = int(word_clean)
            if 1 <= num <= 4:
                print(f"[VOICE] ✓ Number match: '{word_clean}' → Product {num}")
                return num
    
    # Fuzzy matching: check if any product name is contained in the text (partial match)
    for name, product_id in name_mapping.items():
        if len(name) >= 3 and name in text:  # At least 3 chars to avoid false matches
            print(f"[VOICE] ✓ Fuzzy match (name in text): '{name}' found in '{text}' → Product {product_id}")
            return product_id
    
    # Fuzzy matching: check if text contains any product name
    for name, product_id in name_mapping.items():
        if len(name) >= 3 and text in name:  # Text is substring of product name
            print(f"[VOICE] ✓ Fuzzy match (text in name): '{text}' found in '{name}' → Product {product_id}")
            return product_id

    # Try to extract any digit 1-4
    import re
    digits = re.findall(r'[1-4]', text)
    if digits:
        print(f"[VOICE] ✓ Regex digit match: {digits[0]} → Product {int(digits[0])}")
        return int(digits[0])
    
    print(f"[VOICE] ✗ No match found for: '{text}'")
    return None

    return None


def listen_for_commands():
    global bot_running
    
    if not SR_AVAILABLE:
        print("\n[WARNING] Speech recognition not available - voice commands disabled\n")
        print("[FIX] Install with: pip install SpeechRecognition PyAudio pyttsx3")
        add_chat_message("[BOT] Voice system unavailable. Please use web interface.")
        return
    
    try:
        r = sr.Recognizer()
        mic = sr.Microphone()
    except (AttributeError, OSError) as e:
        print(f"\n[WARNING] {e} - voice commands disabled\n")
        print(f"[FIX] Microphone issue: {e}")
        print("[FIX] Ensure microphone is connected and no other app is using it")
        add_chat_message(f"[BOT] Voice system unavailable: {e}")
        return

    print("\n[VOICE] Voice system ready (waiting for start signal)...\n")

    while True:
        try:
            # Check if bot is supposed to be running
            if not bot_running:
                time.sleep(0.5)
                continue
            
            print("\n[VOICE] Voice system active, listening for product...\n")
            add_chat_message("[BOT] Say a product name, number (1, 2, 3, or 4), or 'list products'")

            # Listen for product name/number directly
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=1)
                audio = r.listen(source, timeout=5, phrase_time_limit=4)

            try:
                text = r.recognize_google(audio).lower()
                user_msg = f"[YOU] {text}"
                print(user_msg)
                add_chat_message(user_msg)
            except sr.UnknownValueError:
                error_msg = "[BOT] Could not understand. Please speak clearly and try again..."
                print(error_msg)
                add_chat_message(error_msg)
                continue
            except sr.RequestError as e:
                error_msg = f"[BOT] Connection error: {e}. Check internet connection."
                print(f"[VOICE] API Error: {e}")
                add_chat_message(error_msg)
                continue
            except Exception as e:
                error_msg = f"[BOT] Error: {e}. Please try again..."
                print(f"[VOICE] Unexpected error: {e}")
                add_chat_message(error_msg)
                continue

            # Check if user wants to list products
            if "list" in text and "product" in text:
                list_msg = "[BOT] Available products:"
                print(list_msg)
                add_chat_message(list_msg)
                try:
                    if FIREBASE_ENABLED:
                        products = get_all_products()
                    else:
                        conn = get_db_connection()
                        products = conn.execute("SELECT id, name, price FROM products ORDER BY id").fetchall()
                        conn.close()
                        products = [dict(p) for p in products]
                    
                    for p in products:
                        product_info = f"  {p.get('id')} - {p.get('name')} (Rs{p.get('price')})"
                        print(product_info)
                        add_chat_message(product_info)
                except Exception as e:
                    err_msg = f"[BOT] Could not load products: {e}"
                    print(err_msg)
                    add_chat_message(err_msg)
                continue

            # Check if user wants to stop/cancel
            if any(word in text for word in ["stop", "cancel", "quit", "exit", "back"]):
                bot_msg = "[BOT] Voice bot stopped."
                print(bot_msg)
                add_chat_message(bot_msg)
                bot_running = False
                continue

            # Extract product number from response
            num = extract_number(text)
            
            # Debug output
            debug_msg = f"[DEBUG] Recognized: '{text}' → Extracted Number: {num}"
            print(debug_msg)
            add_chat_message(debug_msg)

            if num:
                buying_msg = f"[BOT] Processing... Opening Product {num}..."
                print(buying_msg)
                add_chat_message(buying_msg)
                url = f"http://127.0.0.1:5000/buy/{num}"
                webbrowser.open_new(url)
                # Continue listening for next product
            else:
                invalid_msg = f"[BOT] Invalid product. Please say a number (1, 2, 3, or 4) or 'list products'."
                print(invalid_msg)
                add_chat_message(invalid_msg)

        except Exception as e:
            error = f"Voice error: {e}"
            print(error)
            add_chat_message(error)

        time.sleep(1)

# ==================== ANALYTICS & RECEIPTS ====================

@app.route("/analytics")
def analytics():
    """Dashboard showing door opens, payments, and sales"""
    try:
        # Read transaction logs
        transactions = []
        txn_log_path = get_logs_path('transactions.json')
        if os.path.exists(txn_log_path):
            with open(txn_log_path, "r") as f:
                transactions = json.load(f)
        
        # Calculate stats
        total_sales = sum(t.get("price", 0) for t in transactions if t.get("type") == "purchase")
        total_transactions = len([t for t in transactions if t.get("type") == "purchase"])
        
        # Group by product
        products_sold = {}
        for t in transactions:
            if t.get("type") == "purchase":
                name = t.get("product", "Unknown")
                products_sold[name] = products_sold.get(name, 0) + 1
        
        return render_template("analytics.html", 
                             total_sales=total_sales,
                             total_transactions=total_transactions,
                             products_sold=products_sold,
                             recent_transactions=transactions[-10:])
    except Exception as e:
        print(f"[ANALYTICS ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/receipt/<int:transaction_id>")
def generate_receipt(transaction_id):
    """Generate PDF receipt for a transaction"""
    if not PDF_AVAILABLE:
        return jsonify({"error": "PDF generation not available"}), 400
    
    try:
        # Create PDF in memory
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        
        # Receipt header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "🏪 VENDING MACHINE RECEIPT")
        
        c.setFont("Helvetica", 10)
        c.drawString(50, 720, f"Transaction ID: TXN_{transaction_id}")
        c.drawString(50, 700, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Generate QR code for transaction
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(f"TXN_{transaction_id}")
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_path = "temp_qr.png"
        qr_img.save(qr_path)
        
        c.drawImage(qr_path, 50, 600, width=100, height=100)
        
        c.setFont("Helvetica", 12)
        c.drawString(180, 650, f"Product: Apple")
        c.drawString(180, 630, f"Price: Rs100")
        c.drawString(180, 610, f"Status: Completed")
        
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 550, "Thank you for your purchase!")
        c.drawString(50, 530, "Please collect your product from the door.")
        
        # Footer
        c.setFont("Helvetica", 8)
        c.drawString(50, 50, "Vending Machine System | Receipt printed: " + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        c.save()
        pdf_buffer.seek(0)
        
        # Clean up temp QR
        if os.path.exists(qr_path):
            os.remove(qr_path)
        
        return pdf_buffer.getvalue(), 200, {'Content-Type': 'application/pdf', 'Content-Disposition': f'attachment; filename=receipt_{transaction_id}.pdf'}
    except Exception as e:
        print(f"[PDF ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/recommendations")
def get_recommendations():
    """Get product recommendations based on current selection"""
    try:
        if FIREBASE_ENABLED:
            products = get_all_products()
            
            # Check SQLite product count
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM products")
                sqlite_count = cursor.fetchone()[0]
                conn.close()
            except:
                sqlite_count = 0
            
            # Check if Firebase products have required fields (name, price)
            has_required_fields = (products and 
                                  all(product.get('name') and product.get('price') for product in products))
            
            # If Firebase is empty, has fewer products than SQLite, or missing required fields, fall back to SQLite
            if not products or len(products) < sqlite_count or not has_required_fields:
                reason = "empty" if not products else "fewer products" if len(products) < sqlite_count else "missing required fields"
                print(f"[RECOMMENDATIONS] Firebase products {reason}, using SQLite")
                conn = get_db_connection()
                products = conn.execute("SELECT * FROM products").fetchall()
                conn.close()
                products = [dict(p) for p in products]
            else:
                # Also fetch image data from SQLite to merge (important!)
                try:
                    conn = get_db_connection()
                    sqlite_products = conn.execute("SELECT id, image FROM products").fetchall()
                    conn.close()
                    
                    # Create a dict of images from SQLite
                    image_map = {str(row[0]): row[1] for row in sqlite_products}
                    
                    # Merge image data into Firebase products
                    for product in products:
                        product_id = str(product.get('id'))
                        if product_id in image_map and not product.get('image'):
                            product['image'] = image_map[product_id]
                except Exception as e:
                    print(f"[WARNING] Failed to merge image data in recommendations: {e}")
        else:
            conn = get_db_connection()
            products = conn.execute("SELECT * FROM products").fetchall()
            products = [dict(p) for p in products]
            conn.close()
        
        # Simple recommendation: show popular products (sort by stock descending)
        recommendations = sorted(products, key=lambda x: x.get('stock', 0), reverse=True)[:3]
        
        result = []
        for r in recommendations:
            image_filename = r.get("image", "")
            image_path = ""
            
            # Build image path - handle None, NULL, and empty strings
            if image_filename and str(image_filename).strip() and str(image_filename) != 'None':
                # If it doesn't start with /, add the full path
                if str(image_filename).startswith('/'):
                    image_path = str(image_filename)
                else:
                    image_path = f"/static/product_images/{image_filename}"
            
            result.append({
                "id": r["id"], 
                "name": r["name"], 
                "price": float(r["price"]),
                "image": image_path
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"[RECOMMENDATIONS ERROR] {e}")
        import traceback
        traceback.print_exc()
        return jsonify([]), 500

# ==================== TRANSACTION API ====================

@app.route("/api/transactions")
def get_transactions_api():
    """API endpoint to get all transactions with transaction IDs"""
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        transactions = []
        
        # Load from local JSON logs
        txn_log_path = get_logs_path('transactions.json')
        if os.path.exists(txn_log_path):
            with open(txn_log_path, "r") as f:
                all_transactions = json.load(f)
                
                # Process and add transaction IDs
                for i, t in enumerate(all_transactions):
                    transaction = {
                        'transaction_id': t.get('transaction_id') or f"TXN_{i}_{int(time.time())}",
                        'date': t.get('date', 'N/A'),
                        'time': t.get('time', 'N/A'),
                        'product_name': t.get('product_name', 'Unknown'),
                        'bin_location': t.get('bin_location', i + 1),
                        'transaction_type': t.get('transaction_type', 'unknown'),
                        'quantity': t.get('quantity', 1),
                        'price': t.get('price', 0),
                        'final_stock': t.get('final_stock', 0)
                    }
                    transactions.append(transaction)
        
        return jsonify({'transactions': transactions}), 200
    except Exception as e:
        print(f"[API ERROR] Failed to load transactions: {e}")
        return jsonify({'error': str(e), 'transactions': []}), 500

# ==================== END TRANSACTION API ====================


# ==================== START APP ------------------
def verify_esp32_before_launch():
    """
    Verify ESP32 is responding before opening browser
    Only sends ID command - if responds, returns True
    If no response or error, still continues (returns False)
    """
    print("\n" + "="*70)
    print("[SEARCH] STARTUP: Checking ESP32 connection...")
    print("="*70)
    
    global esp32_connected
    
    # In MOCK mode, always pretend ESP32 is connected
    if MOCK_WEIGHT_SENSOR:
        print("[MOCK MODE] Skipping real ESP32 check - using simulated weights")
        print("="*70 + "\n")
        esp32_connected = True
        return True
    
    try:
        # Initialize serial connection
        success = init_serial_connection()
        if not success:
            print("[WARNING]  WARNING: Could not establish serial connection to ESP32")
            esp32_connected = False
            return False
        
        if serial_connection is None or not serial_connection.is_open:
            print("[WARNING]  WARNING: Serial connection not open")
            esp32_connected = False
            return False
        
        # Step 1: Send ID command only
        print("\n[SEND] Sending ID command to ESP32...")
        serial_connection.reset_input_buffer()
        time.sleep(0.2)
        serial_connection.write(b'ID\r\n')
        time.sleep(0.5)
        
        id_response = b''
        if serial_connection.in_waiting:
            id_response = serial_connection.read(serial_connection.in_waiting)
            response_str = id_response.decode('utf-8', errors='ignore').strip()
            print(f"[OK] ID Response: {response_str}")
            
            if 'ESP' in response_str.upper():
                print("[OK] ESP32 CONNECTED & VERIFIED!")
                print("="*70 + "\n")
                esp32_connected = True
                return True
        
        print("[WARNING]  No ID response from ESP32 - Connection unavailable")
        print("="*70 + "\n")
        esp32_connected = False
        return False
    
    except Exception as e:
        print(f"[WARNING]  ESP32 check error: {e}")
        esp32_connected = False
        return False


if __name__ == "__main__":
    # Global flag to signal shutdown
    shutdown_event = threading.Event()
    
    def shutdown_handler(signum=None, frame=None):
        """Handle shutdown signals gracefully"""
        print("\n[SHUTDOWN] Shutdown signal received, closing application...")
        shutdown_event.set()
        # Force exit after a brief delay
        import time
        time.sleep(1)
        import os
        os._exit(0)
    
    # Register signal handlers for Windows
    if sys.platform == 'win32':
        import atexit
        atexit.register(shutdown_handler)
    else:
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Verify ESP32 before opening browser
    esp32_ready = verify_esp32_before_launch()
    
    # Auto-open browser after ESP32 verification
    if esp32_ready:
        delay = 1.0
        print("[BROWSER] Opening browser in 1 second...")
    else:
        delay = 2.0
        print("[BROWSER] Opening browser in 2 seconds (ESP32 verification skipped)...")
    
    threading.Timer(delay, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    # Voice command background thread
    t = threading.Thread(target=listen_for_commands, daemon=True)
    t.start()
    
    try:
        # Run Flask on 0.0.0.0 to bind to all interfaces and avoid firewall issues
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Keyboard interrupt received")
        shutdown_handler()
    except Exception as e:
        print(f"[ERROR] Flask app error: {e}")
        shutdown_handler()

