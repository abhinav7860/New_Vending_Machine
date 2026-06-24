#!/usr/bin/env python
# Read all transactions from Firebase

from firebase_config import get_realtime_db
from datetime import datetime

print("=" * 60)
print("Reading All Transactions from Firebase")
print("=" * 60)

db = get_realtime_db()

try:
    print("\nFetching transaction_log...")
    result = db.child('transaction_log').get()
    
    if result.val():
        transactions = result.val()
        print(f"\nFound {len(transactions)} transaction(s):\n")
        
        for txn_id, txn_data in transactions.items():
            print(f"TXN ID: {txn_id}")
            print(f"  Item: {txn_data.get('item', 'N/A')}")
            print(f"  Quantity: {txn_data.get('quantity', 'N/A')}")
            print(f"  Timestamp: {txn_data.get('timestamp', 'N/A')}")
            print()
    else:
        print("\nNo transactions found in Firebase!")
        
except Exception as e:
    print(f"\nError reading transactions: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
print("Complete")
print("=" * 60)
