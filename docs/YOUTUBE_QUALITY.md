# Calidad de YouTube: por qué la app solo ofrecía 360p y cómo se resuelve

Este documento explica el diagnóstico del problema "**en visita anónima YouTube
solo devuelve 360p**" (caso real: *No Doubt - Don't Speak (Official 4K Music
Video)*, `TR3Vdo5etCQ`) y la solución de dos capas implementada en
`osvaldoDownloaderPro`.

---

## 1. Síntoma

Al analizar un video musical en 4K sin sesión iniciada, el panel de calidades
mostraba como máximo **360p**, acompañado de storyboards (`sb0`–`sb3`). El
ladder observado en sandbox fue exactamente:

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
| `web_creator`  | WEB_CREATOR          | sí      | REQ   | REQ  | rec  | sí          |
| `web_embedded` | WEB_EMBEDDED_PLAYER  | sí      | **no** | **no** | **no** | sí    |
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

## 3. Capa 1 — sin cookies (implementada)

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
   Un bot-check en `ios` no impide que `tv_downgraded` aporte sus formatos.
2. **Los formatos de todos los clientes se fusionan**, así que el resultado es
   la unión, no el último en ganar.

Configuración enviada por la app:

```python
"extractor_args": {
    "youtube": {
        "player_client": ["ios", "tv_downgraded", "tv_simply", "web"],
        "player_skip": ["webpage", "configs"],
    }
}
```

- `ios` — no exige PO token para DASH (video-only de alta resolución).
- `tv_downgraded` — TVHTML5; **no exige PO token en ningún protocolo**.
- `tv_simply` — TVHTML5_SIMPLY; rinde al máximo cuando hay PO token.
- `web` — cierre, tal como en la configuración original.

### 3.2 `player_skip`: evitar la vía degradada

`player_skip` es un `extractor_arg` **válido** en yt-dlp 2026.x (el namespace
es `youtube`, se lee con `self._configuration_arg('player_skip')`). Valores
reconocidos: `webpage`, `configs`, `js`, `initial_data`.

| valor          | efecto en yt-dlp                                              | por qué lo usamos |
|----------------|---------------------------------------------------------------|-------------------|
| `webpage`      | no descarga la página inicial (`_video.py:3808`)              | es la petición que dispara el bot-check / age-gate que degrada a 360p |
| `configs`      | no descarga el `ytcfg` de cada cliente no-web (`_video.py:3065`) | una request menos por cliente ⇒ menos riesgo de HTTP 429 |
| `js`           | no descarga el player JS                                       | **no** se usa: los clientes con `REQUIRE_JS_PLAYER` lo necesitan |
| `initial_data` | no extrae el initial data                                      | no aporta nada aquí |

El propio yt-dlp usa `player_skip: ['webpage']` en su suite de pruebas
(`_video.py:1518-1522`).

> **Los saltos solo se aplican en la vía anónima.** Con cookies, la página
> inicial aporta el `player_response` y el `visitor_data` de mayor calidad:
> saltarla solo empeoraría el resultado.

### 3.3 `tv_embedded` no existe

El nombre `tv_embedded` (TVHTML5EMBEDDEDPLAYER) fue retirado de yt-dlp. Sin
traducción, yt-dlp solo emite *"Skipping unsupported client"* y **gasta una
request de red** repitiendo la extracción por defecto.

`LEGACY_CLIENT_ALIASES` lo traduce a **`tv_downgraded`** (TVHTML5 degradado):
el cliente de TV embebido vigente y el único de la familia que **no exige PO
token**. (`tv_simply` pertenece a la familia TV pero **sí** lo exige para
DASH/HTTPS, por lo que sus formatos se descartan sin token.)

Resultado: la configuración literal `["ios", "tv_embedded", "web"]` se
materializa como `["ios", "tv_downgraded", "web"]`.

---

## 4. Capa 2 — con cookies (implementada)

Cuando la IP está marcada por YouTube (HTTP 429 + *"Sign in to confirm you're
not a bot"*), **ninguna** configuración de clientes funciona: es un bloqueo a
nivel de IP, no de protocolo. En sandbox, desde una IP marcada, 10 de 11
combinaciones de cliente fallaron con bot-check y la única que respondió
(`web_safari`/`mweb`) devolvió precisamente el ladder de 360p.

Contra ese bloqueo solo cabe una cosa: **hablar con una sesión iniciada**. Por
eso la Capa 2 usa cookies, y por eso la Capa 1 (sin cookies) nunca llegará a
1080p/4K desde una IP marcada.

### 4.1 Reintento automático del análisis con la sesión del navegador

El motor de descarga ya reintentaba con el navegador detectado cuando el error
era recuperable con cookies; el **análisis no lo hacía**. Ese era el único
hueco: un bot-check o un age-gate bloqueaban el análisis aunque el usuario
tuviera la sesión abierta en Chrome.

Ahora `BasePlatformAdapter` aplica la misma lógica en el análisis
(`_extract_with_ytdlp`) y en el análisis de listas (`analyze_playlist`):

```
pasada 1  estrategias de cliente con la configuración de cookies actual
   ↓  falla con un error recuperable con cookies y NO hay cookies configuradas
pasada 2  misma estrategia con cookiesfrombrowser=(navegador detectado)
   ↓  el navegador está abierto y su almacén no se puede leer
pasada 3  degradación: se reintenta sin cookies (calidades públicas + aviso)
```

Reglas que rigen el reintento:

| regla | por qué |
|-------|---------|
| solo si el error es **recuperable con cookies** | "Video unavailable" no se arregla con una sesión: no se gasta una request de red extra |
| solo si **no hay ninguna cookie configurada** | si el usuario ya eligió su sesión (`cookiefile` o `cookies_from_browser`), no se le cambia a escondidas |
| solo la **primera estrategia** (`COOKIE_RETRY_STRATEGIES = 1`) | es el fallback nativo multi-cliente; si el bloqueo es de IP, ningún cliente lo resuelve y repetir la escalera solo multiplica la espera |
| la clasificación **no se reimplementa** | se reutiliza `ErrorClassifier.classify(...).is_cookie_recoverable` (dominio), el mismo que usa el motor de descarga |

### 4.2 Cuando el navegador está abierto

En Windows, leer el almacén de cookies de Chrome/Edge con el navegador
**abierto** falla por DPAPI. La app no se queda sin contenido: degrada a las
calidades públicas y lo avisa.

```
No se pudieron leer las cookies de 'chrome' (el navegador está abierto en Windows).
Se muestran calidades públicas. Cierra el navegador por completo o utiliza un
archivo cookies.txt para desbloquear 1080p y 4K.
```

### 4.3 Lo que ya hacía la app

- Botón rápido de `cookies.txt` en Inicio (alcance por adaptador:
  `PlatformRegistry.set_cookie_file_scoped`).
- Navegador de cookies global (`cookiesfrombrowser`) en Configuración →
  Avanzado (Sesión y Cookies).
- Con cookies, `player_skip` **no** se aplica: se conserva la página inicial,
  que aporta el `player_response` y el `visitor_data` de mayor calidad.

---

## 5. Coherencia análisis ↔ descarga

La calidad que el análisis promete es la que la descarga puede bajar. Por eso
la política vive en **un solo sitio**
(`src/infrastructure/adapters/platforms/youtube_client_strategy.py`) y la
consumen tanto el adaptador de análisis como el motor de descarga:

| consumidor                       | `player_client`                  | `player_skip`          |
|----------------------------------|----------------------------------|------------------------|
| `BasePlatformAdapter` (análisis) | `CLIENT_STRATEGIES[0]` (nativo)  | `["webpage", "configs"]` |
| `YtDlpDownloadEngine` (descarga) | `DOWNLOAD_CLIENT_STRATEGIES[0]`  | `["webpage", "configs"]` |
| `YtDlpDownloadEngine` (sondeo)   | `PROBE_CLIENT_STRATEGIES[0]`     | `["webpage", "configs"]` |

La clase base es **agnóstica de plataforma**: solo aplica `player_client` cuando
la estrategia lo pide. La política completa (`player_skip`, PO token,
`visitor_data`) la aplica `YouTubeAdapter`, para no colar un bloque
`extractor_args` de YouTube en TikTok, Instagram, etc.

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
        "player_client": ["ios", "tv_downgraded", "tv_simply", "web"],
        "player_skip": ["webpage", "configs"],
    }},
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info("https://www.youtube.com/watch?v=TR3Vdo5etCQ", download=False)

heights = sorted({f["height"] for f in info["formats"] if f.get("height")})
print(heights)          # el ladder real que devuelve YouTube
```

> **Node.js es necesario.** Los clientes con `REQUIRE_JS_PLAYER` (`tv`,
> `tv_downgraded`, `web`) necesitan el solver EJS. La app ya lo detecta
> (`js_runtimes`: node en `shutil.which` y en las rutas de `Program Files`,
> deno como alternativa) y descarga el solver desde
> `remote_components: ["ejs:github"]`.

Pruebas automatizadas del contrato: `tests/unit/infrastructure/test_youtube_native_fallback.py`
(Capa 1) y `tests/unit/infrastructure/test_analysis_cookie_fallback.py` (Capa 2).

---

## 7. Referencia en el código

| Elemento | Ubicación |
|----------|-----------|
| Política compartida | `src/infrastructure/adapters/platforms/youtube_client_strategy.py` |
| Aplicación en análisis | `src/infrastructure/adapters/platforms/youtube_adapter.py::_build_ydl_opts` |
| Escalera de estrategias | `src/infrastructure/adapters/platforms/base_platform_adapter.py::CLIENT_STRATEGIES` |
| Capa 2 (cookies automáticas) | `src/infrastructure/adapters/platforms/base_platform_adapter.py::_extract_with_ytdlp` / `_run_strategies` |
| Clasificación de errores | `src/domain/services/error_classifier.py::ErrorClassifier` |
| Detección de navegador | `src/infrastructure/adapters/platforms/browser_detector.py::get_first_available_browser` |
| Aplicación en descarga | `src/infrastructure/adapters/download/ytdlp_download_engine.py::_apply_clients` |
| Contrato (pruebas) | `tests/unit/infrastructure/test_youtube_native_fallback.py` · `tests/unit/infrastructure/test_analysis_cookie_fallback.py` |
