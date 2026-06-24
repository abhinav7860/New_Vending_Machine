#!/usr/bin/env python
"""
Kill processes that might be holding COM6
"""

import os
import subprocess

print("=" * 70)
print("FINDING PROCESSES USING COM6")
print("=" * 70)

# Use tasklist to find processes
print("\nPossible culprits (close these):")
print("  • Arduino IDE")
print("  • PuTTY or other Terminal emulators")
print("  • Old Flask server instances")
print("  • Any other Serial Monitor")

print("\n" + "=" * 70)
print("QUICK FIXES:")
print("=" * 70)

print("\n1. Task Manager method:")
print("   • Press Ctrl+Shift+Esc to open Task Manager")
print("   • Look for: Arduino, putty, pyserial, or python processes")
print("   • Right-click → End Task")

print("\n2. PowerShell method (Admin required):")
print("   • Open PowerShell as Administrator")
print("   • Get-Process | Where-Object {$_.ProcessName -like '*arduino*' -or $_.ProcessName -like '*putty*'}")
print("   • Then: Stop-Process -Name <processname> -Force")

print("\n3. Unplug/Replug ESP32:")
print("   • Disconnect USB from ESP32")
print("   • Wait 5 seconds")
print("   • Reconnect USB to ESP32")
print("   • Start the Vending Machine app")

print("\n4. Check Device Manager:")
print("   • Windows Key + X → Device Manager")
print("   • Expand 'Ports (COM & LPT)'")
print("   • Right-click COM6 → Properties")
print("   • Check if driver is working properly")

print("\n" + "=" * 70)
print("After fixing, restart the Vending Machine app")
print("=" * 70)
