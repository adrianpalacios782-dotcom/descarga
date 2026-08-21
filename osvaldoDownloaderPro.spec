# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None
ROOT = os.path.abspath('.')

# Collectar yt_dlp completo (incluye sus extractors, hooks y dependencias)
ytdlp_datas, ytdlp_binaries, ytdlp_hiddenimports = collect_all('yt_dlp')

# Collectar curl_cffi completo (incluye _wrapper.pyd y datos)
curl_datas, curl_binaries, curl_hiddenimports = collect_all('curl_cffi')

# Collectar imageio_ffmpeg (incluye su binario ffmpeg embebido)
iio_datas, iio_binaries, iio_hiddenimports = collect_all('imageio_ffmpeg')

# PySide6 hidden imports que PyInstaller podría no detectar
pyside6_hidden = collect_submodules('PySide6.QtCore') + collect_submodules('PySide6.QtGui') + collect_submodules('PySide6.QtWidgets')

a = Analysis(
    [os.path.join(ROOT, 'run.py')],
    pathex=[ROOT, os.path.join(ROOT, 'src')],
    binaries=[
        (os.path.join(ROOT, 'bin', 'ffmpeg.exe'), '.'),
        (os.path.join(ROOT, 'bin', 'ffprobe.exe'), '.'),
    ] + ytdlp_binaries + curl_binaries + iio_binaries,
    datas=ytdlp_datas + curl_datas + iio_datas,
    hiddenimports=ytdlp_hiddenimports + curl_hiddenimports + iio_hiddenimports + pyside6_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'tkinter', 'unittest', 'test', 'tests',
        'pytest', 'py.test', 'pytest_cache',
        'IPython', 'jupyter', 'notebook',
        'sphinx', 'docutils', 'setuptools',
        'youtube_dl', 'youtube_dlc', 'ytdlp_plugins', 'devscripts',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='osvaldoDownloaderPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='osvaldoDownloaderPro',
    contents_directory='.',
)
