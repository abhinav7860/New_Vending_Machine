#!/usr/bin/env python
"""
Test end-to-end purchase flow with Firebase logging
"""

print("=" * 80)
print("TESTING END-TO-END PURCHASE FLOW")
print("=" * 80)

# Step 1: Test weight reading in mock mode
print("\n[STEP 1] Testing MOCK weight reading...")
import os
os.environ['MOCK_WEIGHT_SENSOR'] = 'true'

from app import get_weight_reading, MOCK_WEIGHT_SENSOR
print(f"Mock mode enabled: {MOCK_WEIGHT_SENSOR}")

initial = get_weight_reading()
print(f"Initial weights: {initial}")

final = get_weight_reading()
print(f"Final weights: {final}")

# Calculate difference
if initial and final:
    diff_1 = initial.get(1, 0) - final.get(1, 0)
    print(f"Slot 1 weight diff: {diff_1}g")

# Step 2: Test transaction logging
print("\n[STEP 2] Testing Firebase transaction logging...")
from firebase_db import log_transaction
from firebase_config import get_realtime_db

txn_id = f"TXN_TEST_{int(__import__('time').time() * 1000)}"
print(f"Test TXN ID: {txn_id}")

result = log_transaction(
    product_id='1',
    product_name='Test Product',
    quantity=1,
    transaction_id=txn_id
)
print(f"Log result: {result}")

# Step 3: Verify in Firebase
print("\n[STEP 3] Verifying transaction in Firebase...")
db = get_realtime_db()
firebase_result = db.child('transaction_log').get()
txns = firebase_result.val()

if txns:
    matching = [t for tid, t in txns.items() if txn_id in tid]
    print(f"✅ Found {len(matching)} transaction(s) for {txn_id}")
    if matching:
        print(f"Transaction data: {matching[0]}")
else:
    print(f"❌ No transactions found in Firebase!")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
