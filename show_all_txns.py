#!/usr/bin/env python
# Show all transactions in detail

from firebase_config import get_realtime_db
import json

db = get_realtime_db()
result = db.child('transaction_log').get()
txns = result.val()

print("All transactions in Firebase:\n")
print(json.dumps(dict(txns), indent=2, default=str))
