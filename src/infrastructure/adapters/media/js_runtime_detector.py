"""Deteccion de runtimes JavaScript disponibles para yt-dlp.

YouTube protege sus streams con retos de firma (n-token) que yt-dlp solo
puede resolver si dispone de un runtime JavaScript. Sin el, los clientes que
exigen PO token descartan sus formatos y la extraccion se queda en 360p.

yt-dlp acepta cuatro runtimes y usa el de MAYOR prioridad disponible:
``deno`` > ``node`` > ``quickjs`` > ``bun``. Este modulo los detecta todos y
valida la version de cada uno contra el minimo que exige yt-dlp, porque un
runtime demasiado antiguo hace fallar el reto y con el se pierden las
calidades altas.
"""

import logging
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = ["detect_js_runtimes", "JS_RUNTIME_MINIMUMS"]

#: Version minima que exige yt-dlp 2026.x para cada runtime.
#:
#: - node: ``NodeJsRuntime.MIN_SUPPORTED_VERSION = (22, 0, 0)``
#: - deno: ``DenoJsRuntime.MIN_SUPPORTED_VERSION = (2, 3, 0)``
#: - quickjs: ``QuickJsRuntime.MIN_SUPPORTED_VERSION = (2023, 12, 9)``
#: - bun: ``BunJsRuntime.MIN_SUPPORTED_VERSION = (1, 2, 11)``
JS_RUNTIME_MINIMUMS: Dict[str, Tuple[int, ...]] = {
    "deno": (2, 3, 0),
    "node": (22, 0, 0),
    "quickjs": (2023, 12, 9),
    "bun": (1, 2, 11),
}

#: Rutas habituales de Node.js en Windows cuando no esta en el PATH.
_WINDOWS_NODE_CANDIDATES = (
    r"C:\Program Files\nodejs\node.exe",
    r"C:\Program Files (x86)\nodejs\node.exe",
    r"%LOCALAPPDATA%\Programs\node\node.exe",
)

#: Nombre del ejecutable de cada runtime en el PATH.
#: QuickJS se distribuye como ``quickjs-ng``, cuyo binario es ``qjs``.
_EXECUTABLES: Tuple[Tuple[str, str], ...] = (
    ("node", "node"),
    ("deno", "deno"),
    ("quickjs", "qjs"),
    ("bun", "bun"),
)


def _runtime_version(path: str) -> Optional[Tuple[int, ...]]:
    """Version de un ejecutable como tupla de enteros, o None si no se puede leer."""
    try:
        from yt_dlp.utils import get_exe_version

        raw = get_exe_version(path, version_re=r"(\d+(?:\.\d+)*)")
    except Exception:  # noqa: BLE001 - deteccion opcional: nunca debe romper la app
        logger.debug("No se pudo leer la version del runtime '%s'.", path, exc_info=True)
        return None
    if not raw or not isinstance(raw, str):
        return None
    parts: List[int] = []
    for chunk in raw.split("."):
        if not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts) if parts else None


def _find_node() -> Optional[str]:
    """Localiza el ejecutable de Node.js."""
    found = shutil.which("node")
    if found:
        return found
    for candidate in _WINDOWS_NODE_CANDIDATES:
        expanded = os.path.expandvars(candidate)
        if os.path.exists(expanded):
            return expanded
    return None


def detect_js_runtimes() -> Dict[str, Dict[str, Any]]:
    """Detecta los runtimes JS utilizables por yt-dlp.

    Returns:
        Diccionario ``{runtime: {"path": ruta}}`` con los runtimes detectados
        y validos. Vacio si no hay ninguno (yt-dlp entonces no podra resolver
        los retos de firma).
    """
    candidates: List[Tuple[str, str]] = []
    node_path = _find_node()
    if node_path:
        candidates.append(("node", node_path))
    for key, executable in _EXECUTABLES:
        if key == "node":
            continue
        found = shutil.which(executable)
        if found:
            candidates.append((key, found))

    runtimes: Dict[str, Dict[str, Any]] = {}
    for key, path in candidates:
        minimum = JS_RUNTIME_MINIMUMS.get(key, ())
        version = _runtime_version(path)
        if version is not None and minimum and version < minimum:
            logger.warning(
                "Runtime JS '%s' (%s) es demasiado antiguo (version %s; se requiere %s): se omite.",
                key,
                path,
                ".".join(str(part) for part in version),
                ".".join(str(part) for part in minimum),
            )
            continue
        runtimes[key] = {"path": path}
    return runtimes
