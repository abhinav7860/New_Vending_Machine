from firebase_config import get_realtime_db  # This will initialize Firebase Admin SDK
from firebase_admin import db
from datetime import datetime

try:
    # Use Admin SDK which is authenticated
    timestamp = datetime.now().isoformat()
    date_str = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M:%S')
    
    test_data = {
        'test': 'transaction',
        'timestamp': timestamp,
        'date': date_str,
        'time': time_str
    }
    
    unique_key = f"TEST_{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}"
    path = f"transaction_log/{unique_key}"
    print(f'Attempting to write to {path}')
    ref = db.reference(path)
    ref.set(test_data)
    print(f'[SUCCESS] Transaction written!')
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()

