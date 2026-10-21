"""Configuración global de la suite de pruebas de osvaldoDownloaderPro.

Responsabilidades:
- Garantizar que exista el directorio base de temporales (`scratch/pytest_tmp`)
  que exige `--basetemp` en `pyproject.toml`. En un clon limpio `scratch/` no
  existe (está en `.gitignore`) y pytest falla al crear la carpeta de temporales.
- Exponer un `QApplication` único y compartido por toda la sesión.
- Neutralizar la red en las pruebas: el cargador de miniaturas nunca descarga
  imágenes reales. Sin esto, los hilos daemon de red seguían vivos al finalizar
  el intérprete y el proceso terminaba con un fallo nativo (access violation).
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

# Evitar dependencia de un servidor gráfico real en CI / terminal.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 1) Asegurar el directorio base de temporales ANTES de que pytest cree el basetemp.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
(_PROJECT_ROOT / "scratch").mkdir(exist_ok=True)

# PNG 1x1 válido y diminuto usado como miniatura falsa en las pruebas.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


# Referencia global para que la QApplication sobreviva hasta el final del
# proceso. Si el objeto se destruye antes que los widgets creados en las
# pruebas, PySide6 provoca un fallo nativo al salir.
_QAPP: "object | None" = None


@pytest.fixture(autouse=True)
def _restore_global_time_sleep() -> Iterator[None]:
    """Red de seguridad: ningun test puede dejar parcheado `time.sleep` globalmente.

    Parchear `time.sleep` a nivel de modulo (no con `monkeypatch`) es una bomba
    de reloja: el parche sobrevive al test y convierte cualquier bucle de sondeo
    con `time.sleep(...)` en un *busy-wait* que satura una CPU. En un runner
    lento (2 vCPU en GitHub Actions) eso roba CPU al hilo de descarga y provoca
    timeouts flaky en tests que, en local, pasaban siempre.

    Este fixture restaura el `time.sleep` original tras cada test, de modo que
    un parche accidental solo afecta al test que lo hizo.
    """
    original = time.sleep
    yield
    if time.sleep is not original:
        time.sleep = original


@pytest.fixture(scope="session", autouse=True)
def _qapp_reference() -> Iterator["object"]:
    """Crea (una sola vez) la QApplication y la retiene globalmente.

    Es autouse para garantizar que exista y persista aunque cada módulo de
    pruebas defina su propia fixture `qapp`. Al final cierra y libera los
    widgets de nivel superior para que Shiboken no destruya objetos Qt en un
    orden que provoque un fallo nativo al salir del intérprete.
    """
    global _QAPP
    from PySide6.QtWidgets import QApplication

    if _QAPP is None:
        _QAPP = QApplication.instance() or QApplication([])
    yield _QAPP
    _cleanup_qt_widgets()


def _cleanup_qt_widgets() -> None:
    """Cierra los widgets de nivel superior y fuerza una recolección ordenada."""
    import gc

    app = _QAPP
    if app is None:
        return
    try:
        for widget in list(app.topLevelWidgets()):  # type: ignore[attr-defined]
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                pass
        app.processEvents()  # type: ignore[attr-defined]
    except Exception:
        pass
    gc.collect()


def pytest_sessionfinish(session: object, exitstatus: int) -> None:  # noqa: ARG001
    """Recolecta los objetos Qt pendientes antes de finalizar el intérprete."""
    _cleanup_qt_widgets()


@pytest.fixture(scope="session")
def qapp() -> Iterator["object"]:
    """Instancia única de QApplication compartida por toda la sesión de pruebas."""
    global _QAPP
    from PySide6.QtWidgets import QApplication

    if _QAPP is None:
        _QAPP = QApplication.instance() or QApplication([])
    yield _QAPP


# El parche debe durar TODA la sesión (no solo el test): el hilo que descarga la
# miniatura puede ejecutarse después de que el test termine. Si el parche se
# deshiciera antes, el hilo haría una petición de red real y quedaría vivo al
# cerrar el intérprete, provocando un fallo nativo en Windows.
@pytest.fixture(scope="session", autouse=True)
def _stub_thumbnail_network() -> Iterator[None]:
    """Sustituye la descarga de miniaturas por bytes locales (sin red)."""

    def _fake_fetch(url: str, timeout: float = 10.0) -> bytes:
        return _TINY_PNG

    with patch(
        "src.presentation.components.thumbnail_loader.fetch_thumbnail",
        _fake_fetch,
    ):
        yield

