from enum import Enum
from typing import Optional


class AudioPreset(str, Enum):
    """Presets de conversión de audio con especificación de códec, bitrate y contenedor."""

    MP3_320K = "mp3_320k"
    MP3_192K = "mp3_192k"
    M4A_AAC = "m4a_aac"
    FLAC = "flac"
    WAV = "wav"
    OPUS = "opus"

    @property
    def display_name(self) -> str:
        names = {
            AudioPreset.MP3_320K: "MP3 - Alta Calidad (320 kbps)",
            AudioPreset.MP3_192K: "MP3 - Estándar (192 kbps)",
            AudioPreset.M4A_AAC: "M4A / AAC - Balanceado",
            AudioPreset.FLAC: "FLAC - Lossless (Sin Pérdida)",
            AudioPreset.WAV: "WAV - Audio Puro (PCM)",
            AudioPreset.OPUS: "OPUS - Ultra Eficiente",
        }
        return names.get(self, self.value)

    @property
    def extension(self) -> str:
        exts = {
            AudioPreset.MP3_320K: "mp3",
            AudioPreset.MP3_192K: "mp3",
            AudioPreset.M4A_AAC: "m4a",
            AudioPreset.FLAC: "flac",
            AudioPreset.WAV: "wav",
            AudioPreset.OPUS: "opus",
        }
        return exts.get(self, "mp3")

    @property
    def ffmpeg_codec(self) -> str:
        codecs = {
            AudioPreset.MP3_320K: "libmp3lame",
            AudioPreset.MP3_192K: "libmp3lame",
            AudioPreset.M4A_AAC: "aac",
            AudioPreset.FLAC: "flac",
            AudioPreset.WAV: "pcm_s16le",
            AudioPreset.OPUS: "libopus",
        }
        return codecs.get(self, "libmp3lame")

    @property
    def bitrate(self) -> Optional[str]:
        bitrates = {
            AudioPreset.MP3_320K: "320k",
            AudioPreset.MP3_192K: "192k",
            AudioPreset.M4A_AAC: "256k",
            AudioPreset.OPUS: "160k",
        }
        return bitrates.get(self, None)

    @classmethod
    def from_string(cls, val: str) -> "AudioPreset":
        for member in cls:
            if member.value == val.lower() or member.name == val.upper():
                return member
        return cls.MP3_320K
