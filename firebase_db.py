# Firebase Realtime Database Helper Functions
# Provides database operations for products, transactions, and chat

from firebase_config import get_realtime_db, get_admin_db
from datetime import datetime
import json
import threading
import time


def init_firebase_db():
    """Initialize Firebase database connection - verify it actually works by testing connectivity"""
    try:
        database = get_realtime_db()
        if database is None:
            print("[FIREBASE] Database is None - likely not configured")
            return False
        
        # Test actual connectivity with timeout (5 seconds max)
        result = {'success': False}
        
        def test_connection():
            try:
                test_data = database.child('products').get()
                result['success'] = True
            except Exception as e:
                print(f"[FIREBASE] Connection test error: {e}")
                result['success'] = False
        
        # Run test in background thread with timeout
        test_thread = threading.Thread(target=test_connection, daemon=True)
        test_thread.start()
        test_thread.join(timeout=5)  # Wait max 5 seconds
        
        if result['success']:
            print("[FIREBASE] [OK] Database initialized successfully!")
            return True
        else:
            print("[FIREBASE] Connection test failed or timed out")
            return False
            
    except Exception as e:
        print(f"[FIREBASE] Initialization error: {e}")
        print("[FIREBASE] Firebase unavailable - falling back to SQLite")
    return False


# =============== PRODUCTS & STOCK ===============

def get_all_products():
    """Fetch all products from Firebase Realtime Database"""
    try:
        database = get_realtime_db()
        if database is None:
            return []
        
        products = []
        products_data = database.child('products').get()
        
        if products_data.val() is not None:
            data = products_data.val()
            if isinstance(data, dict):
                for product_id, product_info in data.items():
                    product = product_info.copy() if isinstance(product_info, dict) else {}
                    product['id'] = product_id
                    products.append(product)
            elif isinstance(data, list):
                # Handle list format (Firebase sometimes returns lists)
                for idx, product_info in enumerate(data):
                    if product_info is not None and isinstance(product_info, dict):
                        product = product_info.copy()
                        product['id'] = str(idx)
                        products.append(product)
        
        return products
    except Exception as e:
        print(f"[ERROR] Failed to fetch products: {e}")
        return []


def get_product_by_id(product_id):
    """Fetch a single product by ID"""
    try:
        database = get_realtime_db()
        if database is None:
            return None
        
        product_data = database.child('products').child(str(product_id)).get()
        
        if product_data.val() is not None:
            product = product_data.val()
            if isinstance(product, dict):
                product['id'] = str(product_id)
                return product
        return None
    except Exception as e:
        print(f"[ERROR] Failed to fetch product {product_id}: {e}")
        return None


def update_product_stock(product_id, new_stock):
    """Update product stock in Firebase"""
    try:
        database = get_realtime_db()
        if database is None:
            return False
        
        database.child('products').child(str(product_id)).update({
            'stock': int(new_stock),
            'last_updated': datetime.now().isoformat()
        })
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update stock: {e}")
        return False


def update_product(product_id, name, price, stock, image=None, weight=None):
    """Update product details"""
    try:
        database = get_realtime_db()
        if database is None:
            return False
        
        update_data = {
            'name': name,
            'price': float(price),
            'stock': int(stock),
            'last_updated': datetime.now().isoformat()
        }
        
        # Only update image if provided
        if image is not None:
            update_data['image'] = image
        
        # Only update weight if provided
        if weight is not None:
            update_data['weight'] = int(weight)
        
        database.child('products').child(str(product_id)).update(update_data)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update product: {e}")
        return False


def create_product(name, price, stock, weight=0.0):
    """Create a new product"""
    try:
        database = get_realtime_db()
        if database is None:
            return None
        
        products = get_all_products()
        next_id = str(len(products) + 1) if products else "1"
        
        database.child('products').child(next_id).set({
            'name': name,
            'price': float(price),
            'stock': int(stock),
            'weight': float(weight),
            'created_at': datetime.now().isoformat()
        })
        return next_id
    except Exception as e:
        print(f"[ERROR] Failed to create product: {e}")
        return None


def delete_product(product_id):
    """Delete a product"""
    try:
        database = get_realtime_db()
        if database is None:
            return False
        
        database.child('products').child(str(product_id)).remove()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete product: {e}")
        return False


# =============== PURCHASE LOGS ===============

def log_purchase(product_id, product_name, price, quantity=1):
    """
    Log a product purchase/sale transaction
    Creates detailed purchase history
    """
    try:
        # Always get fresh database reference (don't rely on global)
        database = get_realtime_db()
        
        if database is None:
            print("[FIREBASE ERROR] Cannot log purchase: database is None")
            return False
        
        timestamp = datetime.now().isoformat()
        transaction_id = timestamp.replace(':', '-').replace('.', '-')
        
        purchase_data = {
            'product_id': str(product_id),
            'product_name': product_name,
            'price': float(price),
            'quantity': int(quantity),
            'action': 'PURCHASE',
            'timestamp': timestamp,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        database.child('logs').child('purchases').child(transaction_id).set(purchase_data)
        
        print(f"[FIREBASE] [OK] Purchase logged: {product_name} (ID: {product_id}) - {quantity}x - Rs{price}")
        return True
        
    except Exception as e:
        print(f"[FIREBASE ERROR] Failed to log purchase: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============== STOCKING LOGS ===============

def log_stock_update(product_id, product_name, old_stock, new_stock, reason="MANUAL"):
    """
    Log stock updates (restocking, adjustments, sales)
    """
    try:
        # Always get fresh database reference
        database = get_realtime_db()
        if database is None:
            print("[FIREBASE] Cannot log stock update: database is None")
            return False
        
        timestamp = datetime.now().isoformat()
        transaction_id = timestamp.replace(':', '-').replace('.', '-')
        
        stock_change = new_stock - old_stock
        
        stock_data = {
            'product_id': str(product_id),
            'product_name': product_name,
            'old_stock': int(old_stock),
            'new_stock': int(new_stock),
            'stock_change': int(stock_change),
            'reason': reason,
            'timestamp': timestamp,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        database.child('logs').child('stock_updates').child(transaction_id).set(stock_data)
        
        action = "RESTOCKED" if stock_change > 0 else "SOLD"
        print(f"[Firebase] Stock log: {product_name} - {action} - Old: {old_stock}, New: {new_stock}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to log stock update: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============== TRANSACTION LOGS ===============

def log_transaction(product_id, product_name, action="purchase", quantity=1, final_stock=0, transaction_type="sold", price=0, transaction_id=None):
    """
    Log transaction to Firebase using Admin SDK for authenticated writes
    This solves the 401 Unauthorized error from unauthenticated Pyrebase4
    """
    try:
        from datetime import datetime
        from firebase_admin import db
        
        # Use Admin SDK which has service account authentication built-in
        timestamp = datetime.now().isoformat()
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M:%S")
        txn_id = transaction_id or f"TXN_{int(datetime.now().timestamp() * 1000)}"
        
        # Simple transaction entry - exactly like local logs
        transaction_entry = {
            'transaction_id': txn_id,
            'product_id': str(product_id),
            'product_name': product_name,
            'action': action,
            'quantity': int(quantity),
            'transaction_type': transaction_type,
            'final_stock': int(final_stock),
            'price': float(price),
            'bin_location': str(product_id),
            'timestamp': timestamp,
            'date': date_str,
            'time': time_str
        }
        
        # Use Admin SDK authenticated reference
        # Admin SDK provides authenticated access via service account
        unique_key = f"{date_str}_{time_str}_{txn_id}_{product_id}"
        path = f"transaction_log/{unique_key}"
        
        # Get authenticated reference and set data
        ref = db.reference(path)
        ref.set(transaction_entry)
        
        print(f"[FIREBASE] ✓ Transaction logged: {product_name} x{quantity} (TXN: {txn_id})")
        return True
        
    except Exception as e:
        print(f"[FIREBASE] ✗ Error logging transaction: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============== REAL-TIME STOCK STATUS ===============

def update_current_stock(product_id, stock_count):
    """
    Update real-time stock status in a separate 'stock_status' node
    This allows easy access to current stock levels
    """
    try:
        # Always get fresh database reference
        database = get_realtime_db()
        if database is None:
            print("[FIREBASE] Cannot update stock: database is None")
            return False
        
        database.child('stock_status').child(str(product_id)).set({
            'stock': int(stock_count),
            'last_updated': datetime.now().isoformat()
        })
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update stock status: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_stock_status(product_id):
    """Get current stock status"""
    try:
        database = get_realtime_db()
        if database is None:
            return None
        
        status_data = database.child('stock_status').child(str(product_id)).get()
        if status_data.val() is not None:
            return status_data.val()
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get stock status: {e}")
        return None


# =============== RETRIEVE LOGS ===============

def get_purchase_logs(limit=50):
    """Fetch recent purchase logs"""
    try:
        database = get_realtime_db()
        if database is None:
            return []
        
        logs = []
        purchases_data = database.child('logs').child('purchases').get()
        
        if purchases_data.val() is not None:
            data = purchases_data.val()
            if isinstance(data, dict):
                sorted_items = sorted(data.items(), 
                                    key=lambda x: x[1].get('timestamp', ''), 
                                    reverse=True)
                
                for log_id, log_info in sorted_items[:limit]:
                    log = log_info.copy() if isinstance(log_info, dict) else {}
                    log['id'] = log_id
                    logs.append(log)
        
        return logs
    except Exception as e:
        print(f"[ERROR] Failed to fetch purchase logs: {e}")
        return []


def get_stock_logs(product_id=None, limit=50):
    """Fetch stock update logs"""
    try:
        database = get_realtime_db()
        if database is None:
            return []
        
        logs = []
        stock_data = database.child('logs').child('stock_updates').get()
        
        if stock_data.val() is not None:
            data = stock_data.val()
            if isinstance(data, dict):
                sorted_items = sorted(data.items(), 
                                    key=lambda x: x[1].get('timestamp', ''), 
                                    reverse=True)
                
                # Filter by product_id if specified
                if product_id:
                    sorted_items = [item for item in sorted_items 
                                  if item[1].get('product_id') == str(product_id)]
                
                for log_id, log_info in sorted_items[:limit]:
                    log = log_info.copy() if isinstance(log_info, dict) else {}
                    log['id'] = log_id
                    logs.append(log)
        
        return logs
    except Exception as e:
        print(f"[ERROR] Failed to fetch stock logs: {e}")
        return []


def get_transaction_logs(limit=100):
    """Fetch recent transaction logs"""
    try:
        database = get_realtime_db()
        if database is None:
            return []
        
        logs = []
        transactions_data = database.child('logs').child('transactions').get()
        
        if transactions_data.val() is not None:
            data = transactions_data.val()
            if isinstance(data, dict):
                sorted_items = sorted(data.items(), 
                                    key=lambda x: x[1].get('timestamp', ''), 
                                    reverse=True)
                
                for log_id, log_info in sorted_items[:limit]:
                    log = log_info.copy() if isinstance(log_info, dict) else {}
                    log['id'] = log_id
                    logs.append(log)
        
        return logs
    except Exception as e:
        print(f"[ERROR] Failed to fetch logs: {e}")
        return []


# =============== ADMIN/CHAT LOGS ===============

def save_chat_message(message, sender="bot"):
    """Save chat message to Firebase - DISABLED"""
    # Chat logging disabled - only transaction logs are saved
    return True


def get_chat_messages(limit=50):
    """Fetch recent chat messages - DISABLED"""
    # Chat logging disabled
    return []

