"""Tests del sanitizador de URLs con parámetros de playlist."""
import pytest

from src.domain.services.url_sanitizer import sanitize_single_video_url


class TestSanitizeSingleVideoUrl:

    def test_watch_con_list_se_reduce_al_video(self):
        url = "https://www.youtube.com/watch?v=F3tKutGo1Fo&list=PLxyz123&index=4"
        assert sanitize_single_video_url(url) == "https://www.youtube.com/watch?v=F3tKutGo1Fo"

    def test_watch_con_list_al_inicio_del_query(self):
        url = "https://m.youtube.com/watch?list=PLabc&v=dQw4w9WgXcQ&t=30s"
        result = sanitize_single_video_url(url)
        assert "list=" not in result
        assert "v=dQw4w9WgXcQ" in result
        assert "t=30s" in result

    def test_youtube_shorts_y_live_tambien_se_limpian(self):
        url = "https://www.youtube.com/shorts/abc123?list=PLxyz&feature=share"
        assert sanitize_single_video_url(url) == "https://www.youtube.com/shorts/abc123?feature=share"

    def test_youtu_be_corto_con_list(self):
        url = "https://youtu.be/F3tKutGo1Fo?si=token&list=PLxyz"
        result = sanitize_single_video_url(url)
        assert result == "https://youtu.be/F3tKutGo1Fo?si=token"

    def test_playlist_explcita_no_se_toca(self):
        url = "https://www.youtube.com/playlist?list=PLxyz123"
        assert sanitize_single_video_url(url) == url

    def test_url_sin_list_intacta(self):
        url = "https://www.tiktok.com/@user/video/99887766"
        assert sanitize_single_video_url(url) == url

    def test_parametros_no_relacionados_se_conservan_en_orden(self):
        url = "https://www.facebook.com/watch/?v=456&list=PLz&a=1"
        result = sanitize_single_video_url(url)
        assert "list=PLz" not in result
        assert result.endswith("v=456&a=1")

    def test_url_invalida_retorna_intacta(self):
        assert sanitize_single_video_url("") == ""
        assert sanitize_single_video_url("no-es-una-url") == "no-es-una-url"

    @pytest.mark.parametrize("param", ["index", "start_radio", "pp"])
    def test_parametros_contexto_playlist_se_elimina(self, param):
        url = f"https://www.youtube.com/watch?v=abc12345678&{param}=2"
        assert param not in sanitize_single_video_url(url)
