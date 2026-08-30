"""Test de regresión para asegurar que los títulos de video no se pierdan al generar nombres de archivo."""
from src.domain.entities.format_option import VideoQualityOption
from src.presentation.views.inicio_view import InicioView


def test_build_video_request_preserves_title():
    vqo = VideoQualityOption(
        height=1080,
        label="1080p",
        badge="HD",
        video_format_id="137",
        audio_format_id="140",
        needs_ffmpeg_merge=True,
    )

    fmt_id, filename_template = InicioView._build_video_request(vqo)
    assert fmt_id == "vq_1080"
    assert "{title}" in filename_template

    formatted = filename_template.format(title="Video Musical")
    assert formatted == "Video Musical - 1080p.mp4"
    assert not formatted.startswith(" - ")


def test_build_video_request_with_explicit_title():
    vqo_best = VideoQualityOption(
        height=2160,
        label="Mejor calidad",
        badge="4K",
        video_format_id="best_quality",
        is_best_quality=True,
    )
    fmt_id, filename = InicioView._build_video_request(vqo_best, title="Concierto En Vivo")
    assert fmt_id == "vq_best"
    assert filename == "Concierto En Vivo - Mejor calidad.mp4"
    assert not filename.startswith(" - ")
