import logging
import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import yt_dlp
from yt_dlp.utils import DownloadCancelled

from src.domain.entities.download_task import DownloadTask, DownloadState
from src.domain.entities.format_option import DownloadType
from src.domain.exceptions.domain_exceptions import (
    FormatNotFoundError,
    QualityDegradationError,
)
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
from src.domain.services.format_normalizer import FormatNormalizer
from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter, CancelledOperationError
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus

logger = logging.getLogger(__name__)

_SAFE_FORMAT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class YtDlpDownloadEngine(IDownloadEngine):
    """Motor de descargas real basado en yt-dlp como librería."""

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

    # Estrategias de player_client para yt-dlp (extractores que las soportan, p. ej.
    # YouTube). Cuando la plataforma restringe el cliente por defecto ("Sign in to
    # confirm you're not a bot"), se alterna el cliente entre reintentos igual que
    # hace el análisis (base_platform_adapter.CLIENT_STRATEGIES).
    DOWNLOAD_CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        None,        # defaults de yt-dlp
        ["tv"],
        ["android"],
    ]

    PROBE_CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        None,
        ["tv"],
        ["android"],
        ["web"],
        ["mweb"],
    ]

    @staticmethod
    def _apply_clients(opts: Dict[str, Any], clients: Optional[List[str]]) -> Dict[str, Any]:
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": list(clients)}}
        return opts

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
        task_id = task.id.value
        if task_id in self._cancel_tokens:
            self._cancel_tokens[task_id].set()
        if self.event_bus:
            self.event_bus.publish(DownloadCancelledEvent(task_id=task_id))

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

        self._validate_destination_path(task.destination_path)

        is_audio = fmt.is_audio_only or fmt.download_type == DownloadType.AUDIO

        if is_audio:
            self._download_audio(task, dest_dir, base, cancel_token, pause_token)
        else:
            self._download_video(task, dest_dir, base, cancel_token, pause_token)

    def _download_audio(
        self,
        task: DownloadTask,
        dest_dir: str,
        base: str,
        cancel_token: threading.Event,
        pause_token: threading.Event,
    ) -> None:
        fmt = task.selected_format
        target_fmt = (fmt.target_audio_format or "mp3").lower()
        bitrate = fmt.target_audio_bitrate or 192

        source_tmpl = os.path.join(dest_dir, base + ".audio_src.%(ext)s")
        opts = self._build_base_opts(source_tmpl, task.id.value, cancel_token, pause_token)
        opts["format"] = "bestaudio/best"

        info = None
        last_error = None
        for clients in self.DOWNLOAD_CLIENT_STRATEGIES:
            attempt_opts = self._apply_clients(dict(opts), clients)
            ydl = self._ydl_factory(attempt_opts)
            try:
                info = ydl.extract_info(task.media.url.value, download=True)
                break
            except Exception as ex:
                last_error = ex
                logger.warning(f"Descarga de audio falló con clientes {clients or 'default'}: {ex}")
            finally:
                try:
                    ydl.close()
                except Exception:
                    pass
        if info is None:
            raise last_error or RuntimeError("La descarga de audio falló tras agotar las estrategias de cliente.")

        source_path = self._resolve_final_path(info, dest_dir, base + ".audio_src")
        if not source_path or not os.path.exists(source_path):
            raise RuntimeError("No se pudo obtener la pista de audio fuente de yt-dlp.")
        if os.path.getsize(source_path) <= 0:
            raise RuntimeError("La pista de audio fuente se descargó vacía (0 bytes).")

        self.ffmpeg_adapter.extract_audio_sync(
            input_path=source_path,
            output_path=task.destination_path,
            audio_format=target_fmt,
            bitrate_kbps=bitrate,
            cancel_event=cancel_token,
        )

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

    def _download_video(
        self,
        task: DownloadTask,
        dest_dir: str,
        base: str,
        cancel_token: threading.Event,
        pause_token: threading.Event,
    ) -> None:
        fmt = task.selected_format
        url = task.media.url.value
        requested_height = fmt.height or 0
        requested_label = f"{requested_height}p" if requested_height else "Mejor calidad"

        # ── Fase 1: Sondear formatos disponibles (sin descargar) ──
        available_heights: List[int] = []
        try:
            probe_info = self._probe_available_formats(url, cancel_token)
            available_heights = self._extract_available_video_heights(probe_info)
        except Exception as ex:
            logger.warning(
                f"No se pudieron sondear formatos del servidor ({ex}). "
                f"Se continuará con la descarga directa."
            )

        # ── Fase 2: Validar que la resolución solicitada existe ──
        if requested_height and not fmt.is_best_quality and available_heights:
            self._validate_format_availability(requested_height, available_heights)

        if available_heights:
            logger.info(
                f"Solicitado={requested_label} | "
                f"Formatos disponibles en servidor: {', '.join(str(h)+'p' for h in available_heights)}"
            )
        else:
            logger.info(f"Solicitado={requested_label} | (sin sondeo previo)")

        # ── Fase 3: Descargar ──
        opts = self._build_base_opts(
            os.path.join(dest_dir, base + ".%(ext)s"),
            task.id.value, cancel_token, pause_token,
        )
        opts["format"] = self._build_video_format_spec(fmt)
        opts["merge_output_format"] = "mp4"
        opts["allow_multi_streams"] = True

        info = None
        last_dl_error = None
        for attempt in range(3):
            if attempt > 0:
                delay = [3.0, 8.0][attempt - 1]
                logger.info(f"Reintento de descarga {attempt + 1}/3 tras {delay}s")
                time.sleep(delay)
            attempt_opts = self._apply_clients(
                dict(opts),
                self.DOWNLOAD_CLIENT_STRATEGIES[attempt % len(self.DOWNLOAD_CLIENT_STRATEGIES)],
            )
            clients_used = (attempt_opts.get("extractor_args") or {}).get("youtube", {}).get("player_client")
            if clients_used:
                logger.info(f"Intento {attempt + 1}/3 con player_client={clients_used}")
            ydl = self._ydl_factory(attempt_opts)
            try:
                info = ydl.extract_info(url, download=True)
                break
            except Exception as ex:
                last_dl_error = ex
                logger.warning(f"Intento de descarga {attempt + 1} falló: {ex}")
            finally:
                try:
                    ydl.close()
                except Exception:
                    pass

        if info is None:
            raise last_dl_error or RuntimeError("La descarga falló tras 3 intentos.")

        # ── Fase 4: Resolver y renombrar archivo final ──
        final_path = self._resolve_final_path(info, dest_dir, base)
        if not final_path or not os.path.exists(final_path):
            raise RuntimeError("El archivo de video final no fue generado por yt-dlp.")
        if os.path.getsize(final_path) <= 0:
            raise RuntimeError("El archivo de video final se generó vacío (0 bytes).")

        final_path = self._canonicalize_final_path(final_path, task)
        self._cleanup_task_files(task.destination_path)

        # ── Fase 5: Validar calidad descargada ──
        size = os.path.getsize(final_path)
        probe = self.ffmpeg_adapter.probe_streams(final_path)
        actual_height = (probe.get("video") or {}).get("height")
        video_codec = (probe.get("video") or {}).get("codec")
        audio_codec = (probe.get("audio") or {}).get("codec")
        actual_fps = (probe.get("video") or {}).get("fps")

        actual_label = f"{actual_height}p" if actual_height else "desconocida"
        if actual_fps:
            actual_label += f"@{int(actual_fps)}fps"

        if requested_height and actual_height and not fmt.is_best_quality:
            if getattr(fmt, "height_estimated", False):
                # Altura inferida por etiqueta (ej. Facebook 'sd'/'hd'): la plataforma
                # no garantiza pixeles exactos, se informa sin invalidar la descarga.
                logger.info(
                    f"Calidad aproximada: se solicitó {requested_label} (estimada) y el "
                    f"archivo resultante tiene {actual_label}."
                )
            else:
                # La validación de calidad se mantiene: si hay degradación real se
                # registra como advertencia visible en la tarea completada. La
                # descarga NO se marca como Error: el archivo terminó correctamente,
                # solo que con calidad inferior a la solicitada.
                try:
                    self._validate_downloaded_quality(actual_height, requested_height, requested_label, actual_label)
                except QualityDegradationError as ex:
                    task.quality_warning = str(ex)
                    logger.warning(f"Descarga {task.id.value} completada con {task.quality_warning}")

        if fmt.is_best_quality and actual_height and actual_height < (fmt.height or 0):
            logger.warning(
                f"DEGRADACIÓN DE CALIDAD: 'Mejor calidad' solicitó hasta {requested_label} "
                f"pero la plataforma solo permitió {actual_label} ({video_codec})."
            )

        logger.info(
            f"VIDEO solicitado={requested_label} final={actual_label} "
            f"video={video_codec} audio={audio_codec} contenedor={os.path.splitext(final_path)[1]} tamaño={size}"
        )

        # ── Fase 6: Completar tarea ──
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
                    warning_message=task.quality_warning or "",
                )
            )

    @staticmethod
    def _sanitize_format_id(raw: str) -> str:
        """Sanitiza un format_id para evitar inyección en el spec de yt-dlp.

        Solo permite caracteres alfanuméricos, guiones y guiones bajos.
        Si el format_id contiene caracteres peligrosos, retorna cadena vacía.
        """
        if not raw or not _SAFE_FORMAT_ID_RE.match(raw):
            return ""
        return raw

    @staticmethod
    def _validate_destination_path(destination_path: str) -> None:
        """Valida que la ruta de destino no contenga traversal peligroso.

        Verifica que la ruta resuelta no escape de directorios del sistema.
        """
        abs_path = os.path.abspath(destination_path)
        if os.name == "nt":
            lower = abs_path.lower().replace("\\", "/")
            blocked = (
                "/windows/", "/windows/system32/", "/program files/",
                "/programdata/", "/$recycle.bin/",
            )
            for b in blocked:
                if lower.startswith(b) or b in lower:
                    raise RuntimeError(
                        f"La ruta de destino '{destination_path}' apunta a una ubicación del sistema."
                    )

    @staticmethod
    def _build_video_format_spec(fmt) -> str:
        """Construye la especificación de formato para yt-dlp.

        Utiliza el format_id real identificado por el normalizer como selector primario,
        con fallback a selección por altura cuando el format_id no está disponible o es
        sintético (ej. "best_quality").

        Cadena de fallback:
        1. format_id específico + mejor audio compatible (si format_id es numérico real)
        2. bestvideo con altura EXACTA solicitada (H.264+AAC, luego cualquier codec)
        3. bestvideo con altura <= solicitada (H.264+AAC, luego cualquier codec)
        4. bestvideo + bestaudio (sin límite de altura)
        5. best (último recurso)

        IMPORTANTE: los selectores de altura EXACTA van ANTES que los de rango
        `height<=h` para garantizar que, si la resolución solicitada existe en el
        servidor, se descargue exactamente esa. El rango `<=h` solo actúa cuando la
        resolución exacta no está disponible; la validación final reportará entonces
        la degradación real sin ocultarla.
        """
        if fmt.is_best_quality or fmt.format_id == "best_quality":
            return (
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                "/bestvideo+bestaudio[acodec^=mp4a]"
                "/bestvideo+bestaudio/best"
            )

        is_raw_id = fmt.format_id and fmt.format_id.isdigit()
        safe_id = YtDlpDownloadEngine._sanitize_format_id(fmt.format_id) if fmt.format_id else ""

        if fmt.height and fmt.height > 0:
            h = fmt.height
            exact = (
                f"bestvideo[height={h}][vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[height={h}]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[height={h}]+bestaudio"
            )
            capped = (
                f"bestvideo[height<={h}][vcodec^=avc1]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[height<={h}]+bestaudio[acodec^=mp4a]"
                f"/bestvideo[height<={h}]+bestaudio"
            )
            if is_raw_id and safe_id:
                return (
                    f"{safe_id}+bestaudio[acodec^=mp4a]"
                    f"/{safe_id}+bestaudio"
                    f"/{exact}"
                    f"/{capped}"
                    f"/bestvideo+bestaudio"
                    f"/best"
                )
            if safe_id and not fmt.is_video_only:
                # Formato progresivo con ID alfanumerico (ej. Facebook 'hd'/'sd'):
                # ya incluye audio, se selecciona directamente sin combinaciones de merge.
                return (
                    f"{safe_id}"
                    f"/{exact}"
                    f"/{capped}"
                    f"/best"
                )
            return f"{exact}/{capped}/bestvideo+bestaudio/best"

        if is_raw_id and safe_id:
            return f"{safe_id}/bestvideo+bestaudio/best"

        if safe_id and not fmt.is_video_only:
            return f"{safe_id}/bestvideo+bestaudio/best"

        return "bestvideo+bestaudio/best"

    def _probe_available_formats(self, url: str, cancel_token: threading.Event) -> Dict[str, Any]:
        """Sondea los formatos disponibles en el servidor sin descargar.

        Recorre las mismas estrategias de player_client que el análisis y acepta
        la primera respuesta con formatos de medios reales (no solo storyboards),
        de modo que la pre-validación también funciona cuando la plataforma
        restringe el cliente por defecto.
        """
        if cancel_token.is_set():
            raise DownloadCancelled("Descarga cancelada por el usuario.")

        base_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "skip_download": True,
            "noplaylist": True,
            "format": "all",
            "socket_timeout": 30,
        }
        first_error: Optional[Exception] = None
        for clients in self.PROBE_CLIENT_STRATEGIES:
            ydl = self._ydl_factory(self._apply_clients(dict(base_opts), clients))
            try:
                info = ydl.extract_info(url, download=False)
                formats = (info or {}).get("formats") or []
                if any(not FormatNormalizer.is_auxiliary_format(f) for f in formats):
                    return info or {}
                if first_error is None:
                    first_error = RuntimeError(
                        f"el servidor no entregó formatos de medios reales con clientes {clients or 'default'}"
                    )
            except Exception as ex:
                if first_error is None:
                    first_error = ex
            finally:
                try:
                    ydl.close()
                except Exception:
                    pass
        raise first_error or RuntimeError("No se pudieron sondear los formatos del servidor.")

    @staticmethod
    def _extract_available_video_heights(info: Dict[str, Any]) -> List[int]:
        """Extrae todas las alturas de video disponibles de la información sondeada.

        Devuelve alturas estándar (1080, 720, 480, etc.) ordenadas descendente.
        """
        formats = info.get("formats") or []
        heights: set = set()
        for f in formats:
            vcodec = f.get("vcodec")
            if vcodec and str(vcodec).lower() == "none":
                continue
            std_h = FormatNormalizer.infer_standard_height(f)
            if std_h > 0:
                heights.add(std_h)
        return sorted(heights, reverse=True)

    @staticmethod
    def _validate_format_availability(requested_height: int, available_heights: List[int]) -> None:
        """Verifica que la resolución solicitada existe en los formatos del servidor.

        Lanza FormatNotFoundError con las calidades disponibles si la resolución
        no se encuentra.
        """
        std_requested = FormatNormalizer.get_standard_height(requested_height)
        if std_requested not in available_heights:
            available_labels = [f"{h}p" for h in available_heights]
            raise FormatNotFoundError(
                f"La resolución solicitada ({std_requested}p) no está disponible para este video. "
                f"Calidades disponibles: {', '.join(available_labels)}"
            )

    @staticmethod
    def _validate_downloaded_quality(
        actual_height: int,
        requested_height: int,
        requested_label: str,
        actual_label: str,
    ) -> None:
        """Valida que la resolución descargada se acerca a la solicitada.

        Se tolera una degradación máxima del 15% (ej. 918p para 1080p solicitado)
        para manejar variaciones menores de YouTube (ej. 1074p → 1080p).
        Si la degradación supera el umbral, lanza QualityDegradationError.
        """
        threshold = 0.85
        if actual_height < requested_height * threshold:
            raise QualityDegradationError(
                f"Calidad degradada: se solicitó {requested_label} pero el archivo resultante "
                f"tiene {actual_label}. La resolución solicitada no pudo ser entregada."
            )

    def _build_base_opts(
        self,
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

    def _resolve_final_path(self, info: Dict[str, Any], dest_dir: str, base: str) -> Optional[str]:
        requested = info.get("requested_downloads") or []
        if requested:
            filepath = requested[0].get("filepath")
            if filepath:
                resolved = self._ensure_within_dest(filepath, dest_dir)
                if resolved and os.path.exists(resolved):
                    return resolved
                if resolved and os.path.exists(resolved.replace(".part", "")):
                    return resolved.replace(".part", "")

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

    @staticmethod
    def _ensure_within_dest(filepath: str, dest_dir: str) -> Optional[str]:
        """Verifica que un filepath retornado por yt-dlp esté dentro de dest_dir.

        Si el archivo está fuera del directorio, retorna None para que
        el caller busque en los candidatos del directorio.
        """
        abs_file = os.path.abspath(filepath)
        abs_dest = os.path.abspath(dest_dir)
        if not abs_file.startswith(abs_dest + os.sep) and abs_file != abs_dest:
            logger.warning(
                f"yt-dlp reportó archivo fuera del destino: {filepath} (destino={dest_dir})"
            )
            return None
        return filepath

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
        """Sanitiza un nombre de archivo eliminando caracteres peligrosos.

        Remueve caracteres de control, caracteres no permitidos en nombres de archivo
        de Windows y Linux, y limita la longitud para prevenir overflow.
        """
        if not name:
            return "descarga"
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        cleaned = cleaned.strip().rstrip(".")
        if not cleaned:
            return "descarga"
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

    def _cleanup_file(self, path: str) -> None:
        for attempt in range(3):
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"Archivo temporal eliminado: {path}")
                return
            except OSError as ex:
                time.sleep(0.15 * (attempt + 1))
                if attempt == 2:
                    logger.warning(f"No se pudo eliminar '{path}': {ex}")

    def _save(self, task: DownloadTask) -> None:
        if self.repository is not None:
            try:
                self.repository.save(task)
            except Exception as ex:
                logger.error(f"No se pudo persistir la tarea {task.id.value}: {ex}")
