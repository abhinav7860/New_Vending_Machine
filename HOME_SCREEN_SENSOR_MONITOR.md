# Home Screen Sensor Monitoring - Implementation Summary

## Overview
Added real-time product detection and stock management to the home screen. When a product is taken from the vending machine during normal operation, it's automatically detected via weight sensors every 10 seconds, and the stock is updated in real-time on the home screen.

## Changes Made

### 1. **New API Endpoint: `/api/check_sensor_home` (app.py)**

**Location**: [app.py](app.py#L876-L957)

**Purpose**: Monitors weight sensors periodically and detects when products are taken

**Functionality**:
- Reads current weight from all 4 bins via ESP32 sensor
- Compares with previous weight readings to detect changes
- When weight decreases by >30g, identifies product taken
- Calculates quantity taken based on product weight
- Generates transaction ID with **HSTXN** prefix (Home Screen Transaction)
- Updates database stock immediately
- Logs transaction to local JSON logs
- Returns all products taken in the response

**Global Variable**: `HOME_SCREEN_LAST_WEIGHTS`
- Stores previous weight readings to track changes
- Updated after each check cycle

**Transaction ID Format**: `HSTXN_{timestamp_milliseconds}`
- Example: `HSTXN_1705752145300`
- Easy identification of home-screen-initiated transactions vs normal purchases

**Response Format**:
```json
{
    "success": true,
    "current_weights": {
        1: 1000,
        2: 950,
        3: 850,
        4: 700
    },
    "products_taken": [
        {
            "product_id": 1,
            "name": "Apple",
            "quantity": 1,
            "new_stock": 4,
            "transaction_id": "HSTXN_1705752145300",
            "weight_diff": 50
        }
    ],
    "timestamp": "2025-01-20T14:30:00.123456"
}
```

### 2. **Home Screen JavaScript Updates (templates/index.html)**

**Location**: [index.html](templates/index.html#L106-L148)

**New Functions**:

#### a. `checkSensorHomeScreen()` - Runs Every 10 Seconds
- Calls `/api/check_sensor_home` endpoint
- Processes products that were detected as taken
- Calls `updateProductStockDisplay()` for each product
- Logs activity to browser console

#### b. `updateProductStockDisplay()` - Updates UI
- Finds the product card by name on the page
- Updates the stock display with new quantity
- Adds visual feedback (golden flash animation)
- Removes "Buy Now" button if stock reaches 0
- Logs changes to console for debugging

**Polling Interval**:
```javascript
setInterval(checkSensorHomeScreen, 10000);  // Every 10 seconds
```

**Visual Feedback**:
- Stock numbers flash golden (#FFD700) for 1.5 seconds when updated
- Helps customers see real-time stock changes

### 3. **Transaction Logging**

**Location**: Both [app.py](app.py#L912-L933) and local_logs.py

**Transaction Details Logged**:
- `transaction_id`: HSTXN_{timestamp} format
- `product_id`: Bin slot number
- `product_name`: Product name
- `quantity`: Number of units taken
- `final_stock`: New stock level after transaction
- `transaction_type`: "sold"
- `price`: Product price
- `timestamp`: ISO format with milliseconds
- `date` & `time`: Separate date and time fields

## How It Works

### Sequence Diagram:
```
1. Home screen loads → REST API every 10 seconds
   ↓
2. checkSensorHomeScreen() → GET /api/check_sensor_home
   ↓
3. ESP32 sends weight via serial → GET command
   ↓
4. Compare current weights vs last weights
   ↓
5. If weight_diff > 30g → Product detected as taken
   ↓
6. Query database for product info (name, weight, price)
   ↓
7. Calculate quantity: quantity = weight_diff / product_weight
   ↓
8. Update database: UPDATE products SET stock = new_stock
   ↓
9. Generate HSTXN transaction ID
   ↓
10. Log transaction to local JSON
   ↓
11. Return response with products_taken array
   ↓
12. JavaScript updates product cards on home screen
   ↓
13. Visual feedback: golden flash on stock display
```

## Configuration

### Weight Sensor Threshold
- **Default**: 30g (products must show weight decrease > 30g to be detected)
- Location in code: `if weight_diff > 30:`
- Prevent false positives from minor vibrations

### Polling Interval
- **Default**: 10 seconds
- Location in code: `setInterval(checkSensorHomeScreen, 10000);`
- Configurable in index.html if needed faster/slower updates

### Product Weight
- Retrieved from database field `products.weight`
- Used to calculate quantity taken
- Example: If product weighs 50g and weight_diff is 100g → 2 units taken

## Testing

### Manual Testing Steps:
1. Start the vending machine app
2. Open home screen in browser
3. Check browser console (F12 → Console tab)
4. Manually take a product from the vending machine
5. Watch for console messages: `[HOME SCREEN] Products detected as taken:`
6. Verify stock count updates on the product card
7. Check transaction logs: `logs/transactions.json`
8. Verify HSTXN transaction ID is present

### Mock Testing (for development):
If using `MOCK_WEIGHT_SENSOR=true`:
- Simulated weight changes occur
- Check console for detection messages
- Transaction logs still created

## Log Locations

### Transaction Logs
- **File**: `logs/transactions.json`
- **Contains**: All HSTXN transactions with full details

### Console Output
- **Browser Console**: `F12 → Console tab`
- Look for `[HOME SCREEN]` and `[HOME SCREEN STOCK UPDATE]` messages

### Backend Logs
- **Terminal/Console**: `[HOME SCREEN SENSOR]` messages

## Troubleshooting

### Stock Not Updating
1. Check browser console for errors (F12)
2. Verify weight sensor is connected: Admin → Diagnostics
3. Ensure weight change > 30g
4. Check MOCK_WEIGHT_SENSOR setting

### Transactions Not Logged
1. Check `logs/` directory exists
2. Verify write permissions on logs folder
3. Check browser console for API errors
4. Review terminal output for [HOME SCREEN SENSOR] messages

### Transaction IDs Not HSTXN Format
1. Check if transaction came from normal buy flow (those should be TXN_)
2. Home screen detected products should be HSTXN_
3. Mixed transaction types are normal

## Benefits

✅ **Real-time Stock Updates**: Customers see current stock without page refresh
✅ **Automatic Detection**: No manual counting needed
✅ **Transaction Tracking**: Full audit trail with HSTXN prefix for identification
✅ **No Purchase Flow Required**: Works during idle/normal viewing
✅ **Visual Feedback**: Users know stock changed with golden flash animation
✅ **Database Sync**: Stock updates immediately in database
✅ **Logging**: All transactions properly logged for inventory management

## Files Modified

1. **app.py**
   - Added `HOME_SCREEN_LAST_WEIGHTS` global variable
   - Added `/api/check_sensor_home` endpoint (86 lines)

2. **templates/index.html**
   - Added `checkSensorHomeScreen()` function
   - Added `updateProductStockDisplay()` function
   - Added 10-second polling interval

## Future Enhancements

- [ ] Configurable weight threshold via admin panel
- [ ] Adjustable polling interval
- [ ] Alert notifications when products taken
- [ ] Stock animation options (smooth vs flash)
- [ ] Multi-language support for console messages
- [ ] Advanced analytics on product detection patterns

---

**Last Updated**: 2026-01-20
**Status**: ✅ Implemented and Ready for Testing
