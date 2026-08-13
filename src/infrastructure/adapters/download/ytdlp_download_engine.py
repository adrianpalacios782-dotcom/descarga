import logging
import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import yt_dlp
from yt_dlp.utils import DownloadCancelled

from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import DownloadType
from src.domain.events.domain_events import (
    DownloadProgressChangedEvent,
    DownloadCompletedEvent,
    DownloadFailedEvent,
    DownloadPausedEvent,
    DownloadResumedEvent,
    DownloadCancelledEvent,
)
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.ports.download_repository import IDownloadRepository
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter, CancelledOperationError
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus

logger = logging.getLogger(__name__)


class YtDlpDownloadEngine(IDownloadEngine):
    """Motor de descargas real basado en yt-dlp como librería.

    Comportamiento:
    - Pre-probea las estrategias de cliente y elige la que ofrece más resoluciones antes de descargar.
    - Selección dinámica de formatos (bestvideo<=N + bestaudio), prefiriendo H.264+AAC en MP4
      para máxima compatibilidad; si no hay H.264, usa AV1 con audio AAC (combinación válida en MP4).
    - El audio (MP3/M4A/WAV) se extrae con FFmpeg propio, matable ante cancelación.
    - Verifica el archivo final con `ffmpeg -i` (resolución/códecs reales) y registra de forma
      transparente la resolución SOLICITADA vs la FINALMENTE descargada.
    - Persiste COMPLETED/FAILED/CANCELLED en el historial y publica eventos por el EventBus.
    """

    CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        None,
        ["web", "android", "mweb"],
        ["android_vr", "tv"],
    ]

    def __init__(
        self,
        event_bus: Optional[InProcessEventBus] = None,
        ffmpeg_adapter: Optional[FFmpegProcessAdapter] = None,
        repository: Optional[IDownloadRepository] = None,
        ydl_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.event_bus = event_bus
        self.ffmpeg_adapter = ffmpeg_adapter or FFmpegProcessAdapter()
        self.repository = repository
        self._ydl_factory = ydl_factory or yt_dlp.YoutubeDL

        self._cancel_tokens: Dict[str, threading.Event] = {}
        self._pause_tokens: Dict[str, threading.Event] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ API pública

    def download(self, task: DownloadTask) -> None:
        task_id = task.id.value
        cancel_token = threading.Event()
        pause_token = threading.Event()
        with self._lock:
            self._cancel_tokens[task_id] = cancel_token
            self._pause_tokens[task_id] = pause_token

        thread = threading.Thread(target=self._run, args=(task, cancel_token, pause_token), daemon=True)
        with self._lock:
            self._threads[task_id] = thread
        thread.start()

    def pause(self, task: DownloadTask) -> None:
        """Pausa cooperativa: yt-dlp 2026 ya no expone pause()/resume().

        La pausa se implementa bloqueando el progress_hook, de modo que el bucle de escritura
        de yt-dlp queda detenido (la conexión se mantiene). Aplica durante la transferencia;
        durante el postprocesado FFmpeg (breve) la pausa se aplica al terminar la etapa.
        """
        task_id = task.id.value
        if task_id in self._pause_tokens:
            self._pause_tokens[task_id].set()
        if self.event_bus:
            self.event_bus.publish(DownloadPausedEvent(task_id=task_id))

    def resume(self, task: DownloadTask) -> None:
        task_id = task.id.value
        if task_id in self._pause_tokens:
            self._pause_tokens[task_id].clear()
        if self.event_bus:
            self.event_bus.publish(DownloadResumedEvent(task_id=task_id))

    def cancel(self, task: DownloadTask) -> None:
        """Cancela la tarea: señaliza el hook (aborta la transferencia) y mata FFmpeg si está activo."""
        task_id = task.id.value
        if task_id in self._cancel_tokens:
            self._cancel_tokens[task_id].set()
        if self.event_bus:
            self.event_bus.publish(DownloadCancelledEvent(task_id=task_id))

    # ------------------------------------------------------------------ Ciclo interno

    def _run(self, task: DownloadTask, cancel_token: threading.Event, pause_token: threading.Event) -> None:
        task_id = task.id.value
        try:
            self._do_download(task, cancel_token, pause_token)
        except (DownloadCancelled, CancelledOperationError) as ex:
            logger.info(f"Descarga {task_id} cancelada por el usuario: {ex}")
            self._cleanup_task_files(task.destination_path)
            try:
                task.transition_to(DownloadState.CANCELLED)
            except Exception:
                task.status = DownloadState.CANCELLED
            self._save(task)
        except Exception as ex:
            logger.error(f"Error durante la descarga de la tarea {task_id}: {ex}", exc_info=True)
            self._cleanup_task_files(task.destination_path)
            try:
                task.fail(str(ex))
            except Exception:
                task.status = DownloadState.FAILED
                task.error_message = str(ex)
            self._save(task)
            if self.event_bus:
                self.event_bus.publish(DownloadFailedEvent(task_id=task_id, error_message=str(ex)))
        finally:
            with self._lock:
                self._cancel_tokens.pop(task_id, None)
                self._pause_tokens.pop(task_id, None)
                self._threads.pop(task_id, None)

    def _do_download(self, task: DownloadTask, cancel_token: threading.Event, pause_token: threading.Event) -> None:
        fmt = task.selected_format
        dest_dir, base, _ = self._split_destination(task.destination_path)
        os.makedirs(dest_dir, exist_ok=True)

        is_audio = fmt.is_audio_only or fmt.download_type == DownloadType.AUDIO

        # Elegir la estrategia de cliente con la mayor disponibilidad de formatos para esta URL
        probed = self._probe_best_strategy(task, cancel_token)

        strategies: List[Optional[List[str]]] = [probed]
        for strategy in self.CLIENT_STRATEGIES:
            if strategy not in strategies:
                strategies.append(strategy)

        last_error: Optional[Exception] = None
        for strategy in strategies:
            if cancel_token.is_set():
                raise DownloadCancelled("Descarga cancelada por el usuario.")
            try:
                if is_audio:
                    self._download_audio(task, strategy, dest_dir, base, cancel_token, pause_token)
                else:
                    self._download_video(task, strategy, dest_dir, base, cancel_token, pause_token)
                return
            except (DownloadCancelled,):
                raise
            except Exception as ex:
                last_error = ex
                logger.warning(f"Intento de descarga fallido (clientes={strategy}): {ex}")
                self._cleanup_task_files(task.destination_path)
                time.sleep(1)

        if last_error is not None:
            raise last_error

    # ------------------------------------------------------------------ Pre-probe de disponibilidad

    def _probe_best_strategy(self, task: DownloadTask, cancel_token: threading.Event) -> Optional[List[str]]:
        """Elige la estrategia de cliente que ofrece la mayor resolución de video disponible.

        Reanaliza los formatos antes de descargar (objetivo: que 'Mejor calidad' no caiga
        silenciosamente a una resolución menor por rate-limit).
        """
        url = task.media.url.value
        requested_height = task.selected_format.height or 0

        best_strategy: Optional[List[str]] = None
        best_score: Tuple[int, int] = (-1, -1)

        for clients in self.CLIENT_STRATEGIES:
            if cancel_token.is_set():
                raise DownloadCancelled("Descarga cancelada por el usuario.")
            try:
                max_height, num_formats = self._probe_formats(url, clients)
            except Exception as ex:
                logger.info(f"Probe fallido (clientes={clients}): {ex}")
                continue

            logger.info(
                f"Probe de clientes={clients}: max_height={max_height} formatos={num_formats} "
                f"(solicitado={requested_height or 'Mejor calidad'})"
            )
            score = (max_height, num_formats)
            if score > best_score:
                best_score = score
                best_strategy = clients

            if max_height >= requested_height:
                break

        return best_strategy

    def _probe_formats(self, url: str, clients: Optional[List[str]]) -> Tuple[int, int]:
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "simulate": True,
            "skip_download": True,
        }
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}

        ydl = self._ydl_factory(opts)
        try:
            info = ydl.extract_info(url, download=False)
        finally:
            try:
                ydl.close()
            except Exception:
                pass

        max_height = 0
        count = 0
        for f in info.get("formats") or []:
            vcodec = f.get("vcodec") or "none"
            height = f.get("height") or 0
            if vcodec != "none" and height:
                count += 1
                if height > max_height:
                    max_height = height
        return max_height, count

    # ------------------------------------------------------------------ Descarga de AUDIO (FFmpeg propio)

    def _download_audio(
        self,
        task: DownloadTask,
        strategy: Optional[List[str]],
        dest_dir: str,
        base: str,
        cancel_token: threading.Event,
        pause_token: threading.Event,
    ) -> None:
        fmt = task.selected_format
        target_fmt = (fmt.target_audio_format or "mp3").lower()
        bitrate = fmt.target_audio_bitrate or 192

        # 1. Descargar la mejor pista de audio cruda (sin postprocesado)
        source_tmpl = os.path.join(dest_dir, base + ".audio_src.%(ext)s")
        opts = self._build_base_opts(strategy, source_tmpl, task.id.value, cancel_token, pause_token)
        opts["format"] = "bestaudio/best"

        ydl = self._ydl_factory(opts)
        try:
            info = ydl.extract_info(task.media.url.value, download=True)
        finally:
            try:
                ydl.close()
            except Exception:
                pass

        source_path = self._resolve_final_path(info, dest_dir, base + ".audio_src")
        if not source_path or not os.path.exists(source_path):
            raise RuntimeError("No se pudo obtener la pista de audio fuente de yt-dlp.")
        if os.path.getsize(source_path) <= 0:
            raise RuntimeError("La pista de audio fuente se descargó vacía (0 bytes).")

        # 2. Extraer/transcodificar con FFmpeg propio (matable en cancelación)
        self.ffmpeg_adapter.extract_audio_sync(
            input_path=source_path,
            output_path=task.destination_path,
            audio_format=target_fmt,
            bitrate_kbps=bitrate,
            cancel_event=cancel_token,
        )

        # 3. Limpiar fuente y restos
        self._cleanup_file(source_path)
        self._cleanup_file(source_path + ".part")
        self._cleanup_task_files(task.destination_path)

        probe = self.ffmpeg_adapter.probe_streams(task.destination_path)
        size = os.path.getsize(task.destination_path)
        logger.info(
            f"AUDIO {target_fmt}@{bitrate}k completado: {size} bytes, "
            f"codec={probe.get('audio', {}).get('codec')}, duración={probe.get('duration_seconds')}"
        )

        task.downloaded_bytes = size
        task.total_bytes = size
        task.progress_percent = 100.0
        task.complete()
        self._save(task)

        if self.event_bus:
            self.event_bus.publish(
                DownloadCompletedEvent(
                    task_id=task.id.value,
                    destination_path=task.destination_path,
                    total_bytes=size,
                )
            )

    # ------------------------------------------------------------------ Descarga de VIDEO (merge interno)

    def _download_video(
        self,
        task: DownloadTask,
        strategy: Optional[List[str]],
        dest_dir: str,
        base: str,
        cancel_token: threading.Event,
        pause_token: threading.Event,
    ) -> None:
        fmt = task.selected_format
        opts = self._build_base_opts(strategy, os.path.join(dest_dir, base + ".%(ext)s"), task.id.value, cancel_token, pause_token)
        opts["format"] = self._build_video_format_spec(fmt)
        opts["merge_output_format"] = "mp4"

        ydl = self._ydl_factory(opts)
        try:
            info = ydl.extract_info(task.media.url.value, download=True)
        finally:
            try:
                ydl.close()
            except Exception:
                pass

        final_path = self._resolve_final_path(info, dest_dir, base)
        if not final_path or not os.path.exists(final_path):
            raise RuntimeError("El archivo de video final no fue generado por yt-dlp.")
        if os.path.getsize(final_path) <= 0:
            raise RuntimeError("El archivo de video final se generó vacío (0 bytes).")

        final_path = self._canonicalize_final_path(final_path, task)
        self._cleanup_task_files(task.destination_path)

        size = os.path.getsize(final_path)
        probe = self.ffmpeg_adapter.probe_streams(final_path)
        actual_height = (probe.get("video") or {}).get("height")
        video_codec = (probe.get("video") or {}).get("codec")
        audio_codec = (probe.get("audio") or {}).get("codec")

        # Registro HONESTO de la resolución solicitada vs la finalmente descargada
        requested_label = f"{fmt.height}p" if fmt.height else "Mejor calidad"
        actual_label = f"{actual_height}p" if actual_height else "desconocida"
        if fmt.is_best_quality and actual_height and actual_height < (fmt.height or 0):
            logger.warning(
                f"DEGRADACIÓN DE CALIDAD: 'Mejor calidad' solicitó hasta {requested_label} "
                f"pero YouTube solo permitió {actual_label} ({video_codec})."
            )
        elif actual_height and fmt.height and actual_height < fmt.height:
            logger.warning(
                f"DEGRADACIÓN DE CALIDAD: se solicitó {requested_label} y YouTube entregó {actual_label}."
            )
        logger.info(
            f"VIDEO solicitado={requested_label} final={actual_label} "
            f"video={video_codec} audio={audio_codec} contenedor={os.path.splitext(final_path)[1]} tamaño={size}"
        )

        task.downloaded_bytes = size
        task.total_bytes = size
        task.progress_percent = 100.0
        task.complete()
        self._save(task)

        if self.event_bus:
            self.event_bus.publish(
                DownloadCompletedEvent(
                    task_id=task.id.value,
                    destination_path=task.destination_path,
                    total_bytes=size,
                )
            )

    @staticmethod
    def _build_video_format_spec(fmt) -> str:
        """Construye la especificación de formato priorizando H.264+AAC (MP4 compatible).

        - 1ª opción: video H.264 + audio AAC (remux limpio a MP4 con -c copy).
        - 2ª opción: mejor video (AV1/VP9) + audio AAC (AV1 sí es válido en MP4).
        - 3ª opción: cualquier combinación (respaldo, yt-dlp fusiona a MP4).
        """
        if fmt.is_best_quality:
            return (
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                "/bestvideo+bestaudio[acodec^=mp4a]"
                "/bestvideo+bestaudio/best"
            )
        if fmt.height:
            h = fmt.height
            return (
                f"bestvideo[height<=?{h}][vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[height<=?{h}]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[height<=?{h}]+bestaudio/best"
            )
        return "bestvideo+bestaudio/best"

    def _build_base_opts(
        self,
        clients: Optional[List[str]],
        outtmpl: str,
        task_id: str,
        cancel_token: threading.Event,
        pause_token: threading.Event,
    ) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "windowsfilenames": True,
            "noprogress": True,
            "retries": 5,
            "fragment_retries": 5,
            "file_access_retries": 5,
            "outtmpl": outtmpl,
            "ffmpeg_location": self.ffmpeg_adapter.get_ffmpeg_executable(),
            "progress_hooks": [self._make_progress_hook(task_id, cancel_token, pause_token)],
        }
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}
        return opts

    def _make_progress_hook(
        self, task_id: str, cancel: threading.Event, pause: threading.Event
    ) -> Callable[[Dict[str, Any]], None]:
        def hook(d: Dict[str, Any]) -> None:
            if cancel.is_set():
                raise DownloadCancelled("Descarga cancelada por el usuario.")

            while pause.is_set():
                if cancel.is_set():
                    raise DownloadCancelled("Descarga cancelada por el usuario.")
                time.sleep(0.2)

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0.0
                eta = d.get("eta") or 0
                if self.event_bus:
                    self.event_bus.publish(
                        DownloadProgressChangedEvent(
                            task_id=task_id,
                            progress_percent=(downloaded / total * 100.0) if total else 0.0,
                            downloaded_bytes=downloaded,
                            total_bytes=total,
                            speed_bps=speed,
                            eta_seconds=eta,
                        )
                    )

        return hook

    # ------------------------------------------------------------------ Finalización / utilidades

    def _resolve_final_path(self, info: Dict[str, Any], dest_dir: str, base: str) -> Optional[str]:
        requested = info.get("requested_downloads") or []
        if requested:
            filepath = requested[0].get("filepath")
            if filepath and os.path.exists(filepath):
                return filepath
            if filepath and os.path.exists(filepath.replace(".part", "")):
                return filepath.replace(".part", "")

        if os.path.isdir(dest_dir):
            candidates = [
                os.path.join(dest_dir, entry)
                for entry in os.listdir(dest_dir)
                if entry.startswith(base) and not entry.endswith(".part") and not entry.endswith(".tmp")
            ]
            candidates = [c for c in candidates if os.path.isfile(c)]
            if candidates:
                candidates.sort(key=lambda p: os.path.getsize(p), reverse=True)
                return candidates[0]
        return None

    def _canonicalize_final_path(self, final_path: str, task: DownloadTask) -> str:
        dest = task.destination_path
        if os.path.abspath(final_path) == os.path.abspath(dest):
            return dest

        _, _, desired_ext = self._split_destination(dest)
        _, _, actual_ext = os.path.splitext(final_path)
        if actual_ext.lower() != desired_ext.lower():
            dest = os.path.splitext(dest)[0] + actual_ext

        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        if os.path.exists(dest):
            os.remove(dest)
        os.replace(final_path, dest)
        task.destination_path = dest
        return dest

    @staticmethod
    def _split_destination(destination_path: str) -> tuple[str, str, str]:
        abs_path = os.path.abspath(destination_path)
        dest_dir = os.path.dirname(abs_path)
        basename = os.path.basename(abs_path)
        base, ext = os.path.splitext(basename)
        base = YtDlpDownloadEngine._sanitize_filename(base) or "descarga"
        return dest_dir, base, ext

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        cleaned = cleaned.strip().rstrip(".")
        return cleaned[:180]

    def _cleanup_task_files(self, destination_path: str) -> None:
        try:
            dest_dir, base, _ = self._split_destination(destination_path)
            if not os.path.isdir(dest_dir):
                return
            for entry in os.listdir(dest_dir):
                if entry.startswith(base) and (
                    entry.endswith(".part") or entry.endswith(".tmp") or re.search(r"\.f\d+\.", entry)
                ):
                    self._cleanup_file(os.path.join(dest_dir, entry))
        except Exception as ex:
            logger.warning(f"Error al limpiar archivos temporales: {ex}")

    @staticmethod
    def _cleanup_file(path: str) -> None:
        for attempt in range(3):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"Archivo temporal eliminado: {path}")
                return
            except OSError as ex:
                # Puede haber una ventana de lock transitorio (Windows) al abortar yt-dlp.
                time.sleep(0.15 * (attempt + 1))
                if attempt == 2:
                    logger.warning(f"No se pudo eliminar '{path}': {ex}")

    def _save(self, task: DownloadTask) -> None:
        if self.repository is not None:
            try:
                self.repository.save(task)
            except Exception as ex:
                logger.error(f"No se pudo persistir la tarea {task.id.value}: {ex}")
