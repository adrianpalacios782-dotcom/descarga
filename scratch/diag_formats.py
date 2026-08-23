"""Diagnóstico real: formatos crudos de yt-dlp vs salida del FormatNormalizer."""
import json
import sys

import yt_dlp

sys.path.insert(0, ".")
from src.domain.services.format_normalizer import FormatNormalizer  # noqa: E402

URLS = {
    "CASO_A_OTRO_AMOR": "https://www.youtube.com/watch?v=F3tKutGo1Fo",
    "CASO_C_PARIS": "https://www.youtube.com/watch?v=eUX086mraqc",
}

STRATEGIES = {
    "default": None,
    "web": ["web"],
}


def dump(url: str, tag: str, clients):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "extract_flat": False,
        "format": "all",
    }
    if clients:
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as ex:
        print(f"[{tag}] EXTRACT ERROR: {ex}")
        return
    if not info:
        print(f"[{tag}] EMPTY INFO")
        return
    fmts = info.get("formats") or []
    print(f"\n===== {tag} | title={info.get('title')!r} | n_formats={len(fmts)} =====")
    rows = []
    for f in fmts:
        rows.append({
            "id": f.get("format_id"),
            "ext": f.get("ext"),
            "res": f.get("resolution"),
            "h": f.get("height"),
            "w": f.get("width"),
            "fps": f.get("fps"),
            "vcodec": (f.get("vcodec") or "")[:12],
            "acodec": (f.get("acodec") or "")[:12],
            "fs": f.get("filesize"),
            "fsa": f.get("filesize_approx"),
            "note": f.get("format_note"),
            "proto": f.get("protocol"),
        })
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    vqos = FormatNormalizer.normalize_video_quality_options(fmts)
    vfs = FormatNormalizer.normalize_video_formats(fmts)
    afs = FormatNormalizer.normalize_audio_formats(fmts)
    print("--> normalizer video_quality_options:", [(v.height, v.label, v.video_format_id, v.needs_ffmpeg_merge) for v in vqos])
    print("--> normalizer video_formats:", [(v.format_id, v.height, v.extension, v.has_audio) for v in vfs])
    print("--> normalizer audio_formats:", [(a.format_id, a.extension, a.bitrate_kbps) for a in afs])


for name, url in URLS.items():
    for sname, clients in STRATEGIES.items():
        dump(url, f"{name}/{sname}", clients)
