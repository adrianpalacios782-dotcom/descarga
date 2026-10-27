# Calidad de YouTube: por qué la app solo ofrecía 360p y cómo se resuelve

Este documento explica el diagnóstico del problema "**en visita anónima YouTube
solo devuelve 360p**" (caso real: *No Doubt - Don't Speak (Official 4K Music
Video)*, `TR3Vdo5etCQ`) y la solución implementada en `osvaldoDownloaderPro`.

> **Nota de revisión (2026-10).** La primera versión de este documento
> afirmaba que `player_skip: ["webpage", "configs"]` mejoraba el resultado.
> **Era falso**: ese `player_skip` era precisamente lo que recortaba el ladder
> a 360p. La evidencia medida está en §3.2 y corregió la implementación.

---

## 1. Síntoma

Al analizar un video musical en 4K sin sesión iniciada, el panel de calidades
mostraba como máximo **360p**, acompañado de storyboards (`sb0`–`sb3`). El
ladder observado fue exactamente:

```
[27, 45, 90, 180, 360]
 └─ storyboards ─┘  └─ 360p: el tope
```

---

## 2. Causa raíz: la política de PO token de los clientes

YouTube entrega las calidades altas del ladder **solo si la petición va
acompañada de un PO token** (GVS). Sin token, el servidor recorta el ladder.

En yt-dlp 2026.08.19, cada cliente de YouTube declara su política GVS en
`yt_dlp/extractor/youtube/_base.py::INNERTUBE_CLIENTS`. Extracto verificado:

| cliente        | `clientName`         | cookies | HTTPS | DASH | HLS  | requiere JS |
|----------------|----------------------|---------|-------|------|------|-------------|
| `android`      | ANDROID              | no      | REQ   | REQ  | rec  | no          |
| `android_vr`   | ANDROID_VR           | no      | REQ   | REQ  | rec  | no          |
| **`ios`**      | IOS                  | no      | REQ   | **no** | REQ | no          |
| `mweb`         | MOBILE_WEB           | sí      | REQ   | REQ  | rec  | sí          |
| `tv`           | TVHTML5 (v7)         | sí      | **no** | **no** | **no** | sí    |
| **`tv_downgraded`** | TVHTML5 (v5)     | sí      | **no** | **no** | **no** | sí    |
| `tv_simply`    | TVHTML5_SIMPLY       | no      | REQ   | REQ  | rec  | sí          |
| `visionos`     | VISIONOS             | no      | **no** | **no** | **no** | no       |
| `web`          | WEB                  | sí      | REQ   | REQ  | rec  | sí          |
| **`web_creator`** | WEB_CREATOR        | sí      | REQ   | REQ  | rec  | sí          |
| **`web_embedded`** | WEB_EMBEDDED_PLAYER | sí   | **no** | **no** | **no** | sí    |
| `web_music`    | WEB_REMIX            | sí      | REQ   | REQ  | rec  | sí          |
| `web_safari`   | WEB_SAFARI           | sí      | REQ   | REQ  | rec  | sí          |

`REQ` = exige PO token (sin él, los formatos se descartan).

**El dato decisivo:** los clientes por defecto de yt-dlp son
`_DEFAULT_CLIENTS = ('visionos', 'web')` (`_video.py:143`). `web` exige PO
token para DASH y HTTPS → sin token, **el ladder se recorta a 360p**. Ese es
el mecanismo exacto del síntoma.

Clientes que **no exigen PO token** para vídeo de alta resolución:
`ios` (solo DASH), `tv`, `tv_downgraded`, `visionos` y `web_embedded`.

---

## 3. Capa 1 — sin cookies

Dos mecanismos **nativos de yt-dlp**, sin parches ni proxies.

### 3.1 `player_client` con lista: fallback nativo

`player_client` acepta una **lista** de clientes. yt-dlp los prueba **en
orden** dentro de una **sola extracción** y **fusiona sus formatos**:

```python
# yt_dlp/extractor/youtube/_video.py:3045-3063
all_clients = set(clients)
clients = clients[::-1]
...
while clients:
    client, base_client, variant = _split_innertube_client(clients.pop())
```

> `clients[::-1]` + `pop()` ⇒ se prueba **el primero de la lista**.

Dos garantías hacen que esto sea robusto:

1. **Un fallo en un cliente no aborta la extracción** (`_video.py:3118-3120`):
   ```python
   except ExtractorError as e:
       self.report_warning(e)
       continue
   ```
   Un bot-check en `ios` no impide que `web_embedded` aporte sus formatos.
2. **Los formatos de todos los clientes se fusionan**, así que el resultado es
   la unión, no el último en ganar.

Configuración enviada por la app **en la vía anónima**:

```python
"extractor_args": {
    "youtube": {
        "player_client": ["web_embedded", "ios", "android", "web"],
    }
}
```

- `web_embedded` — **el cliente que rompe el tope de 360p**: no exige PO token
  en ningún protocolo, así que entrega el ladder DASH completo (hasta 2160p)
  con 4 pistas de audio separadas.
- `ios` — no exige PO token para DASH (video-only de alta resolución).
- `android` — DASH de alta resolución; exige PO token, pero no estorba si la
  app no tiene ninguno.
- `web` — cierre, tal como en la configuración original.

Con **sesión** se usa la lista autenticada, que añade `web_creator`:

```python
"player_client": ["web_embedded", "ios", "android", "web", "web_creator"]
```

`web_creator` es el único cliente de la lista con `REQUIRE_AUTH: True`
("*this client now requires sign-in for every video*"), de modo que solo
existe si hay cookies; es el que aporta las calidades de cuenta (Premium,
contenido para miembros).

### 3.2 `player_skip`: por qué YA NO se salta nada

`player_skip` es un `extractor_arg` **válido** en yt-dlp 2026.x (el namespace
es `youtube`, se lee con `self._configuration_arg('player_skip')`). Valores
reconocidos: `webpage`, `configs`, `js`, `initial_data`.

**Evidencia medida** (yt-dlp 2026.08.19, `TR3Vdo5etCQ`, misma IP, sin sesión):

| `player_client`                       | `player_skip`            | ladder                | notas |
|---------------------------------------|--------------------------|-----------------------|-------|
| `web_embedded`                        | *(ninguno)*              | **144…2160** (4K)     | 4 audios separados |
| `web_embedded`                        | `["webpage"]`            | 144…2160 (4K)         | equivalente |
| `web_embedded`                        | `["configs"]`            | **ERROR 152**         | el ladder se pierde |
| `web_embedded`                        | `["webpage","configs"]`  | **ERROR 152**         | el ladder se pierde |
| `web_embedded`                        | `["initial_data"]`       | 360                   | se pierde |
| `android ios web_creator web`         | *(ninguno)*              | 360                   | se pierde |
| `android ios web_creator web`         | `["webpage","configs"]`  | 360                   | se pierde |

Conclusiones:

- **Saltar `configs` destruye el ladder**: `web_embedded` falla con *"Error
  code: 152"* (YouTube rechaza el contexto de embed) y no queda ningún formato
  por encima de 360p.
- **Saltar `webpage`** no rompe el ladder, pero elimina el `visitor_data` que
  necesitan los clientes autenticados (`web`, `web_creator`) para resolver su
  PO token.
- **`DEFAULT_PLAYER_SKIP` es ahora `[]`**: ahorrar una request por cliente no
  compensa perder el 4K. El salto sigue siendo una capacidad configurable
  (`player_skip` explícito) por si hay que minimizar tráfico.

### 3.3 `tv_embedded` no existe

El nombre `tv_embedded` (TVHTML5EMBEDDEDPLAYER) fue retirado de yt-dlp. Sin
traducción, yt-dlp solo emite *"Skipping unsupported client"* y **gasta una
request de red** repitiendo la extracción por defecto.

`LEGACY_CLIENT_ALIASES` lo traduce a **`tv_downgraded`** (TVHTML5 degradado):
el cliente de TV embebido vigente y el único de la familia que **no exige PO
token**. (`tv_simply` pertenece a la familia TV pero **sí** lo exige para
DASH/HTTPS, por lo que sus formatos se descartan sin token.)

---

## 4. Capa 2 — sesión automática del navegador

### 4.1 Sesión vinculada sin intervención del usuario

El objetivo es que el usuario **nunca** tenga que cargar un `cookies.txt`. La
app detecta sola el navegador con **perfil activo** y aplica
`cookiesfrombrowser` de forma silenciosa.

`src/infrastructure/adapters/platforms/browser_detector.py`:

| pieza | qué hace |
|-------|----------|
| `SESSION_BROWSER_ORDER` | orden de prioridad: **Chrome → Brave → Edge → Firefox** |
| `detect_browser_sessions()` | recorre los navegadores y sus perfiles, y devuelve las sesiones con almacén de cookies |
| `detect_active_browser_session()` | elige la mejor: por orden de navegador, luego perfil activo, y a igualdad el de almacén **legible** |

Perfil activo:

- **Chromium** (Chrome/Brave/Edge): `Local State` → `profile.last_used`, con
  reserva en `Default` y `Profile N`. El almacén es `<perfil>/Network/Cookies`.
- **Firefox**: `profiles.ini` → sección marcada `Default=1`. El almacén es
  `Profiles/<perfil>/cookies.sqlite`.

El perfil se le pasa a yt-dlp explícitamente (`cookiesfrombrowser=(navegador,
perfil)`) para que no elija otro por su cuenta.

Prioridad de las cookies (adapter y motor de descarga comparten la misma):

```
cookies.txt del usuario  >  navegador configurado  >  sesión automática
```

### 4.2 El límite real de Windows: el navegador abierto

En Windows, los navegadores Chromium (Chrome, Brave, Edge) mantienen su base
de cookies **exclusivamente bloqueada** mientras están abiertos: `CreateFile`
devuelve `WinError 32` y yt-dlp falla con *"Could not copy Chrome cookie
database"*. Se comprobó que ni siquiera la API de respaldo de Windows
(`BackupRead`) permite saltarse el bloqueo.

Por eso la detección **mide la legibilidad** del almacén antes de usarlo:

| estado | qué hace la app |
|--------|-----------------|
| almacén legible (navegador cerrado) | aplica `cookiesfrombrowser` y usa la lista de clientes autenticada |
| almacén bloqueado (navegador abierto) | sigue en vía anónima, degrada a calidades públicas y **avisa** de que se cierre el navegador |
| sin navegador con perfil activo | sigue en vía anónima y avisa |

Firefox no sufre este bloqueo (SQLite permite lectores concurrentes), así que
su almacén suele ser legible incluso con el navegador abierto.

### 4.3 El aviso en la interfaz

El banner *"¿Esperabas calidades superiores (720p, 1080p, 4K)? … Cargar
cookies.txt"* se sustituyó por un **indicador de estado de sesión**:

| estado | texto en la vista | botón `cookies.txt` |
|--------|-------------------|---------------------|
| `LINKED` | 🔗 Sesión vinculada automáticamente desde Chrome (perfil Default). Se están usando las calidades de tu sesión. | oculto |
| `BLOCKED` | ⚠ No se pudo vincular la sesión de Chrome (perfil Default): el navegador está abierto y Windows bloquea su almacén de cookies. Ciérralo por completo… | visible (último recurso) |
| `UNAVAILABLE` | ℹ No se encontró ningún navegador con sesión activa: se muestran las calidades públicas… | visible (último recurso) |

El estado viaja desde la infraestructura hasta la vista en el value object
`src/domain/value_objects/session_status.py` (`SessionStatus` + `SessionState`),
que `MediaMetadata` expone como `session_status`.

### 4.4 Runtime JS

Los retos de firma (n-token) de YouTube solo se resuelven con un runtime
JavaScript. `src/infrastructure/adapters/media/js_runtime_detector.py` detecta
`deno`, `node`, `quickjs` (binario `qjs`) y `bun`, y **valida la versión** de
cada uno contra el mínimo que exige yt-dlp (node ≥ 22, deno ≥ 2.3, quickjs ≥
2023.12.9, bun ≥ 1.2.11): un runtime demasiado antiguo hace fallar el reto y
con él se pierden las calidades altas.

---

## 5. Coherencia análisis ↔ descarga

La calidad que el análisis promete es la que la descarga puede bajar. Por eso
la política vive en **un solo sitio**
(`src/infrastructure/adapters/platforms/youtube_client_strategy.py`) y la
consumen tanto el adaptador de análisis como el motor de descarga:

| consumidor                       | `player_client` (sin sesión) | `player_client` (con sesión) | `player_skip` |
|----------------------------------|------------------------------|------------------------------|---------------|
| `BasePlatformAdapter` (análisis) | `ANONYMOUS_FALLBACK_CLIENTS` | `AUTHENTICATED_FALLBACK_CLIENTS` | `[]` |
| `YtDlpDownloadEngine` (descarga) | idem                          | idem                          | `[]` |
| `YtDlpDownloadEngine` (sondeo)   | idem                          | idem                          | `[]` |

La clase base es **agnóstica de plataforma**: solo aplica `player_client` cuando
la estrategia lo pide. La política completa (`player_skip`, PO token,
`visitor_data`) la aplica `YouTubeAdapter`, para no colar un bloque
`extractor_args` de YouTube en TikTok, Instagram, etc.

El merge con FFmpeg ya existía: `bestvideo+bestaudio` + `merge_output_format=mp4`.
Lo que faltaba era que el análisis entregara el ladder completo; con
`web_embedded` sin `player_skip` se obtiene **video DASH + audio separados**
(4 pistas de audio) y la tabla lista 720p, 1080p, 1440p y 2160p.

---

## 6. Verificación

Reproducir el diagnóstico (sonda de una sola vez, sin tocar la app):

```python
import yt_dlp
opts = {
    "quiet": True, "skip_download": True, "format": "all",
    "remote_components": ["ejs:github"],
    "js_runtimes": {"node": {"path": r"C:\Program Files\nodejs\node.exe"}},
    "extractor_args": {"youtube": {
        "player_client": ["web_embedded", "ios", "android", "web"],
    }},
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/watch?v=TR3Vdo5etCQ", download=False)

heights = sorted({f["height"] for f in info["formats"] if f.get("height")})
print(heights)          # [144, 240, 360, 480, 720, 1080, 1440, 2160]
```

> **Node.js es necesario.** Los clientes con `REQUIRE_JS_PLAYER`
> (`web_embedded`, `web`, `web_creator`) necesitan el solver EJS. La app lo
> detecta (`js_runtime_detector`) y descarga el solver desde
> `remote_components: ["ejs:github"]`.

Pruebas automatizadas del contrato:

- `tests/unit/infrastructure/test_youtube_native_fallback.py` (política de clientes y `player_skip`).
- `tests/unit/infrastructure/test_analysis_cookie_fallback.py` (reintento con sesión).
- `tests/unit/infrastructure/test_browser_session.py` (detección de sesión).
- `tests/unit/infrastructure/test_session_status_ui.py` (indicador de la vista).

---

## 7. Referencia en el código

| Elemento | Ubicación |
|----------|-----------|
| Política compartida | `src/infrastructure/adapters/platforms/youtube_client_strategy.py` |
| Aplicación en análisis | `src/infrastructure/adapters/platforms/youtube_adapter.py::_build_ydl_opts` |
| Escalera de estrategias | `src/infrastructure/adapters/platforms/base_platform_adapter.py::CLIENT_STRATEGIES` |
| Sesión automática | `src/infrastructure/adapters/platforms/base_platform_adapter.py::_resolve_cookie_source` / `_client_strategies` |
| Detección de sesión | `src/infrastructure/adapters/platforms/browser_detector.py::detect_active_browser_session` |
| Runtime JS | `src/infrastructure/adapters/media/js_runtime_detector.py::detect_js_runtimes` |
| Estado de sesión (dominio) | `src/domain/value_objects/session_status.py` |
| Indicador en la vista | `src/presentation/views/inicio_view.py::_session_hint_text` |
| Clasificación de errores | `src/domain/services/error_classifier.py::ErrorClassifier` |
| Aplicación en descarga | `src/infrastructure/adapters/download/ytdlp_download_engine.py::_apply_clients` |
| Contrato (pruebas) | `tests/unit/infrastructure/test_youtube_native_fallback.py` · `test_analysis_cookie_fallback.py` · `test_browser_session.py` · `test_session_status_ui.py` |
