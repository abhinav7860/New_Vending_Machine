#!/usr/bin/env python
# Test Firebase transaction logging

from firebase_db import log_transaction
from firebase_config import get_realtime_db
from datetime import datetime

print("=" * 60)
print("Testing Firebase Transaction Logging")
print("=" * 60)

# Get database
db = get_realtime_db()
print(f"\n1. Database connection: {db}")
print(f"   Type: {type(db)}")

# Try to log a transaction
try:
    txn_id = 'TXN_TEST_' + str(int(datetime.now().timestamp() * 1000))
    print(f"\n2. Attempting to log transaction...")
    print(f"   Transaction ID: {txn_id}")
    print(f"   Product: Test Product")
    print(f"   Quantity: 2")
    
    result = log_transaction(
        product_id='1', 
        product_name='Test Product', 
        action='purchase', 
        quantity=2, 
        transaction_id=txn_id
    )
    
    print(f"\n3. Result: {result}")
    
    # Try to verify the transaction was stored
    print(f"\n4. Attempting to read back transaction...")
    try:
        read_result = db.child('transaction_log').child(txn_id).get()
        print(f"   Read result: {read_result.val()}")
    except Exception as e:
        print(f"   Error reading: {e}")
        
except Exception as e:
    print(f"\nError during transaction logging: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
