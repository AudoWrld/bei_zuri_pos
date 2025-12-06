# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Get the base directory
base_dir = os.path.abspath('.')

# List of Django apps to include
django_apps = [
    'inventory', 'users', 'settings', 'hardware', 'sync', 'reports',
    'sales', 'payments', 'dashboard', 'customers', 'products', 'delivery'
]

# Collect Django data files
datas = [
    ('bei_zuri_pos', 'bei_zuri_pos'),
    ('manage.py', '.'),
]

# Add directories if they exist
for directory in ['static', 'media', 'templates', 'staticfiles']:
    if os.path.exists(directory):
        datas.append((directory, directory))

# Add each Django app
for app in django_apps:
    if os.path.exists(app):
        datas.append((app, app))

# Add database if it exists
if os.path.exists('db.sqlite3'):
    datas.append(('db.sqlite3', '.'))

a = Analysis(
    ['desktop_app.py'],
    pathex=[base_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Core Django
        'django',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.core.management',
        'django.core.mail',
        'django.db.backends.sqlite3',
        'django.template.loaders.filesystem',
        'django.template.loaders.app_directories',
        
        # Server and webview
        'waitress',
        'webview',
        'multiprocessing',
        'socket',
        'threading',
        'whitenoise', 
        'whitenoise.middleware', 
        'whitenoise.storage',
        
        # All your Django apps
        'inventory',
        'users',
        'settings',
        'hardware',
        'sync',
        'reports',
        'sales',
        'payments',
        'dashboard',
        'customers',
        'products',
        'delivery',
        
        # Other dependencies
        'PIL',
        'reportlab',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BeiZuriPOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Keep True for testing, change to False when it works
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static\\images\\favicon.ico',
)