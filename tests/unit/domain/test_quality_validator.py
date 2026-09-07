"""Pruebas unitarias para el servicio de dominio QualityValidator y resolución por aspect ratio."""

from src.domain.entities.format_option import FormatOption, StreamType
from src.domain.services.format_normalizer import FormatNormalizer
from src.domain.services.quality_validator import (
    QualityMatchStatus,
    QualityValidator,
)


class TestQualityValidator:
    """Verifica el cálculo de altura efectiva y la validación de calidad cinematográfica."""

    def test_standard_16_9_effective_height(self) -> None:
        assert QualityValidator.calculate_effective_height(1080, 1920) == 1080
        assert QualityValidator.calculate_effective_height(720, 1280) == 720
        assert QualityValidator.calculate_effective_height(480, 854) == 480
        assert QualityValidator.calculate_effective_height(360, 640) == 360

    def test_widescreen_ultrawide_effective_height(self) -> None:
        # 1920x806 es el formato Full HD nativo sin letterbox para cine 2.39:1 en YouTube
        assert QualityValidator.calculate_effective_height(806, 1920) == 1080
        # 1280x538 es 720p ultrawide
        assert QualityValidator.calculate_effective_height(538, 1280) == 720
        # 854x358 es 480p ultrawide
        assert QualityValidator.calculate_effective_height(358, 854) == 480
        # 3840x1600 es 4K ultrawide
        assert QualityValidator.calculate_effective_height(1600, 3840) == 2160

    def test_vertical_video_shorts_effective_height(self) -> None:
        # Videos verticales (Shorts, Reels, TikTok - 9:16)
        assert QualityValidator.calculate_effective_height(1920, 1080) == 1080
        assert QualityValidator.calculate_effective_height(1280, 720) == 720

    def test_disproportionate_non_cinema_not_inflated(self) -> None:
        # Una relación no cinematográfica como 1920x360 no debe inflarse a 1080p
        assert QualityValidator.calculate_effective_height(360, 1920) == 360

    def test_widescreen_1080p_not_flagged_as_degraded(self) -> None:
        requested = FormatOption(
            format_id="137",
            extension="mp4",
            height=1080,
            stream_type=StreamType.VIDEO_ONLY,
            needs_ffmpeg_merge=True,
        )
        probe = {
            "video": {
                "width": 1920,
                "height": 806,
                "fps": 24.0,
                "codec": "h264",
            }
        }
        res = QualityValidator.validate_video_quality(requested, probe)
        assert res.status == QualityMatchStatus.EXACT_OR_COMPATIBLE
        assert res.is_acceptable is True
        assert res.effective_height == 1080
        assert res.message == ""

    def test_real_degradation_detected(self) -> None:
        requested = FormatOption(
            format_id="137",
            extension="mp4",
            height=1080,
            stream_type=StreamType.VIDEO_ONLY,
            needs_ffmpeg_merge=True,
        )
        probe = {
            "video": {
                "width": 640,
                "height": 360,
                "fps": 30.0,
                "codec": "h264",
            }
        }
        res = QualityValidator.validate_video_quality(requested, probe)
        assert res.status == QualityMatchStatus.DEGRADED
        assert res.is_acceptable is True
        assert res.effective_height == 360
        assert "degradada" in res.message.lower()
        assert "1080p" in res.message
        assert "360p" in res.message

    def test_empty_or_corrupt_probe_rejected(self) -> None:
        requested = FormatOption(format_id="137", extension="mp4", height=1080)
        res = QualityValidator.validate_video_quality(requested, {"video": {}})
        assert res.status == QualityMatchStatus.INVALID_OR_EMPTY
        assert res.is_acceptable is False

    def test_best_quality_option_always_accepted(self) -> None:
        requested = FormatOption(
            format_id="best_quality",
            extension="mp4",
            height=1080,
            is_best_quality=True,
        )
        probe = {
            "video": {
                "width": 854,
                "height": 480,
                "fps": 30.0,
                "codec": "h264",
            }
        }
        res = QualityValidator.validate_video_quality(requested, probe)
        assert res.status == QualityMatchStatus.EXACT_OR_COMPATIBLE
        assert res.is_acceptable is True
        assert res.message == ""

    def test_format_normalizer_widescreen_inference(self) -> None:
        raw_format = {
            "format_id": "137",
            "width": 1920,
            "height": 806,
            "ext": "mp4",
        }
        std_h = FormatNormalizer.infer_standard_height(raw_format)
        assert std_h == 1080

        raw_resolution_string = {
            "format_id": "custom",
            "resolution": "1920x806",
            "ext": "mp4",
        }
        std_h2 = FormatNormalizer.infer_standard_height(raw_resolution_string)
        assert std_h2 == 1080
