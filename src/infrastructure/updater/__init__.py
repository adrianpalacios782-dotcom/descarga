"""Sistema de actualización automática de osvaldoDownloaderPro.

Fuente oficial: GitHub Releases (ver update_config.py).
Diseño seguro: HTTPS obligatorio, allowlist de hosts, verificación SHA-256
obligatoria antes de ejecutar, archivos temporales con limpieza garantizada.
"""
from src.infrastructure.updater.github_releases_source import GitHubReleasesSource
from src.infrastructure.updater.installer_downloader import InstallerDownloader
from src.infrastructure.updater.installer_launcher import (
    InstallerLauncher,
    cleanup_stale_update_dirs,
    is_frozen_app,
    make_update_tempdir,
)

__all__ = [
    "GitHubReleasesSource",
    "InstallerDownloader",
    "InstallerLauncher",
    "cleanup_stale_update_dirs",
    "is_frozen_app",
    "make_update_tempdir",
]
