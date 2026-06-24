#!/usr/bin/env python
"""
Simulate the weight verification flow
"""

import os
os.environ['MOCK_WEIGHT_SENSOR'] = 'true'

print("=" * 80)
print("SIMULATING WEIGHT VERIFICATION FLOW")
print("=" * 80)

from app import app, get_weight_reading, MOCK_WEIGHTS, FIREBASE_ENABLED
import json

print(f"\nFirebase enabled: {FIREBASE_ENABLED}")
print(f"Mock weights: {MOCK_WEIGHTS}")

# Simulate the purchase flow
with app.test_client() as client:
    product_id = 1
    
    # Step 1: Get initial weight
    print(f"\n[STEP 1] Getting initial weight for product {product_id}...")
    response = client.get(f'/api/weight/initial/{product_id}')
    print(f"Status: {response.status_code}")
    initial_data = response.get_json()
    print(f"Response: {initial_data}")
    
    if initial_data.get('success'):
        initial_weights = initial_data.get('weights')
        transaction_id = f"TXN_DIRECT_TEST_{int(__import__('time').time() * 1000)}"
        print(f"Initial weights: {initial_weights}")
        
        # Step 2: Verify weight change
        print(f"\n[STEP 2] Verifying weight change...")
        verify_payload = {
            'initial_weights': initial_weights,
            'transaction_id': transaction_id
        }
        
        response = client.post(
            f'/api/weight/verify/{product_id}',
            data=json.dumps(verify_payload),
            content_type='application/json'
        )
        print(f"Status: {response.status_code}")
        verify_data = response.get_json()
        print(f"Response: {json.dumps(verify_data, indent=2)}")
        
        if verify_data.get('verified'):
            print(f"\n✅ WEIGHT VERIFICATION PASSED!")
            print(f"   Message: {verify_data.get('message')}")
            print(f"   Transaction should be logged to Firebase")
        else:
            print(f"\n❌ WEIGHT VERIFICATION FAILED!")
            print(f"   Message: {verify_data.get('message')}")
            print(f"   This is why no transaction is being created")
    else:
        print(f"❌ Failed to get initial weight: {initial_data}")

print("\n" + "=" * 80)
