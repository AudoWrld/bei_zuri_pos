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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static\\images\\favicon.ico',
)