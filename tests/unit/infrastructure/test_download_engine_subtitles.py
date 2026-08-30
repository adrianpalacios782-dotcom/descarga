from src.domain.entities.subtitle import SubtitleConfig, SubtitleMode
from src.infrastructure.adapters.download.ytdlp_download_engine import (
    apply_subtitle_options,
    extract_subtitle_tracks,
)


def test_extract_subtitle_tracks():
    info = {
        "subtitles": {
            "es": [{"ext": "vtt", "name": "Español"}],
            "en": [{"ext": "vtt", "name": "English"}],
        },
        "automatic_captions": {
            "fr": [{"ext": "vtt", "name": "Français"}],
        },
    }
    tracks = extract_subtitle_tracks(info)
    assert len(tracks) == 3

    es_track = next(t for t in tracks if t.language_code == "es")
    assert es_track.name == "Español"
    assert es_track.is_auto_generated is False

    fr_track = next(t for t in tracks if t.language_code == "fr")
    assert fr_track.name == "Français"
    assert fr_track.is_auto_generated is True


def test_apply_subtitle_options_none():
    opts = {"quiet": True}
    res = apply_subtitle_options(opts, None)
    assert "subtitleslangs" not in res
    assert "writesubtitles" not in res

    cfg_none = SubtitleConfig(mode=SubtitleMode.NONE)
    res2 = apply_subtitle_options(opts, cfg_none)
    assert "subtitleslangs" not in res2


def test_apply_subtitle_options_embed_manual():
    opts = {"quiet": True}
    cfg = SubtitleConfig(
        mode=SubtitleMode.EMBED,
        language_code="es",
        is_auto_generated=False,
    )
    res = apply_subtitle_options(opts, cfg)
    assert res["subtitleslangs"] == ["es"]
    assert res["writesubtitles"] is True
    assert "writeautomaticsub" not in res

    pps = res.get("postprocessors", [])
    assert any(p.get("key") == "FFmpegEmbedSubtitle" for p in pps)


def test_apply_subtitle_options_embed_auto():
    opts = {"quiet": True}
    cfg = SubtitleConfig(
        mode=SubtitleMode.EMBED,
        language_code="en",
        is_auto_generated=True,
    )
    res = apply_subtitle_options(opts, cfg)
    assert res["subtitleslangs"] == ["en"]
    assert res["writeautomaticsub"] is True

    pps = res.get("postprocessors", [])
    assert any(p.get("key") == "FFmpegEmbedSubtitle" for p in pps)


def test_apply_subtitle_options_external():
    opts = {"quiet": True}
    cfg = SubtitleConfig(
        mode=SubtitleMode.EXTERNAL,
        language_code="de",
        is_auto_generated=False,
    )
    res = apply_subtitle_options(opts, cfg)
    assert res["subtitleslangs"] == ["de"]
    assert res["writesubtitles"] is True

    pps = res.get("postprocessors", [])
    assert any(p.get("key") == "FFmpegSubtitlesConvertor" and p.get("format") == "srt" for p in pps)
