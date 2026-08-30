from src.domain.services.format_normalizer import FormatNormalizer


class TestFormatNormalizer:

    def test_is_auxiliary_format_filters_storyboards_and_mhtml(self) -> None:
        aux_formats = [
            {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none", "format_note": "storyboard"},
            {"format_id": "sb1", "ext": "jpg", "vcodec": "none", "acodec": "none"},
            {"format_id": "137", "ext": "mhtml", "container": "mhtml", "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "302", "ext": "webm", "protocol": "mhtml", "vcodec": "vp9", "acodec": "opus"},
            {"format_id": "none_none", "ext": "mp4", "vcodec": "none", "acodec": "none"},
        ]

        for f in aux_formats:
            assert FormatNormalizer.is_auxiliary_format(f) is True, f"Fallo al detectar formato auxiliar: {f}"

    def test_is_auxiliary_format_keeps_valid_media(self) -> None:
        valid_formats = [
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 30, "vcodec": "avc1.640028", "acodec": "none"},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128},
            {"format_id": "18", "ext": "mp4", "height": 360, "fps": 24, "vcodec": "avc1.42001E", "acodec": "mp4a.40.2"},
        ]

        for f in valid_formats:
            assert FormatNormalizer.is_auxiliary_format(f) is False, f"Se clasificó erróneamente como auxiliar: {f}"

    def test_normalize_video_quality_options_descending_with_badges(self) -> None:
        raw = [
            {"format_id": "313", "ext": "webm", "height": 2160, "fps": 60, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 30, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "136", "ext": "mp4", "height": 720, "fps": 30, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "18", "ext": "mp4", "height": 360, "fps": 24, "vcodec": "avc1", "acodec": "mp4a"},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "tbr": 128},
        ]

        options = FormatNormalizer.normalize_video_quality_options(raw)

        # "Mejor calidad" al inicio + 4 resoluciones reales
        assert len(options) == 5
        assert options[0].is_best_quality is True
        assert options[0].label == "Mejor calidad"
        assert options[0].height == 2160
        assert options[0].needs_ffmpeg_merge is True
        assert options[0].audio_format_id == "140"

        # Orden descendente de las opciones reales
        assert [o.height for o in options[1:]] == [2160, 1080, 720, 360]
        assert [o.label for o in options[1:]] == ["2160p", "1080p", "720p", "360p"]

        # Insignias
        assert options[1].badge == "4K"
        assert options[2].badge == "HD"
        assert options[3].badge == "HD"
        assert options[4].badge == ""

        # Sincronización automática con mejor audio cuando requiere merge
        assert options[1].needs_ffmpeg_merge is True
        assert options[1].audio_format_id == "140"
        assert options[4].needs_ffmpeg_merge is False

    def test_normalize_video_formats_separates_video_and_synthesizes_best_quality(self) -> None:
        raw = [
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 60, "vcodec": "avc1.640028", "acodec": "none", "filesize": 100 * 1024 * 1024},
            {"format_id": "136", "ext": "mp4", "height": 720, "fps": 30, "vcodec": "avc1.4d401f", "acodec": "none", "filesize": 50 * 1024 * 1024},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128, "filesize": 10 * 1024 * 1024},
        ]

        video_formats = FormatNormalizer.normalize_video_formats(raw)

        # 1. El formato de solo audio (140) NO debe estar en las opciones de video
        for vf in video_formats:
            assert vf.video_codec is not None and vf.video_codec != "none"

        # 2. Al haber 2 resoluciones distintas (1080p y 720p), debe existir "best_quality" al inicio
        assert video_formats[0].is_best_quality is True
        assert video_formats[0].height == 1080

    def test_normalize_audio_formats_separates_audio(self) -> None:
        raw = [
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 60, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "tbr": 128, "filesize": 10 * 1024 * 1024},
            {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "tbr": 160, "filesize": 12 * 1024 * 1024},
        ]

        audio_formats = FormatNormalizer.normalize_audio_formats(raw)

        # 1. No debe haber ningún flujo con video
        assert len(audio_formats) == 2
        for af in audio_formats:
            assert af.audio_codec is not None
            # Las descripciones de audio NUNCA contienen resolución (360p, 720p, 1080p)
            desc = af.get_description()
            assert "1080p" not in desc
            assert "720p" not in desc

    def test_single_resolution_no_duplicate_best_quality(self) -> None:
        raw = [
            {"format_id": "18", "ext": "mp4", "height": 360, "fps": 24, "vcodec": "avc1", "acodec": "mp4a", "filesize": 10 * 1024 * 1024},
        ]

        video_formats = FormatNormalizer.normalize_video_formats(raw)

        # Al existir una sola resolución (360p), NO se debe duplicar agregando un objeto sintético "Mejor calidad" idéntico
        assert len(video_formats) == 1
        assert video_formats[0].height == 360
        assert video_formats[0].is_best_quality is False

    def test_full_resolution_chain_descending(self) -> None:
        raw = [
            {"format_id": "313", "ext": "webm", "height": 2160, "fps": 60, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "308", "ext": "webm", "height": 1440, "fps": 60, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 30, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "136", "ext": "mp4", "height": 720, "fps": 30, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "135", "ext": "mp4", "height": 480, "fps": 30, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "134", "ext": "mp4", "height": 360, "fps": 30, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "133", "ext": "mp4", "height": 240, "fps": 30, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "160", "ext": "mp4", "height": 144, "fps": 15, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "tbr": 128},
        ]

        options = FormatNormalizer.normalize_video_quality_options(raw)

        assert len(options) == 9  # Mejor calidad + 8 resoluciones reales
        assert options[0].is_best_quality is True
        assert options[0].height == 2160
        assert [o.height for o in options[1:]] == [2160, 1440, 1080, 720, 480, 360, 240, 144]
        assert [o.label for o in options[1:]] == ["2160p", "1440p", "1080p", "720p", "480p", "360p", "240p", "144p"]
        # Ninguna opción real duplicada ni auxiliar
        heights = [o.height for o in options[1:]]
        assert len(heights) == len(set(heights))

    def test_storyboard_and_thumbnails_never_become_options(self) -> None:
        raw = [
            {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none", "format_note": "storyboard"},
            {"format_id": "sb1", "ext": "jpg", "vcodec": "none", "acodec": "none", "format_note": "storyboard"},
            {"format_id": "sth", "ext": "mhtml", "vcodec": "none", "acodec": "none", "format_note": "thumbnail"},
            {"format_id": "313", "ext": "webm", "height": 2160, "fps": 60, "vcodec": "vp9", "acodec": "none"},
            {"format_id": "137", "ext": "mp4", "height": 1080, "fps": 30, "vcodec": "avc1", "acodec": "none"},
        ]

        options = FormatNormalizer.normalize_video_quality_options(raw)

        assert len(options) == 3  # Mejor calidad + 2160p + 1080p
        # Ninguna opción proviene de storyboard/thumbnail (sb0, sb1, sth)
        ids = [o.video_format_id for o in options]
        assert "sb0" not in ids and "sb1" not in ids and "sth" not in ids
        assert "best_quality" in ids
        assert all(o.label in ("Mejor calidad", "2160p", "1080p") for o in options)
