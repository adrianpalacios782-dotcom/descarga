"""Extractor y normalizador de subtítulos de yt-dlp."""
from typing import Any, Dict, List
from src.domain.entities.subtitle import SubtitleTrack


def extract_subtitle_tracks(info: Dict[str, Any]) -> List[SubtitleTrack]:
    """Extrae y normaliza las pistas de subtítulos (manuales y automáticas) de yt-dlp."""
    tracks: List[SubtitleTrack] = []
    seen_codes: set[tuple[str, bool]] = set()

    # 1. Subtítulos manuales / oficiales
    manual_subs = info.get("subtitles") or {}
    if isinstance(manual_subs, dict):
        for lang_code, formats in manual_subs.items():
            if not lang_code:
                continue
            name = ""
            ext = "vtt"
            if isinstance(formats, list) and formats:
                first_fmt = formats[0] if isinstance(formats[0], dict) else {}
                name = first_fmt.get("name") or first_fmt.get("ext") or ""
                ext = first_fmt.get("ext") or "vtt"
            key = (lang_code.lower(), False)
            if key not in seen_codes:
                seen_codes.add(key)
                tracks.append(
                    SubtitleTrack(
                        language_code=lang_code,
                        name=name or lang_code,
                        extension=ext,
                        is_auto_generated=False,
                    )
                )

    # 2. Subtítulos automáticos (automatic_captions)
    auto_subs = info.get("automatic_captions") or {}
    if isinstance(auto_subs, dict):
        for lang_code, formats in auto_subs.items():
            if not lang_code:
                continue
            name = ""
            ext = "vtt"
            if isinstance(formats, list) and formats:
                first_fmt = formats[0] if isinstance(formats[0], dict) else {}
                name = first_fmt.get("name") or first_fmt.get("ext") or ""
                ext = first_fmt.get("ext") or "vtt"
            key = (lang_code.lower(), True)
            if key not in seen_codes:
                seen_codes.add(key)
                tracks.append(
                    SubtitleTrack(
                        language_code=lang_code,
                        name=name or f"{lang_code} (Auto)",
                        extension=ext,
                        is_auto_generated=True,
                    )
                )

    return tracks
