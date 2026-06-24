#!/usr/bin/env python3
"""
Quick test script to diagnose weight sensor issues
"""
import serial
import time
import sys

def find_serial_port():
    """Find available COM ports"""
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    
    print("Available COM ports:")
    for port in ports:
        print(f"  - {port.device}: {port.description}")
    return ports

def test_weight_sensor():
    """Test weight sensor connection and readings"""
    ports = find_serial_port()
    
    if not ports:
        print("\n[ERROR] No COM ports found. Check ESP32 connection.")
        return False
    
    # Try each port
    for port_info in ports:
        port = port_info.device
        print(f"\n[TEST] Trying port: {port}")
        
        try:
            ser = serial.Serial(port, 9600, timeout=1)
            time.sleep(1)  # Wait for connection
            
            # Clear buffer
            ser.reset_input_buffer()
            time.sleep(0.3)
            
            # Send GET command
            print("[SEND] GET")
            ser.write(b'GET\r\n')
            time.sleep(0.5)
            
            # Read response
            response = b''
            for _ in range(10):
                if ser.in_waiting > 0:
                    response += ser.read(ser.in_waiting)
                time.sleep(0.1)
            
            if response:
                print(f"[RECEIVE] {response}")
                
                # Parse response
                try:
                    text = response.decode('utf-8', errors='ignore').strip()
                    if text.startswith('B') or text.startswith('b'):
                        # Parse format: B1xxxB2xxxB3xxxB4xxx
                        weights = {}
                        i = 0
                        while i < len(text):
                            if text[i].upper() == 'B' and i+1 < len(text):
                                slot = text[i+1]
                                weight_str = ''
                                i += 2
                                while i < len(text) and text[i].isdigit():
                                    weight_str += text[i]
                                    i += 1
                                if slot.isdigit() and weight_str:
                                    weights[int(slot)] = int(weight_str)
                            else:
                                i += 1
                        
                        if weights:
                            print(f"[PARSED] Bin weights:")
                            for slot, weight in sorted(weights.items()):
                                print(f"  Slot {slot}: {weight}g")
                            
                            ser.close()
                            print(f"\n[SUCCESS] Sensor working on {port}")
                            return True
                except Exception as e:
                    print(f"[ERROR] Failed to parse response: {e}")
            else:
                print("[ERROR] No response received")
            
            ser.close()
        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")
    
    print("\n[FAIL] Could not communicate with weight sensor on any port")
    return False

if __name__ == '__main__':
    print("="*60)
    print("Weight Sensor Diagnostic Tool")
    print("="*60)
    
    success = test_weight_sensor()
    sys.exit(0 if success else 1)
