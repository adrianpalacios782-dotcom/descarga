"""Tests unitarios del gestor dinamico del motor yt-dlp.

Cubiertos:
- Resolucion del motor: wheel de AppData vs fallback empaquetado.
- Comparador de versiones calendario de yt-dlp.
- Chequeo asincrono GitHub Releases con fallback PyPI (sin red real).
- Descarga segura: SHA-256 obligatorio, cotas, atomicidad y cancelacion.
- Politica de URLs (allowlist HTTPS) del engine_config.
"""
import hashlib
import io
import sys
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.domain.exceptions.domain_exceptions import (
    InvalidUpdateInfoError,
    UpdateDownloadError,
    UpdateError,
)
from src.infrastructure.adapters.engine import engine_config
from src.infrastructure.adapters.engine.engine_manager import (
    MODE_APPDATA_WHEEL,
    MODE_PACKAGED,
    SOURCE_GITHUB,
    SOURCE_PYPI,
    EngineAsset,
    EngineManager,
    is_newer_version,
    parse_calendar_version,
)

WHEEL_VERSION_CURRENT = "2026.08.19"
WHEEL_NAME_OLD = "yt_dlp-2024.01.15-py3-none-any.whl"
WHEEL_NAME_NEW = "yt_dlp-2099.01.02-py3-none-any.whl"

GITHUB_WHEEL_URL = (
    "https://github.com/yt-dlp/yt-dlp/releases/download/2099.01.02/" + WHEEL_NAME_NEW
)
GITHUB_SUMS_URL = (
    "https://github.com/yt-dlp/yt-dlp/releases/download/2099.01.02/SHA2-256SUMS"
)
PYPI_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/aa/bb/ff/" + WHEEL_NAME_NEW
)


# ============================================================ Helpers
def _wheel_bytes(version: str) -> bytes:
    """Construye una wheel minimalista pero estructuralmente valida en memoria."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("yt_dlp/__init__.py", "")
        bundle.writestr("yt_dlp/version.py", f"__version__ = '{version}'\n")
    return buffer.getvalue()


def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakeYtDlpModule:
    """Modulo yt_dlp falso para inyectar en EngineManager."""

    def __init__(self, version: str = WHEEL_VERSION_CURRENT) -> None:
        self.version = SimpleNamespace(__version__=version)
        self.__file__ = f"<site-packages>/yt_dlp_{id(self)}/__init__.py"


def _fake_import(module: FakeYtDlpModule):
    def _import():
        return module  # type: ignore[return-value]

    return _import


class FakeResponse:
    """Respuesta HTTP minima compatible con el protocolo de descarga."""

    def __init__(self, chunks: list[bytes], headers: dict | None = None) -> None:
        self._chunks = list(chunks)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _asset_from_bytes(
    payload: bytes,
    filename: str = WHEEL_NAME_NEW,
    url: str = GITHUB_WHEEL_URL,
    sha256: str | None = None,
    size: int | None = None,
) -> EngineAsset:
    return EngineAsset(
        filename=filename,
        url=url,
        size_bytes=len(payload) if size is None else size,
        sha256=_sha256_of(payload) if sha256 is None else sha256,
    )


def _github_payload(
    tag: str = "v2099.01.02",
    digest: str | None = None,
    sums_content: str | None = None,
    extra_assets: list | None = None,
    wheel_url: str = GITHUB_WHEEL_URL,
) -> dict:
    wheel_entry: dict = {
        "name": WHEEL_NAME_NEW,
        "browser_download_url": wheel_url,
        "size": 1024,
    }
    if digest is not None:
        wheel_entry["digest"] = f"sha256:{digest}"
    assets: list = [wheel_entry]
    if sums_content is not None:
        assets.append(
            {
                "name": "SHA2-256SUMS",
                "browser_download_url": GITHUB_SUMS_URL,
            }
        )
    if extra_assets:
        assets.extend(extra_assets)
    return {"tag_name": tag, "assets": assets}


def _pypi_payload(
    version: str = "2099.01.02",
    files: list | None = None,
) -> dict:
    if files is None:
        files = [
            {
                "filename": WHEEL_NAME_NEW,
                "url": PYPI_WHEEL_URL,
                "size": 2048,
                "packagetype": "bdist_wheel",
                "digests": {"sha256": "b" * 64},
            }
        ]
    return {"info": {"version": version}, "urls": files}


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "engine"
    directory.mkdir()
    return directory


@pytest.fixture
def clean_sys_path():
    saved = list(sys.path)
    yield
    sys.path[:] = saved


# ============================================================
# COMPARADOR DE VERSIONES CALENDARIO
# ============================================================
class TestVersionesCalendario:

    @pytest.mark.parametrize("raw,expected", [
        ("2026.08.19", (2026, 8, 19)),
        ("v2026.08.19", (2026, 8, 19)),
        ("V2099.01.02", (2099, 1, 2)),
        ("2023.12.30.1", (2023, 12, 30, 1)),
        ("  2025.06.11  ", (2025, 6, 11)),
    ])
    def test_parseo_valido(self, raw, expected):
        assert parse_calendar_version(raw) == expected

    @pytest.mark.parametrize("raw", [
        None, 123, "", "abc", "1.2", "2026.8.19", "2026.08", "v", "2026.08.19-beta",
    ])
    def test_parseo_invalido_devuelve_none(self, raw):
        assert parse_calendar_version(raw) is None

    def test_comparaciones_estrictas(self):
        assert is_newer_version("2099.01.02", "2026.08.19") is True
        assert is_newer_version("2026.08.19", "2026.08.19") is False
        assert is_newer_version("2020.01.01", "2026.08.19") is False
        # padding: 4 componentes contra 3 equivalentes
        assert is_newer_version("2026.08.19.0", "2026.08.19") is False
        assert is_newer_version("2026.08.19.1", "2026.08.19") is True

    def test_comparacion_con_versiones_no_interpretables_es_conservadora(self):
        assert is_newer_version("2099.01.02", "") is False
        assert is_newer_version("", "2026.08.19") is False
        assert is_newer_version("garbage", "garbage") is False


# ============================================================
# RESOLUCION DEL MOTOR (AppData <-> empaquetado)
# ============================================================
class TestResolucionMotor:

    def test_appdata_vacio_activa_empaquetado(self, engine_dir, clean_sys_path):
        module = FakeYtDlpModule()
        manager = EngineManager(engine_dir=engine_dir, import_ytdlp=_fake_import(module))

        status = manager.activate()

        assert status.mode == MODE_PACKAGED
        assert status.wheel_path is None
        assert status.version == WHEEL_VERSION_CURRENT
        assert manager.is_using_updated_engine() is False
        assert manager.get_active_status() is status
        assert manager.get_active_module() is module

    def test_wheel_valida_en_appdata_se_activa(self, engine_dir, clean_sys_path):
        payload = _wheel_bytes("2099.01.01")
        wheel_path = engine_dir / WHEEL_NAME_NEW.replace("2099.01.02", "2099.01.01")
        wheel_path.write_bytes(payload)
        module = FakeYtDlpModule()
        manager = EngineManager(engine_dir=engine_dir, import_ytdlp=_fake_import(module))

        status = manager.activate()

        assert status.mode == MODE_APPDATA_WHEEL
        assert status.wheel_path == str(wheel_path)
        assert manager.is_using_updated_engine() is True
        assert sys.path[0] == str(wheel_path)

    def test_wheel_corrupta_hace_fallback_y_limpia_sys_path(
        self, engine_dir, clean_sys_path
    ):
        (engine_dir / WHEEL_NAME_NEW).write_bytes(b"esto-no-es-un-zip")
        module = FakeYtDlpModule()
        manager = EngineManager(engine_dir=engine_dir, import_ytdlp=_fake_import(module))

        status = manager.activate()

        assert status.mode == MODE_PACKAGED
        assert all(not p.endswith(".whl") for p in sys.path)

    def test_wheel_sin_paquete_yt_dlp_es_rechazada(self, engine_dir, clean_sys_path):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            bundle.writestr("malware/not_yt_dlp.py", "x")
        (engine_dir / WHEEL_NAME_NEW).write_bytes(buffer.getvalue())
        manager = EngineManager(engine_dir=engine_dir, import_ytdlp=_fake_import(FakeYtDlpModule()))

        status = manager.activate()

        assert status.mode == MODE_PACKAGED

    def test_archivos_con_nombre_invalido_son_ignorados(self, engine_dir, clean_sys_path):
        payload = _wheel_bytes("2099.01.01")
        (engine_dir / "yt_dlp-version-inventada.whl").write_bytes(payload)
        (engine_dir / "pepe.exe").write_bytes(payload)
        manager = EngineManager(engine_dir=engine_dir, import_ytdlp=_fake_import(FakeYtDlpModule()))

        assert manager.find_installed_wheel() is None
        assert manager.activate().mode == MODE_PACKAGED

    def test_find_installed_wheel_prefiere_la_version_mas_reciente(
        self, engine_dir, clean_sys_path
    ):
        vieja = engine_dir / WHEEL_NAME_OLD
        nueva = engine_dir / WHEEL_NAME_NEW
        vieja.write_bytes(_wheel_bytes("2024.01.15"))
        nueva.write_bytes(_wheel_bytes("2099.01.02"))
        manager = EngineManager(engine_dir=engine_dir, import_ytdlp=_fake_import(FakeYtDlpModule()))

        assert manager.find_installed_wheel() == nueva

    def test_reactivacion_no_acumula_entradas_en_sys_path(
        self, engine_dir, clean_sys_path
    ):
        wheel_path = engine_dir / WHEEL_NAME_NEW
        wheel_path.write_bytes(_wheel_bytes("2099.01.02"))
        manager = EngineManager(engine_dir=engine_dir, import_ytdlp=_fake_import(FakeYtDlpModule()))

        manager.activate()
        manager.activate()

        entries = [p for p in sys.path if p == str(wheel_path)]
        assert len(entries) == 1

    def test_get_active_version_antes_de_activar_consulta_modulo_empaquetado(self):
        manager = EngineManager(import_ytdlp=_fake_import(FakeYtDlpModule()))
        assert manager.get_active_version() == WHEEL_VERSION_CURRENT

    def test_directorio_por_defecto_usa_appdata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        manager = EngineManager(import_ytdlp=_fake_import(FakeYtDlpModule()))
        assert manager.get_engine_dir() == (
            tmp_path / "osvaldoDownloaderPro" / "engine"
        )

    def test_directorio_por_defecto_sin_appdata_usa_home(
        self, monkeypatch, clean_sys_path
    ):
        monkeypatch.delenv("APPDATA", raising=False)
        manager = EngineManager(import_ytdlp=_fake_import(FakeYtDlpModule()))
        assert "osvaldoDownloaderPro" in str(manager.get_engine_dir())


# ============================================================
# CHEQUEO DE ACTUALIZACIONES (GitHub -> PyPI)
# ============================================================
class _RoutingJson:
    """fetch_json falso que enruta por URL y puede fallar en orden."""

    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses
        self.called: list[str] = []

    def __call__(self, url: str) -> dict:
        self.called.append(url)
        response = self._responses[url]
        if isinstance(response, BaseException):
            raise response
        assert isinstance(response, dict)
        return response


class TestChequeoActualizaciones:

    def _manager(
        self,
        fetch_json,
        engine_dir: Path,
        fetch_text=None,
    ) -> EngineManager:
        return EngineManager(
            engine_dir=engine_dir,
            import_ytdlp=_fake_import(FakeYtDlpModule()),
            fetch_json=fetch_json,
            fetch_text=fetch_text or (lambda url: ""),
        )

    def test_github_exitoso_con_digest(self, engine_dir):
        digest = "a" * 64
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: _github_payload(digest=digest),
        })
        manager = self._manager(router, engine_dir)

        info = manager.check_for_updates()

        assert info.source == SOURCE_GITHUB
        assert info.latest_version == "2099.01.02"
        assert info.current_version == WHEEL_VERSION_CURRENT
        assert info.update_available is True
        assert info.asset is not None
        assert info.asset.sha256 == digest
        assert info.asset.filename == WHEEL_NAME_NEW

    def test_digest_y_sums_contradictorios_rechazan_github_y_caen_a_pypi(
        self, engine_dir
    ):
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: _github_payload(
                digest="a" * 64,
                sums_content=f"{_sha256_of(b'otra-cosa')}  {WHEEL_NAME_NEW}\n",
            ),
            engine_config.PYPI_JSON_API_URL: _pypi_payload(),
        })

        def fake_text(url: str) -> str:
            assert url == GITHUB_SUMS_URL
            return f"{_sha256_of(b'otra-cosa')}  {WHEEL_NAME_NEW}\n"

        manager = self._manager(router, engine_dir, fetch_text=fake_text)

        info = manager.check_for_updates()

        assert info.source == SOURCE_PYPI
        assert info.asset is not None
        assert info.asset.sha256 == "b" * 64

    def test_github_inaccesible_hace_fallback_a_pypi(self, engine_dir):
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: UpdateError("red caida"),
            engine_config.PYPI_JSON_API_URL: _pypi_payload(version="2099.03.04"),
        })
        manager = self._manager(router, engine_dir)

        info = manager.check_for_updates()

        assert info.source == SOURCE_PYPI
        assert info.latest_version == "2099.03.04"
        assert engine_config.PYPI_JSON_API_URL in router.called

    def test_ambas_fuentes_caidas_propagan_error(self, engine_dir):
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: UpdateError("sin red"),
            engine_config.PYPI_JSON_API_URL: OSError("dns"),
        })
        manager = self._manager(router, engine_dir)

        with pytest.raises(UpdateError):
            manager.check_for_updates()

    def test_tag_name_invalido_cae_a_pypi(self, engine_dir):
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: {"tag_name": "", "assets": []},
            engine_config.PYPI_JSON_API_URL: _pypi_payload(),
        })
        manager = self._manager(router, engine_dir)

        assert manager.check_for_updates().source == SOURCE_PYPI

    def test_release_sin_wheel_devuelve_info_sin_asset(self, engine_dir):
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: {
                "tag_name": "v2099.01.02",
                "assets": [{"name": "yt-dlp.exe", "browser_download_url": GITHUB_WHEEL_URL}],
            },
        })
        manager = self._manager(router, engine_dir)

        info = manager.check_for_updates()

        assert info.update_available is True
        assert info.asset is None

    def test_pypi_ignora_archivos_no_validos_y_elige_la_mejor_wheel(self, engine_dir):
        files = [
            {"filename": WHEEL_NAME_NEW.replace("2099.01.02", "2024.01.15"),
             "url": PYPI_WHEEL_URL.replace(WHEEL_NAME_NEW, "yt_dlp-2024.01.15-py3-none-any.whl"),
             "size": 10, "packagetype": "bdist_wheel", "digests": {"sha256": "c" * 64}},
            {"filename": "yt_dlp-2099.01.02.tar.gz",
             "url": PYPI_WHEEL_URL.replace(".whl", ".tar.gz"),
             "packagetype": "sdist", "digests": {"sha256": "d" * 64}},
            {"filename": WHEEL_NAME_NEW,
             "url": "https://evil.example/" + WHEEL_NAME_NEW,
             "size": 10, "packagetype": "bdist_wheel", "digests": {"sha256": "e" * 64}},
            {"filename": WHEEL_NAME_NEW,
             "url": PYPI_WHEEL_URL,
             "size": 2048, "packagetype": "bdist_wheel", "digests": {}},
            {"filename": WHEEL_NAME_NEW,
             "url": PYPI_WHEEL_URL,
             "size": 4096, "packagetype": "bdist_wheel",
             "digests": {"sha256": "f" * 64}},
        ]
        router = _RoutingJson({engine_config.PYPI_JSON_API_URL: _pypi_payload(files=files)})
        manager = self._manager(router, engine_dir)

        info = manager.check_for_updates()

        assert info.source == SOURCE_PYPI
        assert info.asset is not None
        assert info.asset.url == PYPI_WHEEL_URL
        assert info.asset.sha256 == "f" * 64
        assert info.asset.size_bytes == 4096

    def test_version_remota_no_superior_reporta_false(self, engine_dir):
        payload = _github_payload(tag="v2020.01.01", digest="a" * 64)
        router = _RoutingJson({engine_config.GITHUB_RELEASES_API_URL: payload})
        manager = self._manager(router, engine_dir)

        info = manager.check_for_updates()

        assert info.update_available is False

    def test_chequeo_asincrono_entrega_resultado_fuera_del_hilo_principal(
        self, engine_dir
    ):
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: _github_payload(digest="a" * 64),
        })
        manager = self._manager(router, engine_dir)
        done = threading.Event()
        captured: dict = {}

        def on_finished(result) -> None:
            captured["result"] = result
            captured["thread"] = threading.current_thread()
            done.set()

        thread = manager.check_for_updates_async(on_finished=on_finished)
        assert done.wait(timeout=5)

        assert not thread.is_alive()
        assert captured["thread"] is not threading.main_thread()
        assert captured["result"].source == SOURCE_GITHUB

    def test_chequeo_asincrono_fallido_invoca_on_error_sin_explotar(self, engine_dir):
        router = _RoutingJson({
            engine_config.GITHUB_RELEASES_API_URL: UpdateError("x"),
            engine_config.PYPI_JSON_API_URL: UpdateError("y"),
        })
        manager = self._manager(router, engine_dir)
        done = threading.Event()
        errors: list[BaseException] = []

        thread = manager.check_for_updates_async(
            on_error=lambda exc: (errors.append(exc), done.set())
        )
        assert done.wait(timeout=5)

        thread.join(timeout=1)
        assert len(errors) == 1
        assert isinstance(errors[0], UpdateError)


# ============================================================
# DESCARGA E INSTALACION SEGURA DE LA WHEEL
# ============================================================
class TestDescargaInstalacion:

    def _manager(self, engine_dir: Path, opener) -> EngineManager:
        return EngineManager(
            engine_dir=engine_dir,
            import_ytdlp=_fake_import(FakeYtDlpModule()),
            fetch_json=lambda url: {},
            opener=opener,
        )

    def test_descarga_exitosa_es_atomica_y_elimina_wheels_anteriores(self, engine_dir):
        payload = _wheel_bytes("2099.01.02")
        old_wheel = engine_dir / WHEEL_NAME_OLD
        old_wheel.write_bytes(_wheel_bytes("2024.01.15"))
        stale_part = engine_dir / (WHEEL_NAME_OLD + ".part")
        stale_part.write_bytes(b"resto")

        chunks = [payload[i:i + 512] for i in range(0, len(payload), 512)]
        manager = self._manager(engine_dir, lambda url: FakeResponse(chunks))
        progress: list[tuple[int, int]] = []
        asset = _asset_from_bytes(payload)

        installed = manager.install_update(asset, progress_callback=lambda d, t: progress.append((d, t)))

        assert installed == engine_dir / WHEEL_NAME_NEW
        assert installed.read_bytes() == payload
        assert not (engine_dir / (WHEEL_NAME_NEW + ".part")).exists()
        assert not old_wheel.exists()          # wheel anterior eliminada
        assert not stale_part.exists()         # resto .part limpiado
        assert progress[-1] == (len(payload), len(payload))

    def test_sha256_incorrecto_bloquea_activacion_y_no_deja_residuos(self, engine_dir):
        payload = b"contenido-malicioso"
        manager = self._manager(engine_dir, lambda url: FakeResponse([payload]))
        asset = _asset_from_bytes(payload, sha256="0" * 64)

        with pytest.raises(UpdateDownloadError):
            manager.install_update(asset)

        assert not (engine_dir / WHEEL_NAME_NEW).exists()
        assert list(engine_dir.glob("*.part")) == []

    def test_tamano_declarado_excesivo_se_rechaza_antes_de_conectar(self, engine_dir):
        opened: list[str] = []

        def opener(url: str):
            opened.append(url)
            return FakeResponse([b"x"])

        manager = self._manager(engine_dir, opener)
        asset = _asset_from_bytes(b"x", size=engine_config.MAX_WHEEL_BYTES + 1)

        with pytest.raises(UpdateDownloadError):
            manager.install_update(asset)

        assert opened == []

    def test_stream_que_supera_la_cota_se_aborta(self, engine_dir):
        chunk = b"A" * engine_config.DOWNLOAD_CHUNK_SIZE
        overflow = [chunk] * (engine_config.MAX_WHEEL_BYTES // engine_config.DOWNLOAD_CHUNK_SIZE + 2)
        manager = self._manager(engine_dir, lambda url: FakeResponse(overflow))
        asset = _asset_from_bytes(chunk, sha256=_sha256_of(chunk), size=None)

        with pytest.raises(UpdateDownloadError):
            manager.install_update(asset)

        assert list(engine_dir.glob("*")) == []

    def test_url_fuera_de_allowlist_rechazada(self, engine_dir):
        manager = self._manager(engine_dir, lambda url: FakeResponse([]))
        asset = _asset_from_bytes(b"x", url="https://evil.example/yt_dlp-2099.01.02-py3-none-any.whl")

        with pytest.raises(InvalidUpdateInfoError):
            manager.install_update(asset)

    def test_asset_sin_checksum_rechazado_por_politica(self, engine_dir):
        manager = self._manager(engine_dir, lambda url: FakeResponse([]))
        asset = _asset_from_bytes(b"x", sha256="")

        with pytest.raises(InvalidUpdateInfoError):
            manager.install_update(asset)

    @pytest.mark.parametrize("filename", [
        "../yt_dlp-2099.01.02-py3-none-any.whl",
        "sub/dir/yt_dlp-2099.01.02-py3-none-any.whl",
        "yt_dlp-2099.01.02-py3-none-any.whl.exe",
        "",
    ])
    def test_nombres_locales_invalidos_rechazados(self, engine_dir, filename):
        manager = self._manager(engine_dir, lambda url: FakeResponse([]))
        asset = _asset_from_bytes(b"x", filename=filename)

        with pytest.raises((InvalidUpdateInfoError, UpdateDownloadError)):
            manager.install_update(asset)

    def test_cancelacion_a_mitad_de_descarga_limpia_el_part(self, engine_dir):
        payload = _wheel_bytes("2099.01.02")
        chunks = [payload[i:i + 256] for i in range(0, len(payload), 256)]
        cancel_event = threading.Event()

        def progress(downloaded: int, total: int) -> None:
            if downloaded >= 256:
                cancel_event.set()

        manager = self._manager(engine_dir, lambda url: FakeResponse(chunks))
        asset = _asset_from_bytes(payload)

        with pytest.raises(UpdateDownloadError):
            manager.install_update(asset, progress_callback=progress, cancel_event=cancel_event)

        assert list(engine_dir.glob("*")) == []

    def test_download_update_async_entrega_ruta_instalada(self, engine_dir):
        payload = _wheel_bytes("2099.01.02")
        chunks = [payload]
        manager = self._manager(engine_dir, lambda url: FakeResponse(chunks))
        done = threading.Event()
        results: list[Path] = []
        threads_seen: list[threading.Thread] = []

        thread = manager.download_update_async(
            _asset_from_bytes(payload),
            on_finished=lambda path: (results.append(path), threads_seen.append(threading.current_thread()), done.set()),
        )
        assert done.wait(timeout=5)

        thread.join(timeout=1)
        assert results == [engine_dir / WHEEL_NAME_NEW]
        assert threads_seen[0] is not threading.main_thread()


# ============================================================
# POLITICA DE URLs DEL ENGINE_CONFIG
# ============================================================
class TestPoliticaUrlsEngine:

    def test_fuentes_oficiales_aceptadas(self):
        assert engine_config.is_allowed_metadata_url(engine_config.GITHUB_RELEASES_API_URL)
        assert engine_config.is_allowed_metadata_url(engine_config.PYPI_JSON_API_URL)
        assert engine_config.is_allowed_asset_url(GITHUB_WHEEL_URL)
        assert engine_config.is_allowed_asset_url(PYPI_WHEEL_URL)
        assert engine_config.is_allowed_asset_url(GITHUB_SUMS_URL)

    @pytest.mark.parametrize("url", [
        "http://pypi.org/pypi/yt-dlp/json",
        "https://evil.example/yt_dlp-2099.01.02-py3-none-any.whl",
        "https://api.github.com.evil.com/x",
        "file:///C:/Windows/system32/evil.whl",
        "not-a-url",
    ])
    def test_urls_peligrosas_rechazadas(self, url):
        assert not engine_config.is_allowed_metadata_url(url)
        assert not engine_config.is_allowed_asset_url(url)

    def test_patron_wheel_estrecho(self):
        match = engine_config.WHEEL_ASSET_PATTERN.match(WHEEL_NAME_NEW)
        assert match is not None and match.group(1) == "2099.01.02"
        for bad in ("yt_dlp-2099.01.02-win_amd64.whl", "yt_dlp-latest-py3-none-any.whl"):
            assert engine_config.WHEEL_ASSET_PATTERN.match(bad) is None

