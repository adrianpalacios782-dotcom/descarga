# osvaldoDownloaderPro — Documentación de Arquitectura

**Proyecto:** osvaldoDownloaderPro  
**Patrón Arquitectónico:** Hexagonal Architecture (Ports & Adapters) + Event-Driven Modular Monolith  
**Independencia:** 100% Independiente  

---

## 1. CAPAS DEL SISTEMA

```text
src/
├── domain/                  # Núcleo de Dominio Puro (0% dependencias de infraestructura/GUI)
│   ├── entities/            # DownloadTask, MediaMetadata, FormatOption, VideoFormat, AudioFormat, SubtitleTrack, FavoriteItem
│   ├── value_objects/       # Url (anti-SSRF), DownloadId, MediaId
│   ├── events/              # DomainEvent y catálogo de 8 subclases de eventos
│   ├── exceptions/          # DomainError y jerarquía estricta de excepciones
│   ├── ports/               # Contratos IPlatformAdapter, IDownloadEngine, IDownloadRepository, IFavoriteRepository, ISettingsRepository
│   └── services/            # FormatNormalizer, FilenameSanitizer (anti-DOS nombres reservados Windows)
├── application/             # Casos de Uso (Orquestación de lógica de negocio)
│   └── use_cases/           # AnalyzeUrl, CreateDownload, StartDownload, PauseDownload, ResumeDownload, CancelDownload, RetryDownload, CheckForUpdates
├── infrastructure/          # Adaptadores de Infraestructura y E/S
│   ├── adapters/
│   │   ├── platforms/       # YouTubeAdapter, TikTokAdapter, InstagramAdapter, FacebookAdapter, GenericAdapter, PlatformRegistry
│   │   ├── storage/         # DatabaseManager (SQLite WAL), SQLiteDownloadRepository, SQLiteFavoriteRepository, SQLiteSettingsRepository
│   │   ├── media/           # FFmpegProcessAdapter, ThumbnailFetcher (con contención SSRF y caché)
│   │   └── download/        # YtDlpDownloadEngine (yt-dlp 2026 + pre-probe de estrategias, incrustación de subtítulos, cookies)
│   ├── event_bus/           # InProcessEventBus (Thread-safe)
│   ├── logging/             # setup_logger y SensitiveDataFilter
│   └── updater/             # Actualizador automático desacoplado y seguro (GitHub Releases oficial)
└── presentation/            # Capa de Presentación Nativa PySide6 (Qt6)
    ├── main_window.py       # MainWindow (QStackedWidget + Sidebar)
    ├── view_models/         # MainViewModel, UpdateCoordinator (Signals/Slots reactivos)
    ├── components/          # SidebarWidget, DownloadCardWidget, ContentPreviewCard, FormatTableWidget, BatchDownloadDialog, SystemTrayComponent
    ├── views/               # InicioView, DescargasView, HistorialView, FavoritosView, ConfiguracionView, AcercaDeView
    └── styles/              # DARK_STYLE QSS, Paleta consistente, soporte Fusion oscuro nativo en menús contextuales
```

---

## 2. REGLAS DE COMUNICACIÓN ENTRE CAPAS

1. **Inversión de Dependencias:** La capa de Dominio no conoce a PySide6, SQLite, FFmpeg ni `yt-dlp`.
2. **Puertos y Adaptadores:** La capa de Aplicación solo interactúa con abstracciones (`IDownloadRepository`, `IDownloadEngine`, `IPlatformAdapter`).
3. **Comunicación Reactiva UI:** La interfaz gráfica escucha eventos emitidos por el `InProcessEventBus` a través del `MainViewModel`.

---

## 3. MOTOR DE DESCARGA (YtDlpDownloadEngine)

- **yt-dlp real** (2026.07.04): sin HTTP Range simulado; usa yt-dlp + `ffmpeg_location` (binario de imageio-ffmpeg).
- **Pre-probe de estrategias:** antes de descargar se reanalizan los formatos con las estrategias de
  `player_client` (`None`, `web/android/mweb`, `android_vr/tv`) y se elige la que ofrezca mayor
  resolución real (objetivo: que "Mejor calidad" no caiga silenciosamente por rate-limit 403).
- **Compatibilidad MP4:** el spec de formato prefiere `bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]`
  (H.264 + AAC) con fallbacks, y `merge_output_format=mp4`. El archivo final se verifica con
  `ffmpeg -i` (probe_streams) y se registra honestamente la resolución solicitada vs. la final
  (log `DEGRADACIÓN DE CALIDAD`).
- **Audio honesto por formato:** se descarga `bestaudio/best` crudo y se extrae con FFmpeg propio
  (`extract_audio_sync`): MP3 (`libmp3lame -b:a`), M4A (`aac -b:a`) y WAV (`pcm_s16le` sin compresión).
  El proceso FFmpeg es matable (cancelación real, sin procesos huérfanos).
- **Pausa/Cancelación reales:** yt-dlp ya no expone `pause()/resume()`; la pausa es cooperativa
  (se bloquea el `progress_hook`, la conexión se mantiene) y la cancelación eleva
  `yt_dlp.utils.DownloadCancelled` en el hook, que aborta la transferencia; los restos `.part/.tmp/.f*`
  se limpian con reintentos. Se publican eventos `DownloadPausedEvent`, `DownloadResumedEvent` y
  `DownloadCancelledEvent` para reflejar el estado real en la UI.

---

## 4. MODOS DE DESCARGA

- **Video por resolución** (`vq_*`): opciones de `FormatNormalizer.normalize_video_quality_options`
  (Mejor calidad + resoluciones reales ordenadas desc, sin duplicados ni storyboard/MHTML/thumbs).
- **Audio** (`audio_*_<fmt>_<br>`): MP3 320/256/192/128, M4A 192/160/128, WAV sin compresión
  (bitrates honestos y producibles).
- **Fallback y errores:** si una estrategia falla (403 intermitente) se reintenta con las demás;
  en caso de error persistente la tarea se persiste como `FAILED` con mensaje y se permite reintentar
  (`RetryDownloadUseCase`).

---

## 5. SISTEMA DE ACTUALIZACIÓN AUTOMÁTICA (src/infrastructure/updater)

- **Fuente oficial única:** GitHub Releases (update_config.py fija owner/repo y allowlists
  de hosts; ninguna URL proviene de entrada del usuario).
- **Flujo:** al iniciar (una sola vez, con retraso) UpdateCoordinator consulta la API JSON
  oficial en un hilo worker → CheckForUpdatesUseCase compara SemanticVersion (solo
  upgrade, nunca downgrade, rechazo de versiones inválidas) → si hay versión superior se abre
  UpdateDialog (estilo DARK_STYLE integrado, notas como texto plano) → descarga streaming a
  %TEMP%\osvaldoDownloaderPro-update-*\*.part con SHA-256 incremental → re-verificación en
  disco (tamaño + hash constant-time) → lanzamiento silencioso del instalador encadenado con
  el reinicio de la app.
- **Seguridad:** HTTPS obligatorio; guardia de redirecciones limitada a hosts permitidos;
  SHA-256 obligatorio (SHA256SUMS.txt del release o campo digest); sin checksum no se ejecuta
  nada; archivos .part nunca se ejecutan; temporales eliminados siempre; sin tokens ni
  cookies ni datos personales; compatible con futura firma Authenticode.
- **Resiliencia:** cualquier fallo (sin red, timeout, GitHub caído, hash incorrecto) deja la
  aplicación actual plenamente funcional y limpia los temporales.
- **Versión:** única fuente de verdad en src/__init__.py::__version__; pyproject la deriva
  dinámica, installer.iss la recibe vía /DAPP_VERSION desde build_release.ps1.
