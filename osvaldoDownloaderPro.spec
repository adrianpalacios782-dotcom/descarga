# -*- mode: python ; coding: utf-8 -*-
#
# Spec de empaquetado onedir para osvaldoDownloaderPro.
#
# Estandares de reputacion Windows aplicados:
#   - UPX DESACTIVADO (upx=False): los empaquetadores ejecutables disparan
#     heuristicas de malware (Smart App Control, Defender, etc.), duplican el
#     costo de arranque (descompresion en memoria) y corrompen firmas
#     Authenticode posteriores. Sin compresion externa el exe queda tal cual
#     lo produce MSVC y firma limpio.
#   - Recurso VERSIONINFO incrustado (version=scripts/version_info.txt):
#     identidad completa en Propiedades del archivo. Mantener sincronizado con
#     src/__init__.py (__version__); build_release.ps1 valida la coincidencia.
#
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
ROOT = os.path.abspath('.')

# Collectar yt_dlp completo (incluye sus extractors, hooks y dependencias)
ytdlp_datas, ytdlp_binaries, ytdlp_hiddenimports = collect_all('yt_dlp')

# Collectar curl_cffi completo (incluye _wrapper.pyd y datos)
curl_datas, curl_binaries, curl_hiddenimports = collect_all('curl_cffi')

# Collectar imageio_ffmpeg (incluye su binario ffmpeg embebido, fallback del motor)
iio_datas, iio_binaries, iio_hiddenimports = collect_all('imageio_ffmpeg')

# PySide6 hidden imports que PyInstaller podría no detectar
pyside6_hidden = collect_submodules('PySide6.QtCore') + collect_submodules('PySide6.QtGui') + collect_submodules('PySide6.QtWidgets')

# Modulos de primera parte y stdlib referenciados dinamicamente o criticos
# para el gestor de motor actualizable (EngineManager en %APPDATA%).
app_hiddenimports = [
    'src.infrastructure.adapters.engine',
    'zipfile',
    'hashlib',
    'urllib.request',
]

a = Analysis(
    [os.path.join(ROOT, 'run.py')],
    pathex=[ROOT, os.path.join(ROOT, 'src')],
    # ffmpeg/ffprobe NO se incluyen aqui: build_release.ps1 los copia desde
    # bin\\ a la raiz de dist tras el build (layout unico esperado por
    # installer.iss y FFmpegProcessAdapter). Incluirlos tambien via Analysis
    # los duplicaria dentro de _internal (+150 MB sin beneficio).
    binaries=ytdlp_binaries + curl_binaries + iio_binaries,
    # Assets de UI: los temas QSS se generan desde codigo
    # (src/presentation/styles/theme.py -> build_qss), no hay archivos
    # externos que empacar. Si se agregan iconos/recursos, van aqui:
    #   datas=[(os.path.join(ROOT, 'assets'), 'assets')] + ...
    datas=ytdlp_datas + curl_datas + iio_datas,
    hiddenimports=(
        ytdlp_hiddenimports
        + curl_hiddenimports
        + iio_hiddenimports
        + pyside6_hidden
        + app_hiddenimports
    ),
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    version=os.path.join(ROOT, 'scripts', 'version_info.txt'),
    # icon=... : pendiente hasta existir assets/brand.ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='osvaldoDownloaderPro',
    # Layout estandar PyInstaller 6: dependencias en _internal\\ junto al exe.
    # Era '.': rompia el layout _internal que consumen installer.iss
    # (Source: "dist\\...\\_internal\\*") y la verificacion de artefactos de
    # build_release.ps1.
    contents_directory='_internal',
)
