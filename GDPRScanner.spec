# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for GDPRScanner — onefile, no console window.
#
# Build:
#   pyinstaller GDPRScanner.spec
#
# Output: dist/GDPRScanner.exe

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # pystray Windows backend
        'pystray._win32',
        # Pillow image formats used by icon generation
        'PIL._imaging',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        # python-docx
        'docx',
        'docx.oxml',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        # openpyxl
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        # PyPDF2
        'PyPDF2',
        # xlrd
        'xlrd',
        # tkinter (usually auto-detected but listed explicitly)
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        # win32 (pystray dependency)
        'win32api',
        'win32con',
        'win32gui',
        'win32gui_struct',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the binary lean — exclude heavy unused packages
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GDPRScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX can trigger false-positive AV alerts — disabled
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # No console window (D-tray app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment if you add a .ico file later
)
