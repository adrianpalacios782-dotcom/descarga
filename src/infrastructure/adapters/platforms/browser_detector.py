"""Deteccion de navegadores instalados y de sesiones activas para cookies.

Dos responsabilidades:

1. :func:`detect_installed_browsers` / :func:`get_first_available_browser`
   responden a "que navegadores hay en el sistema" (uso general).
2. :func:`detect_active_browser_session` responde a "de que navegador puedo
   TOMAR una sesion ahora mismo": busca un navegador con perfil activo y su
   almacen de cookies, e indica si ese almacen se puede leer.

El segundo punto es el que habilita la vinculacion automatica de sesion (sin
que el usuario cargue cookies.txt a mano) y tambien el que detecta el caso mas
frecuente en Windows: el navegador esta ABIERTO y el sistema bloquea su base de
cookies, de modo que la sesion no se puede leer (yt-dlp falla con "Could not
copy Chrome cookie database"). En ese caso la app debe avisar al usuario en
lugar de romperse.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

_BROWSER_PATHS: dict[str, dict[str, list[str]]] = {
    "chrome": {
        "win32": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/Google/Chrome")],
        "linux": [os.path.expanduser("~/.config/google-chrome")],
    },
    "edge": {
        "win32": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/Microsoft Edge")],
        "linux": [os.path.expanduser("~/.config/microsoft-edge")],
    },
    "firefox": {
        "win32": [
            os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/Firefox")],
        "linux": [os.path.expanduser("~/.mozilla/firefox")],
    },
    "brave": {
        "win32": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data"),
        ],
        "darwin": [os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser")],
        "linux": [os.path.expanduser("~/.config/BraveSoftware/Brave-Browser")],
    },
}

#: Orden de prioridad para vincular la sesion automaticamente.
#:
#: El orden pedido es Chrome -> Brave -> Edge -> Firefox. Entre los candidatos
#: con la misma prioridad gana el que tiene el almacen de cookies LEGIBLE: si
#: el navegador esta abierto, Windows lo bloquea y no se podria leer la
#: sesion, asi que conviene elegir otro que si lo este.
SESSION_BROWSER_ORDER: List[str] = ["chrome", "brave", "edge", "firefox"]

#: Orden de preferencia para auto-reintento con cookies.
PREFERRED_BROWSER_ORDER: List[str] = list(SESSION_BROWSER_ORDER)

#: Navegadores derivados de Chromium: comparten layout de perfiles y de la base
#: de cookies (``<perfil>/Network/Cookies``).
_CHROMIUM_BROWSERS = ("chrome", "brave", "edge")


@dataclass(frozen=True)
class BrowserSession:
    """Sesion de navegador localizable: navegador, perfil y almacen de cookies.

    Attributes:
        browser: identificador del navegador ("chrome", "brave", "edge",
            "firefox").
        profile: nombre del perfil activo ("Default", "Profile 1",
            "default-release", ...). ``None`` si no se pudo determinar.
        cookie_db: ruta del almacen de cookies del perfil. ``None`` si el
            perfil no tiene almacen (navegador nunca usado).
        locked: True si el almacen existe pero no se puede leer, tipicamente
            porque el navegador esta abierto y Windows lo bloquea.
    """

    browser: str
    profile: Optional[str] = None
    cookie_db: Optional[str] = None
    locked: bool = False

    @property
    def usable(self) -> bool:
        """Indica si la sesion se puede leer ahora mismo."""
        return bool(self.cookie_db) and not self.locked

    @property
    def display_name(self) -> str:
        """Nombre legible del navegador para la interfaz."""
        return {
            "chrome": "Chrome",
            "brave": "Brave",
            "edge": "Edge",
            "firefox": "Firefox",
        }.get(self.browser, self.browser.capitalize())


def detect_installed_browsers(platform_sys: Optional[str] = None) -> List[str]:
    """Retorna una lista de identificadores de navegadores detectados en el sistema."""
    plat = platform_sys or sys.platform
    detected: List[str] = []
    for browser_name, platform_paths in _BROWSER_PATHS.items():
        paths = platform_paths.get(plat, [])
        if any(os.path.isdir(p) for p in paths if p):
            detected.append(browser_name)
    return detected


def get_first_available_browser(preferred: Optional[str] = None) -> Optional[str]:
    """Retorna el primer navegador disponible según el orden de preferencia o el preferido."""
    detected = detect_installed_browsers()
    if not detected:
        return None

    if preferred and preferred.lower() in detected:
        return preferred.lower()

    for candidate in PREFERRED_BROWSER_ORDER:
        if candidate in detected:
            return candidate

    return detected[0]


# ---------------------------------------------------------------------------
# Deteccion de sesion activa (navegador + perfil + almacen de cookies)
# ---------------------------------------------------------------------------


def _browser_roots(browser: str, platform_sys: str) -> List[str]:
    """Rutas raiz de datos del navegador para la plataforma indicada."""
    return [p for p in _BROWSER_PATHS.get(browser, {}).get(platform_sys, []) if p]


def _is_readable(path: str) -> bool:
    """Indica si el archivo se puede abrir para lectura.

    En Windows, un navegador abierto mantiene su base de cookies con un
    bloqueo que impide abrirla (WinError 32): ese es el caso que marca la
    sesion como bloqueada.
    """
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False


def _chromium_last_used_profile(root: str) -> Optional[str]:
    """Perfil activo segun ``Local State`` (``profile.last_used``)."""
    state_path = os.path.join(root, "Local State")
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    profile = data.get("profile")
    if not isinstance(profile, dict):
        return None
    last_used = profile.get("last_used")
    return str(last_used) if last_used else None


def _chromium_profile_sort_key(name: str, last_used: Optional[str]) -> Tuple[int, int, int, str]:
    """Ordena perfiles: el activo primero, luego "Default", luego "Profile N"."""
    number = -1
    if name.startswith("Profile "):
        try:
            number = int(name[len("Profile "):])
        except ValueError:
            number = -1
    return (
        0 if name == last_used else 1,
        0 if name == "Default" else 1,
        number,
        name,
    )


def _chromium_cookie_db(profile_dir: str) -> Optional[str]:
    """Ruta del almacen de cookies de un perfil Chromium."""
    for relative in (os.path.join("Network", "Cookies"), "Cookies"):
        candidate = os.path.join(profile_dir, relative)
        if os.path.isfile(candidate):
            return candidate
    return None


def _chromium_sessions(browser: str, root: str) -> List[BrowserSession]:
    """Sesiones de los perfiles Chromium de una raiz de datos."""
    if not os.path.isdir(root):
        return []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return []

    names = [
        entry
        for entry in entries
        if entry == "Default"
        or (entry.startswith("Profile ") and entry[len("Profile "):].isdigit())
    ]
    if not names:
        return []

    last_used = _chromium_last_used_profile(root)
    sessions: List[BrowserSession] = []
    for name in sorted(names, key=lambda item: _chromium_profile_sort_key(item, last_used)):
        cookie_db = _chromium_cookie_db(os.path.join(root, name))
        if not cookie_db:
            continue
        sessions.append(
            BrowserSession(
                browser=browser,
                profile=name,
                cookie_db=cookie_db,
                locked=not _is_readable(cookie_db),
            )
        )
    return sessions


def _firefox_default_profile(root: str) -> Optional[str]:
    """Perfil marcado como predeterminado en ``profiles.ini``."""
    ini_path = os.path.join(root, "profiles.ini")
    try:
        with open(ini_path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except OSError:
        return None

    default_name: Optional[str] = None
    current_name: Optional[str] = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            current_name = None
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key == "name":
            current_name = value
        elif key == "default" and value.lower() == "1" and current_name:
            default_name = current_name
    return default_name


def _firefox_sessions(browser: str, root: str) -> List[BrowserSession]:
    """Sesiones de los perfiles de Firefox de una raiz de datos."""
    profiles_dir = os.path.join(root, "Profiles")
    if not os.path.isdir(profiles_dir):
        return []
    try:
        entries = sorted(os.listdir(profiles_dir))
    except OSError:
        return []

    default_profile = _firefox_default_profile(root)
    sessions: List[BrowserSession] = []
    for name in entries:
        cookie_db = os.path.join(profiles_dir, name, "cookies.sqlite")
        if not os.path.isfile(cookie_db):
            continue
        sessions.append(
            BrowserSession(
                browser=browser,
                profile=name,
                cookie_db=cookie_db,
                locked=not _is_readable(cookie_db),
            )
        )
    if default_profile:
        sessions.sort(key=lambda item: 0 if item.profile == default_profile else 1)
    return sessions


def detect_browser_sessions(platform_sys: Optional[str] = None) -> List[BrowserSession]:
    """Detecta las sesiones disponibles en el sistema.

    Recorre los navegadores en el orden de prioridad y, para cada uno, sus
    perfiles con almacen de cookies. Devuelve TODAS las sesiones encontradas
    (un navegador puede tener varios perfiles); dentro de cada navegador, el
    perfil activo va primero.
    """
    plat = platform_sys or sys.platform
    sessions: List[BrowserSession] = []
    for browser in SESSION_BROWSER_ORDER:
        for root in _browser_roots(browser, plat):
            if browser in _CHROMIUM_BROWSERS:
                sessions.extend(_chromium_sessions(browser, root))
            else:
                sessions.extend(_firefox_sessions(browser, root))
    return sessions


def detect_active_browser_session(platform_sys: Optional[str] = None) -> Optional[BrowserSession]:
    """Devuelve la mejor sesion disponible para vincular la cuenta.

    Prioridad:

    1. Orden de navegadores: Chrome -> Brave -> Edge -> Firefox.
    2. A igualdad de navegador, el perfil activo (el que el navegador declara
       como ultimo usado).
    3. Entre navegadores empatados, el que tiene el almacen de cookies
       LEGIBLE: si el navegador esta abierto, Windows lo bloquea y la sesion
       no se podria leer.

    Devuelve ``None`` si no hay ningun navegador con perfil activo.
    """
    sessions = detect_browser_sessions(platform_sys=platform_sys)
    if not sessions:
        return None

    def rank(session: BrowserSession) -> Tuple[int, int]:
        try:
            browser_rank = SESSION_BROWSER_ORDER.index(session.browser)
        except ValueError:
            browser_rank = len(SESSION_BROWSER_ORDER)
        return (browser_rank, 0 if session.usable else 1)

    return sorted(sessions, key=rank)[0]
