"""
Local JSON Logging System
Saves all transactions, purchases, and stock updates to local JSON files
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Determine the correct logs directory (works in both dev and exe modes)
if getattr(sys, 'frozen', False):
    # Running as exe - use external data directory
    exe_dir = os.path.dirname(sys.executable)
    # Try to find external data directory
    possible_data_dirs = [
        os.getenv('SENSEMART_DATA_DIR'),
        os.path.normpath(os.path.join(exe_dir, '..', 'data')),
        'C:\\SenseMart_V1\\data',
        os.path.expanduser('~\\SenseMart_V1\\data'),
    ]
    
    LOGS_DIR = None
    for data_dir in possible_data_dirs:
        if data_dir and os.path.isdir(data_dir):
            LOGS_DIR = os.path.join(data_dir, 'logs')
            break
    
    if LOGS_DIR is None:
        # Fallback to bundle directory
        LOGS_DIR = os.path.join(sys._MEIPASS, 'logs')
else:
    # Running in dev mode - use local logs folder relative to workspace
    LOGS_DIR = "logs"

# Ensure logs directory exists
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)

# Log files
PURCHASES_LOG = os.path.join(LOGS_DIR, "purchases.json")
STOCK_LOG = os.path.join(LOGS_DIR, "stock_updates.json")
TRANSACTIONS_LOG = os.path.join(LOGS_DIR, "transactions.json")
STOCK_STATUS_FILE = os.path.join(LOGS_DIR, "stock_status.json")


def _load_json(filepath):
    """Load JSON file, return empty list if not exists"""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return []
    return []


def _save_json(filepath, data):
    """Save data to JSON file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {filepath}: {e}")
        return False


def log_purchase_local(product_id, product_name, price, quantity=1):
    """Log purchase to local JSON AND Firebase"""
    try:
        timestamp = datetime.now().isoformat()
        date_str = datetime.now().strftime('%Y-%m-%d')
        time_str = datetime.now().strftime('%H:%M:%S')
        
        purchase_data = {
            'product_id': str(product_id),
            'product_name': product_name,
            'price': float(price),
            'quantity': int(quantity),
            'action': 'PURCHASE',
            'timestamp': timestamp,
            'date': date_str,
            'time': time_str
        }
        
        # Save to local JSON
        purchases = _load_json(PURCHASES_LOG)
        purchases.append(purchase_data)
        
        if _save_json(PURCHASES_LOG, purchases):
            print(f"[LOCAL LOG] ✓ Purchase: {product_name} x{quantity} @ ₹{price}")
            
            # Also save to Firebase if available (using Admin SDK for authentication)
            try:
                from firebase_admin import db as admin_db
                unique_key = f"{date_str}_{time_str}_{product_id}"
                path = f"purchases/{unique_key}"
                ref = admin_db.reference(path)
                ref.set(purchase_data)
                print(f"[FIREBASE] ✓ Purchase logged")
            except Exception as firebase_error:
                print(f"[FIREBASE] ✗ Could not log to Firebase: {firebase_error}")
            
            return True
    except Exception as e:
        print(f"[ERROR] Failed to log purchase: {e}")
    return False


def log_stock_update_local(product_id, product_name, old_stock, new_stock, reason="MANUAL"):
    """Log stock update to local JSON AND Firebase"""
    try:
        timestamp = datetime.now().isoformat()
        date_str = datetime.now().strftime('%Y-%m-%d')
        time_str = datetime.now().strftime('%H:%M:%S')
        stock_change = new_stock - old_stock
        
        stock_data = {
            'product_id': str(product_id),
            'product_name': product_name,
            'old_stock': int(old_stock),
            'new_stock': int(new_stock),
            'stock_change': int(stock_change),
            'reason': reason,
            'timestamp': timestamp,
            'date': date_str,
            'time': time_str
        }
        
        stocks = _load_json(STOCK_LOG)
        stocks.append(stock_data)
        
        if _save_json(STOCK_LOG, stocks):
            action = "RESTOCKED" if stock_change > 0 else "SOLD"
            print(f"[LOCAL LOG] ✓ Stock: {product_name} {action} - {old_stock} → {new_stock}")
            
            # Also save to Firebase if available (using Admin SDK for authentication)
            try:
                from firebase_admin import db as admin_db
                unique_key = f"{date_str}_{time_str}_{product_id}"
                path = f"stock_updates/{unique_key}"
                ref = admin_db.reference(path)
                ref.set(stock_data)
                print(f"[FIREBASE] ✓ Stock update logged")
            except Exception as firebase_error:
                print(f"[FIREBASE] ✗ Could not log to Firebase: {firebase_error}")
            
            return True
    except Exception as e:
        print(f"[ERROR] Failed to log stock update: {e}")
    return False


def log_transaction_local(product_id, product_name, action="purchase", quantity=1, final_stock=0, transaction_type="sold", price=0, transaction_id=None, image_path=None):
    """Log transaction to local JSON AND Firebase with all fields including image path"""
    try:
        timestamp = datetime.now().isoformat()
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M:%S")
        
        # Complete transaction log with all fields
        transaction_data = {
            'transaction_id': transaction_id or f"TXN_{int(datetime.now().timestamp() * 1000)}",
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
        
        # Add image_path only if provided
        if image_path:
            transaction_data['image_path'] = image_path
        
        transactions = _load_json(TRANSACTIONS_LOG)
        transactions.append(transaction_data)
        
        if _save_json(TRANSACTIONS_LOG, transactions):
            img_str = f", Image={image_path}" if image_path else ""
            print(f"[LOCAL LOG] ✓ TXN_ID={transaction_data['transaction_id']}, Item={product_name}, Qty={quantity}, Type={transaction_type}{img_str}")
            
            # Also save to Firebase if available (using Admin SDK for authentication)
            try:
                from firebase_admin import db as admin_db
                txn_id = transaction_data['transaction_id']
                unique_key = f"{date_str}_{time_str}_{txn_id}_{product_id}"
                path = f"transaction_log/{unique_key}"
                ref = admin_db.reference(path)
                ref.set(transaction_data)
                print(f"[FIREBASE] ✓ Transaction logged")
            except Exception as firebase_error:
                print(f"[FIREBASE] ✗ Could not log to Firebase: {firebase_error}")
            
            return True
    except Exception as e:
        print(f"[ERROR] Failed to log transaction: {e}")
    return False


def update_stock_status_local(product_id, stock_count):
    """Update current stock status in local JSON"""
    try:
        status_data = _load_json(STOCK_STATUS_FILE)
        
        # If it's not a dict, make it one
        if not isinstance(status_data, dict):
            status_data = {}
        
        status_data[str(product_id)] = {
            'stock': int(stock_count),
            'last_updated': datetime.now().isoformat()
        }
        
        if _save_json(STOCK_STATUS_FILE, status_data):
            return True
    except Exception as e:
        print(f"[ERROR] Failed to update stock status: {e}")
    return False


def get_purchase_logs_local(limit=None):
    """Get purchase logs from local JSON"""
    purchases = _load_json(PURCHASES_LOG)
    if limit:
        return purchases[-limit:]
    return purchases


def get_stock_logs_local(product_id=None, limit=None):
    """Get stock logs from local JSON"""
    stocks = _load_json(STOCK_LOG)
    
    if product_id:
        stocks = [s for s in stocks if s.get('product_id') == str(product_id)]
    
    if limit:
        return stocks[-limit:]
    return stocks


def get_transaction_logs_local(limit=None):
    """Get transaction logs from local JSON"""
    transactions = _load_json(TRANSACTIONS_LOG)
    if limit:
        return transactions[-limit:]
    return transactions


def get_stock_status_local():
    """Get current stock status from local JSON"""
    status = _load_json(STOCK_STATUS_FILE)
    return status if isinstance(status, dict) else {}


def check_consecutive_sales_and_update_price(product_id, current_price):
    """
    Check if total SOLD transactions for this product is a multiple of 3 (3, 6, 9, 12, etc).
    If yes, increase price by 10% and round down.
    Only increase once per 3-purchase milestone.
    Returns: new_price (int/float) or None if no update needed
    """
    try:
        transactions = get_transaction_logs_local()
        
        if not transactions:
            return None
        
        # Get all SOLD transactions for this product
        product_sold = [t for t in transactions if t.get('product_id') == str(product_id) and t.get('transaction_type') == 'sold']
        
        total_sold = len(product_sold)
        
        # Check if total sold count is exactly divisible by 3 (3, 6, 9, 12, etc.)
        if total_sold > 0 and total_sold % 3 == 0:
            # This is a milestone (3rd, 6th, 9th purchase)
            # Calculate 10% increase and round down (floor)
            new_price = int(current_price * 1.10)
            print(f"[PRICE UPDATE] Product {product_id}: Sold {total_sold} times. Price increased from {current_price} to {new_price} (10% increase)")
            return new_price
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to check consecutive sales: {e}")
        return None


def print_logs_summary():
    """Print summary of all logs"""
    print("\n" + "="*60)
    print("LOCAL LOGS SUMMARY")
    print("="*60)
    
    purchases = get_purchase_logs_local()
    stocks = get_stock_logs_local()
    transactions = get_transaction_logs_local()
    status = get_stock_status_local()
    
    print(f"\n📦 Purchases: {len(purchases)} records")
    if purchases:
        print(f"   First: {purchases[0]['date']} {purchases[0]['time']}")
        print(f"   Last:  {purchases[-1]['date']} {purchases[-1]['time']}")
    
    print(f"\n📊 Stock Updates: {len(stocks)} records")
    if stocks:
        print(f"   First: {stocks[0]['date']} {stocks[0]['time']}")
        print(f"   Last:  {stocks[-1]['date']} {stocks[-1]['time']}")
    
    print(f"\n💾 Transactions: {len(transactions)} records")
    if transactions:
        print(f"   First: {transactions[0]['date']} {transactions[0]['time']}")
        print(f"   Last:  {transactions[-1]['date']} {transactions[-1]['time']}")
    
    print(f"\n📈 Current Stock Status: {len(status)} products")
    for product_id, info in sorted(status.items()):
        print(f"   Product {product_id}: {info['stock']} units")
    
    print("\n" + "="*60)
    print(f"Log files location: {os.path.abspath(LOGS_DIR)}")
    print("="*60 + "\n")
