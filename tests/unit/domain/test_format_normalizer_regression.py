"""Regresiones de normalización de formatos (Problemas 6, 7 y 8).

- La resolución se deriva de metadata REAL (height > width/resolution), nunca
  se asume que format_note o format_id == resolución.
- Un formato sin filesize/filesize_approx NO se descarta: aparece con
  "Tamaño no disponible".
- Las tarjetas solo se generan a partir de formatos realmente disponibles,
  en WEBM, MP4, video-only + audio-only.
"""
from src.domain.services.format_normalizer import FormatNormalizer


class TestResolutionDerivationFromRealMetadata:

    def test_height_real_wins_over_misleading_format_note(self) -> None:
        """format_note engañoso ('HD' → 720) no debe ganarle al height real (1080)."""
        raw = [
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 30,
             "vcodec": "avc1.640028", "acodec": "none", "format_note": "HD"},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        assert [o.height for o in options] == [1080]

    def test_resolution_string_used_when_height_missing(self) -> None:
        """Formato con 'resolution': '1920x1080' pero sin height numérico: la
        altura estándar se deriva del texto de resolución real."""
        raw = [
            {"format_id": "dash-1080", "ext": "mp4", "resolution": "1920x1080",
             "vcodec": "avc1", "acodec": "none"},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        assert [o.height for o in options] == [1080]

    def test_resolution_wxh_derives_standard_height(self) -> None:
        """Cliente android real (sandbox): '640x338' sin height numérico → tarjeta 360p.
        Antes de la corrección el formato se descartaba y no había tarjetas."""
        raw = [
            {"format_id": "18", "ext": "mp4", "resolution": "640x338", "fps": 24,
             "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        assert [(o.label, o.video_format_id) for o in options] == [("360p", "18")]
        assert options[0].needs_ffmpeg_merge is False

    def test_format_id_numeric_is_not_assumed_to_be_resolution(self) -> None:
        """format_id '43' no significa altura 43 ni 480; sin evidencia real no hay tarjeta."""
        raw = [
            {"format_id": "43", "ext": "webm", "vcodec": "vp8", "acodec": "vorbis"},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        assert options == []

    def test_non_standard_height_maps_to_nearest_standard_bucket(self) -> None:
        """Alturas recortadas reales de YouTube: 1074→1080, 806→720, 538→480."""
        raw = [
            {"format_id": "a", "ext": "mp4", "height": 1074, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "b", "ext": "mp4", "height": 806, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "c", "ext": "mp4", "height": 538, "vcodec": "avc1", "acodec": "none"},
        ]
        heights = sorted(
            (o.height for o in FormatNormalizer.normalize_video_quality_options(raw) if not o.is_best_quality),
            reverse=True,
        )
        assert heights == [1080, 720, 480]

    def test_width_fps_codecs_captured(self) -> None:
        raw = [
            {"format_id": "298", "ext": "mp4", "width": 1920, "height": 1080, "fps": 60,
             "vcodec": "avc1.64002a", "acodec": "none"},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128},
        ]
        vf = FormatNormalizer.normalize_video_formats(raw)[0]
        assert vf.width == 1920 and vf.fps == 60.0
        assert vf.video_codec == "avc1.64002a"
        assert vf.has_audio is False and vf.needs_ffmpeg_merge is True
        assert vf.audio_format_id == "140"


class TestMissingFilesizeNeverDiscards:

    def test_formats_without_filesize_still_become_cards(self) -> None:
        """Sin filesize NI filesize_approx: la calidad aparece igual (caso obligatorio 2)."""
        raw = [
            {"format_id": "313", "ext": "webm", "height": 2160, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "137", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none",
             "filesize_approx": 250 * 1024 * 1024},
            {"format_id": "136", "ext": "mp4", "height": 720, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "18", "ext": "mp4", "height": 360, "vcodec": "avc1", "acodec": "mp4a"},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        labels = [o.label for o in options if not o.is_best_quality]
        assert labels == ["2160p", "1080p", "720p", "360p"]
        by_label = {o.label: o for o in options}
        assert by_label["2160p"].estimated_size_bytes is None
        assert by_label["2160p"].get_technical_info().count("Tamaño no disponible") == 1
        assert by_label["1080p"].estimated_size_bytes == 250 * 1024 * 1024

    def test_audio_without_filesize_kept(self) -> None:
        raw = [
            {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "tbr": 160},
        ]
        audio = FormatNormalizer.normalize_audio_formats(raw)
        assert len(audio) == 1
        assert audio[0].filesize_bytes is None
        assert audio[0].format_id == "251"


class TestRealContainerChains:

    def test_webm_only_chain_produces_cards(self) -> None:
        """CASO A (OTRO AMOR): cadena WEBM VP9 con 1440p disponible."""
        raw = [
            {"format_id": "271", "ext": "webm", "height": 1440, "fps": 60, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "248", "ext": "webm", "height": 1080, "fps": 24, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "247", "ext": "webm", "height": 720, "fps": 24, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "tbr": 160},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        labels = [o.label for o in options if not o.is_best_quality]
        assert labels == ["1440p", "1080p", "720p"]
        best = options[0]
        assert best.is_best_quality and best.height == 1440
        assert best.extension == "webm"
        assert best.audio_format_id == "251" and best.needs_ffmpeg_merge

    def test_mp4_progressive_chain_produces_cards(self) -> None:
        raw = [
            {"format_id": "22", "ext": "mp4", "height": 720, "fps": 30,
             "vcodec": "avc1.64001f", "acodec": "mp4a.40.2"},
            {"format_id": "18", "ext": "mp4", "height": 360, "fps": 24,
             "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        real = [o for o in options if not o.is_best_quality]
        assert [o.label for o in real] == ["720p", "360p"]
        # Formatos progresivos: sin merge
        assert all(o.needs_ffmpeg_merge is False for o in real)

    def test_video_only_plus_audio_only_builds_merge_option(self) -> None:
        """video-only DASH + audio-only separados: opción con merge y audio correcto."""
        raw = [
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 24,
             "vcodec": "avc1.640028", "acodec": "none"},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 129},
        ]
        options = FormatNormalizer.normalize_video_quality_options(raw)
        opt_1080 = next(o for o in options if o.height == 1080)
        assert opt_1080.needs_ffmpeg_merge is True
        assert opt_1080.audio_format_id == "140"
        assert opt_1080.video_format_id == "137"

    def test_cards_only_from_really_available_heights(self) -> None:
        """Si el video solo ofrece 720/480/360, no se inventan 1080p ni 4K (caso obligatorio 8)."""
        raw = [
            {"format_id": "136", "ext": "mp4", "height": 720, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "135", "ext": "mp4", "height": 480, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "134", "ext": "mp4", "height": 360, "vcodec": "avc1", "acodec": "mp4a"},
        ]
        labels = [o.label for o in FormatNormalizer.normalize_video_quality_options(raw)]
        assert "1080p" not in labels and "2160p" not in labels and "1440p" not in labels
        assert labels == ["Mejor calidad", "720p", "480p", "360p"]


class TestBestQualitySynthetic:

    def test_best_quality_only_with_two_or_more_distinct_heights(self) -> None:
        single = [{"format_id": "18", "ext": "mp4", "height": 360, "vcodec": "avc1", "acodec": "mp4a"}]
        assert FormatNormalizer.normalize_video_quality_options(single)[0].is_best_quality is False

        multi = [
            *single,
            {"format_id": "136", "ext": "mp4", "height": 720, "vcodec": "avc1", "acodec": "none"},
        ]
        options = FormatNormalizer.normalize_video_quality_options(multi)
        assert options[0].is_best_quality is True
        assert options[0].label == "Mejor calidad"
