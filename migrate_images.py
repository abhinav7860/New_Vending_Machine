#!/usr/bin/env python3
"""
Migrate missing image_path entries in transactions.json
This script will backfill image_path for transactions that have corresponding capture files
"""

import json
import os
from pathlib import Path

def migrate_transaction_images():
    """Backfill transaction_id and image_path for older transactions"""
    
    trans_file = "logs/transactions.json"
    captures_folder = "static/captures"
    
    if not os.path.exists(trans_file):
        print(f"[ERROR] {trans_file} not found")
        return False
    
    if not os.path.exists(captures_folder):
        print(f"[ERROR] {captures_folder} not found")
        return False
    
    # Load transactions
    with open(trans_file, 'r') as f:
        transactions = json.load(f)
    
    # Get list of available capture files
    capture_files = set(os.listdir(captures_folder))
    
    print(f"[MIGRATE] Found {len(transactions)} transactions")
    print(f"[MIGRATE] Found {len(capture_files)} capture files")
    
    updated_count = 0
    
    # Process each transaction
    for i, transaction in enumerate(transactions):
        trans_id = transaction.get('transaction_id')
        
        # Skip if already has image_path
        if 'image_path' in transaction and transaction['image_path']:
            continue
        
        # If no transaction_id, try to generate one from timestamp
        if not trans_id:
            timestamp = transaction.get('timestamp', '')
            # Generate transaction_id from index and timestamp if available
            if timestamp:
                # Use last part of timestamp as basis for ID
                import hashlib
                hash_input = f"{i}_{timestamp}"
                hash_val = hashlib.md5(hash_input.encode()).hexdigest()[:8]
                trans_id = f"TXN_{int(timestamp.replace('-', '').replace('T', '').replace(':', '').split('.')[0])}"
            else:
                # Skip if we can't generate an ID
                continue
            transaction['transaction_id'] = trans_id
        
        # Check if corresponding capture file exists
        capture_filename = f"capture_{trans_id}.jpg"
        if capture_filename in capture_files:
            image_path = f"/static/captures/{capture_filename}"
            transaction['image_path'] = image_path
            updated_count += 1
            print(f"[MIGRATE] Transaction {trans_id}: Added image_path")
    
    # Save updated transactions
    if updated_count > 0:
        with open(trans_file, 'w') as f:
            json.dump(transactions, f, indent=2)
        print(f"\n[SUCCESS] Updated {updated_count} transactions with image_path")
        print(f"[SUCCESS] Saved changes to {trans_file}")
        return True
    else:
        print(f"\n[INFO] No transactions with matching capture files found")
        print(f"[INFO] This is expected if captures were not enabled for past transactions")
        return True


if __name__ == "__main__":
    migrate_transaction_images()
