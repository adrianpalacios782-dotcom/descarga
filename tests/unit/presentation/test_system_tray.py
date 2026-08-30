from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from src.presentation.components.system_tray import AppTrayIcon
from src.presentation.views.configuracion_view import ConfiguracionView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_app_tray_icon_creation_and_menu(qapp):
    tray = AppTrayIcon()
    assert tray.toolTip() == "osvaldoDownloaderPro"

    menu = tray.contextMenu()
    assert menu is not None
    actions = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "Mostrar osvaldoDownloaderPro" in actions
    assert "Buscar actualizaciones..." in actions
    assert "Salir" in actions


def test_app_tray_icon_signals(qapp):
    tray = AppTrayIcon()

    restore_emitted = []
    update_emitted = []
    exit_emitted = []

    tray.restore_requested.connect(lambda: restore_emitted.append(True))
    tray.check_updates_requested.connect(lambda: update_emitted.append(True))
    tray.exit_requested.connect(lambda: exit_emitted.append(True))

    menu = tray.contextMenu()
    assert menu is not None
    for act in menu.actions():
        if act.text() == "Mostrar osvaldoDownloaderPro":
            act.trigger()
        elif act.text() == "Buscar actualizaciones...":
            act.trigger()
        elif act.text() == "Salir":
            act.trigger()

    assert len(restore_emitted) == 1
    assert len(update_emitted) == 1
    assert len(exit_emitted) == 1


def test_app_tray_icon_activated_double_click(qapp):
    tray = AppTrayIcon()
    restore_emitted = []
    tray.restore_requested.connect(lambda: restore_emitted.append(True))

    tray._on_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert len(restore_emitted) == 1

    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert len(restore_emitted) == 2


def test_app_tray_icon_notifications(qapp):
    tray = AppTrayIcon()

    with patch.object(tray, "isVisible", return_value=True):
        with patch.object(tray, "showMessage") as mock_show:
            tray.notify_download_completed("Mi Video", "/path/to/video.mp4")
            mock_show.assert_called_once()
            assert "Mi Video" in mock_show.call_args[0][1]

        with patch.object(tray, "showMessage") as mock_show:
            tray.notify_download_failed("Mi Video", "403 Forbidden")
            mock_show.assert_called_once()
            assert "403 Forbidden" in mock_show.call_args[0][1]


def test_configuracion_view_tray_options(qapp):
    mock_repo = MagicMock()
    mock_repo.get_all.return_value = {
        "minimize_to_tray": True,
        "tray_notifications": False,
    }

    view = ConfiguracionView(settings_repo=mock_repo)
    assert view.chk_minimize_to_tray.isChecked() is True
    assert view.chk_tray_notifications.isChecked() is False

    # Guardar
    view.chk_minimize_to_tray.setChecked(False)
    view.chk_tray_notifications.setChecked(True)

    saved_settings = []
    view.settings_saved.connect(lambda s: saved_settings.append(s))
    with patch.object(QMessageBox, "information"):
        view._on_save_clicked()

    assert len(saved_settings) == 1
    assert saved_settings[0]["minimize_to_tray"] is False
    assert saved_settings[0]["tray_notifications"] is True
