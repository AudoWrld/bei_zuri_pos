import os

block_cipher = None

base_dir = os.path.abspath('.')

django_apps = [
    'inventory', 'users', 'settings', 'hardware', 'sync', 'reports',
    'sales', 'payments', 'dashboard', 'customers', 'products', 'delivery'
]

datas = [
    ('templates/splash.html', 'templates'),
    ('bei_zuri_pos', 'bei_zuri_pos'),
    ('manage.py', '.'),
]

for directory in ['static', 'media', 'templates', 'staticfiles']:
    if os.path.exists(directory):
        datas.append((directory, directory))

for app in django_apps:
    if os.path.exists(app):
        datas.append((app, app))

a = Analysis(
    ['desktop_app.py'],
    pathex=[base_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'django',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.core.management',
        'django.core.management.commands',
        'django.core.management.commands.makemigrations',
        'django.core.management.commands.migrate',
        'django.core.mail',
        'django.db.backends.sqlite3',
        'django.template.loaders.filesystem',
        'django.template.loaders.app_directories',
        'waitress',
        'webview',
        'multiprocessing',
        'socket',
        'threading',
        'whitenoise',
        'whitenoise.middleware',
        'whitenoise.storage',
        'rest_framework',
        'rest_framework.authtoken',
        'django_select2',
        'inventory',
        'inventory.models',
        'inventory.migrations',
        'users',
        'users.models',
        'users.migrations',
        'settings',
        'settings.models',
        'settings.migrations',
        'hardware',
        'hardware.models',
        'hardware.migrations',
        'sync',
        'sync.models',
        'sync.migrations',
        'sync.sync_manager',
        'sync.background_sync',
        'sync.api_client',
        'reports',
        'reports.models',
        'reports.migrations',
        'sales',
        'sales.models',
        'sales.migrations',
        'payments',
        'payments.models',
        'payments.migrations',
        'dashboard',
        'dashboard.models',
        'dashboard.migrations',
        'customers',
        'customers.models',
        'customers.migrations',
        'products',
        'products.models',
        'products.migrations',
        'delivery',
        'delivery.models',
        'delivery.migrations',
        'PIL',
        'reportlab',
        'requests',
        'dotenv',
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static\\images\\favicon.ico' if os.path.exists('static\\images\\favicon.ico') else None,
)