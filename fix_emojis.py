#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script removes all emoji and special unicode characters from app.py
to prevent UnicodeEncodeError on Windows consoles with cp1252 encoding.
"""

# Read the file with UTF-8
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define emoji/special character replacements
replacements = {
    '⏳': '[WAIT]',
    '✅': '[OK]',
    '🔍': '[SEARCH]',
    '⚠️': '[WARNING]',
    '❌': '[ERROR]',
    '📤': '[SEND]',
    '📥': '[RECEIVE]',
    '🔗': '[CONNECT]',
    '🌐': '[BROWSER]',
    '🛍️': '[SHOP]',
    '⚙️': '[SETTINGS]',
    '📋': '[LOG]',
    '💬': '[CHAT]',
    '🎤': '[VOICE]',
    '🔊': '[SOUND]',
    '🚪': '[DOOR]',
    '📸': '[CAPTURE]',
    '🎵': '[AUDIO]',
}

# Replace all emojis
count = 0
for emoji, replacement in replacements.items():
    if emoji in content:
        occurrences = content.count(emoji)
        count += occurrences
        content = content.replace(emoji, replacement)

# Write back
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Fixed {count} emoji/special characters in app.py")
