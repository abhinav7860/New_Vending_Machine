#!/usr/bin/env python
# Simulate a complete purchase transaction to Firebase

from firebase_db import log_transaction
from local_logs import log_transaction_local
from datetime import datetime
import time

print("=" * 70)
print("SIMULATING COMPLETE PURCHASE - FIREBASE & LOCAL LOGGING")
print("=" * 70)

# Generate transaction ID
txn_id = f"TXN_SIM_{int(datetime.now().timestamp() * 1000)}"
timestamp = datetime.now().isoformat()

print(f"\nSimulating purchase:")
print(f"  Transaction ID: {txn_id}")
print(f"  Timestamp: {timestamp}")
print()

# Simulate 3 products purchased at same time (multi-bin)
products = [
    {'id': 1, 'name': 'Apple', 'quantity': 2},
    {'id': 2, 'name': 'Orange', 'quantity': 1},
    {'id': 3, 'name': 'Banana', 'quantity': 3}
]

print("Logging transactions to Firebase and Local logs...\n")

for product in products:
    print(f"Logging: {product['name']} (Qty: {product['quantity']})")
    
    # Log to Firebase
    try:
        result_firebase = log_transaction(
            product_id=str(product['id']),
            product_name=product['name'],
            transaction_id=txn_id,
            quantity=product['quantity']
        )
        print(f"  ✓ Firebase: {result_firebase}")
    except Exception as e:
        print(f"  ✗ Firebase Error: {e}")
    
    # Log to Local
    try:
        result_local = log_transaction_local(
            product_id=str(product['id']),
            product_name=product['name'],
            transaction_id=txn_id,
            quantity=product['quantity']
        )
        print(f"  ✓ Local: {result_local}")
    except Exception as e:
        print(f"  ✗ Local Error: {e}")
    
    time.sleep(0.5)
    print()

print("=" * 70)
print("VERIFICATION - Reading back from Firebase")
print("=" * 70)

from firebase_config import get_realtime_db

db = get_realtime_db()
print(f"\nChecking transaction_log for {txn_id}...\n")

for product in products:
    try:
        result = db.child('transaction_log').child(f"{txn_id}_product_{product['id']}").get()
        if result.val():
            print(f"✓ Found {product['name']}: {result.val()}")
        else:
            # Try alternate key format
            result2 = db.child('transaction_log').get()
            if result2.val():
                all_txns = result2.val()
                matching = [t for tid, t in all_txns.items() if txn_id in tid]
                if matching:
                    print(f"✓ Found transactions for TXN {txn_id}")
    except Exception as e:
        print(f"Note: {e}")

print("\n" + "=" * 70)
print("Simulation Complete - Check Firebase console or run read_firebase.py")
print("=" * 70)
