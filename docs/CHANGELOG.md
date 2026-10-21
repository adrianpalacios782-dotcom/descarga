# osvaldoDownloaderPro — Historial de Cambios (Changelog)

Todos los cambios notables realizados en este proyecto se documentan en este archivo.

## [1.5.4] - 2026-10-21

### Añadido
- **CI y publicación automatizada en GitHub Actions:**
  - `.github/workflows/ci.yml`: gate de calidad (ruff + mypy `--strict` + pytest) en cada push y PR a `main`.
  - `.github/workflows/release.yml`: pipeline de 3 jobs (`quality` → `build` → `publish`) que compila el instalador en `windows-latest`, **verifica que existan los dos assets obligatorios** (`osvaldoDownloaderPro-<version>-Setup.exe` y `SHA256SUMS.txt`) y publica la release comprobando por API que los assets quedaron disponibles. La release v1.5.3 quedó vacía justamente porque no existía este automatismo.
  - Descarga automática de `ffmpeg.exe`/`ffprobe.exe` en el runner (están en `.gitignore` por ser binarios de terceros).
- **Documentación de firma Authenticode** (`docs/SIGNING.md`): configuración de `scripts\signing.config.json` con certificado real (almac de Windows o PFX) y flujo de autofirmado de pruebas para desarrollo local.
- **Documentación de limpieza segura** (`docs/CLEANUP.md`): comandos de respaldo, verificación y borrado del prototipo `YTDownloaderPro` y de los repositorios externos con cambios sin commitear.

### Corregido
- **Adaptador de TikTok:** `TikTokAdapter._build_ydl_opts()` reconstruía el bloque de opciones de yt-dlp desde cero y perdía `remote_components` (solver EJS), `js_runtimes` (Node/Deno) y `ffmpeg_location`. Ahora llama a `super()` y solo añade encima los encabezados `Referer`/`Origin` de TikTok.
- **Las cookies rápidas ya no borran el navegador global:** `apply_settings` es ahora semántico de **presencia** (solo toca las claves presentes en el diccionario). Antes, el botón de `cookies.txt` de Inicio llamaba `apply_settings({"cookies_file": path})`, lo que terminaba en `set_cookies_from_browser(None)` y vaciaba el navegador de cookies en el motor de descargas y en los 7 adaptadores durante toda la sesión.
- **Clientes de YouTube `ios` y TV embebido:** se integran `ios` y `tv_simply` en `CLIENT_STRATEGIES`. El parche heredado usaba `tv_embedded`, nombre que **ya no existe** en yt-dlp 2026.x: se descartaba con un warning y consumía una request sin obtener nada. Ahora el adaptador consulta `INNERTUBE_CLIENTS` y filtra los clientes no soportados antes de llamar a yt-dlp.

### Optimizado
- **PO Token y Visitor Data funcionales:** ambas credenciales de sesión de YouTube estaban declaradas en el constructor pero nunca se usaban. `YouTubeAdapter` las inyecta ahora como `extractor_args` (formato `CLIENT.CONTEXT+TOKEN`), que es donde yt-dlp las lee.
- **`scripts\build_release.ps1`:** busca `ISCC.exe` en varias rutas (LOCALAPPDATA, `Program Files (x86)`, `Program Files`) para funcionar también en el runner de Actions, y elimina los instaladores de versiones anteriores (12 `Setup.exe` obsoletos = 1.4 GB acumulados).
- **`scripts\publish_release.ps1`:** nuevo parámetro `-Repo` (lo usa el workflow) y notas de uso actualizadas.
- **`pyproject.toml`:** PyInstaller entra en el extra `dev` (necesario para compilar en CI).

### Calidad
- 701 pruebas automatizadas en verde (26 nuevas), `ruff` sin errores y `mypy --strict` sin errores en 110 archivos fuente.
- Workflow de CI ejecutado en GitHub Actions: `Lint + tipos + tests` en verde.
- **Timeouts flaky en el job `quality` del workflow de Release (corregidos):** `tests/integration/test_download_engine.py` parcheaba `time.sleep` sobre el **módulo `time` completo** y nunca lo restauraba. El parche sobrevivía al test y convertía el sondeo de `_wait_for` en un *busy-wait* que saturaba una CPU y robaba tiempo de CPU al hilo de descarga; con un presupuesto de espera de 8 s, en un runner de 2 vCPU (57 s de suite frente a 31 s en local) los dos tests de descarga expiraban. No era un fallo funcional del motor: el mismo commit pasó el job de CI y falló el de Release. Ahora `time.sleep` se parchea con `monkeypatch` (se revierte al terminar el test), `_wait_for` espera con `threading.Event.wait()` (bloqueo real del SO, sin busy-wait) y `time.monotonic()`, el presupuesto sube a 30 s, y un fixture autouse en `tests/conftest.py` restaura `time.sleep` tras cada test como red de seguridad. Se añade `tests/unit/test_test_hygiene.py` como test de regresión del antipatrón.
- El job `quality` de `release.yml` queda **idéntico** al de `ci.yml` (Node + gate de coherencia de versión) para que ambos no diverjan, y ambos workflows ejecutan pytest con `--durations=10` para poder diagnosticar cualquier futura caída.

## [1.5.3] - 2026-10-20

### Añadido
- **Desbloqueo rápido de calidades con `cookies.txt`:** nuevo botón en `InicioView` para seleccionar un archivo `cookies.txt` y re-analizar la URL al instante, sin salir de la pantalla de inicio. Persiste el ajuste y lo aplica en caliente a los adaptadores.
- **Aviso de bloqueo de cookies del navegador:** cuando en Windows no se pueden leer las cookies de Chrome/Edge (navegador abierto), la app lo comunica con un mensaje explícito y ofrece cargar un `cookies.txt` como alternativa.
- **Soporte de cookies en TikTok:** `TikTokAdapter` envía `cookiefile` o `cookiesfrombrowser`, más los encabezados `Referer`/`Origin`, para reducir bloqueos y recuperar todas las calidades.

### Corregido
- **Tema claro:** `QPlainTextEdit` y `QTextEdit` respetan la paleta del tema y ya no muestran fondo oscuro en modo claro.

### Calidad
- Sincronización de versión entre `src/__init__.py`, `scripts/version_info.txt`, `installer.iss` y `README.md` (el build de releaseaba de forma abortada por desincronización).
- Hook `pre-push` versionado en `.githooks/` que muestra el destino del push, y `LOCAL-SETUP.md` documentando la carpeta canónica local.

## [1.5.2] - 2026-10-19

### Optimizado y Mejorado
- **Optimización de formatos YouTube (Anti-Bot / SABR / EJS):**
  - Integración nativa de Node.js y ejecutor JavaScript EJS (`yt-dlp-ejs>=0.8.0`) con `remote_components = ["ejs:github"]` para solventar los retos antibot y de firma `n-challenge` de YouTube a velocidad nativa.
  - Inyección automática y robusta de la ubicación de FFmpeg (`ffmpeg_location`) en `BasePlatformAdapter` y `YtDlpDownloadEngine`, asegurando la disponibilidad del procesador para combinar pistas DASH (1080p, 1440p, 4K) y audio.
  - Blindaje en la normalización de formatos de video para soportar flujos con atributos de altura nulos sin degradación.
  - Detección preventiva de restricciones anónimas de YouTube (videos limitados a 360p) con banner informativo contextual en `InicioView`.
- **Armonización de interfaz y documentación:**
  - Consistencia en el nombre de la sección de ajustes de sesión: `Avanzado (Sesión y Cookies)` tanto en la interfaz gráfica como en los mensajes descriptivos.
  - Nueva documentación completa en `docs/COOKIES.md` explicando cómo exportar cookies de sesión con la extensión segura `Get cookies.txt LOCALLY` para desbloquear 1080p, 4K y 60 FPS en videos protegidos.

## [1.5.1] - 2026-10-13

### Corregido
- **Cierre ordenado de la cola de descargas:** nuevo `DownloadQueueManager.shutdown()` que cancela las tareas activas y en cola, se desuscribe del bus de eventos y espera al `QThreadPool`, invocado desde `main.py` antes de cerrar la base de datos. Evita que la aplicación quede bloqueada al salir durante una descarga.
- **Carga de miniaturas sin hilos residuales:** el cargador de miniaturas rastrea sus hilos de trabajo (con liberación vía `atexit`), eliminando hilos de red vivos al terminar el proceso que podían causar un fallo nativo en Windows.

### Añadido
- **Configuración global de pruebas (`tests/conftest.py`):** crea el directorio temporal requerido por `--basetemp`, comparte una única `QApplication` de sesión con limpieza ordenada de widgets y neutraliza la red, permitiendo ejecutar la suite en un clon limpio sin errores ni fallos al finalizar el intérprete.

### Calidad
- `ruff` y `mypy --strict` sin errores (110 archivos fuente). 675 pruebas automatizadas en verde.
- Limpieza de imports no usados y de un test duplicado.

## [1.4.0] - 2026-09-07

### Añadido & Optimizado (Recorte de Tiempo en Vivo y Descarga por Segmentos - Lossless Time-Clipper)
- **Recorte de Tiempo en Vivo y Descarga por Segmentos (Lossless Time-Clipper):**
  - Permite recortar y descargar exclusivamente intervalos específicos de tiempo (ej. de 01:25 a 03:40) sin descargar archivos multimedia completos de horas o gigabytes.
  - Value Object inmutable `TimeRange` en el dominio con propiedades `duration`, `to_section_spec()` (`*HH:MM:SS-HH:MM:SS`), `format_range()` e invariantes matemáticas estrictas.
  - Aceleración en `YtDlpDownloadEngine` mediante `download_ranges` de yt-dlp y precisión de keyframes FFmpeg (`force_keyframes_at_cuts = True`).
  - Nuevo caso de uso `DownloadMediaUseCase` y entidad `DownloadRequest` desacoplada para parametrización flexible en la capa de aplicación.
  - Componente PySide6 interactivo `TimeRangeSelectorWidget` integrado en `InicioView` con slider dual interactivo (`DualRangeSlider`), chips de presets rápidos (`Primer minuto`, `Últimos 30s`, `Clip de 1 min`, `Restablecer todo`), duración calculada en tiempo real y validación visual inline.
  - 100% de sincronización con los temas visuales (Oscuro Multimedia, Oscuro OLED y Claro Moderno) vía `get_current_palette()`.

## [1.3.0] - 2026-09-07

### Añadido & Optimizado (Modernización y Expansión Integral)
- **Expansión Universal de Plataformas y Modo Genérico Seguro:**
  - Reconocimiento nativo y badges dedicados para **X / Twitter** (`x.com`, `twitter.com`, `t.co`), **Reddit** (`reddit.com`, `v.redd.it`), **Vimeo** (`vimeo.com`), **SoundCloud** (`soundcloud.com`), **Pinterest** (`pinterest.com`, `pin.it`), **Dailymotion** (`dailymotion.com`, `dai.ly`), **Bilibili** (`bilibili.com`, `b23.tv`), **Bluesky** (`bsky.app`), y **Threads** (`threads.net`).
  - Modo `Generic` seguro que permite analizar y descargar desde cualquier sitio web público compatible con yt-dlp.
  - Blindaje estricto anti-SSRF: bloqueo de localhost, direcciones privadas RFC 1918, loopback, redes link-local (`169.254.x.x`), rangos reservados, multicast, puertos peligrosos y TLDs internos reservados (`.local`, `.internal`, `.lan`, etc.).
  - `GenericAdapter` mejorado para inferir dinámicamente el nombre de plataforma y extractor de yt-dlp.
- **Resiliencia en Persistencia SQLite y Paginación:**
  - Sustitución de `INNER JOIN format_options` por `LEFT JOIN format_options` en `SqliteDownloadRepository`, garantizando que ninguna tarea histórica quede oculta por discrepancias menores de formato.
  - Nuevos métodos `get_paginated(limit, offset, search_query, platform_filter, order_by, descending)` y `count()` con consultas 100% parametrizadas y ordenamiento validado contra lista blanca.
- **Sincronización Completa del Sistema de Temas (Claro / Oscuro / OLED):**
  - Refactorización de `ThumbnailLabel` (`thumbnail_loader.py`) sustituyendo colores hexadecimales oscuros hardcodeados por tokens dinámicos de `get_current_palette()`.
  - Conexión reactiva en `ThumbnailLabel.changeEvent` para redibujado instantáneo al conmutar entre Claro Moderno, Oscuro Multimedia y Oscuro OLED.
  - Eliminación de estilos forzados en `PlaylistDownloadDialog`, `BatchDownloadDialog`, `UpdateDialog` y menús contextuales (`QMenu`), permitiendo herencia pura de los tokens de diseño.
- **Rendimiento de Descargas y Drag & Drop Intuitivo:**
  - Configuración de fragmentos concurrentes DASH/HLS (1 a 8 fragmentos, por defecto 4) en `ConfiguracionView` y `YtDlpDownloadEngine`, persistida en `SettingsRepository`.
  - Soporte para Drag & Drop (arrastrar y soltar) tanto de URLs individuales como de archivos `.txt` masivos directamente sobre `InicioView` y `MainWindow` con retroalimentación visual en tiempo real.

## [1.2.2] - 2026-09-07

### Añadido & Optimizado
- **Tema Claro (Claro Moderno):**
  - Soporte completo y nativo para modo claro con paleta de alto contraste `#F8FAFC`, superficies `#FFFFFF` y tipografía nítida `#0F172A`.
  - Conmutación instantánea y vista previa en tiempo real al seleccionar el tema en la sección Apariencia.
- **Persistencia y Sincronización Global del Tema:**
  - Carga transparente del tema configurado al iniciar la aplicación y propagación reactiva en todas las vistas y componentes.

## [1.2.1] - 2026-09-07

### Corregido & Optimizado
- **Escalado y Diseño Visual de la Interfaz:**
  - Integración de `QScrollArea` elástico en `ConfiguracionView` eliminando la compresión vertical de tarjetas en cualquier resolución de pantalla.
  - Estandarización de alturas (`36px`) y anchos mínimos en selectores (`QComboBox`, `QSpinBox`) para garantizar tipografía nítida y legible.
  - Expansión horizontal al 100% de los campos de ruta de carpetas y archivos de cookies.
- **Rendimiento de Descarga Acelerado:**
  - Descarga concurrente de 4 fragmentos DASH/HLS (`concurrent_fragment_downloads: 4`) en `YtDlpDownloadEngine` para descargas ultrarrápidas en YouTube, Twitch, Kick y TikTok.
  - Buffer de E/S de 64 KB y troceado HTTP de 10 MB optimizado.
- **Manejo de Errores y Robustez:**
  - Corrección de la variable `plat_name` en `BasePlatformAdapter` para avisos de contenido restringido (+18).

## [1.2.0] - 2026-09-07

### Añadido
- **Nuevas Plataformas Soportadas:**
  - **Twitch** (`twitch.tv`, `clips.twitch.tv`): Soporte nativo para clips, directos (VODs) y videos bajo demanda.
  - **Kick** (`kick.com`): Soporte nativo para clips, transmisiones y grabaciones de canales.
  - Insignias de plataforma (Spotlight badges), colores de acento y filtros dedicados en `HistorialView`.
- **Descarga de Playlists y Álbumes:**
  - Detección automática de enlaces de listas de reproducción con `PlaylistMetadata` y `PlaylistEntry`.
  - Diálogo modal interactivo `PlaylistDownloadDialog` con selección masiva/individual de videos, selector de calidad unificado y encolamiento por lotes.
- **Conversor de Audio Profesional con Metadatos ID3 y Carátula:**
  - Nuevos presets avanzados de audio (`MP3 320k`, `MP3 192k`, `FLAC Lossless`, `WAV PCM`, `M4A/AAC`, `OPUS`).
  - Incrustación automática de etiquetas ID3v2 (Título, Artista, Álbum) y carátula oficial en el contenedor de audio final vía FFmpeg.
- **Recortador de Fragmentos por Intervalo de Tiempo:**
  - Objeto de valor `TimeRange` con parseo flexible de marcas de tiempo (`MM:SS`, `HH:MM:SS`).
  - Recorte rápido sin pérdida con fallback a re-codificación precisa para descargar fragmentos específicos (`Desde` / `Hasta`).
- **Limitador de Velocidad de Descarga (Throttling):**
  - Configuración global de ancho de banda en `ConfiguracionView` (`Sin límite`, `50 MB/s`, `20 MB/s`, `10 MB/s`, `5 MB/s`, `2 MB/s`, `1 MB/s`, `500 KB/s`) con persistencia en SQLite.
- **Actualizador del Motor yt-dlp en 1 Clic:**
  - Botón de actualización directa del motor en `AcercaDeView` y `ConfiguracionView`.
  - Descarga e instalación atómica de wheel oficial con validación criptográfica SHA-256 e importación dinámica sin reiniciar la aplicación.

---

## [1.1.0] - 2026-08-29

### Añadido
- **Subtítulos y Accesibilidad:** Detección automática de pistas de subtítulos manuales y autogeneradas con `SubtitleTrack`. Opciones de incrustación directa en el video vía FFmpeg (`FFmpegEmbedSubtitle`) o descarga externa convertida a `.srt`.
- **Descargas Masivas (Batch):** Nuevo diálogo modal `BatchDownloadDialog` con área de texto multilínea e importación de listas `.txt` para encolamiento asíncrono respetando la cola de concurrencia.
- **Sistema de Favoritos:** Persistencia en SQLite (`user_favorites`), botón dinámico de guardado (`♡ Guardar` / `♥ En Favoritos`) y pantalla `FavoritosView` interactiva con descarga en 1 clic.
- **System Tray y Notificaciones:** Integración en segundo plano con `AppTrayIcon`, notificaciones Toast nativas en Windows al finalizar descargas y opción de minimizar a la bandeja al cerrar.
- **Historial Interactivo:** Menú contextual (clic derecho) y doble clic en `HistorialView` con acciones de reproducción local, localización en explorador de Windows, re-descarga y borrado en SQLite.
- **Configuración y Cookies:** Persistencia en SQLite (`user_settings`) e inyección de `--cookies-from-browser` (Chrome, Edge, Firefox, Brave) para contenido protegido o con restricciones de edad.

### Seguridad y Optimización
- **Protección de Archivos en Windows:** Prevención de denegación de servicio por nombres de dispositivo reservados (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) en `filename_sanitizer`.
- **Tipado Estricto y Calidad:** 0 errores en MyPy modo `--strict` sobre 98 módulos y linter Ruff completamente en verde.
- **Suite de Pruebas:** 560 pruebas unitarias, de integración y E2E superadas al 100% con cero advertencias (`ResourceWarning` erradicado).

---

## [1.0.4] - 2026-08-29

### Añadido
- **Identidad de Marca:** Integración del nuevo icono oficial **ODP PRO** (diseño squircle moderno, hexágono cian y flecha de descarga) en el ejecutable (`icon.ico`), instalador y accesos directos.
- **Presentación:** Icono de la marca en la barra de título personalizada y soporte de agrupación en la barra de tareas de Windows (`AppUserModelID`).
- **Instalador:** Accesos directos de escritorio y menú inicio configurados para referenciar directamente `assets\icon.ico`.

---

## [1.0.3] - 2026-08-28

### Mejorado
- **Presentación:** Rediseño integral de la pantalla de análisis y descarga (`InicioView`) con arquitectura modular (`ContentPreviewCard`, `FormatTableHeader`, `FormatTableRow`, `DownloadConfigWidget`).
- **Presentación:** Solucionado el colapso vertical de las filas de formato mediante alturas mínimas garantizadas y contenedor responsive con `QScrollArea`.
- **Formatos:** Nueva tabla estructurada de formatos con columnas técnicas claras (`ELEGIR`, `CALIDAD`, `FORMATO`, `TAMAÑO`, `CÓDEC`, `FPS`, `ESTADO`) y selector circular visible con acento moderno.
- **Configuración de Descarga:** Incorporación del campo para editar y personalizar el nombre de archivo final con sanitización automática para Windows.
- **Descarga:** Botón principal de descarga destacado con feedback inmediato y nota informativa de tamaño aproximado.

---

## [1.0.2] - 2026-08-28

### Corregido
- **Presentación:** Solucionado `SyntaxError` en hoja de estilos QSS (`theme.py`) que impedía la carga de estilos.
- **Motor de Descarga:** Corregido error de desempaquetado de tupla y prevención de borrado accidental de archivo en `_canonicalize_final_path`.
- **Presentación:** Restaurada la preservación del título real del video en los archivos descargados (`_build_video_request`).
- **Concurrencia:** Comunicación asíncrona segura con `Signal` de Qt en la comprobación de FFmpeg (`MainWindow`).
- **Seguridad:** Validación anti-spoofing en detección de plataforma basada exclusivamente en `hostname` de la URL (`Url.detect_platform`).
- **Adaptadores:** Optimización del ciclo de clientes para ejecutar rotación anti-bot únicamente en YouTube, previniendo rate-limiting innecesario en Facebook e Instagram.
- **Infraestructura:** Conexión del namespace de logs de proyecto al archivo rotativo y filtro de datos sensibles (`logger_config.py`).

---

## [1.0.1] - 2026-08-22

### Añadido
- **Presentación:** Rediseño visual integral de la interfaz: sistema de diseño con tokens (`src/presentation/styles/theme.py`), QSS generado por builder y paleta preparada para futuro modo claro.
- **Presentación:** Barra de título personalizada (frameless) con controles minimizar/maximizar/cerrar y arrastre nativo de ventana.
- **Presentación:** Sidebar rediseñado con grupos PRINCIPAL / BIBLIOTECA / SISTEMA, etiquetas de sección y pie con la versión.
- **Presentación:** Inicio renovado: héroe "¿Qué quieres descargar?", campo URL grande con botón Pegar, validación en línea, banner de enlace del portapapeles y microinteracciones.
- **Presentación:** Descargas con tarjetas modernas, velocidad destacada y estado vacío elegante; Historial, Favoritos, Configuración y Acerca de pulidos.
- **Testing:** Suite ampliada a 349 pruebas (incluye 8 nuevas para el sistema visual).

### Corregido
- Estado de descarga fallida ahora se muestra como "Error".
- Diálogo de actualización unificado al sistema de tokens.

---

## [1.0.0] - 2026-08-12

### Añadido
- **Dominio:** Entidades `VideoFormat`, `AudioFormat`, `FormatOption` y enum `DownloadType`.
- **Dominio:** Servicio de dominio `FormatNormalizer` para filtrado estricto de storyboards, MHTML, thumbnails y duplicados.
- **Presentación:** Rediseño completo UX/UI estilo reproductor multimedia oscuro inspirado en aplicaciones modernas (tipo Spotify, fondos oscuros `#121212`, acentos `#1db954`, cero emojis).
- **Presentación:** Selector dinámico de modo `[ VIDEO ]` vs `[ AUDIO ]` en `InicioView`.
- **Presentación:** Análisis de URLs asíncrono en segundo plano (`threading.Thread`) evitando bloqueos de la GUI ("No responde").
- **Infraestructura:** Integración de `"noplaylist": True` y `"socket_timeout": 10` en `BasePlatformAdapter` para prevenir congelamientos con listas/mixes de YouTube.
- **Testing:** 50 pruebas pasadas en pytest para Dominio, Aplicación, Infraestructura, Integración y GUI.

### Corregido
- Eliminación total de formatos basura `storyboard MHTML 0fps` y duplicados en el selector.
- Eliminación de avisos `RuntimeWarning` sobre corrutinas de asyncio no esperadas.
- Solución al error `ModuleNotFoundError: No module named 'src'` al ejecutar `python src/main.py`.
