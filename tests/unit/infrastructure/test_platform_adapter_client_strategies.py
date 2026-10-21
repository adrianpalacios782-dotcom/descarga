"""Pruebas de las correcciones de adaptadores de plataforma.

Cubre tres correcciones:

1. CLIENT_STRATEGIES de YouTube: se integraron los clientes "ios" y el cliente
   de TV embebido. En yt-dlp 2026.x el cliente de TV embebido se llama
   "tv_simply" (TVHTML5_SIMPLY); "tv_embedded" ya NO existe en
   yt_dlp.extractor.youtube._base.INNERTUBE_CLIENTS y yt-dlp lo descarta
   silenciosamente con un warning ("Skipping unsupported client"), gastando
   una request de red sin obtener nada. Por eso el adaptador filtra los
   clientes no soportados ANTES de llamar a yt-dlp.

2. PO token / visitor_data: estaban declarados en el constructor pero nunca
   se usaban. Ahora YouTubeAdapter los inyecta como extractor_args, que es
   donde yt-dlp los lee.

3. TikTokAdapter._build_ydl_opts no llamaba a super() y por eso perdia
   remote_components (solver EJS), js_runtimes (node/deno) y ffmpeg_location.
"""

from typing import Any, Dict

import pytest

from src.infrastructure.adapters.platforms.base_platform_adapter import (
    BasePlatformAdapter,
    get_supported_player_clients,
)
from src.infrastructure.adapters.platforms.tiktok_adapter import TikTokAdapter
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter


class TestClientStrategies:

    def test_ios_and_embedded_tv_clients_are_integrated(self) -> None:
        strategies = BasePlatformAdapter.CLIENT_STRATEGIES
        flat = [c for s in strategies for c in (s or [])]
        assert "ios" in flat, "El cliente iOS debe estar en las estrategias"
        assert "tv_simply" in flat, "El cliente TV embebido (tv_simply) debe estar en las estrategias"
        # "tv_embedded" no existe en yt-dlp 2026.x: no debe volver a colarse.
        assert "tv_embedded" not in flat

    def test_every_listed_client_is_supported_by_installed_ytdlp(self) -> None:
        supported = get_supported_player_clients()
        if supported is None:
            pytest.skip("No se pudo determinar la lista de clientes de yt-dlp")
        for strategy in BasePlatformAdapter.CLIENT_STRATEGIES:
            for client in strategy or []:
                assert client in supported, f"Cliente obsoleto en CLIENT_STRATEGIES: {client}"

    def test_unsupported_client_is_filtered_before_reaching_ytdlp(self) -> None:
        supported = get_supported_player_clients()
        if supported is None:
            pytest.skip("No se pudo determinar la lista de clientes de yt-dlp")
        opts = YouTubeAdapter()._build_ydl_opts(["tv_embedded"])
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert "tv_embedded" not in (youtube_args.get("player_client") or [])

    def test_valid_clients_are_kept_untouched(self) -> None:
        opts = YouTubeAdapter()._build_ydl_opts(["ios", "tv_simply"])
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert youtube_args["player_client"] == ["ios", "tv_simply"]


class TestPoTokenAndVisitorData:

    def test_po_token_is_injected_as_extractor_arg(self) -> None:
        adapter = YouTubeAdapter(po_token="TOKEN_CRUZ")
        opts = adapter._build_ydl_opts(["ios"])
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert youtube_args["po_token"] == ["ios.gvs+TOKEN_CRUZ"]

    def test_po_token_with_client_prefix_is_passed_verbatim(self) -> None:
        adapter = YouTubeAdapter(po_token="web.gvs+ABCDEF")
        opts = adapter._build_ydl_opts(["web"])
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert youtube_args["po_token"] == ["web.gvs+ABCDEF"]

    def test_visitor_data_is_injected(self) -> None:
        adapter = YouTubeAdapter(visitor_data="VISITOR-XYZ")
        opts = adapter._build_ydl_opts(["ios"])
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert youtube_args["visitor_data"] == "VISITOR-XYZ"

    def test_no_extractor_args_when_nothing_configured(self) -> None:
        opts = YouTubeAdapter()._build_ydl_opts()
        assert "extractor_args" not in opts

    def test_po_token_without_clients_defaults_to_web(self) -> None:
        adapter = YouTubeAdapter(po_token="TOKEN_CRUZ")
        opts = adapter._build_ydl_opts()
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert youtube_args["po_token"] == ["web.gvs+TOKEN_CRUZ"]


class TestTikTokAdapterOptions:

    def test_tiktok_reuses_base_options(self, monkeypatch) -> None:
        """TikTokAdapter debe llamar a super(): si no, pierde las opciones base."""
        sentinel: Dict[str, Any] = {"remote_components": ["ejs:github"], "sentinel": True}
        monkeypatch.setattr(
            BasePlatformAdapter,
            "_build_ydl_opts",
            lambda self, *args, **kwargs: dict(sentinel),
        )
        opts = TikTokAdapter()._build_ydl_opts()
        assert opts["sentinel"] is True
        assert opts["remote_components"] == ["ejs:github"]

    def test_tiktok_inherits_all_base_options(self) -> None:
        """TikTok no puede perder ninguna opcion que construye la clase base."""
        base = BasePlatformAdapter()._build_ydl_opts()
        tiktok = TikTokAdapter()._build_ydl_opts()
        missing = sorted(k for k in base if k not in tiktok)
        assert not missing, f"TikTok perdio opciones de la clase base: {missing}"
        assert tiktok["remote_components"] == ["ejs:github"], "Se perdia el solver EJS"
        # Si el entorno tiene node/deno o ffmpeg, TikTok debe heredarlos igual.
        for key in ("js_runtimes", "ffmpeg_location"):
            if key in base:
                assert tiktok[key] == base[key], f"Se perdio {key}"

    def test_tiktok_keeps_referer_and_origin(self) -> None:
        opts = TikTokAdapter()._build_ydl_opts()
        assert opts["referer"] == "https://www.tiktok.com/"
        assert opts["origin"] == "https://www.tiktok.com/"

    def test_tiktok_cookie_precedence_matches_base(self, tmp_path) -> None:
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

        adapter = TikTokAdapter(cookies_from_browser="firefox", cookiefile=str(cookie_file))
        opts = adapter._build_ydl_opts()
        assert opts["cookiefile"] == str(cookie_file)
        assert "cookiesfrombrowser" not in opts

        adapter_browser = TikTokAdapter(cookies_from_browser="firefox")
        opts_browser = adapter_browser._build_ydl_opts()
        assert opts_browser["cookiesfrombrowser"] == ("firefox",)
        assert "cookiefile" not in opts_browser

    def test_tiktok_can_disable_browser_cookies(self) -> None:
        adapter = TikTokAdapter(cookies_from_browser="firefox")
        opts = adapter._build_ydl_opts(disable_browser_cookies=True)
        assert "cookiesfrombrowser" not in opts


class TestCookiesFromBrowserSetter:

    def test_base_adapter_exposes_setter(self) -> None:
        adapter = BasePlatformAdapter(cookies_from_browser="firefox")
        adapter.set_cookies_from_browser("chrome")
        assert adapter.cookies_from_browser == "chrome"
        adapter.set_cookies_from_browser(None)
        assert adapter.cookies_from_browser is None
        adapter.set_cookies_from_browser("   ")
        assert adapter.cookies_from_browser is None
