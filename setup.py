#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup script to build Windows EXE for Vending Machine App using py2exe
Run: python setup.py py2exe
"""

from py2exe import py2exe
from distutils.core import setup
import os
import sys

# Collect all template files
template_files = []
templates_dir = 'templates'
if os.path.exists(templates_dir):
    for filename in os.listdir(templates_dir):
        if filename.endswith('.html'):
            template_files.append(os.path.join(templates_dir, filename))

# Collect static files
static_files = []
static_dir = 'static'
if os.path.exists(static_dir):
    static_files.append(os.path.join(static_dir, 'style.css'))

# Collect product images
product_images = []
product_images_dir = os.path.join(static_dir, 'product_images')
if os.path.exists(product_images_dir):
    for filename in os.listdir(product_images_dir):
        product_images.append(os.path.join(product_images_dir, filename))

# Data files to include
data_files = [
    ('templates', template_files),
    (os.path.join('static'), [os.path.join('static', 'style.css')]),
    (os.path.join('static', 'product_images'), product_images),
    ('.', ['database.db', 'firebase_credentials.json', 'requirements.txt']),
]

# Create logs folder if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

setup(
    name='VendingMachine',
    version='1.0.0',
    description='Smart Vending Machine Control System',
    author='Your Name',
    windows=[
        {
            'script': 'app.py',
            'dest_base': 'VendingMachine',
            'icon_resources': [(1, 'app.ico')] if os.path.exists('app.ico') else [],
        }
    ],
    data_files=data_files,
    options={
        'py2exe': {
            'packages': [
                'flask',
                'sqlite3',
                'serial',
                'requests',
                'jinja2',
                'werkzeug',
                'firebase_admin',
                'pyaudio',
                'speech_recognition',
                'reportlab',
            ],
            'includes': [
                'encodings',
                'encodings.utf_8',
                'json',
                'datetime',
                'threading',
                'time',
                'base64',
                're',
                'os',
                'sys',
            ],
            'excludes': ['matplotlib', 'numpy', 'pandas', 'scipy'],
            'dist_dir': 'dist',
            'build_dir': 'build',
            'bundle_files': 1,  # Bundle everything into exe
            'compressed': True,
            'optimize': 2,
            'dll_excludes': ['w9xpopen.exe', 'MSVCP90.dll'],
        }
    },
)

print("\n" + "="*60)
print("BUILD COMPLETE!")
print("="*60)
print("\nYour EXE has been created in the 'dist' folder:")
print("  - dist/VendingMachine.exe")
print("\nTo run the application:")
print("  1. Copy the 'dist' folder to your deployment location")
print("  2. Double-click VendingMachine.exe")
print("\nRequired files in the same folder as .exe:")
print("  - database.db")
print("  - firebase_credentials.json")
print("  - templates/ folder")
print("  - static/ folder")
print("  - logs/ folder (will be created if missing)")
print("="*60 + "\n")
