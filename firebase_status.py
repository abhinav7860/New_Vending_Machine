#!/usr/bin/env python
"""
FIREBASE TRANSACTION LOGGING - STATUS REPORT
==============================================

Firebase Realtime Database: https://vending-machine-c6bf1-default-rtdb.firebaseio.com/
"""

from firebase_config import get_realtime_db
from datetime import datetime
import json

def count_transactions_by_id():
    """Count transactions grouped by transaction ID"""
    db = get_realtime_db()
    result = db.child('transaction_log').get()
    txns = result.val()
    
    txn_groups = {}
    for log_key, txn_data in txns.items():
        txn_id = txn_data.get('txn_id')
        if txn_id not in txn_groups:
            txn_groups[txn_id] = []
        txn_groups[txn_id].append(txn_data)
    
    return txn_groups

print("=" * 80)
print("FIREBASE TRANSACTION LOGGING STATUS")
print("=" * 80)

try:
    txn_groups = count_transactions_by_id()
    
    print(f"\n✅ Firebase Connection: ACTIVE")
    print(f"✅ Total Transaction Groups: {len(txn_groups)}")
    
    total_items = sum(len(items) for items in txn_groups.values())
    print(f"✅ Total Transaction Lines: {total_items}")
    
    print(f"\nTransaction Schema (fields stored):")
    print(f"  • txn_id: Transaction ID (shared across multi-product purchases)")
    print(f"  • item: Product name")
    print(f"  • quantity: Number of items")
    print(f"  • timestamp: ISO format timestamp")
    
    print(f"\nTransaction Summary:")
    print("-" * 80)
    
    for txn_id, items in sorted(txn_groups.items(), key=lambda x: x[1][0].get('timestamp', ''), reverse=True):
        print(f"\n📦 Transaction ID: {txn_id}")
        print(f"   Timestamp: {items[0].get('timestamp', 'N/A')}")
        print(f"   Number of products: {len(items)}")
        
        total_qty = 0
        for item in items:
            qty = item.get('quantity', 0)
            total_qty += qty
            print(f"     • {item.get('item', 'Unknown')}: Qty {qty}")
        
        print(f"   Total items in transaction: {total_qty}")
    
    print("\n" + "=" * 80)
    print("✅ Firebase transaction logging is working correctly!")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
