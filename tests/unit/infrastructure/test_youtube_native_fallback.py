"""Contrato de la Capa 1: fallback NATIVO de yt-dlp + saltos del extractor.

Problema de origen: en visita anónima YouTube degrada la respuesta y solo
entrega 360p (mas storyboards). La causa es que los clientes por defecto de
yt-dlp 2026.x (``_DEFAULT_CLIENTS = ('visionos', 'web')``) exigen un PO token
para las calidades altas; sin el, YouTube recorta el ladder.

La Capa 1 lo resuelve SIN cookies, con dos mecanismos nativos de yt-dlp:

1. ``player_client`` con una LISTA de clientes: yt-dlp los prueba EN ORDEN
   dentro de una sola extracción y fusiona sus formatos. Un fallo (bot-check)
   en un cliente no aborta la extracción (ver
   ``yt_dlp/extractor/youtube/_video.py::_extract_player_responses``, que
   captura el ``ExtractorError`` y continua con el siguiente cliente).

2. ``player_skip``: salta la página inicial y el ``ytcfg`` por cliente, que son
   las peticiones que devuelven la vía degradada.

Este archivo fija el CONTRATO de esa política: qué se envía a yt-dlp, en qué
condiciones y que el análisis y la descarga no se separen nunca.
"""

from typing import Any, Dict

import pytest

from src.infrastructure.adapters.download.ytdlp_download_engine import YtDlpDownloadEngine
from src.infrastructure.adapters.platforms.base_platform_adapter import BasePlatformAdapter
from src.infrastructure.adapters.platforms.tiktok_adapter import TikTokAdapter
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter
from src.infrastructure.adapters.platforms.youtube_client_strategy import (
    DEFAULT_PLAYER_SKIP,
    LEGACY_CLIENT_ALIASES,
    NATIVE_FALLBACK_CLIENTS,
    VALID_PLAYER_SKIP,
    build_youtube_extractor_args,
    resolve_player_clients,
    sanitize_player_skip,
)


def _youtube_args(opts: Dict[str, Any]) -> Dict[str, Any]:
    return (opts.get("extractor_args") or {}).get("youtube") or {}


class TestPlayerSkipContract:
    """``player_skip`` debe existir, ser valido y aplicarse en la via anonima."""

    def test_player_skip_is_present_in_the_youtube_extractor_args(self) -> None:
        opts = YouTubeAdapter()._build_ydl_opts()
        assert _youtube_args(opts).get("player_skip") == list(DEFAULT_PLAYER_SKIP)

    def test_player_skip_values_are_recognized_by_the_installed_ytdlp(self) -> None:
        """Un valor no reconocido se ignora en silencio: el salto se perderia."""
        opts = YouTubeAdapter()._build_ydl_opts()
        skip = _youtube_args(opts).get("player_skip") or []
        assert skip, "Debe declararse al menos un salto"
        for value in skip:
            assert value in VALID_PLAYER_SKIP

    def test_default_skip_skips_the_webpage_and_the_configs(self) -> None:
        """``webpage`` evita el bot-check/age-gate; ``configs`` ahorra una
        request por cliente de fallback (menos riesgo de HTTP 429)."""
        assert set(DEFAULT_PLAYER_SKIP) == {"webpage", "configs"}

    def test_unknown_skip_values_are_discarded(self) -> None:
        assert sanitize_player_skip(["webpage", "inventado", "configs"]) == ["webpage", "configs"]

    def test_player_skip_is_not_applied_when_there_are_cookies(self) -> None:
        """Con cookies la pagina inicial aporta el player_response y el
        visitor_data de mayor calidad: saltarla solo empeoraria el resultado."""
        adapter = YouTubeAdapter(cookies_from_browser="firefox")
        opts = adapter._build_ydl_opts()
        assert "player_skip" not in _youtube_args(opts)
        assert opts["cookiesfrombrowser"] == ("firefox",)

    def test_player_skip_is_applied_again_when_browser_cookies_are_disabled(self) -> None:
        """El reintento sin cookies del navegador vuelve a la via anonima."""
        adapter = YouTubeAdapter(cookies_from_browser="firefox")
        opts = adapter._build_ydl_opts(disable_browser_cookies=True)
        assert "cookiesfrombrowser" not in opts
        assert _youtube_args(opts).get("player_skip") == list(DEFAULT_PLAYER_SKIP)

    def test_player_skip_is_not_applied_with_a_cookie_file(self, tmp_path) -> None:
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        adapter = YouTubeAdapter(cookiefile=str(cookie_file))
        opts = adapter._build_ydl_opts()
        assert opts["cookiefile"] == str(cookie_file)
        assert "player_skip" not in _youtube_args(opts)


class TestNativeFallbackContract:
    """``player_client`` debe ser una LISTA que YouTube pueda fusionar."""

    def test_native_fallback_declares_more_than_one_client(self) -> None:
        assert len(NATIVE_FALLBACK_CLIENTS) > 1

    def test_native_fallback_contains_a_client_that_does_not_require_po_token(self) -> None:
        """``ios`` no exige PO token para DASH (video-only de alta resolucion).
        ``tv_downgraded`` no lo exige en NINGUN protocolo."""
        assert "ios" in NATIVE_FALLBACK_CLIENTS
        assert "tv_downgraded" in NATIVE_FALLBACK_CLIENTS

    def test_native_fallback_is_the_first_strategy(self) -> None:
        """El fallback nativo va primero: fusiona formatos en una sola extraccion."""
        assert BasePlatformAdapter.CLIENT_STRATEGIES[0] == NATIVE_FALLBACK_CLIENTS

    def test_legacy_tv_embedded_is_resolved_to_its_modern_equivalent(self) -> None:
        """``tv_embedded`` fue retirado de yt-dlp: sin traduccion, yt-dlp solo
        avisaria y gastaria una request de red para repetir la extraccion."""
        assert "tv_embedded" in LEGACY_CLIENT_ALIASES
        resolved = resolve_player_clients(["ios", "tv_embedded", "web"])
        assert resolved == ["ios", LEGACY_CLIENT_ALIASES["tv_embedded"], "web"]
        assert "tv_embedded" not in resolved

    def test_resolution_preserves_the_order_and_removes_duplicates(self) -> None:
        """El orden ES el orden de intento de yt-dlp: no se puede reordenar."""
        assert resolve_player_clients(["web", "ios", "web"]) == ["web", "ios"]

    def test_resolution_of_an_empty_list_is_empty(self) -> None:
        assert resolve_player_clients(None) == []
        assert resolve_player_clients([]) == []

    def test_build_youtube_extractor_args_combines_clients_and_skip(self) -> None:
        args = build_youtube_extractor_args(["ios", "tv_simply"], anonymous=True)
        assert args["player_client"] == ["ios", "tv_simply"]
        assert args["player_skip"] == list(DEFAULT_PLAYER_SKIP)

    def test_build_youtube_extractor_args_without_clients_keeps_the_skip(self) -> None:
        args = build_youtube_extractor_args(None, anonymous=True)
        assert "player_client" not in args
        assert args["player_skip"] == list(DEFAULT_PLAYER_SKIP)

    def test_build_youtube_extractor_args_authenticated_has_no_skip(self) -> None:
        args = build_youtube_extractor_args(["web"], anonymous=False)
        assert args["player_client"] == ["web"]
        assert "player_skip" not in args


class TestAnalysisAndDownloadShareThePolicy:
    """Si el analisis y la descarga no coinciden, la calidad prometida no se
    puede bajar: es el mismo contrato, no dospoliticas distintas."""

    def test_analysis_and_download_use_the_same_client_list(self) -> None:
        analysis = _youtube_args(YouTubeAdapter()._build_ydl_opts(NATIVE_FALLBACK_CLIENTS))
        download = _youtube_args(
            YtDlpDownloadEngine._apply_clients({}, NATIVE_FALLBACK_CLIENTS)
        )
        assert analysis["player_client"] == download["player_client"]
        assert analysis["player_skip"] == download["player_skip"]

    def test_download_probe_and_download_use_the_same_first_strategy(self) -> None:
        assert (
            YtDlpDownloadEngine.DOWNLOAD_CLIENT_STRATEGIES[0]
            == YtDlpDownloadEngine.PROBE_CLIENT_STRATEGIES[0]
            == NATIVE_FALLBACK_CLIENTS
        )

    def test_download_engine_does_not_restrict_to_a_single_client(self) -> None:
        opts = YtDlpDownloadEngine._apply_clients({}, NATIVE_FALLBACK_CLIENTS)
        assert len(_youtube_args(opts)["player_client"]) > 1

    def test_download_engine_applies_the_skip_in_the_anonymous_path(self) -> None:
        opts = YtDlpDownloadEngine._apply_clients({}, NATIVE_FALLBACK_CLIENTS)
        assert _youtube_args(opts)["player_skip"] == list(DEFAULT_PLAYER_SKIP)

    def test_download_engine_omits_the_skip_with_cookies(self) -> None:
        opts = YtDlpDownloadEngine._apply_clients({"cookiefile": "c.txt"}, NATIVE_FALLBACK_CLIENTS)
        assert "player_skip" not in _youtube_args(opts)

    def test_download_engine_does_not_mutate_the_shared_options(self) -> None:
        """``opts`` suele ser una copia superficial: si se mutase el dict
        anidado de ``extractor_args``, se contaminarian las extracciones
        siguientes (el mismo fallo que se corrigio en TikTok)."""
        shared: Dict[str, Any] = {"player_client": ["web"]}
        base: Dict[str, Any] = {"extractor_args": {"youtube": shared}}
        YtDlpDownloadEngine._apply_clients(base, NATIVE_FALLBACK_CLIENTS)
        # El bloque anidado original queda intacto: se construye uno nuevo.
        assert shared == {"player_client": ["web"]}
        assert "player_skip" not in shared


class TestNoCrossPlatformLeak:
    """La politica es de YouTube: no debe colarse en otras plataformas."""

    def test_tiktok_does_not_receive_youtube_extractor_args(self) -> None:
        opts = TikTokAdapter()._build_ydl_opts()
        assert "extractor_args" not in opts

    def test_base_adapter_without_clients_has_no_extractor_args(self) -> None:
        opts = BasePlatformAdapter()._build_ydl_opts()
        assert "extractor_args" not in opts

    def test_base_adapter_with_clients_keeps_only_the_client(self) -> None:
        """La clase base es agnóstica de plataforma: aplica el cliente pedido,
        pero no la politica de saltos (eso es de YouTubeAdapter)."""
        opts = BasePlatformAdapter()._build_ydl_opts(["ios"])
        args = _youtube_args(opts)
        assert args["player_client"] == ["ios"]
        assert "player_skip" not in args


class TestRegression360pCeiling:
    """Regresión del síntoma reportado: video musical que solo devolvia 360p."""

    def test_ios_is_not_excluded_from_the_fallback(self) -> None:
        """``ios`` es el unico cliente sin PO token que entrega DASH: sin el, el
        ladder se recorta a 360p en visita anonima."""
        assert "ios" in NATIVE_FALLBACK_CLIENTS

    def test_the_web_client_alone_is_not_enough(self) -> None:
        """``web`` exige PO token para DASH: es el cliente que produce el tope
        de 360p, por eso va al final y no solo."""
        assert NATIVE_FALLBACK_CLIENTS[-1] == "web"
        assert len(NATIVE_FALLBACK_CLIENTS) > 1

    def test_every_client_of_the_fallback_exists_in_the_installed_ytdlp(self) -> None:
        from src.infrastructure.adapters.platforms.youtube_client_strategy import (
            get_supported_player_clients,
        )

        supported = get_supported_player_clients()
        if supported is None:
            pytest.skip("No se pudo determinar la lista de clientes de yt-dlp")
        for client in NATIVE_FALLBACK_CLIENTS:
            assert client in supported, f"Cliente inexistente en yt-dlp: {client}"


class TestStrategyLadder:
    """La escalera de reintentos debe seguir siendo una progresión válida."""

    def test_isolated_strategies_do_not_repeat_a_client(self) -> None:
        """Los reintentos con un cliente aislado no se repiten entre si.

        El primer peldano (fallback nativo) si puede repetir clientes: su
        proposito es fusionar todos los formatos en una sola extraccion.
        """
        isolated = [s[0] for s in BasePlatformAdapter.CLIENT_STRATEGIES[1:] if s]
        assert len(isolated) == len(set(isolated)), f"Reintentos repetidos: {isolated}"

    def test_every_strategy_is_valid(self) -> None:
        for strategy in BasePlatformAdapter.CLIENT_STRATEGIES:
            assert strategy is None or isinstance(strategy, list)
