# osvaldoDownloaderPro — Guía de Estrategia de Testing

**Proyecto:** osvaldoDownloaderPro  
**Framework de Pruebas:** Pytest 8.0+  

---

## 1. EJECUCIÓN DE PRUEBAS

Para ejecutar la suite completa (67 pruebas unitarias, de integración y E2E de la GUI):

```bash
python -m pytest
```

Para verificar compilación de todos los módulos:

```bash
python -m compileall -q src tests
```

Para ejecutar pruebas con reporte de cobertura:

```bash
python -m pytest --cov=src
```

---

## 2. ESTRUCTURA DE LA SUITE DE PRUEBAS

```text
tests/
├── unit/
│   ├── domain/
│   │   ├── test_value_objects.py          # Pruebas de Url (Anti-SSRF), DownloadId, MediaId
│   │   ├── test_format_option.py          # Pruebas de FormatOption, VideoFormat, AudioFormat
│   │   ├── test_format_normalizer.py      # Pruebas de FormatNormalizer (filtrado storyboards/MHTML, cadena 2160p→144p)
│   │   ├── test_download_task.py          # Pruebas de máquina de estados DownloadTask (pausa/resumen/cancel idempotentes)
│   │   ├── test_media_metadata.py         # Pruebas de MediaMetadata y formateadores
│   │   └── test_events_and_exceptions.py  # Pruebas de jerarquía de eventos y excepciones
│   ├── application/
│   │   └── test_use_cases.py              # Pruebas de los 7 casos de uso (vq_best, vq_height, audio)
│   └── infrastructure/
│       └── test_ffmpeg_adapter.py         # Parser de salida `ffmpeg -i` (contenedor, duración, video, audio)
├── integration/
│   ├── test_download_engine.py            # Pruebas del motor YtDlpDownloadEngine (flujo completo, fallo, progreso,
│   │                                      #   audio con FFmpeg propio, spec H.264+AAC, Mejor calidad, cancel + limpieza)
│   ├── test_sqlite_repository.py          # Pruebas de SQLiteDownloadRepository y WAL Mode
│   ├── test_event_bus.py                  # Pruebas de InProcessEventBus
│   ├── test_logging.py                    # Pruebas de SensitiveDataFilter y setup_logger
│   └── test_platform_adapters.py          # Pruebas de PlatformRegistry y adaptadores
└── e2e/
    └── test_gui.py                        # Pruebas E2E de navegación PySide6 GUI + bitrates de audio por formato
```

---

## 3. PRUEBAS REALES (RED + FFmpeg)

El motor se valida además con descargas reales (YouTube público) ejecutadas desde la CLI:

```bash
python C:\Users\qyt95\AppData\Local\Temp\opencode\odp_battery.py
```

Verifica para cada caso (Mejor calidad, 1080p, 720p, 480p, MP3 320, M4A 192, WAV):
archivo presente, tamaño > 0, extensión correcta, codecs/contenedor/resolución vía `ffmpeg -i`
(probe_streams), ausencia de `.part/.tmp` y estado `COMPLETED` persistido en el historial SQLite.
La cancelación real se valida con `odp_cancel_test.py` (estado CANCELLED, sin procesos FFmpeg
huérfanos y sin archivos residuales).
