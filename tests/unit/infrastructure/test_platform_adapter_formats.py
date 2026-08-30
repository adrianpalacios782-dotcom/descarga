"""Regresiones del flujo de análisis: respuestas degeneradas de YouTube.

Causa raíz del problema "CALIDAD DE VIDEO vacía" (CASO C - Junior H PARIS):
cuando YouTube aplica su verificación anti-bot a un player_client, la extracción
NO falla: responde con metadata completa (título, canal, duración, miniatura...)
pero SOLO formatos storyboard (mhtml sb0-sb3, vcodec=none, acodec=none).

El adapter debe:
- rechazar esas respuestas como candidatas si otra estrategia entrega formatos reales,
- lanzar MediaAnalysisError solo si TODAS las estrategias resultan degeneradas.
"""
from typing import Any, Dict, List

import pytest

import src.infrastructure.adapters.platforms.base_platform_adapter as bpa_module
from src.domain.exceptions.domain_exceptions import MediaAnalysisError
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.platforms.youtube_adapter import YouTubeAdapter


STORYBOARD_ONLY_FORMATS = [
    {"format_id": "sb3", "ext": "mhtml", "resolution": "48x27", "vcodec": "none", "acodec": "none", "protocol": "mhtml"},
    {"format_id": "sb2", "ext": "mhtml", "resolution": "85x45", "vcodec": "none", "acodec": "none", "protocol": "mhtml"},
    {"format_id": "sb1", "ext": "mhtml", "resolution": "170x90", "vcodec": "none", "acodec": "none", "protocol": "mhtml"},
    {"format_id": "sb0", "ext": "mhtml", "resolution": "340x180", "vcodec": "none", "acodec": "none", "protocol": "mhtml"},
]

FULL_DASH_FORMATS = [
    *STORYBOARD_ONLY_FORMATS,
    {"format_id": "313", "ext": "webm", "height": 2160, "fps": 60, "vcodec": "vp9", "acodec": "none"},
    {"format_id": "308", "ext": "webm", "height": 1440, "fps": 60, "vcodec": "vp9", "acodec": "none"},
    {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 30, "vcodec": "avc1.640028", "acodec": "none"},
    {"format_id": "136", "ext": "mp4", "height": 720, "fps": 30, "vcodec": "avc1.4d401f", "acodec": "none"},
    {"format_id": "135", "ext": "mp4", "height": 480, "fps": 30, "vcodec": "avc1.4d401e", "acodec": "none"},
    {"format_id": "18", "ext": "mp4", "height": 360, "fps": 24, "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
    {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128},
    {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "tbr": 160},
]

AUDIO_ONLY_FORMATS = [
    *STORYBOARD_ONLY_FORMATS,
    {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128},
]

# Respuesta real del cliente android desde IP sin PO token (verificada en sandbox)
CAPPED_ANDROID_FORMATS = [
    *STORYBOARD_ONLY_FORMATS,
    {"format_id": "18", "ext": "mp4", "resolution": "640x338", "fps": 24,
     "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
]


def _info(formats: List[Dict[str, Any]], title: str = "Junior H - PARIS [Official Visualizer]") -> Dict[str, Any]:
    return {
        "id": "eUX086mraqc",
        "title": title,
        "uploader": "Junior H",
        "duration": 236.0,
        "thumbnail": "https://i.ytimg.com/vi/eUX086mraqc/maxresdefault.jpg",
        "upload_date": "20231005",
        "description": "Official Visualizer",
        "formats": formats,
    }


class ScriptedYoutubeDL:
    """Fake de yt_dlp.YoutubeDL que responde según el player_client solicitado.

    behaviors: lista de dicts {clients|default -> ("storyboards"|"full"|"audio"|"error")}.
    Registra cada client usado para verificar cuántas estrategias se intentaron.
    """

    def __init__(self, opts, behaviors: Dict[str, str], calls: List[str]):
        self.opts = opts
        self.behaviors = behaviors
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def close(self):
        pass

    def extract_info(self, url, download=False):
        clients = None
        ea = self.opts.get("extractor_args") or {}
        youtube_args = ea.get("youtube") or {}
        clients = (youtube_args.get("player_client") or [None])[0]
        key = "default" if clients is None else clients
        self.calls.append(key)
        behavior = self.behaviors.get(key, "error")
        if behavior == "error":
            raise RuntimeError(
                "ERROR: [youtube] eUX086mraqc: Sign in to confirm you're not a bot."
            )
        if behavior == "storyboards":
            return _info(STORYBOARD_ONLY_FORMATS)
        if behavior == "audio":
            return _info(AUDIO_ONLY_FORMATS)
        if behavior == "capped":
            return _info(CAPPED_ANDROID_FORMATS, title="Junior H - OTRO AMOR [Official Visualizer]")
        if behavior == "full":
            return _info(FULL_DASH_FORMATS)
        raise RuntimeError(f"comportamiento desconocido: {behavior}")


def _install(monkeypatch, behaviors: Dict[str, str]) -> List[str]:
    calls: List[str] = []

    def factory(opts):
        return ScriptedYoutubeDL(opts, behaviors, calls)

    monkeypatch.setattr(bpa_module.yt_dlp, "YoutubeDL", factory)
    return calls


class TestAdapterDegenerateResponses:

    def test_caso_c_storyboard_default_falls_back_to_tv_full_formats(self, monkeypatch) -> None:
        """CASO C (PARIS): default responde solo storyboards; tv entrega DASH completo.
        El análisis DEBE terminar con calidades reales, no con tarjetas vacías."""
        calls = _install(monkeypatch, {
            "default": "storyboards",
            "tv": "full",
        })
        adapter = YouTubeAdapter()
        metadata = adapter.analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))

        assert calls == ["default", "tv"], "Debe intentar la siguiente estrategia al detectar storyboards"
        heights = [v.height for v in metadata.video_quality_options]
        assert heights, "Deben existir opciones de calidad"
        assert 2160 in heights and 1440 in heights and 1080 in heights
        assert metadata.title == "Junior H - PARIS [Official Visualizer]"

    def test_all_strategies_degenerate_raises_media_analysis_error(self, monkeypatch) -> None:
        """Si TODAS las estrategias devuelven solo storyboards, el análisis debe
        fallar con mensaje claro en lugar de mostrar una previsualización sin calidades."""
        calls = _install(monkeypatch, {
            "default": "storyboards",
            "tv": "storyboards",
            "web": "storyboards",
            "mweb": "storyboards",
        })
        adapter = YouTubeAdapter()
        with pytest.raises(MediaAnalysisError) as ex:
            adapter.analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))
        assert len(calls) == len(adapter.CLIENT_STRATEGIES)
        assert "Fallo al analizar" in str(ex.value)

    def test_bot_check_error_then_full_formats_on_next_strategy(self, monkeypatch) -> None:
        """Estrategia default lanza bot-check; la siguiente entrega formatos completos."""
        calls = _install(monkeypatch, {
            "default": "error",
            "tv": "full",
        })
        adapter = YouTubeAdapter()
        metadata = adapter.analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))
        assert calls == ["default", "tv"]
        assert metadata.video_quality_options

    def test_first_strategy_with_real_video_wins_without_extra_calls(self, monkeypatch) -> None:
        """Camino feliz (CASO A): default entrega formatos completos y no se
        consultan más estrategias (latencia mínima)."""
        calls = _install(monkeypatch, {"default": "full"})
        adapter = YouTubeAdapter()
        metadata = adapter.analyze(Url("https://www.youtube.com/watch?v=F3tKutGo1Fo"))
        assert calls == ["default"]
        labels = [o.label for o in metadata.video_quality_options]
        assert "Mejor calidad" in labels
        assert "1440p" in labels

    def test_android_fallback_accepts_capped_real_formats(self, monkeypatch) -> None:
        """IP restringida (verificada en sandbox): default/tv con bot-check y
        android entrega contenido real pero limitado (itag 18, 640x338).
        El adapter debe aceptarlo: 360p real > cero tarjetas."""
        calls = _install(monkeypatch, {
            "default": "error",
            "tv": "error",
            "android": "capped",
        })
        adapter = YouTubeAdapter()
        metadata = adapter.analyze(Url("https://www.youtube.com/watch?v=F3tKutGo1Fo"))
        assert calls == ["default", "tv", "android"]
        labels = [o.label for o in metadata.video_quality_options]
        assert labels == ["360p"], "Solo hay una altura real: sin síntetica 'Mejor calidad'"
        assert metadata.video_quality_options[0].video_format_id == "18"
        assert metadata.video_quality_options[0].needs_ffmpeg_merge is False

    def test_audio_only_response_accepted_when_no_strategy_has_video(self, monkeypatch) -> None:
        """Contenido solo-audio legítimo: se agotan estrategias buscando video y
        al final se acepta la respuesta solo-audio sin explotar."""
        calls = _install(monkeypatch, {
            "default": "audio",
            "tv": "audio",
            "web": "audio",
            "mweb": "audio",
        })
        adapter = YouTubeAdapter()
        metadata = adapter.analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))
        assert calls == ["default", "tv", "android", "web", "mweb"], "Debe agotar estrategias buscando video"
        assert metadata.audio_formats, "Debe conservar las pistas de audio"
        assert not metadata.video_quality_options

    def test_degenerate_error_message_is_user_friendly(self, monkeypatch) -> None:
        _install(monkeypatch, {
            "default": "storyboards",
            "tv": "storyboards",
            "web": "storyboards",
            "mweb": "storyboards",
        })
        adapter = YouTubeAdapter()
        with pytest.raises(MediaAnalysisError) as ex:
            adapter.analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))
        msg = str(ex.value)
        assert "Traceback" not in msg
        assert "auxiliares" in msg or "restringido" in msg.lower() or "formatos" in msg.lower()

    def test_metadata_survives_empty_formats_list(self, monkeypatch) -> None:
        """Respuesta sin clave formats pero con url directa (single-file). No debe explotar."""
        class SingleFileYDL(ScriptedYoutubeDL):
            def extract_info(self, url, download=False):
                info = _info([])
                info["url"] = "https://media.example.com/file.mp4"
                info["ext"] = "mp4"
                return info

        calls: List[str] = []

        def factory(opts):
            return SingleFileYDL(opts, {}, calls)

        monkeypatch.setattr(bpa_module.yt_dlp, "YoutubeDL", factory)
        adapter = YouTubeAdapter()
        metadata = adapter.analyze(Url("https://www.youtube.com/watch?v=eUX086mraqc"))
        assert metadata.title == "Junior H - PARIS [Official Visualizer]"
        assert metadata.formats, "El archivo directo debe generar un FormatOption 'default'"
