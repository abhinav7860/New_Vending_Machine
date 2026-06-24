#!/usr/bin/env python
"""
Clean up test transactions from Firebase
"""

from firebase_config import get_realtime_db
from datetime import datetime

print("=" * 80)
print("CLEANING UP TEST TRANSACTIONS FROM FIREBASE")
print("=" * 80)

db = get_realtime_db()

# Get all transactions
result = db.child('transaction_log').get()
txns = result.val()

# Find test transactions
test_patterns = [
    'TXN_TEST_',
    'TXN_SIM_',
]

to_delete = []
if txns:
    for log_key, txn_data in txns.items():
        for pattern in test_patterns:
            if pattern in log_key:
                to_delete.append(log_key)
                break

print(f"\nFound {len(to_delete)} test transaction(s) to delete:")
for key in to_delete:
    print(f"  • {key}")

if to_delete:
    print(f"\nDeleting test transactions...")
    for key in to_delete:
        try:
            db.child('transaction_log').child(key).remove()
            print(f"  ✓ Deleted: {key}")
        except Exception as e:
            print(f"  ✗ Error deleting {key}: {e}")
    
    print(f"\n✅ Cleanup complete! All test data removed.")
else:
    print(f"\nNo test transactions found to delete.")

print("\n" + "=" * 80)
print("Your Firebase database is now clean and ready for production data!")
print("=" * 80)
