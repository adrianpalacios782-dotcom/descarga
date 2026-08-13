import asyncio
import logging
import os
import re
import shutil
import subprocess
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CancelledOperationError(RuntimeError):
    """Se eleva cuando una operación FFmpeg es abortada por cancelación del usuario."""


class FFmpegProcessAdapter:
    """Adaptador de infraestructura que gestiona la detección y ejecución de FFmpeg como proceso Sidecar."""

    def __init__(self, custom_binary_path: Optional[str] = None) -> None:
        self.custom_binary_path = custom_binary_path
        self._cached_executable: Optional[str] = None
        self._cached_version: Optional[str] = None

    def get_ffmpeg_executable(self) -> str:
        """Determina la ruta del ejecutable FFmpeg (embebido local, binario pip o PATH del sistema)."""
        if self._cached_executable:
            return self._cached_executable

        candidates: List[str] = []
        if self.custom_binary_path:
            candidates.append(self.custom_binary_path)
        candidates.append(os.path.join(os.getcwd(), "bin", "ffmpeg.exe"))
        candidates.append(os.path.join(os.getcwd(), "bin", "ffmpeg"))

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                self._cached_executable = candidate
                return candidate

        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            self._cached_executable = system_ffmpeg
            return system_ffmpeg

        try:
            import imageio_ffmpeg
            bundled = imageio_ffmpeg.get_ffmpeg_exe()
            if bundled and os.path.exists(bundled):
                self._cached_executable = bundled
                return bundled
        except ImportError:
            logger.debug("imageio-ffmpeg no está instalado; se usará el comando 'ffmpeg' del sistema.")

        return "ffmpeg"

    def get_ffmpeg_version(self) -> str:
        """Retorna la versión de FFmpeg detectada o un mensaje de no disponible."""
        if self._cached_version:
            return self._cached_version

        exe = self.get_ffmpeg_executable()
        try:
            res = subprocess.run(
                [exe, "-version"],
                capture_output=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if res.returncode == 0:
                first_line = res.stdout.decode("utf-8", errors="replace").splitlines()
                self._cached_version = first_line[0].strip() if first_line else "FFmpeg (sin versión)"
                return self._cached_version
        except Exception as ex:
            logger.warning(f"No se pudo obtener la versión de FFmpeg: {ex}")

        return "No disponible"

    def check_ffmpeg_sync(self) -> Tuple[bool, str]:
        """Verifica disponibilidad, ruta y versión de FFmpeg de forma síncrona (hilo secundario)."""
        exe = self.get_ffmpeg_executable()
        version = self.get_ffmpeg_version()
        available = not version.startswith("No disponible")
        return available, f"{exe} — {version}"

    async def check_availability(self) -> bool:
        """Verifica de forma asíncrona si FFmpeg se encuentra instalado y ejecutable."""
        exe = self.get_ffmpeg_executable()
        try:
            process = await asyncio.create_subprocess_exec(
                exe, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            return process.returncode == 0 and b"ffmpeg version" in stdout.lower()
        except Exception as ex:
            logger.warning(f"FFmpeg no está disponible: {ex}")
            return False

    def check_availability_sync(self) -> Tuple[bool, str]:
        """Verifica de forma síncrona si FFmpeg está disponible, retornando (disponible, versión)."""
        return self.check_ffmpeg_sync()

    async def merge_video_audio(self, video_path: str, audio_path: str, output_path: str) -> None:
        """Combina video y audio intentando primero -c copy; si falla, reintenta con re-codificación."""
        exe = self.get_ffmpeg_executable()
        base_cmd = [exe, "-y", "-i", video_path, "-i", audio_path]

        copy_cmd = base_cmd + ["-c:v", "copy", "-c:a", "copy", output_path]
        try:
            await self._run_ffmpeg(copy_cmd, "merge (-c copy)")
        except RuntimeError:
            logger.info("El merge con -c copy no fue compatible; reintentando con re-codificación.")
            reencode_cmd = base_cmd + ["-c:v", "libx264", "-preset", "fast", "-c:a", "aac", output_path]
            await self._run_ffmpeg(reencode_cmd, "merge (re-codificación)")

    async def extract_audio(self, input_path: str, output_path: str, audio_format: str = "mp3", bitrate_kbps: int = 320) -> None:
        """Extrae y transcodifica la pista de audio a MP3 / WAV / M4A con la tasa de bits solicitada."""
        exe = self.get_ffmpeg_executable()
        codec_args = ["-vn"]

        if audio_format.lower() == "mp3":
            codec_args.extend(["-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])
        elif audio_format.lower() == "wav":
            codec_args.extend(["-c:a", "pcm_s16le"])
        elif audio_format.lower() == "m4a":
            codec_args.extend(["-c:a", "aac", "-b:a", f"{bitrate_kbps}k"])
        else:
            raise ValueError(f"Formato de audio no soportado: {audio_format}")

        cmd = [exe, "-y", "-i", input_path] + codec_args + [output_path]
        await self._run_ffmpeg(cmd, f"extracción de audio {audio_format}")

    @staticmethod
    async def _run_ffmpeg(cmd: List[str], operation: str) -> None:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"Error durante la {operation} con FFmpeg: {err_msg}")

    @staticmethod
    def cleanup_temp_files(*file_paths: str) -> None:
        """Elimina de forma segura archivos temporales o fragmentados (.part, .tmp, .fXXX)."""
        for path in file_paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"Archivo temporal eliminado: {path}")
            except Exception as ex:
                logger.warning(f"No se pudo eliminar el archivo temporal '{path}': {ex}")

    # ------------------------------------------------------------------ Sincrónico (hilos del motor)

    def probe_streams(self, file_path: str) -> Dict[str, object]:
        """Inspecciona un archivo multimedia con `ffmpeg -i` y extrae codecs, resolución y duración.

        Retorna un dict con las claves: format_name, duration_seconds, video, audio.
        video/audio: dict con codec, width, height, fps (solo aplicables a video).
        """
        exe = self.get_ffmpeg_executable()
        try:
            res = subprocess.run(
                [exe, "-hide_banner", "-i", file_path],
                capture_output=True,
                timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        except Exception as ex:
            logger.warning(f"No se pudo inspeccionar '{file_path}': {ex}")
            return {"format_name": "", "duration_seconds": None, "video": {}, "audio": {}, "error": str(ex)}

        text = (res.stderr or b"").decode("utf-8", errors="replace")
        return self.parse_probe_output(text)

    @staticmethod
    def parse_probe_output(text: str) -> Dict[str, object]:
        """Parsea la salida de `ffmpeg -i` (stderr) extrayendo contenedor, duración, video y audio."""
        # Unir líneas envueltas por ffmpeg (la resolución puede quedar en una línea continuada)
        joined: List[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith(("Stream #", "Duration:", "Input #")):
                joined.append(line)
            elif joined:
                joined[-1] += " " + line

        result: Dict[str, object] = {
            "format_name": "",
            "duration_seconds": None,
            "video": {},
            "audio": {},
        }

        for line in joined:
            if line.startswith("Input #"):
                m = re.search(r"Input #\d+, (.+?), from ", line)
                if m:
                    result["format_name"] = m.group(1).strip()
            elif line.startswith("Duration:"):
                m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
                if m:
                    h, mm, ss = m.groups()
                    result["duration_seconds"] = int(h) * 3600 + int(mm) * 60 + float(ss)
            elif "Video:" in line and not result["video"]:
                vm = re.search(r"Video:\s*(\S+)", line)
                rm = re.search(r"(\d{3,5})x(\d{3,5})", line)
                fm = re.search(r",\s*([\d.]+)\s*(?:fps|tb)", line)
                result["video"] = {
                    "codec": vm.group(1) if vm else "",
                    "width": int(rm.group(1)) if rm else None,
                    "height": int(rm.group(2)) if rm else None,
                    "fps": float(fm.group(1)) if fm else None,
                }
            elif "Audio:" in line and not result["audio"]:
                am = re.search(r"Audio:\s*([^,\s]+)", line)
                sm = re.search(r"(\d+)\s*Hz", line)
                result["audio"] = {
                    "codec": am.group(1) if am else "",
                    "sample_rate": int(sm.group(1)) if sm else None,
                }

        if not result["video"] and not result["audio"] and not result["format_name"]:
            result["error"] = "Archivo no legible o no es multimedia."

        return result

    def extract_audio_sync(
        self,
        input_path: str,
        output_path: str,
        audio_format: str = "mp3",
        bitrate_kbps: int = 320,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        """Extrae/transcodifica audio con FFmpeg en modo síncrono, matable mediante cancel_event.

        - mp3:  libmp3lame con -b:a <bitrate>k
        - m4a:  aac con -b:a <bitrate>k
        - wav:  pcm_s16le (sin compresión; se ignora bitrate)
        """
        exe = self.get_ffmpeg_executable()
        codec_args = ["-vn"]
        fmt = audio_format.lower()

        if fmt == "mp3":
            codec_args.extend(["-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])
        elif fmt == "m4a":
            codec_args.extend(["-c:a", "aac", "-b:a", f"{bitrate_kbps}k"])
        elif fmt == "wav":
            codec_args.extend(["-c:a", "pcm_s16le"])
        else:
            raise ValueError(f"Formato de audio no soportado: {audio_format}")

        cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", input_path] + codec_args + [output_path]

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=flags,
        )

        if cancel_event is not None:
            while proc.poll() is None:
                if cancel_event.is_set():
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise CancelledOperationError("Extracción de audio cancelada por el usuario.")
                cancel_event.wait(0.2)

        _, stderr = proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")[-1500:]
            raise RuntimeError(f"Error al extraer audio {fmt} con FFmpeg: {err_msg}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError(f"La extracción de audio no produjo un archivo válido: {output_path}")

    def merge_video_audio_sync(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        """Combina video+audio con `-c copy` (remux sin re-codificación); si el contenedor no lo permite, re-codifica."""
        exe = self.get_ffmpeg_executable()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        def _run(cmd: List[str]) -> None:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
            if cancel_event is not None:
                while proc.poll() is None:
                    if cancel_event.is_set():
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        raise CancelledOperationError("Merge cancelado por el usuario.")
                    cancel_event.wait(0.2)
            _, stderr = proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace")[-1500:]
                raise RuntimeError(f"Error al fusionar con FFmpeg: {err}")

        copy_cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", video_path, "-i", audio_path,
                    "-c:v", "copy", "-c:a", "copy", output_path]
        try:
            _run(copy_cmd)
        except RuntimeError:
            logger.info("El merge con -c copy no fue compatible; re-codificando a H.264/AAC.")
            reencode_cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", video_path, "-i", audio_path,
                            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", output_path]
            _run(reencode_cmd)
