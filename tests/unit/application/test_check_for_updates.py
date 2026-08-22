"""Tests de la política de actualización (CheckForUpdatesUseCase).

Casos cubiertos:
1. versión remota == local → no actualizar
2. versión remota superior → ofrecer actualización
3. versión remota inferior → nunca downgrade
4. versión inválida → rechazo explícito
"""
import pytest

from src.application.use_cases.check_for_updates import (
    CheckForUpdatesUseCase,
    UpdateCheckStatus,
)
from src.domain.exceptions.domain_exceptions import InvalidUpdateInfoError
from src.domain.ports.update_source import IUpdateSource, RemoteAsset, RemoteRelease


def _release(tag: str, notes: str = "Novedades", with_installer: bool = True) -> RemoteRelease:
    asset = None
    if with_installer:
        asset = RemoteAsset(
            name="osvaldoDownloaderPro-9.9.9-Setup.exe",
            url=(
                "https://github.com/adrianpalacios782-dotcom/descarga/releases/"
                f"download/{tag}/osvaldoDownloaderPro-9.9.9-Setup.exe"
            ),
            size_bytes=1024,
            sha256="a" * 64,
        )
    return RemoteRelease(tag_name=tag, release_notes=notes, installer_asset=asset)


class FakeSource(IUpdateSource):
    def __init__(self, release: RemoteRelease | Exception) -> None:
        self._release = release

    def get_latest_release(self) -> RemoteRelease:
        if isinstance(self._release, Exception):
            raise self._release
        return self._release


@pytest.fixture
def use_case() -> CheckForUpdatesUseCase:
    return CheckForUpdatesUseCase(update_source=FakeSource(_release("v1.0.0")))


class TestUpdatePolicy:

    def test_same_version_means_no_update(self, use_case):
        result = use_case.execute("1.0.0")
        assert result.status is UpdateCheckStatus.UP_TO_DATE
        assert not result.update_available
        assert result.release is None  # no se ofrece nada para instalar

    def test_remote_higher_offers_update(self):
        uc = CheckForUpdatesUseCase(update_source=FakeSource(_release("v1.1.0")))
        result = uc.execute("1.0.0")
        assert result.status is UpdateCheckStatus.UPDATE_AVAILABLE
        assert result.update_available
        assert str(result.latest_version) == "1.1.0"
        assert str(result.current_version) == "1.0.0"

    def test_remote_higher_patch_offers_update(self):
        uc = CheckForUpdatesUseCase(update_source=FakeSource(_release("1.0.1")))
        assert uc.execute("1.0.0").update_available

    def test_remote_higher_major_offers_update(self):
        uc = CheckForUpdatesUseCase(update_source=FakeSource(_release("2.0.0")))
        assert uc.execute("1.99.99").update_available

    def test_remote_lower_never_downgrades(self):
        uc = CheckForUpdatesUseCase(update_source=FakeSource(_release("0.9.0")))
        result = uc.execute("1.0.0")
        assert result.status is UpdateCheckStatus.UP_TO_DATE
        assert not result.update_available

    @pytest.mark.parametrize("bad_tag", ["not-a-version", "1.0", "", "abc"])
    def test_invalid_remote_version_rejected(self, bad_tag):
        uc = CheckForUpdatesUseCase(update_source=FakeSource(_release(bad_tag)))
        with pytest.raises(InvalidUpdateInfoError):
            uc.execute("1.0.0")

    def test_invalid_local_version_rejected(self):
        uc = CheckForUpdatesUseCase(update_source=FakeSource(_release("1.0.0")))
        with pytest.raises(InvalidUpdateInfoError):
            uc.execute("dev-local")

    def test_release_notes_pass_through(self):
        uc = CheckForUpdatesUseCase(
            update_source=FakeSource(_release("v1.5.0", notes="- Mejoras"))
        )
        result = uc.execute("1.0.0")
        assert result.release.release_notes == "- Mejoras"
