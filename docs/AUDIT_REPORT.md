# osvaldoDownloaderPro — INFORME DE AUDITORÍA INTEGRAL DE ARQUITECTURA Y CÓDIGO

**Proyecto:** osvaldoDownloaderPro  
**Versión:** 1.1.0 BETA  
**Fecha:** 29 de Agosto de 2026  
**Estado del Informe:** FASE 1 — Auditoría y Saneamiento Completo Finalizado  
**Independencia:** 100% Independiente  

---

## 1. RESUMEN DE AUDITORÍA

Se ha realizado una inspección exhaustiva de la totalidad del árbol de código fuente, modelo de dominio, casos de uso de la capa de aplicación, adaptadores de infraestructura (yt-dlp, FFmpeg sidecar, SQLite WAL, EventBus, actualizador GitHub Releases), capa de presentación (PySide6 / Qt6) y la suite de pruebas unitarias, de integración y E2E.

A continuación se detalla la matriz de auditoría técnica con la taxonomía de problemas detectados, su causa raíz, impacto, solución aplicada y estado.

---

## 2. MATRIZ DE HALLAZGOS Y AUDITORÍA

| ID | Problema | Causa Raíz | Archivo Afectado | Impacto | Solución Propuesta | Prioridad | Estado |
|---|---|---|---|---|---|---|---|
| **AUD-001** | Formatos auxiliares de previsualización (`storyboard`, `MHTML`) mostrándose en el selector de la UI. | Ingesta cruda de la lista `info["formats"]` de `yt-dlp` sin filtro en capa de dominio. | `src/infrastructure/adapters/platforms/base_platform_adapter.py` | **ALTO** — Muestra opciones no descargables al usuario. | Crear `FormatNormalizer` en Dominio para excluir storyboards, MHTML, thumbnails y codecs nulos. | **ALTA** | **RESUELTO** |
| **AUD-002** | Mezcla de opciones de Video y Audio en un único combo box. | Entidad `FormatOption` sin distinción entre flujos de Video y flujos de Audio. | `src/domain/entities/format_option.py` | **ALTO** — Confusión en la UX al seleccionar audio. | Implementar las entidades `VideoFormat`, `AudioFormat`, `DownloadType` y paneles dedicados en la UI. | **ALTA** | **RESUELTO** |
| **AUD-003** | Congelamiento de la ventana principal ("No responde") al analizar URLs de red. | Ejecución síncrona de `AnalyzeUrlUseCase.execute()` sobre el Hilo Principal de la GUI de PySide6. | `src/presentation/view_models/main_view_model.py` | **CRÍTICO** — Bloquea el event loop de Qt y causa cuelgues en Windows. | Ejecutar el análisis en un hilo secundario asíncrono (`threading.Thread`) con emisión thread-safe de señales Qt. | **CRÍTICA** | **RESUELTO** |
| **AUD-004** | Bloqueo o demora excesiva al analizar enlaces con listas de reproducción (`list=...`). | Ausencia del parámetro `"noplaylist": True` en la configuración de `yt-dlp`. | `src/infrastructure/adapters/platforms/base_platform_adapter.py` | **ALTO** — `yt-dlp` intentaba parsear iterativamente listas completas de 50+ ítems. | Configurar `"noplaylist": True`, `"socket_timeout": 10` y sanitizar URLs de video en Dominio (`UrlSanitizer`). | **ALTA** | **RESUELTO** |
| **AUD-005** | Uso de emojis en la interfaz gráfica (`🏠`, `📥`, `⭐`, `⚙️`). | Diseño inicial prototípico con caracteres Unicode emojis como iconos principales. | `src/presentation/components/sidebar.py`, `src/presentation/views/` | **MEDIO** — Apariencia informal no profesional. | Sustituir emojis por iconos vectoriales trazados con QPainter y diseño visual oscuro Studio Desktop con tokens. | **MEDIA** | **RESUELTO** |
| **AUD-006** | Excepción no capturada en consola sobre corrutinas de asyncio no esperadas. | Invocación de `asyncio.create_task()` sin event loop activo en el hilo de la GUI. | `src/presentation/main_window.py` | **MEDIO** — Genera advertencias RuntimeWarning en pytest y consola. | Migrar a verificación síncrona en hilo secundario mediante `check_availability_sync()`. | **MEDIA** | **RESUELTO** |
| **AUD-007** | Inexistencia de empaquetado y especificación de construcción para Windows. | Falta de configuración de PyInstaller e Inno Setup para generar ejecutable e instalador. | `osvaldoDownloaderPro.spec` / `scripts/build_release.ps1` / `installer.iss` | **ALTO** — Dificultaba la distribución a usuarios finales en Windows. | Implementar spec de PyInstaller con manifest, script PowerShell de build automatizado e instalador Inno Setup con SHA-256. | **ALTA** | **RESUELTO** |
| **AUD-008** | Advertencias de tipado estricto MyPy en componentes de presentación e infraestructura. | Falta de tipos en firmas de eventos Qt, métodos sobreescritos y colecciones genéricas no parametrizadas. | Varios archivos en `src/` (26 archivos) | **MEDIO** — Dificultad para garantizar seguridad de tipos en CI. | Tipar exhaustivamente todas las firmas, casting seguro en extractores y compatibilidad con `strict = true`. | **MEDIA** | **RESUELTO** |
| **AUD-009** | Error de permisos `[WinError 5]` al limpiar symlinks temporales de pytest en Windows. | Pytest intentaba resolver el symlink `pytest-current` en `%LOCALAPPDATA%\Temp` sin permisos de elevación. | `pyproject.toml` | **MEDIO** — Fallo artificial al finalizar la sesión de pruebas en Windows. | Configurar `--basetemp=scratch/pytest_tmp` en `addopts` de `pyproject.toml`. | **MEDIA** | **RESUELTO** |
| **AUD-010** | Configuración global volátil y falta de inyección de cookies de navegador para contenido restringido. | Ausencia de repositorio de persistencia de configuración e integración de `--cookies-from-browser` en el motor de descarga. | `src/presentation/views/configuracion_view.py`, `src/infrastructure/adapters/` | **ALTO** — Preferencias perdidas al reiniciar y fallo al procesar contenido con inicio de sesión. | Implementar puerto `ISettingsRepository`, `SQLiteSettingsRepository`, conectar `ConfiguracionView` e inyectar `cookiesfrombrowser` dinámicamente en `YtDlpDownloadEngine` y `PlatformRegistry`. | **ALTA** | **RESUELTO** |
| **AUD-011** | Falta de interactividad en HistorialView (tabla en modo solo lectura). | Carencia de menú contextual y eventos de doble clic para gestionar archivos y registros previos. | `src/presentation/views/historial_view.py`, `src/presentation/main_window.py` | **MEDIO** — Imposibilidad de reproducir descargas completadas, explorar archivos en Windows o eliminar entradas antiguas. | Implementar menú contextual con clic derecho, doble clic para abrir/explorar, copia de URL original y eliminación de registros en SQLite. | **MEDIA** | **RESUELTO** |
| **AUD-012** | Ausencia de notificaciones nativas en Windows y falta de integración con System Tray. | El usuario no era notificado al finalizar descargas en segundo plano y cerrar la ventana terminaba la aplicación de forma abrupta. | `src/presentation/components/system_tray.py`, `src/presentation/main_window.py`, `src/presentation/views/configuracion_view.py` | **MEDIO** — Falta de visibilidad de estado de descargas cuando la app no está en primer plano. | Crear componente `AppTrayIcon` con menú contextual, notificaciones Toast de éxito/fallo y opción configurable de minimizar a la bandeja al cerrar. | **MEDIA** | **RESUELTO** |
| **AUD-013** | Estado estático sin persistencia en FavoritosView (pantalla decorativa). | Carencia de entidad, puerto y tabla para gestionar favoritos y ausencia de botón de favorito en la vista previa. | `src/presentation/views/favoritos_view.py`, `src/domain/`, `src/infrastructure/adapters/storage/` | **MEDIO** — Incapacidad del usuario de conservar contenidos preferidos para descargarlos rápidamente. | Implementar entidad `FavoriteItem`, puerto `IFavoriteRepository`, `SQLiteFavoriteRepository` (tabla `user_favorites`), botón toggle en `ContentPreviewCard` y tarjetas interactivas con descarga en 1 clic en `FavoritosView`. | **MEDIA** | **RESUELTO** |
| **AUD-014** | Carencia de soporte para procesamiento y descarga masiva por lotes (Batch Download). | Carencia de componente modal y método en ViewModel para procesar múltiples enlaces o archivos de texto. | `src/presentation/components/batch_download_dialog.py`, `src/presentation/view_models/main_view_model.py`, `src/domain/services/filename_sanitizer.py` | **MEDIO** — El usuario debía ingresar, esperar el análisis y configurar cada descarga individualmente. | Implementar servicio puro `filename_sanitizer`, diálogo modal `BatchDownloadDialog` con importación de archivos `.txt`, selector de calidad predeterminada y encolamiento asíncrono en `MainViewModel`. | **MEDIA** | **RESUELTO** |
| **AUD-015** | Carencia de soporte para detección, descarga e incrustación de subtítulos en videos. | Carencia de entidades de subtítulos, métodos de extracción en `yt-dlp` y controles interactivos en la interfaz. | `src/domain/entities/subtitle.py`, `src/infrastructure/adapters/download/ytdlp_download_engine.py`, `src/presentation/components/content_preview_card.py` | **MEDIO** — Los usuarios no podían acceder a pistas de subtítulos en videos multilingües o educativos. | Crear entidades `SubtitleTrack`, `SubtitleConfig` y `SubtitleMode`, implementar `extract_subtitle_tracks` y `apply_subtitle_options` con soporte `FFmpegEmbedSubtitle`, e integrar selector interactivo y checkbox en `ContentPreviewCard`. | **MEDIA** | **RESUELTO** |

---

## 3. AUDITORÍA POR CAPAS Y ARQUITECTURA

### 3.1 Dominio (`src/domain/`)
- **Fortalezas:** Totalmente desacoplado de PySide6, SQLite, FFmpeg y `yt-dlp`.
- **Entidades:** `DownloadTask` con máquina de estados estricta (`QUEUED`, `ANALYZING`, `READY`, `DOWNLOADING`, `PAUSED`, `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED`), `FavoriteItem` y entidades de subtítulos `SubtitleTrack`, `SubtitleConfig`, `SubtitleMode`.
- **Seguridad:** `Url` previene ataques SSRF y spoofing verificando `hostname` contra loopback y rangos privados. `UrlSanitizer` elimina parámetros de playlist en enlaces individuales. `filename_sanitizer` normaliza títulos para evitar inyecciones en el sistema de archivos de Windows.
- **Normalizador de Dominio:** `FormatNormalizer` clasifica flujos progresivos vs adaptativos DASH y elimina artefactos storyboard/MHTML.
- **Puertos de Persistencia:** `IDownloadRepository`, `ISettingsRepository` e `IFavoriteRepository` desacoplan por completo el almacenamiento.

### 3.2 Aplicación (`src/application/`)
- **Casos de Uso:** `AnalyzeUrl`, `CreateDownload`, `StartDownload`, `PauseDownload`, `ResumeDownload`, `CancelDownload`, `RetryDownload`, `CheckForUpdates`.
- **Inversión de Dependencias:** Utilizan exclusivamente interfaces/puertos de dominio (`IDownloadRepository`, `ISettingsRepository`, `IFavoriteRepository`, `IDownloadEngine`, `IPlatformAdapter`, `IUpdateSource`).

### 3.3 Infraestructura (`src/infrastructure/`)
- **SQLite WAL Engine:** Base de datos relacional en modo WAL con persistencia de descargas, configuraciones en `user_settings` y favoritos en `user_favorites`.
- **FFmpeg Sidecar Processor:** Probe de medios (`ffmpeg -i`), extracción de audio nativo (MP3/M4A/WAV), multiplexación e incrustación de subtítulos sin recodificación innecesaria.
- **Gestión de Concurrencia:** `DownloadQueueManager` implementa control de descargas simultáneas en orden FIFO con pausas y reintentos transparentes.
- **Actualizador Automático Integrado:** Consulta oficial a la API de GitHub Releases con validación estricta de sumas SHA-256 en disco e instalación silenciosa.
- **Integración de Cookies y Subtítulos:** Soporte para extracción de credenciales de sesión local mediante `--cookies-from-browser` y extracción/aplicación de subtítulos (`extract_subtitle_tracks` y `apply_subtitle_options`).

### 3.4 Presentación (`src/presentation/`)
- **Visuales:** Estética "Studio Desktop" con paleta de tokens centralizada (`#0B0F19` fondo, superficies `#111827`/`#1E293B`, bordes sutiles y acento Índigo `#6366F1` para acciones primarias).
- **Ventana Nativa Frameless:** Barra de título personalizada con hit-testing de Windows (`WM_NCHITTEST`) para soporte de redimensionamiento nativo y Aero Snap.
- **Módulos Claros:** Pantalla de inicio modular (`ContentPreviewCard`, `FormatTableHeader`, `FormatTableRow`, `DownloadConfigWidget`) con selector circular visible, botón de favoritos dinámico (`♡ Guardar` / `♥ En Favoritos`) y selector de subtítulos con opción de incrustado.
- **Descargas Masivas (Batch):** `BatchDownloadDialog` integrado con importación de listas `.txt`, contador de enlaces en vivo, selector de resolución/formato y botón de acceso rápido `"Lote..."` en `InicioView`.
- **Configuración Persistente:** `ConfiguracionView` vinculada en tiempo real al almacenamiento con selector nativo de carpeta y aplicación en caliente.
- **Historial Interactivo:** Menú contextual (clic derecho) y doble clic en `HistorialView` con acciones de reproducción local, localización en explorador, re-descarga y borrado en SQLite.
- **System Tray y Notificaciones:** `AppTrayIcon` integrado con menú de restauración rápida, notificaciones Toast de Windows al completar descargas y minimizado inteligente a segundo plano.
- **Gestión Real de Favoritos:** `FavoritosView` con tarjetas visuales dinámicas (`FavoriteCard`), miniatura cargada de forma asíncrona, re-descarga en 1 clic y eliminación en base de datos.

---

## 4. ESTADO DE PRUEBAS AUTOMÁTICAS Y ANÁLISIS ESTÁTICO

Pruebas ejecutadas con `python -m pytest -W default`:
```text
============================ 560 passed in 25.36s =============================
```
- **Total de pruebas:** 560/560 (100% pasando sin errores y con 0 advertencias).
- **Advertencias de recursos:** 0 advertencias (`ResourceWarning: unclosed database` totalmente erradicado).
- **Cobertura global:** 83% (29 módulos clave al 100%).
- **Análisis estático MyPy:** `Success: no issues found in 98 source files` bajo modo `strict = true`.
- **Linter & Code Quality:** Ruff (`All checks passed!`, 0 errores).
