#!/usr/bin/env python
"""
Detect available COM ports and find ESP32
"""

import serial.tools.list_ports

print("=" * 70)
print("AVAILABLE COM PORTS")
print("=" * 70)

ports = serial.tools.list_ports.comports()

if not ports:
    print("\n❌ No COM ports found!")
    print("\nMake sure:")
    print("  1. ESP32 is plugged in via USB")
    print("  2. USB drivers are installed")
    print("  3. No other app is using the port")
else:
    print(f"\n✅ Found {len(ports)} COM port(s):\n")
    
    for i, port in enumerate(ports, 1):
        print(f"{i}. Port: {port.device}")
        print(f"   Description: {port.description}")
        print(f"   Manufacturer: {port.manufacturer}")
        print()

print("=" * 70)
print("If you see your ESP32, update app.py line with the correct COM port")
print("=" * 70)
