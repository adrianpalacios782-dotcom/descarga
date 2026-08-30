# osvaldoDownloaderPro — Guía de Estrategia de Testing

**Proyecto:** osvaldoDownloaderPro  
**Framework de Pruebas:** Pytest 8.0+ / Pytest 9.0+  
**Total de Pruebas:** 560 pruebas (100% pasando, 0 advertencias)  
**Cobertura de Código:** 83% global (29 módulos clave al 100%)  
**Análisis Estático:** MyPy (`strict = true`, 0 errores en 98 archivos fuente)  
**Linter & Calidad:** Ruff (`All checks passed!`, 0 errores)  

---

## 1. EJECUCIÓN DE PRUEBAS

Para ejecutar la suite completa de pruebas (560 pruebas unitarias, de integración y E2E):

```powershell
python -m pytest
```

Para verificar análisis de tipos estricto con MyPy:

```powershell
mypy src --strict
```

Para verificar calidad de código con Ruff:

```powershell
ruff check src tests
```

Para verificar compilación de sintaxis de todos los módulos:

```powershell
python -m compileall -q src tests
```

---

## 2. ESTRUCTURA DE LA SUITE DE PRUEBAS (45 Archivos, 559 Tests)

```text
tests/
├── unit/
│   ├── domain/
│   │   ├── test_content_preview.py                      # Servicios de previsualización (año, truncado y formato de tamaño)
│   │   ├── test_download_task.py                        # Máquina de estados (QUEUED, DOWNLOADING, COMPLETED, etc.)
│   │   ├── test_events_and_exceptions.py                # Eventos de dominio y excepciones de negocio tipadas
│   │   ├── test_filename_sanitizer.py                   # Sanitización de nombres de archivo para Windows
│   │   ├── test_format_normalizer.py                    # Clasificación y filtrado de formatos DASH/HLS/progresivos y MHTML
│   │   ├── test_format_normalizer_regression.py         # Regresiones de resolución y prioridad de formatos
│   │   ├── test_format_option.py                        # Entidades VideoFormat, AudioFormat y FormatOption
│   │   ├── test_media_metadata.py                       # Metadata agnóstica, sanitización y badges técnicos
│   │   ├── test_security.py                             # Validación SSRF, loopback y spoofing de URLs
│   │   ├── test_semantic_version.py                     # Versionado semántico y ordenamiento de releases
│   │   ├── test_subtitle.py                             # Entidades SubtitleTrack, SubtitleConfig y SubtitleMode
│   │   ├── test_url_sanitizer.py                        # Eliminación de parámetros de playlist en enlaces individuales
│   │   ├── test_url_spoofing_prevention.py              # Prevención de ataques homógrafos y suplantación de dominio
│   │   └── test_value_objects.py                        # Inmutabilidad de DownloadId, MediaId y Url
│   ├── application/
│   │   ├── test_check_for_updates.py                    # Orquestación de chequeo de versiones remotas
│   │   ├── test_create_download_quality_contracts.py    # Contratos de calidad técnica en creación de descargas
│   │   └── test_use_cases.py                            # Casos de uso: inicio, pausa, reanudación y cancelación
│   ├── infrastructure/
│   │   ├── test_download_engine_cookies.py              # Inyección y validación de cookies de navegador en el motor
│   │   ├── test_download_engine_subtitles.py            # Extracción de subtítulos y opciones de incrustación
│   │   ├── test_download_queue_manager.py               # Cola de descargas con límite de concurrencia y reintentos
│   │   ├── test_engine_canonicalize_regression.py       # Canonicalización de extensiones y preservación de archivos
│   │   ├── test_engine_manager.py                       # Gestión dinámica de wheels yt-dlp y auto-reparación
│   │   ├── test_ffmpeg_adapter.py                       # Probe de medios, extracción de audio y multiplexación
│   │   ├── test_platform_adapter_formats.py             # Formatos extraídos por adaptadores de plataforma
│   │   ├── test_platform_adapter_metadata.py            # Extracción de metadatos de plataformas
│   │   ├── test_sqlite_favorite_repository.py           # Persistencia de favoritos en SQLite (user_favorites)
│   │   ├── test_sqlite_settings_repository.py          # Persistencia y tipado en user_settings (SQLite)
│   │   ├── test_thumbnail_fetcher_security.py           # Fetcher seguro de miniaturas (DNS público y redirects)
│   │   └── test_updater_security.py                     # Sanitización de rutas y ejecución segura de instaladores
│   └── presentation/
│       ├── test_batch_download_dialog.py                # Diálogo modal y procesamiento masivo por lotes
│       ├── test_content_preview_card_subtitles.py       # Controles de subtítulos e incrustación en ContentPreviewCard
│       ├── test_favoritos_view.py                       # Tarjetas de favoritos, descarga y eliminación
│       ├── test_historial_view_interactions.py          # Menú contextual, doble clic, copia de URL y borrado
│       ├── test_inicio_view_enhanced.py                 # Nombres de archivo editables y sanitizados para Windows
│       ├── test_inicio_view_filename_regression.py      # Preservación de nombres sin sobreescritura accidental
│       ├── test_inicio_view_states.py                   # Estados de interfaz (vacío, analizando, error, descarga)
│       ├── test_system_tray.py                          # System Tray, notificaciones nativas y minimizado
│       └── test_visual_theme.py                         # Sistema de tokens de diseño, QSS y barra de título nativa
├── integration/
│   ├── test_download_engine.py                          # YtDlpDownloadEngine (descarga real, cancelaciones y reintentos)
│   ├── test_event_bus.py                                # InProcessEventBus multi-hilo thread-safe
│   ├── test_logging.py                                  # SensitiveDataFilter y rotación de registros en disco
│   ├── test_platform_adapters.py                        # Integración de PlatformRegistry con adaptadores concretos
│   └── test_sqlite_repository.py                        # Persistencia en SQLite (modo WAL, transacciones seguras)
└── e2e/
    ├── test_gui.py                                      # Flujo completo de navegación e interacción PySide6
    ├── test_ui_redesign.py                              # Verificación del rediseño modular v1.0.3/v1.0.4
    └── test_update_ui.py                                # Flujo completo del diálogo y coordinador de actualización
```

---

## 3. PRUEBAS REALES DE DESCARGA Y SEGURIDAD

Adicionalmente a la suite automatizada, el motor se valida contra casos de uso reales:
- **Descargas reales en plataformas soportadas:** Validación de formatos DASH (H.264 / AAC), extracción transparente a MP3 (320kbps), M4A y WAV sin recodificación innecesaria.
- **Cancelación real:** Verificación de detención inmediata del proceso `yt-dlp` y de `ffmpeg`, eliminación de residuos `.part` y persistencia honesta en SQLite.
- **Aislamiento en Windows:** Ejecución sin privilegios elevados con directorio base de pruebas aislado (`--basetemp=scratch/pytest_tmp`) para compatibilidad completa en entornos de desarrollo y CI.
