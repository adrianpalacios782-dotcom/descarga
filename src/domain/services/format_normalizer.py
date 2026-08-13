from typing import Any, Dict, List, Optional, Tuple

from src.domain.entities.format_option import (
    FormatOption, StreamType, VideoFormat, AudioFormat, VideoQualityOption
)


class FormatNormalizer:
    """Servicio de dominio para filtrar, normalizar y clasificar por separado formatos de VIDEO y AUDIO."""

    AUXILIARY_EXTENSIONS = ("mhtml", "sb0", "sb1", "sb2", "sb3", "jpg", "jpeg", "png", "webp", "json")
    AUXILIARY_FORMAT_IDS = ("sb0", "sb1", "sb2", "sb3", "none", "none_none", "0", "storyboard", "thumbnails", "thumbnail")

    @staticmethod
    def is_auxiliary_format(f: Dict[str, Any]) -> bool:
        """Determina si un formato de yt-dlp es un recurso auxiliar (storyboard, MHTML, thumbnail, metadata-only, etc.)."""
        fmt_id = str(f.get("format_id") or "").lower()
        ext = str(f.get("ext") or "").lower()
        container = str(f.get("container") or "").lower()
        protocol = str(f.get("protocol") or "").lower()
        format_note = str(f.get("format_note") or "").lower()
        format_name = str(f.get("format") or "").lower()
        resolution = str(f.get("resolution") or "").lower()

        vcodec = str(f.get("vcodec") or "none").lower()
        acodec = str(f.get("acodec") or "none").lower()

        # 1. Ningún flujo de audio ni video (metadata-only / none/none / thumbnails)
        if vcodec == "none" and acodec == "none":
            return True

        # 2. Extensiones y contenedores auxiliares
        if ext in FormatNormalizer.AUXILIARY_EXTENSIONS:
            return True
        if container == "mhtml" or "mhtml" in protocol or ext == "mhtml":
            return True
        if vcodec in ("images", "storyboard", "image"):
            return True

        # 3. Marcas de storyboard o recursos auxiliares
        if fmt_id in FormatNormalizer.AUXILIARY_FORMAT_IDS or fmt_id.startswith("sb"):
            return True
        if "storyboard" in format_note or "storyboard" in fmt_id or "storyboard" in format_name:
            return True
        if "mhtml" in fmt_id or "mhtml" in format_name or "mhtml" in format_note:
            return True
        if "thumbnail" in format_note or "thumbnail" in fmt_id:
            return True
        if "metadata" in format_note and vcodec == "none":
            return True

        # 4. Marcas de resolución auxiliar
        if "storyboard" in resolution or resolution in ("images", "thumbnails"):
            return True

        # 5. FPS == 0 sin resolución ni video real
        fps = f.get("fps")
        height = f.get("height")
        if fps == 0 and (height is None or height == 0) and vcodec in ("none", "storyboard", "images"):
            return True

        return False

    @classmethod
    def normalize_video_quality_options(cls, raw_formats: List[Dict[str, Any]]) -> List[VideoQualityOption]:
        """Genera las opciones de resolución de video reales ordenadas descendentemente, con 'Mejor calidad' al inicio."""
        best_audio_id = cls._find_best_audio_format_id(raw_formats)
        formats_by_height: Dict[int, List[VideoFormat]] = {}

        for vf in cls.normalize_video_formats(raw_formats):
            if vf.is_best_quality or not vf.height:
                continue
            height = vf.height
            if height not in formats_by_height:
                formats_by_height[height] = []
            formats_by_height[height].append(vf)

        if not formats_by_height:
            return []

        sorted_heights = sorted(formats_by_height.keys(), reverse=True)
        max_height = sorted_heights[0]

        quality_options: List[VideoQualityOption] = []

        # 1. Opción sintética "Mejor calidad" (solo si hay 2+ resoluciones distintas para evitar duplicados)
        if len(sorted_heights) >= 2:
            best_vfs = formats_by_height[max_height]
            best_vf = max(best_vfs, key=lambda v: (1 if v.has_audio else 0, v.fps or 0, v.filesize_bytes or 0))
            quality_options.append(
                VideoQualityOption(
                    height=max_height,
                    label="Mejor calidad",
                    badge="",
                    video_format_id="best_quality",
                    audio_format_id=best_audio_id,
                    needs_ffmpeg_merge=True,
                    estimated_size_bytes=best_vf.filesize_bytes,
                    fps=best_vf.fps,
                    extension=best_vf.extension,
                    width=best_vf.width,
                    video_codec=best_vf.video_codec,
                    is_best_quality=True
                )
            )

        # 2. Resoluciones reales descendentes (1080p, 720p, 480p, 360p, ...)
        for h in sorted_heights:
            vfs = formats_by_height[h]
            best_vf = max(vfs, key=lambda v: (1 if v.has_audio else 0, v.fps or 0, v.filesize_bytes or 0))

            badge = ""
            if h >= 2160:
                badge = "4K"
            elif h >= 1440:
                badge = "2K"
            elif h >= 720:
                if h in (1080, 720) or h == max_height:
                    badge = "HD"

            label = f"{h}p"
            needs_merge = not best_vf.has_audio
            audio_id = best_audio_id if needs_merge else None

            quality_options.append(
                VideoQualityOption(
                    height=h,
                    label=label,
                    badge=badge,
                    video_format_id=best_vf.format_id,
                    audio_format_id=audio_id,
                    needs_ffmpeg_merge=needs_merge,
                    estimated_size_bytes=best_vf.filesize_bytes,
                    fps=best_vf.fps,
                    extension=best_vf.extension,
                    width=best_vf.width,
                    video_codec=best_vf.video_codec,
                )
            )

        return quality_options

    @classmethod
    def normalize_video_formats(cls, raw_formats: List[Dict[str, Any]]) -> List[VideoFormat]:
        """Normaliza y deduplica las opciones de VIDEO (VIDEO_ONLY y VIDEO_AUDIO). No descarta VIDEO_ONLY."""
        seen: Dict[Tuple[int, int, str], VideoFormat] = {}
        best_audio_id: Optional[str] = cls._find_best_audio_format_id(raw_formats)

        for f in raw_formats:
            if cls.is_auxiliary_format(f):
                continue

            vcodec = f.get("vcodec")
            if not vcodec or vcodec == "none":
                continue  # Descartar solo-audio

            acodec = f.get("acodec")
            has_audio = acodec is not None and acodec != "none"
            fmt_id = str(f.get("format_id") or "")
            ext = str(f.get("ext") or "mp4")
            height = f.get("height") or 0
            fps = float(f.get("fps")) if f.get("fps") else 0.0
            res = str(f.get("format_note") or f.get("resolution") or "")
            if not res and height:
                res = f"{height}p"

            filesize = f.get("filesize") or f.get("filesize_approx")

            vf = VideoFormat(
                format_id=fmt_id,
                extension=ext,
                resolution=res,
                width=f.get("width"),
                height=height if height > 0 else None,
                fps=fps if fps > 0 else None,
                video_codec=str(vcodec),
                has_audio=has_audio,
                needs_ffmpeg_merge=not has_audio,
                audio_format_id=best_audio_id if not has_audio else None,
                filesize_bytes=filesize
            )

            dedup_key = (height, int(fps), ext.lower())
            if dedup_key not in seen:
                seen[dedup_key] = vf
            else:
                existing = seen[dedup_key]
                if (has_audio and not existing.has_audio) or (filesize or 0) > (existing.filesize_bytes or 0):
                    seen[dedup_key] = vf

        video_list = list(seen.values())
        video_list.sort(key=lambda v: (-(v.height or 0), -(int(v.fps or 0)), -(v.filesize_bytes or 0)))

        # Solo sintetizar "Mejor calidad" si hay 2 o más resoluciones distintas para evitar duplicados
        distinct_heights = {v.height for v in video_list if v.height}
        if len(distinct_heights) >= 2:
            best = video_list[0]
            best_synthetic = VideoFormat(
                format_id="best_quality",
                extension=best.extension,
                resolution=best.resolution,
                width=best.width,
                height=best.height,
                fps=best.fps,
                video_codec=best.video_codec,
                has_audio=best.has_audio,
                needs_ffmpeg_merge=best.needs_ffmpeg_merge,
                audio_format_id=best.audio_format_id,
                filesize_bytes=best.filesize_bytes,
                is_best_quality=True
            )
            video_list.insert(0, best_synthetic)

        return video_list

    @classmethod
    def normalize_audio_formats(cls, raw_formats: List[Dict[str, Any]]) -> List[AudioFormat]:
        """Normaliza y deduplica únicamente las opciones de AUDIO (AUDIO_ONLY)."""
        audio_list: List[AudioFormat] = []
        seen_bitrates: set[int] = set()

        for f in raw_formats:
            if cls.is_auxiliary_format(f):
                continue

            acodec = f.get("acodec")
            vcodec = f.get("vcodec")
            if not acodec or acodec == "none" or (vcodec and vcodec != "none"):
                continue  # Solo flujos puramente audio

            fmt_id = str(f.get("format_id") or "")
            ext = str(f.get("ext") or "m4a")
            bitrate = float(f.get("tbr") or f.get("abr") or 0.0) if (f.get("tbr") or f.get("abr")) else None
            filesize = f.get("filesize") or f.get("filesize_approx")

            int_br = int(bitrate) if bitrate else 128
            if int_br in seen_bitrates:
                continue
            seen_bitrates.add(int_br)

            af = AudioFormat(
                format_id=fmt_id,
                extension=ext,
                bitrate_kbps=bitrate,
                audio_codec=str(acodec),
                filesize_bytes=filesize
            )
            audio_list.append(af)

        audio_list.sort(key=lambda a: (-(a.bitrate_kbps or 0.0), -(a.filesize_bytes or 0)))

        if not audio_list:
            audio_list.append(
                AudioFormat(
                    format_id="best_audio",
                    extension="m4a",
                    bitrate_kbps=128.0
                )
            )

        return audio_list

    @classmethod
    def normalize(cls, raw_formats: List[Dict[str, Any]]) -> List[FormatOption]:
        """Normaliza los formatos crudos y devuelve una lista unificada de FormatOption."""
        video_formats = cls.normalize_video_formats(raw_formats)
        audio_formats = cls.normalize_audio_formats(raw_formats)

        options: List[FormatOption] = []
        for vf in video_formats:
            options.append(FormatOption.from_video_format(vf))

        for af in audio_formats:
            options.append(FormatOption.from_audio_format(af))

        return options

    @classmethod
    def _find_best_audio_format_id(cls, raw_formats: List[Dict[str, Any]]) -> Optional[str]:
        best_id = None
        best_bitrate = -1.0

        for f in raw_formats:
            if cls.is_auxiliary_format(f):
                continue
            acodec = f.get("acodec")
            vcodec = f.get("vcodec")
            if acodec and acodec != "none" and (not vcodec or vcodec == "none"):
                bitrate = float(f.get("tbr") or f.get("abr") or 0.0)
                if bitrate > best_bitrate:
                    best_bitrate = bitrate
                    best_id = str(f.get("format_id") or "")
        return best_id
