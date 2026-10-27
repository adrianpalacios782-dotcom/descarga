import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import yt_dlp
import re

from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.entities.playlist_metadata import PlaylistEntry, PlaylistMetadata
from src.domain.services.error_classifier import ErrorClassifier
from src.domain.services.format_normalizer import FormatNormalizer
from src.domain.exceptions.domain_exceptions import MediaAnalysisError
from src.domain.ports.platform_adapter import IPlatformAdapter
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.session_status import SessionState, SessionStatus
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.media.js_runtime_detector import detect_js_runtimes
from src.infrastructure.adapters.media.subtitle_extractor import extract_subtitle_tracks
from src.infrastructure.adapters.platforms.browser_detector import (
    BrowserSession,
    detect_active_browser_session,
    get_first_available_browser,
)
from src.infrastructure.adapters.platforms.youtube_client_strategy import (
    NATIVE_FALLBACK_CLIENTS,
    YOUTUBE_NAMESPACE,
    get_fallback_clients,
    get_supported_player_clients,
    resolve_player_clients,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BasePlatformAdapter",
    "NATIVE_FALLBACK_CLIENTS",
    "get_supported_player_clients",
    "resolve_player_clients",
]



class BasePlatformAdapter(IPlatformAdapter):
    """Adaptador base de infraestructura que aísla yt-dlp detrás del contrato IPlatformAdapter.

    Usa el fallback NATIVO de yt-dlp (``player_client`` con varios clientes):
    en una sola extracción yt-dlp prueba cada cliente en orden y fusiona sus
    formatos. Es preferible a N extracciones secuenciales (una por estrategia)
    porque cada extracción secuencial es una request extra a YouTube.
    Soporta cookies de navegador y archivos cookies.txt personalizados para contenido con restricción de edad.
    """

    # Estrategia principal: fallback nativo de yt-dlp (web_embedded -> ios ->
    # android -> web) en UNA extracción. Las siguientes son reintentos con un
    # cliente aislado, por si la extracción multi-cliente falla entera
    # (p. ej. IP bloqueada).
    CLIENT_STRATEGIES: List[Optional[List[str]]] = [
        NATIVE_FALLBACK_CLIENTS,  # fallback nativo: yt-dlp fusiona los formatos
        None,                     # defaults de yt-dlp (visionos + web)
        ["web_embedded"],         # cliente de embed (no exige PO token)
        ["ios"],                  # cliente iOS: DASH sin PO token
        ["android"],              # cliente Android: contenido real aunque limitado (sin PO token)
        ["mweb"],                 # cliente web movil
    ]

    #: Cuántas estrategias se reintentan con la sesión del navegador detectada
    #: (Capa 2). Solo la primera: es el fallback nativo multi-cliente, que ya
    #: prueba varios clientes y fusiona sus formatos. Si el bloqueo es de IP,
    #: ningún cliente lo resuelve y repetir la escalera solo multiplica la
    #: espera del usuario.
    COOKIE_RETRY_STRATEGIES: int = 1

    #: Si es True, el adaptador vincula automaticamente la sesion del navegador
    #: detectado cuando el usuario no ha configurado cookies. Solo YouTube lo
    #: activa: la sesion automatica es la via para superar el tope de 360p.
    AUTOMATIC_SESSION_ENABLED: bool = False

    def __init__(
        self,
        cookies_from_browser: Optional[str] = None,
        cookiefile: Optional[str] = None,
        po_token: Optional[str] = None,
        visitor_data: Optional[str] = None,
    ) -> None:
        self.cookies_from_browser: Optional[str] = (
            cookies_from_browser.strip() if cookies_from_browser and cookies_from_browser.strip() else None
        )
        self.cookiefile: Optional[str] = (
            cookiefile.strip() if cookiefile and cookiefile.strip() else None
        )
        self.po_token: Optional[str] = po_token.strip() if po_token and po_token.strip() else None
        self.visitor_data: Optional[str] = visitor_data.strip() if visitor_data and visitor_data.strip() else None
        self._session: Optional[BrowserSession] = None
        self._session_resolved: bool = False
        self._session_linked: bool = False

    def detect(self, url: Url) -> bool:
        """Determina si este adaptador puede procesar la URL (sobrescrito por adaptadores específicos)."""
        return False

    def analyze(self, url: Url) -> MediaMetadata:
        """Analiza la URL y extrae los metadatos (sobrescrito por adaptadores específicos o usado por genérico)."""
        info = self._extract_with_ytdlp(url)
        return self._parse_ytdlp_info(url, info, platform_name=url.detect_platform())

    def set_cookie_file(self, cookiefile: Optional[str]) -> None:
        """Actualiza la ruta del archivo de cookies (cookies.txt)."""
        self.cookiefile = cookiefile.strip() if cookiefile and cookiefile.strip() else None

    def set_cookies_from_browser(self, browser: Optional[str]) -> None:
        """Actualiza el navegador de cookies global (firefox/chrome/edge/...)."""
        self.cookies_from_browser = browser.strip() if browser and browser.strip() else None

    @staticmethod
    def _filter_supported_clients(player_clients: List[str]) -> List[str]:
        """Normaliza los player_client: alias historicos + descarte de no soportados.

        Ver ``youtube_client_strategy.resolve_player_clients``.
        """
        return resolve_player_clients(player_clients)

    @staticmethod
    def _detect_js_runtimes() -> Dict[str, Dict[str, Any]]:
        """Detecta los runtimes JavaScript disponibles para yt-dlp.

        YouTube usa retos de firma (n-token) que yt-dlp solo puede resolver si
        hay un runtime JS. Sin el, los clientes que exigen PO token descartan
        sus formatos y la extraccion se queda en 360p.
        """
        return detect_js_runtimes()

    def _resolve_session(self) -> Optional[BrowserSession]:
        """Detecta (una sola vez) la sesion de navegador disponible.

        La deteccion se cachea durante toda la vida del adaptador: leer el
        arbol de perfiles del navegador en cada analisis es trabajo de disco
        innecesario, y el usuario no va a cambiar de navegador entre analyses.
        """
        if self._session_resolved:
            return self._session
        self._session_resolved = True
        try:
            self._session = detect_active_browser_session()
        except Exception:  # noqa: BLE001 - deteccion opcional: nunca debe romper
            logger.debug("No se pudo detectar la sesion del navegador.", exc_info=True)
            self._session = None
        return self._session

    def _resolve_cookie_source(
        self,
        disable_browser_cookies: bool = False,
        browser_override: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[BrowserSession]]:
        """Resuelve de donde salen las cookies de la extraccion.

        Returns:
            Tupla ``(cookiefile, browser, profile, session)`` donde ``browser``
            y ``profile`` son los que se pasan a ``cookiesfrombrowser`` y
            ``session`` es la sesion detectada (puede ser None).
        """
        if disable_browser_cookies:
            return None, None, None, None
        if self.cookiefile and os.path.isfile(self.cookiefile):
            return self.cookiefile, None, None, None
        if browser_override:
            return None, browser_override, None, None
        if self.cookies_from_browser:
            return None, self.cookies_from_browser, None, None

        session = self._resolve_session()
        if not self.AUTOMATIC_SESSION_ENABLED or session is None:
            return None, None, None, session
        if not session.usable:
            logger.info(
                "La sesion de '%s' (perfil '%s') no se puede leer: el navegador esta abierto "
                "y Windows bloquea su almacen de cookies.",
                session.browser,
                session.profile or "?",
            )
            return None, None, None, session

        logger.info(
            "Vinculando la sesion automaticamente desde '%s' (perfil '%s').",
            session.browser,
            session.profile or "?",
        )
        return None, session.browser, session.profile, session

    def _client_strategies(
        self,
        disable_browser_cookies: bool = False,
        browser_override: Optional[str] = None,
    ) -> List[Optional[List[str]]]:
        """Escalera de estrategias de cliente adaptada a la sesion disponible.

        Con sesion se usa la lista autenticada (incluye ``web_creator``, que
        exige iniciar sesion); sin sesion, la anonima.
        """
        strategies = list(self.CLIENT_STRATEGIES)
        _, browser, _, _ = self._resolve_cookie_source(
            disable_browser_cookies=disable_browser_cookies,
            browser_override=browser_override,
        )
        if browser:
            strategies[0] = get_fallback_clients(authenticated=True)
        return strategies

    def _build_ydl_opts(
        self,
        player_clients: Optional[List[str]] = None,
        disable_browser_cookies: bool = False,
        browser_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construye las opciones de yt-dlp.

        Args:
            player_clients: clientes a forzar para los extractores que lo
                soportan (YouTube). ``None`` usa los defaults de yt-dlp.
            disable_browser_cookies: ignora el navegador configurado. Se usa
                para reintentar sin cookies cuando el almacén del navegador
                está bloqueado (navegador abierto en Windows).
            browser_override: navegador concreto del que leer cookies. Tiene
                prioridad sobre el configurado: es el mecanismo de la Capa 2
                (reintento con el navegador detectado automáticamente).
        """
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "extract_flat": False,
            "format": "all",
            "remote_components": ["ejs:github"],
        }
        try:
            from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter
            ffmpeg_path = FFmpegProcessAdapter().get_ffmpeg_executable()
            if ffmpeg_path and os.path.exists(ffmpeg_path):
                ydl_opts["ffmpeg_location"] = ffmpeg_path
        except Exception:
            pass

        js_runtimes = self._detect_js_runtimes()
        if js_runtimes:
            ydl_opts["js_runtimes"] = js_runtimes

        cookiefile, browser, profile, session = self._resolve_cookie_source(
            disable_browser_cookies=disable_browser_cookies,
            browser_override=browser_override,
        )
        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile
            self._session_linked = False
        elif browser:
            # yt-dlp acepta (navegador, perfil, keyring, contenedor). Indicar el
            # perfil evita que yt-dlp elija otro por su cuenta.
            ydl_opts["cookiesfrombrowser"] = (browser, profile) if profile else (browser,)
            self._session_linked = (
                session is not None
                and browser == session.browser
                and browser_override is None
                and not self.cookies_from_browser
            )
        else:
            self._session_linked = False

        # La clase base es agnóstica de plataforma: solo aplica `player_client`
        # cuando la estrategia lo pide. La política completa de YouTube
        # (player_client + player_skip + credenciales) la aplica YouTubeAdapter,
        # para no colar un bloque `extractor_args` de YouTube en otras
        # plataformas (TikTok, Instagram, ...).
        if player_clients:
            effective = resolve_player_clients(player_clients)
            if effective:
                ydl_opts["extractor_args"] = {YOUTUBE_NAMESPACE: {"player_client": effective}}
        return ydl_opts

    def _run_strategies(
        self,
        url: Url,
        strategies: List[Optional[List[str]]],
        errors: List[str],
        disable_browser_cookies: bool = False,
        browser_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Ejecuta las estrategias de cliente en orden y devuelve la mejor respuesta.

        Una estrategia solo se considera exitosa si entregó al menos un formato REAL
        de medios (no storyboard/mhtml/thumbnail). Se acepta la primera estrategia
        que entregue video real; si ninguna entrega video, se usa la mejor que haya
        entregado solo audio. Si ninguna sirve, se devuelve ``None`` y los fallos
        quedan registrados en ``errors``.
        """
        video_info: Optional[Dict[str, Any]] = None
        audio_only_info: Optional[Dict[str, Any]] = None
        direct_url_info: Optional[Dict[str, Any]] = None

        for clients in strategies:
            try:
                opts = self._build_ydl_opts(
                    clients,
                    disable_browser_cookies=disable_browser_cookies,
                    browser_override=browser_override,
                )
                with yt_dlp.YoutubeDL(opts) as ydl:
                    raw_info = ydl.extract_info(url.value, download=False)
                if not raw_info or not isinstance(raw_info, dict):
                    continue
                info: Dict[str, Any] = dict(raw_info)
                if "entries" in info or info.get("_type") == "playlist":
                    raw_entries = info.get("entries")
                    if isinstance(raw_entries, list):
                        dict_entries = [e for e in raw_entries if isinstance(e, dict)]
                        if dict_entries:
                            info = dict_entries[0]
                formats: List[Dict[str, Any]] = (
                    [f for f in info.get("formats", []) if isinstance(f, dict)]
                    if isinstance(info.get("formats"), list)
                    else []
                )

                if not formats:
                    # Extracción de archivo directo (sin lista de formatos): válida.
                    if info.get("url"):
                        direct_url_info = info
                        break
                    errors.append("respuesta sin formatos")
                    continue

                real_formats = [f for f in formats if not FormatNormalizer.is_auxiliary_format(f)]
                if not real_formats:
                    errors.append("respuesta sin formatos de medios reales (solo recursos auxiliares)")
                    continue

                video_opts = FormatNormalizer.normalize_video_quality_options(formats)
                video_fmts = FormatNormalizer.normalize_video_formats(formats)
                max_height = max([v.height for v in video_opts if v.height], default=0)
                if (max_height > 0 or len(video_fmts) > 0) and video_info is None:
                    video_info = info
                    break
                if audio_only_info is None:
                    audio_only_info = info
            except Exception as ex:
                errors.append(str(ex))
                continue

        return video_info if video_info is not None else (
            direct_url_info if direct_url_info is not None else audio_only_info
        )

    def _has_effective_cookies(self) -> bool:
        """Indica si hay cookies realmente aplicables (archivo existente o navegador)."""
        if self.cookiefile and os.path.isfile(self.cookiefile):
            return True
        return bool(self.cookies_from_browser)

    def _build_session_status(self) -> SessionStatus:
        """Describe el estado de la sesion para la interfaz.

        La app vincula la sesion del navegador de forma automatica; este estado
        es lo que la vista muestra en lugar de pedir un cookies.txt a mano.
        """
        session = self._resolve_session()
        if self._session_linked and session is not None:
            return SessionStatus(
                state=SessionState.LINKED,
                browser=session.browser,
                profile=session.profile or "",
            )
        if session is not None:
            return SessionStatus(
                state=SessionState.BLOCKED if session.locked else SessionState.UNAVAILABLE,
                browser=session.browser,
                profile=session.profile or "",
            )
        if self.cookies_from_browser:
            return SessionStatus(state=SessionState.BLOCKED, browser=self.cookies_from_browser)
        if self.cookiefile and os.path.isfile(self.cookiefile):
            return SessionStatus(state=SessionState.LINKED)
        return SessionStatus(state=SessionState.UNAVAILABLE)

    @staticmethod
    def _is_cookie_recoverable(errors: List[str], plat_name: str) -> bool:
        """Indica si algún fallo se puede recuperar aportando una sesión con cookies.

        Reutiliza la clasificación de dominio (ErrorClassifier) en lugar de
        duplicar los patrones: bot-check, restricción de edad, contenido de
        miembros, contenido privado, "inicia sesión" y error de cookies.
        """
        for err in errors:
            if not err:
                continue
            if ErrorClassifier.classify(err, platform_name=plat_name).is_cookie_recoverable:
                return True
        return False

    @staticmethod
    def _has_cookie_read_error(errors: List[str]) -> bool:
        """Detecta el fallo al leer el almacén de cookies (navegador abierto / DPAPI)."""
        for err in errors:
            low = err.lower()
            if (
                ("could not copy" in low and "cookie" in low)
                or "dpapi" in low
                or ("could not find" in low and "cookie" in low)
            ):
                return True
        return False

    def _extract_with_ytdlp(self, url: Url) -> Dict[str, Any]:
        """Extrae la información con la mejor estrategia de clientes disponible.

        Capas de recuperación, en orden:

        1. **Sesión automática + estrategias de cliente**: si el usuario no ha
           configurado cookies, se vincula automáticamente la sesión del
           navegador detectado (perfil activo y almacén de cookies legible) y
           se prueban las estrategias de cliente de YouTube.
        2. **Capa 2 (cookies automáticas)**: si el fallo es recuperable con
           cookies (bot-check, restricción de edad, "inicia sesión") y no hay
           ninguna cookie configurada, se reintenta con la sesión del
           navegador detectado automáticamente.
        3. **Degradación**: si el navegador está abierto y su almacén de
           cookies no se puede leer, se reintenta sin cookies para no perder
           el contenido público.

        Una estrategia solo se considera exitosa si entregó al menos un formato REAL
        de medios (no storyboard/mhtml/thumbnail). Se acepta la primera estrategia
        que entregue video real; si ninguna entrega video, se usa la mejor que haya
        entregado solo audio; si todas fallan o devuelven únicamente recursos
        auxiliares, se lanza MediaAnalysisError.
        """
        errors: List[str] = []

        plat_name = url.detect_platform()
        is_youtube = plat_name == "YouTube"
        strategies: List[Optional[List[str]]] = (
            self._client_strategies() if is_youtube else [None]
        )

        chosen = self._run_strategies(url, strategies, errors)
        if chosen is not None:
            return chosen

        # --- Capa 2: reintento con la sesión del navegador detectado ---
        auto_browser: Optional[str] = None
        if not self._has_effective_cookies() and self._is_cookie_recoverable(errors, plat_name):
            session = self._resolve_session()
            auto_browser = session.browser if session else get_first_available_browser()
            # Si la sesion automatica ya se aplico en la primera pasada, repetir
            # con el mismo navegador solo duplica la espera.
            if auto_browser and not self._session_linked:
                logger.info(
                    "Reintentando el análisis con la sesión del navegador '%s' "
                    "(el fallo es recuperable con cookies).",
                    auto_browser,
                )
                retry_strategies: List[Optional[List[str]]] = (
                    self._client_strategies(browser_override=auto_browser) if is_youtube else [None]
                )
                chosen = self._run_strategies(
                    url,
                    retry_strategies[: self.COOKIE_RETRY_STRATEGIES],
                    errors,
                    browser_override=auto_browser,
                )
                if chosen is not None:
                    return chosen

        has_cookie_err = self._has_cookie_read_error(errors)

        # Si falló por bloqueo/encriptación del navegador de cookies, reintentar sin cookies del navegador
        # para no romper videos públicos si el usuario dejó Chrome/Edge seleccionado con el navegador abierto.
        if has_cookie_err and (self.cookies_from_browser or self._session_linked):
            retry_errors: List[str] = []
            retry_info = self._run_strategies(
                url,
                self._client_strategies(disable_browser_cookies=True) if is_youtube else [None],
                retry_errors,
                disable_browser_cookies=True,
            )
            if retry_info is not None:
                browser_used = self.cookies_from_browser or (
                    self._session.browser if self._session else None
                )
                retry_info["_warning_message"] = (
                    f"No se pudieron leer las cookies de '{browser_used}' (el navegador está abierto en Windows). "
                    "Se muestran calidades públicas. Cierra el navegador por completo para que la app "
                    "vincule tu sesión automáticamente."
                )
                return retry_info

        raw_msg = errors[0] if errors else "Respuesta vacía"
        clean_msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", raw_msg)
        clean_msg = re.sub(r"ERROR:\s*", "", clean_msg).strip()

        is_age_restricted = any(term in clean_msg.lower() for term in ("confirm your age", "age-restricted", "age restricted", "restricción de edad", "inappropriate for some users")) or ("age" in clean_msg.lower() and "sign in" in clean_msg.lower())
        browser_used = self.cookies_from_browser or auto_browser
        if has_cookie_err and browser_used:
            clean_msg = (
                f"No se pudieron leer las cookies de '{browser_used}' (el navegador está abierto o protegido por Windows). "
                "Cierra el navegador por completo para que la app vincule tu sesión automáticamente."
            )
        elif is_age_restricted:
            clean_msg = (
                f"Este video tiene restricción de edad (+18) en {plat_name}. "
                "Para descargarlo, ve a la pestaña 'Configuración' -> 'Avanzado (Sesión y Cookies)' y carga tu archivo cookies.txt o selecciona tu navegador."
            )
        elif any(term in clean_msg.lower() for term in ("sign in", "bot", "too many requests", "429")):
            clean_msg = (
                f"La plataforma ({plat_name}) ha restringido temporalmente las solicitudes "
                "o requiere verificación de cuenta para este contenido. "
                + self._cookie_advice(auto_browser)
            )
        elif all("auxiliares" in e for e in errors):
            clean_msg = (
                "La plataforma no entregó formatos descargables para este contenido "
                "(solo recursos auxiliares). Intenta de nuevo en unos minutos."
            )

        raise MediaAnalysisError(f"Fallo al analizar el contenido multimedia: {clean_msg}")

    def _cookie_advice(self, auto_browser: Optional[str]) -> str:
        """Mensaje de orientación sobre cookies según lo que ya se intentó."""
        if auto_browser:
            return (
                f"Se intentó usar automáticamente la sesión del navegador '{auto_browser}' y no fue suficiente. "
                "Cierra el navegador por completo (Windows bloquea su almacén de cookies mientras está abierto) "
                "o carga un archivo cookies.txt en Configuración (sección 'Avanzado (Sesión y Cookies)')."
            )
        if not self._has_effective_cookies():
            return (
                "No se encontró ningún navegador con perfil activo del que tomar la sesión automáticamente: "
                "carga un archivo cookies.txt o selecciona tu navegador en Configuración "
                "(sección 'Avanzado (Sesión y Cookies)')."
            )
        return (
            "Puedes configurar un archivo cookies.txt o tu navegador en Configuración "
            "(sección 'Avanzado (Sesión y Cookies)')."
        )

    def _parse_ytdlp_info(self, url: Url, info: Dict[str, Any], platform_name: str) -> MediaMetadata:
        title = info.get("title") or "Sin título"
        author = info.get("uploader") or info.get("channel") or info.get("uploader_id") or ""
        description = info.get("description") or ""
        duration = float(info.get("duration") or 0.0)
        thumbnail = info.get("thumbnail") or ""
        upload_date = info.get("upload_date") or ""

        raw_formats = info.get("formats") or []
        video_quality_options = FormatNormalizer.normalize_video_quality_options(raw_formats)
        video_formats = FormatNormalizer.normalize_video_formats(raw_formats)
        audio_formats = FormatNormalizer.normalize_audio_formats(raw_formats)
        formats_list = FormatNormalizer.normalize(raw_formats)
        subtitles_list = extract_subtitle_tracks(info)

        if not formats_list and info.get("url"):
            default_fmt = FormatOption(
                format_id="default",
                extension=info.get("ext") or "mp4",
                resolution="Standard"
            )
            formats_list.append(default_fmt)

        media_id = MediaId.from_string(url.value)
        warning_msg = info.get("_warning_message")
        return MediaMetadata(
            media_id=media_id,
            url=url,
            platform=platform_name,
            title=title,
            author=author,
            description=description,
            duration_seconds=duration,
            thumbnail_url=thumbnail,
            upload_date=upload_date,
            video_quality_options=video_quality_options,
            video_formats=video_formats,
            audio_formats=audio_formats,
            formats=formats_list,
            subtitles=subtitles_list,
            warning_message=warning_msg,
            session_status=self._build_session_status(),
        )

    def analyze_playlist(self, url: Url) -> PlaylistMetadata:
        """Extrae la lista de reproducción de forma plana y rápida (extract_flat).

        Aplica la misma Capa 2 que el análisis de un video: si el fallo es
        recuperable con cookies y no hay ninguna configurada, se reintenta con
        la sesión del navegador detectado automáticamente.
        """
        errors: List[str] = []
        info = self._extract_playlist_info(url, errors)

        if info is None and not self._has_effective_cookies():
            plat_name = url.detect_platform()
            if self._is_cookie_recoverable(errors, plat_name):
                auto_browser = get_first_available_browser()
                if auto_browser:
                    logger.info(
                        "Reintentando el análisis de la lista con la sesión del navegador '%s'.",
                        auto_browser,
                    )
                    info = self._extract_playlist_info(url, errors, browser_override=auto_browser)

        if info is None:
            detail = errors[0] if errors else "La plataforma devolvió una lista vacía o no válida."
            raise MediaAnalysisError(f"No se pudo analizar la lista de reproducción: {detail}")

        entries_raw = info.get("entries")
        entries_list = entries_raw if isinstance(entries_raw, list) else []
        entries: List[PlaylistEntry] = []
        for e in entries_list:
            if not e or not isinstance(e, dict):
                continue
            v_id = str(e.get("id") or "")
            v_title = str(e.get("title") or "Sin título")
            v_url = str(e.get("url") or e.get("webpage_url") or "")
            if not v_url and v_id:
                v_url = f"https://www.youtube.com/watch?v={v_id}"
            v_dur = float(e.get("duration") or 0.0)
            v_thumb = str(e.get("thumbnail") or "")
            v_uploader = str(e.get("uploader") or e.get("channel") or "")
            entries.append(
                PlaylistEntry(
                    video_id=v_id,
                    title=v_title,
                    url=v_url,
                    duration_seconds=v_dur,
                    thumbnail_url=v_thumb,
                    uploader=v_uploader,
                )
            )

        return PlaylistMetadata(
            playlist_id=str(info.get("id") or "playlist"),
            title=str(info.get("title") or "Lista de reproducción"),
            url=url,
            platform=url.detect_platform(),
            uploader=str(info.get("uploader") or info.get("channel") or ""),
            description=str(info.get("description") or ""),
            entries=entries,
        )

    def _extract_playlist_info(
        self,
        url: Url,
        errors: List[str],
        browser_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extrae la lista de reproducción; devuelve None si no se pudo."""
        opts = self._build_ydl_opts(browser_override=browser_override)
        opts["extract_flat"] = "in_playlist"
        opts["noplaylist"] = False

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url.value, download=False)
        except Exception as ex:
            errors.append(str(ex))
            return None

        if not info or not isinstance(info, dict):
            errors.append("La plataforma devolvió una lista vacía o no válida.")
            return None
        return info

