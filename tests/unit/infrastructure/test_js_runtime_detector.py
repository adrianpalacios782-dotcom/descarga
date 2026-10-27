"""Contrato de la detección de runtimes JavaScript.

Los retos de firma (n-token) de YouTube solo se resuelven con un runtime JS.
yt-dlp acepta ``deno``, ``node``, ``quickjs`` y ``bun`` y usa el de mayor
prioridad disponible, así que la app habilita todos los que detecte, pero
validando la versión de cada uno: un runtime demasiado antiguo hace fallar el
reto y con él se pierden las calidades altas.
"""

import shutil
from typing import Dict, Optional

import pytest

from src.infrastructure.adapters.media import js_runtime_detector as jrd
from src.infrastructure.adapters.media.js_runtime_detector import (
    JS_RUNTIME_MINIMUMS,
    detect_js_runtimes,
)


def _patch_which(monkeypatch: pytest.MonkeyPatch, found: Dict[str, str]) -> None:
    """Simula el PATH del equipo y desactiva el fallback de Node.js de Windows."""
    monkeypatch.setattr(shutil, "which", lambda name: found.get(name))
    monkeypatch.setattr(jrd, "_WINDOWS_NODE_CANDIDATES", ())


def _patch_version(monkeypatch: pytest.MonkeyPatch, versions: Dict[str, Optional[tuple]]) -> None:
    def fake_version(path: str) -> Optional[tuple]:
        for name, version in versions.items():
            if path.endswith(name):
                return version
        return None

    monkeypatch.setattr(jrd, "_runtime_version", fake_version)


class TestRuntimeDetection:

    def test_no_runtime_returns_an_empty_dict(self, monkeypatch) -> None:
        _patch_which(monkeypatch, {})
        _patch_version(monkeypatch, {})

        assert detect_js_runtimes() == {}

    def test_node_is_detected(self, monkeypatch) -> None:
        _patch_which(monkeypatch, {"node": "C:/nodejs/node.exe"})
        _patch_version(monkeypatch, {"node.exe": (24, 19, 0)})

        runtimes = detect_js_runtimes()

        assert "node" in runtimes
        assert runtimes["node"]["path"] == "C:/nodejs/node.exe"

    def test_every_supported_runtime_is_detected(self, monkeypatch) -> None:
        _patch_which(
            monkeypatch,
            {
                "node": "C:/nodejs/node.exe",
                "deno": "C:/deno/deno.exe",
                "qjs": "C:/quickjs/qjs.exe",
                "bun": "C:/bun/bun.exe",
            },
        )
        _patch_version(
            monkeypatch,
            {
                "node.exe": (24, 19, 0),
                "deno.exe": (2, 3, 0),
                "qjs.exe": (2024, 1, 1),
                "bun.exe": (1, 2, 11),
            },
        )

        runtimes = detect_js_runtimes()

        assert set(runtimes) == {"node", "deno", "quickjs", "bun"}

    def test_quickjs_uses_the_qjs_executable_but_the_quickjs_key(self, monkeypatch) -> None:
        """yt-dlp llama al binario 'qjs' pero indexa el runtime como 'quickjs'."""
        _patch_which(monkeypatch, {"qjs": "C:/quickjs/qjs.exe"})
        _patch_version(monkeypatch, {"qjs.exe": (2024, 1, 1)})

        runtimes = detect_js_runtimes()

        assert "quickjs" in runtimes
        assert "qjs" not in runtimes
        assert runtimes["quickjs"]["path"] == "C:/quickjs/qjs.exe"

    def test_an_outdated_runtime_is_discarded(self, monkeypatch) -> None:
        """Un node antiguo hace fallar el reto de firma: no se habilita."""
        _patch_which(monkeypatch, {"node": "C:/nodejs/node.exe"})
        _patch_version(monkeypatch, {"node.exe": (18, 0, 0)})

        assert detect_js_runtimes() == {}

    def test_an_unreadable_version_does_not_discard_the_runtime(self, monkeypatch) -> None:
        """Si no se puede leer la versión, se habilita: es preferible a no
        tener runtime (yt-dlp vuelve a comprobar la versión al usarlo)."""
        _patch_which(monkeypatch, {"node": "C:/nodejs/node.exe"})
        _patch_version(monkeypatch, {"node.exe": None})

        assert "node" in detect_js_runtimes()

    def test_the_minimums_are_the_ones_required_by_yt_dlp(self) -> None:
        """Los mínimos deben coincidir con los de yt-dlp 2026.x."""
        assert JS_RUNTIME_MINIMUMS["node"] == (22, 0, 0)
        assert JS_RUNTIME_MINIMUMS["deno"] == (2, 3, 0)
        assert JS_RUNTIME_MINIMUMS["quickjs"] == (2023, 12, 9)
        assert JS_RUNTIME_MINIMUMS["bun"] == (1, 2, 11)


class TestRuntimesReachYtDlp:
    """El runtime detectado tiene que llegar a las opciones de yt-dlp."""

    def test_the_adapter_forwards_the_detected_runtimes(self, monkeypatch) -> None:
        from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter

        _patch_which(monkeypatch, {"node": "C:/nodejs/node.exe"})
        _patch_version(monkeypatch, {"node.exe": (24, 19, 0)})

        opts = YouTubeAdapter()._build_ydl_opts()

        assert opts["js_runtimes"] == {"node": {"path": "C:/nodejs/node.exe"}}

    def test_the_download_engine_forwards_the_detected_runtimes(self, monkeypatch) -> None:
        from src.infrastructure.adapters.download.ytdlp_download_engine import (
            YtDlpDownloadEngine,
        )

        _patch_which(monkeypatch, {"node": "C:/nodejs/node.exe"})
        _patch_version(monkeypatch, {"node.exe": (24, 19, 0)})

        opts: dict = {}
        YtDlpDownloadEngine()._apply_js_runtimes(opts)

        assert opts["js_runtimes"] == {"node": {"path": "C:/nodejs/node.exe"}}
