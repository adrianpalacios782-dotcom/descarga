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

    def test_ios_and_embedded_clients_are_integrated(self) -> None:
        strategies = BasePlatformAdapter.CLIENT_STRATEGIES
        flat = [c for s in strategies for c in (s or [])]
        assert "ios" in flat, "El cliente iOS debe estar en las estrategias"
        assert "web_embedded" in flat, (
            "El cliente de embed (web_embedded) debe estar en las estrategias: "
            "es el que entrega el ladder completo sin PO token"
        )
        assert "android" in flat, "El cliente Android debe estar en las estrategias"
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

    def test_legacy_tv_embedded_is_aliased_to_its_modern_equivalent(self) -> None:
        """"tv_embedded" fue retirado de yt-dlp: debe traducirse al cliente de TV
        embebido vigente, que ademas NO exige PO token."""
        opts = YouTubeAdapter()._build_ydl_opts(["ios", "tv_embedded", "web"])
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert youtube_args["player_client"] == ["ios", "tv_downgraded", "web"]

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
        """Sin PO token ni visitor_data no debe colarse ningun extractor_arg de
        credenciales; solo queda el bloque de la politica anonima."""
        opts = YouTubeAdapter()._build_ydl_opts()
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        assert "po_token" not in youtube_args
        assert "visitor_data" not in youtube_args
        assert "player_client" not in youtube_args

    def test_po_token_without_clients_covers_the_fallback_clients(self) -> None:
        """Sin estrategia explicita, el token se indexa para los clientes del
        fallback nativo mas los defaults de yt-dlp (visionos + web)."""
        adapter = YouTubeAdapter(po_token="TOKEN_CRUZ")
        opts = adapter._build_ydl_opts()
        youtube_args = (opts.get("extractor_args") or {}).get("youtube") or {}
        entries = youtube_args["po_token"]
        assert "web.gvs+TOKEN_CRUZ" in entries
        assert "ios.gvs+TOKEN_CRUZ" in entries
        assert "visionos.gvs+TOKEN_CRUZ" in entries


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

    def test_tiktok_options_are_decoupled_from_the_base(self, monkeypatch) -> None:
        """El overlay de TikTok no puede mutar por referencia el dict de la base.

        Sin `copy.deepcopy`, mutar una estructura anidada del dict devuelto
        (extractor_args, js_runtimes, remote_components) contaminaria la
        configuracion compartida y afectaria a las demas extracciones.
        """
        base: Dict[str, Any] = {
            "remote_components": ["ejs:github"],
            "js_runtimes": {"node": {"path": ["node"]}},
            "ffmpeg_location": "C:/bin/ffmpeg.exe",
            "extractor_args": {"youtube": {"player_client": ["web"]}},
        }
        monkeypatch.setattr(
            BasePlatformAdapter,
            "_build_ydl_opts",
            lambda self, *args, **kwargs: base,
        )

        opts = TikTokAdapter()._build_ydl_opts()

        # Mutar el resultado NO puede tocar el dict de la clase base.
        opts["remote_components"].append("ejs:otro")
        opts["js_runtimes"]["node"]["path"].append("deno")
        opts["extractor_args"]["youtube"]["player_client"].append("ios")

        assert base["remote_components"] == ["ejs:github"]
        assert base["js_runtimes"]["node"]["path"] == ["node"]
        assert base["extractor_args"]["youtube"]["player_client"] == ["web"]

    def test_tiktok_runtime_keys_are_guaranteed(self, monkeypatch) -> None:
        """remote_components, js_runtimes y ffmpeg_location se re-afirman."""
        base: Dict[str, Any] = {
            "remote_components": ["ejs:github"],
            "js_runtimes": {"node": {}},
            "ffmpeg_location": "C:/bin/ffmpeg.exe",
        }
        monkeypatch.setattr(
            BasePlatformAdapter,
            "_build_ydl_opts",
            lambda self, *args, **kwargs: dict(base),
        )

        opts = TikTokAdapter()._build_ydl_opts()

        for key in TikTokAdapter.RUNTIME_KEYS:
            assert key in opts, f"TikTok perdio la clave de runtime {key}"
        assert opts["remote_components"] == ["ejs:github"]
        assert opts["js_runtimes"] == {"node": {}}
        assert opts["ffmpeg_location"] == "C:/bin/ffmpeg.exe"

    def test_runtime_keys_contract(self) -> None:
        assert TikTokAdapter.RUNTIME_KEYS == (
            "remote_components",
            "js_runtimes",
            "ffmpeg_location",
        )


class TestCookiesFromBrowserSetter:

    def test_base_adapter_exposes_setter(self) -> None:
        adapter = BasePlatformAdapter(cookies_from_browser="firefox")
        adapter.set_cookies_from_browser("chrome")
        assert adapter.cookies_from_browser == "chrome"
        adapter.set_cookies_from_browser(None)
        assert adapter.cookies_from_browser is None
        adapter.set_cookies_from_browser("   ")
        assert adapter.cookies_from_browser is None
