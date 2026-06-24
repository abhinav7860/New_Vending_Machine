# Firebase Configuration
# This file initializes Firebase Admin SDK for both Firestore and Realtime Database

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import db as firebase_db_admin
import os
import json
import sys

# Try to import pyrebase, but make it optional
try:
    import pyrebase
    PYREBASE_AVAILABLE = True
except ImportError:
    PYREBASE_AVAILABLE = False
    print("[WARNING] pyrebase not installed. Run: pip install Pyrebase4")

# Determine the config directory
# Priority order:
# 1. C:\SenseMart (shared location)
# 2. config folder alongside executable/script
if getattr(sys, 'frozen', False):
    # Running as an executable
    base_path = sys._MEIPASS
    app_dir = os.path.dirname(sys.executable)
else:
    # Running as a script
    base_path = os.getcwd()
    app_dir = os.getcwd()

# Check C:\SenseMart first (shared location for all instances)
sensemart_path = r'C:\SenseMart'
sensemart_creds = os.path.join(sensemart_path, 'firebase_credentials.json')

# Fallback to config folder
config_dir = os.path.join(app_dir, 'config')
config_creds = os.path.join(config_dir, 'firebase_credentials.json')

# Ensure config directory exists
os.makedirs(config_dir, exist_ok=True)

# Credentials path - prefer C:\SenseMart if it exists
if os.path.exists(sensemart_creds):
    credentials_path = sensemart_creds
    print(f"[Firebase Config] Using credentials from: {sensemart_creds}")
else:
    credentials_path = config_creds
    print(f"[Firebase Config] Using credentials from: {config_creds}")

# Load Firebase credentials from JSON file first to get project details
try:
    with open(credentials_path) as f:
        firebase_creds_data = json.load(f)
    PROJECT_ID = firebase_creds_data.get('project_id', 'vending-machine-c6bf1')
    
    # Build the Realtime Database URL from project ID
    # Support both regional (.asia-southeast1) and default (.firebaseio.com) URLs
    # For sense-mart project, use asia-southeast1 region
    if PROJECT_ID == 'sense-mart':
        FIREBASE_DATABASE_URL = f"https://{PROJECT_ID}-default-rtdb.asia-southeast1.firebasedatabase.app/"
    else:
        # Default format for other projects
        FIREBASE_DATABASE_URL = f"https://{PROJECT_ID}-default-rtdb.firebaseio.com/"
    
    print(f"[Firebase Config] Loaded project: {PROJECT_ID}")
    print(f"[Firebase Config] Database URL: {FIREBASE_DATABASE_URL}")
except FileNotFoundError:
    print("[ERROR] firebase_credentials.json not found!")
    # Fallback to old project URL
    PROJECT_ID = 'vending-machine-c6bf1'
    FIREBASE_DATABASE_URL = "https://vending-machine-c6bf1-default-rtdb.firebaseio.com/"
except Exception as e:
    print(f"[ERROR] Failed to parse firebase_credentials.json: {e}")
    PROJECT_ID = 'vending-machine-c6bf1'
    FIREBASE_DATABASE_URL = "https://vending-machine-c6bf1-default-rtdb.firebaseio.com/"

# Load Firebase credentials from JSON file
# Download your Firebase credentials from: 
# Firebase Console > Project Settings > Service Accounts > Generate New Private Key

try:
    # Path to your Firebase service account key JSON file
    cred = credentials.Certificate(credentials_path)
    
    # Initialize Firebase Admin SDK
    firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DATABASE_URL
    })
    
    # Initialize Firestore database
    firestore_db = firestore.client()
    
    # Initialize Realtime Database using Pyrebase4
    if PYREBASE_AVAILABLE:
        config = {
            "apiKey": "AIzaSyDPk6K1B2oRxU5YLnRXXXXXXXXXXXXXXX",  # Placeholder, not needed for admin
            "authDomain": f"{PROJECT_ID}.firebaseapp.com",
            "databaseURL": FIREBASE_DATABASE_URL,
            "storageBucket": f"{PROJECT_ID}.appspot.com"
        }
        
        rtdb = pyrebase.initialize_app(config)
        rtdb_ref = rtdb.database()
        
        print("[Firebase] Connected to Firebase Realtime Database successfully!")
        print(f"[Firebase] Project: {PROJECT_ID}")
        print(f"[Firebase] Database URL: {FIREBASE_DATABASE_URL}")
    else:
        print("[WARNING] Pyrebase4 not available - Firebase Realtime Database disabled")
        rtdb = None
        rtdb_ref = None
    
except FileNotFoundError:
    print(f"[ERROR] firebase_credentials.json not found at {credentials_path}!")
    print("To set up Firebase:")
    print("1. Go to https://console.firebase.google.com/")
    print("2. Create a new project")
    print("3. Enable Realtime Database")
    print("4. Go to Project Settings > Service Accounts > Python")
    print("5. Click 'Generate New Private Key'")
    print(f"6. Save the JSON file as 'firebase_credentials.json' in the 'config' folder: {config_dir}")
    print("7. Re-run the app")
    firestore_db = None
    rtdb = None
    rtdb_ref = None
    
except Exception as e:
    print(f"[ERROR] Failed to initialize Firebase: {e}")
    firestore_db = None
    rtdb = None
    rtdb_ref = None


# Helper functions for Firebase operations

def get_firestore_db():
    """Get Firestore database instance"""
    return firestore_db


def get_realtime_db():
    """Get Realtime Database instance"""
    return rtdb_ref


def get_admin_db():
    """
    Get Firebase access via Admin SDK with Service Account credentials
    This provides authenticated writes to bypass 401 Unauthorized errors
    """
    try:
        # The Admin SDK is already initialized and authenticated with the service account
        # We'll use firebase_admin.db to make authenticated REST calls
        from firebase_admin import db as admin_db_module
        
        # Return a wrapper that uses admin SDK methods
        class AdminDBWrapper:
            def __init__(self):
                self.ref = admin_db_module.reference()
            
            def child(self, path):
                """Navigate to a child path"""
                # Return another wrapper for chaining
                return AdminDBChild(self.ref, path)
        
        class AdminDBChild:
            def __init__(self, ref, path):
                self.ref = ref
                self.path = path
                self.child_ref = ref.child(path) if hasattr(ref, 'child') else ref.path(path).get_reference() if hasattr(ref, 'path') else None
            
            def child(self, child_path):
                """Chain child calls"""
                new_path = f"{self.path}/{child_path}"
                return AdminDBChild(self.ref, new_path)
            
            def set(self, data):
                """Set data at this path"""
                # Use Admin SDK's update method which is authenticated
                try:
                    # Navigate through the tree path
                    ref = admin_db_module.reference()
                    for part in self.path.split('/'):
                        ref = ref.child(part)
                    ref.set(data)
                    return True
                except:
                    # Fallback to direct reference
                    self.ref.update({self.path: data})
                    return True
        
        return AdminDBWrapper()
    except Exception as e:
        print(f"[Firebase Admin DB] Error: {e}")
        return None


def get_database_url():
    """Get Firebase Realtime Database URL"""
    return FIREBASE_DATABASE_URL


def collection_exists(collection_name):
    """Check if a collection exists in Firestore"""
    try:
        if firestore_db is None:
            return False
        docs = firestore_db.collection(collection_name).limit(1).stream()
        return any(docs)
    except:
        return False


def initialize_default_data():
    """Initialize default products and admin user if not present"""
    if rtdb is None:
        return False
    
    try:
        # Check and create default products in Realtime Database
        products_ref = rtdb.child('products')
        
        # Get existing products
        existing = products_ref.get()
        
        if existing.val() is None:
            # Initialize default products
            default_products = {
                "1": {"name": "Soda Can", "price": 25, "stock": 10, "weight": 0.0},
                "2": {"name": "Chips Pack", "price": 30, "stock": 8, "weight": 0.0},
                "3": {"name": "Chocolate", "price": 20, "stock": 12, "weight": 0.0},
                "4": {"name": "Water Bottle", "price": 15, "stock": 15, "weight": 0.0},
            }
            products_ref.set(default_products)
            print("[Firebase] Default products initialized in Realtime Database!")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize data: {e}")
        return False
