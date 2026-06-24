#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fix Unicode characters in HTML template files
"""
import os
import glob

# Define replacements
replacements = {
    '₹': 'Rs',
    '⚡': '[SURGE]',
    '🛍️': '[SHOP]',
    '💳': '[PAYMENT]',
    '✓': '[CHECK]',
    '✗': '[X]',
    '⚠️': '[WARNING]',
    '❌': '[ERROR]',
    '✅': '[OK]',
    '📦': '[PACKAGE]',
    '🚚': '[DELIVERY]',
    '⏰': '[TIME]',
    '🎁': '[GIFT]',
    '💰': '[MONEY]',
    '📊': '[CHART]',
    '📈': '[UP]',
}

# Find and fix all HTML files
html_files = glob.glob('templates/**/*.html', recursive=True)
total_replacements = 0

for html_file in html_files:
    if not os.path.exists(html_file):
        continue
        
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    for char, replacement in replacements.items():
        if char in content:
            count = content.count(char)
            total_replacements += count
            content = content.replace(char, replacement)
    
    if content != original_content:
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {html_file}")

print(f"\nTotal replacements made: {total_replacements}")
