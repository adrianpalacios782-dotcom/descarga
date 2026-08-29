"""osvaldoDownloaderPro — paquete raíz.

FUENTE ÚNICA DE VERDAD DE LA VERSIÓN.
Todos los consumidores (UI, actualizador, pyproject vía setuptools dynamic,
build_release.ps1 e installer.iss a través del script de build) derivan de
este atributo. Para publicar una nueva versión, cambiar SOLO este valor.
"""

__version__ = "1.0.3"

APP_NAME = "osvaldoDownloaderPro"
