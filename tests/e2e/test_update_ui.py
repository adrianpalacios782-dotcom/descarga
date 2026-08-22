"""Tests e2e de la interfaz de actualización.

Casos cubiertos:
10. GitHub no disponible → la aplicación continúa iniciando.
11. Timeout → la aplicación continúa iniciando.
12. Cancelación del usuario → no actualizar.
15. Versión correctamente mostrada en la interfaz + única fuente de verdad.
"""
import os
import sys

import pytest

import src as app_pkg
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from src.application.use_cases.check_for_updates import (
    CheckForUpdatesUseCase,
    UpdateCheckResult,
    UpdateCheckStatus,
)
from src.domain.exceptions.domain_exceptions import UpdateError
from src.domain.ports.update_source import RemoteAsset, RemoteRelease
from src.domain.value_objects.semantic_version import SemanticVersion
from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
from src.infrastructure.adapters.platforms.platform_registry import PlatformRegistry
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus
from src.presentation.components.update_dialog import UpdateDialog
from src.presentation.main_window import MainWindow
from src.presentation.view_models.main_view_model import MainViewModel
from src.presentation.view_models.update_coordinator import UpdateCoordinator
from src.presentation.views.acerca_de_view import AcercaDeView
from src.presentation.views.configuracion_view import ConfiguracionView


@pytest.fixture(scope="module")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture()
def main_window(qapp):
    db_mgr = DatabaseManager(":memory:")
    repo = SQLiteDownloadRepository(db_mgr)
    event_bus = InProcessEventBus()
    vm = MainViewModel(
        platform_adapter=PlatformRegistry(),
        download_engine=YtDlpDownloadEngine(
            event_bus=event_bus, ffmpeg_adapter=FFmpegProcessAdapter()
        ),
        repository=repo,
        event_bus=event_bus,
    )
    window = MainWindow(view_model=vm)
    yield window
    window.close()
    db_mgr.close()


def _available_result() -> UpdateCheckResult:
    asset = RemoteAsset(
        name="osvaldoDownloaderPro-1.1.0-Setup.exe",
        url=(
            "https://github.com/adrianpalacios782-dotcom/descarga/releases/"
            "download/v1.1.0/osvaldoDownloaderPro-1.1.0-Setup.exe"
        ),
        size_bytes=1024 * 1024,
        sha256="a" * 64,
    )
    release = RemoteRelease(
        tag_name="v1.1.0",
        release_notes="- Mejoras visuales\n- Correcciones",
        installer_asset=asset,
    )
    return UpdateCheckResult(
        status=UpdateCheckStatus.UPDATE_AVAILABLE,
        current_version=SemanticVersion.parse("1.0.0"),
        latest_version=SemanticVersion.parse("1.1.0"),
        release=release,
    )


def _up_to_date_result() -> UpdateCheckResult:
    return UpdateCheckResult(
        status=UpdateCheckStatus.UP_TO_DATE,
        current_version=SemanticVersion.parse(app_pkg.__version__),
        latest_version=SemanticVersion.parse(app_pkg.__version__),
        release=None,
    )


class _ExplodingSource:
    """Fuente que simula GitHub caído / sin conexión / timeout."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def get_latest_release(self) -> RemoteRelease:
        raise self._exc


# ============================================================
# 10 / 11: RESILIENCIA — un fallo del actualizador NUNCA impide usar la app
# ============================================================

class TestStartupResilience:

    def test_github_unavailable_app_continues(self, qapp):
        coordinator = UpdateCoordinator()
        received = []
        coordinator.check_finished.connect(
            lambda result, manual: received.append((result, manual))
        )

        coordinator._check_use_case = CheckForUpdatesUseCase(
            update_source=_ExplodingSource(UpdateError("fuente no disponible"))
        )
        coordinator._check_worker(manual=False)  # síncrono: sin hilos en tests

        assert received == [(None, False)]
        assert not coordinator.is_busy

    def test_timeout_app_continues(self, qapp):
        coordinator = UpdateCoordinator()
        received = []
        coordinator.check_finished.connect(
            lambda result, manual: received.append((result, manual))
        )

        coordinator._check_use_case = CheckForUpdatesUseCase(
            update_source=_ExplodingSource(TimeoutError("connect timeout"))
        )
        coordinator._check_worker(manual=True)

        assert received == [(None, True)]

    def test_manual_check_failure_shows_clear_message(self, main_window, monkeypatch):
        warnings = []

        def fake_warning(*args, **kwargs):
            warnings.append(args[2] if len(args) >= 3 else kwargs.get("text", ""))
            return QMessageBox.StandardButton.Ok

        monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))
        main_window._on_update_check_finished(None, manual=True)

        assert len(warnings) == 1
        assert "No se pudo comprobar" in warnings[0]

    def test_startup_check_failure_is_silent(self, main_window, monkeypatch):
        shown = []

        def fake_warning(*a, **k):
            shown.append("warning")
            return QMessageBox.StandardButton.Ok

        def fake_information(*a, **k):
            shown.append("info")
            return QMessageBox.StandardButton.Ok

        monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))
        monkeypatch.setattr(QMessageBox, "information", staticmethod(fake_information))

        # Fallo de red en el chequeo de inicio y resultado sin novedades:
        # la app arranca normal, CERO ventanas molestas.
        main_window._on_update_check_finished(None, manual=False)
        main_window._on_update_check_finished(_up_to_date_result(), manual=False)

        assert shown == []


# ============================================================
# 12: CANCELACIÓN DEL USUARIO → NO ACTUALIZAR
# ============================================================

class TestUserCancellation:

    def test_cancel_during_download_closes_without_updating(self, qapp):
        dialog = UpdateDialog(_available_result())
        dialog.show()

        cancelled = []
        dialog.cancel_requested.connect(lambda: cancelled.append(True))

        dialog.btn_update.click()          # pasa a estado "descargando"
        assert dialog.btn_later.text() == "Cancelar"

        dialog.btn_later.click()           # cancelar durante descarga
        assert cancelled == [True]
        assert not dialog.isVisible()
        assert dialog.result() == int(dialog.DialogCode.Rejected)

    def test_later_button_never_starts_update(self, qapp):
        accepted = []
        dialog = UpdateDialog(_available_result())
        dialog.update_accepted.connect(lambda: accepted.append(True))
        dialog.show()

        dialog.btn_later.click()
        assert accepted == []
        assert not dialog.isVisible()

    def test_coordinator_request_cancel_sets_event(self, qapp):
        coordinator = UpdateCoordinator()
        assert not coordinator._cancel_event.is_set()
        coordinator.request_cancel()
        assert coordinator._cancel_event.is_set()


# ============================================================
# 15: VERSIÓN EN LA INTERFAZ + ÚNICA FUENTE DE VERDAD
# ============================================================

class TestVersionDisplay:

    def test_acerca_de_shows_current_version(self, qapp):
        view = AcercaDeView()
        joined = "\n".join(lbl.text() for lbl in view.findChildren(QLabel))
        assert f"Versión: {app_pkg.__version__}" in joined
        assert f"osvaldoDownloaderPro v{app_pkg.__version__}" in joined

    def test_configuracion_has_manual_check_button(self, qapp):
        view = ConfiguracionView()
        fired = []
        view.update_check_requested.connect(lambda: fired.append(True))

        buttons = [
            b for b in view.findChildren(QPushButton)
            if b.text() == "Buscar actualizaciones ahora"
        ]
        assert len(buttons) == 1
        buttons[0].click()
        assert fired == [True]

    def test_acerca_de_has_check_updates_button(self, qapp):
        view = AcercaDeView()
        buttons = [
            b for b in view.findChildren(QPushButton)
            if b.text() == "Buscar actualizaciones"
        ]
        assert len(buttons) == 1

    def test_single_source_of_truth_across_artifacts(self):
        # 1) src/__init__.py es SemVer válido (única fuente de verdad)
        SemanticVersion.parse(app_pkg.__version__)

        # 2) installer.iss usa ese mismo valor como default
        iss_path = os.path.join(os.path.dirname(__file__), "..", "..", "installer.iss")
        with open(iss_path, "r", encoding="utf-8") as fh:
            iss_content = fh.read()
        assert f'#define APP_VERSION "{app_pkg.__version__}"' in iss_content

        # 3) pyproject.toml deriva la versión dinámicamente desde src.__version__
        toml_path = os.path.join(os.path.dirname(__file__), "..", "..", "pyproject.toml")
        with open(toml_path, "r", encoding="utf-8") as fh:
            toml_content = fh.read()
        assert 'dynamic = ["version"]' in toml_content
        assert 'version = { attr = "src.__version__" }' in toml_content


# ============================================================
# DIÁLOGO: estados y contenido visual integrado con la app
# ============================================================

class TestUpdateDialogStates:

    def test_dialog_shows_versions_and_notes(self, qapp):
        dialog = UpdateDialog(_available_result())
        dialog.show()
        all_text = "\n".join(lbl.text() for lbl in dialog.findChildren(QLabel))
        assert "Nueva actualización disponible" in all_text
        assert "Versión actual:" in all_text and "1.0.0" in all_text
        assert "Nueva versión:" in all_text and "1.1.0" in all_text
        assert "Mejoras visuales" in all_text  # novedades visibles
        dialog.close()

    def test_accept_flow_switches_to_downloading_state(self, qapp):
        dialog = UpdateDialog(_available_result())
        dialog.show()
        dialog.btn_update.click()
        assert dialog.progress_bar.isVisible()
        assert dialog.status_label.isVisible()
        assert not dialog.btn_update.isEnabled()
        dialog.close()

    def test_error_state_offers_continue_with_current_version(self, qapp):
        dialog = UpdateDialog(_available_result())
        dialog.show()
        dialog.btn_update.click()
        dialog.on_download_error("Verificación SHA-256 fallida.")
        assert "SHA-256" in dialog.status_label.text()
        assert dialog.btn_later.text() == "Continuar con la versión actual"
        assert not dialog.btn_update.isVisibleTo(dialog)
        dialog.close()

    def test_ready_to_install_disables_all_controls(self, qapp):
        dialog = UpdateDialog(_available_result())
        dialog.show()
        dialog.btn_update.click()
        dialog.on_ready_to_install()
        assert not dialog.btn_later.isEnabled()
        assert not dialog.btn_update.isEnabled()
        dialog.close()
