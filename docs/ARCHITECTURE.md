# osvaldoDownloaderPro — Documentación de Arquitectura

**Proyecto:** osvaldoDownloaderPro  
**Patrón Arquitectónico:** Hexagonal Architecture (Ports & Adapters) + Event-Driven Modular Monolith  
**Independencia:** 100% Independiente  

---

## 1. CAPAS DEL SISTEMA

```text
src/
├── domain/                  # Núcleo de Dominio Puro (0% dependencias de infraestructura/GUI)
│   ├── entities/            # DownloadTask, MediaMetadata, FormatOption, VideoFormat, AudioFormat
│   ├── value_objects/       # Url (anti-SSRF), DownloadId, MediaId
│   ├── events/              # DomainEvent y catálogo de 8 subclases de eventos
│   ├── exceptions/          # DomainError y jerarquía estricta de excepciones
│   ├── ports/               # Contratos IPlatformAdapter, IDownloadEngine, IDownloadRepository
│   └── services/            # FormatNormalizer (filtrado y clasificación de formatos)
├── application/             # Casos de Uso (Orquestación de lógica de negocio)
│   └── use_cases/           # AnalyzeUrl, CreateDownload, StartDownload, PauseDownload, ResumeDownload, CancelDownload, RetryDownload
├── infrastructure/          # Adaptadores de Infraestructura y E/S
│   ├── adapters/
│   │   ├── platforms/       # YouTubeAdapter, TikTokAdapter, InstagramAdapter, FacebookAdapter, GenericAdapter, PlatformRegistry
│   │   ├── storage/         # DatabaseManager (SQLite WAL), SQLiteDownloadRepository
│   │   ├── media/           # FFmpegProcessAdapter (Sidecar Process Manager: probe de medios, extracción de audio, merge)
│   │   └── download/        # YtDlpDownloadEngine (yt-dlp 2026 + pre-probe de estrategias, cancelación real)
│   ├── event_bus/           # InProcessEventBus (Thread-safe)
│   └── logging/             # setup_logger y SensitiveDataFilter
└── presentation/            # Capa de Presentación Nativa PySide6 (Qt6)
    ├── main_window.py       # MainWindow (QStackedWidget + Sidebar)
    ├── view_models/         # MainViewModel (Conexión Signals/Slots y Casos de Uso)
    ├── components/          # SidebarWidget, DownloadCardWidget
    ├── views/               # InicioView, DescargasView, HistorialView, FavoritosView, ConfiguracionView, AcercaDeView
    └── styles/              # DARK_STYLE QSS (Estética multimedia oscura moderna, acentos #1db954)
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
