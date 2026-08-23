# Informe final — Corrección funcional del flujo de formatos/calidades

**Proyecto:** osvaldoDownloaderPro · **Fecha:** 2026-08-23 · **Estado:** implementado, 394/394 tests en verde, sin commit/push/tag/release (según restricciones).

---

## 1. Causas raíz (con evidencia)

### RAÍZ #1 — Tarjetas de calidad vacías (CASO C: `eUX086mraqc` PARIS)
Cuando YouTube aplica su verificación anti-bot a un `player_client`, **la extracción NO falla**: yt-dlp devuelve metadata completa (título, canal, duración, miniatura) pero **solo storyboards mhtml** (`sb0-sb3`, vcodec=none/acodec=none). El adapter antiguo aceptaba esa respuesta degenerada como exitosa → 0 calidades reales → grid vacío.
Verificado empíricamente en sandbox: clientes `mweb`, `web_embedded`, `web_safari` devuelven solo storyboards; `default`/`tv` lanzan "Sign in to confirm you're not a bot" / "The page needs to be reloaded".

### RAÍZ #2 — 1080p pedido → 806p entregado (CASO B)
El spec de formato usaba solo selectores con tope `bestvideo[height<=1080]` como fallback: si el formato exacto no está disponible o falla, yt-dlp elige **silenciosamente la resolución menor más alta** (806px reales recortados por YouTube). Además análisis y descarga podían usar clientes distintos.

### RAÍZ #3 — Descarga completada clasificada como Error
`QualityDegradationError` se lanzaba en fase 5 (post-descarga, archivo ya al 100%): caía al `except` genérico de `_run()` → estado FAILED + borrado del archivo. El usuario perdía un archivo válido.

### RAÍZ #4 — Motor sin fallback de clientes (descubierta en prueba real E2E)
El adapter de análisis y el motor de descarga eran inconsistentes: tras arreglar #1 el análisis sobrevivía al bot-check, pero el motor usaba solo los clientes default de yt-dlp para descargar → fallo garantizado en IPs restringidas aunque el análisis hubiera tenido éxito.

## 2. Soluciones implementadas

| # | Archivo | Cambio |
|---|---------|--------|
| 1a | `src/infrastructure/adapters/platforms/base_platform_adapter.py` | `CLIENT_STRATEGIES = [None, ["tv"], ["android"], ["web"], ["mweb"]]`. `_extract_with_ytdlp` reescrito: rechaza respuestas solo-storyboards, acepta la primera estrategia con video real, fallback a solo-audio o URL directa, lanza `MediaAnalysisError` con mensaje claro si todo degenera |
| 1b | `src/domain/services/format_normalizer.py` | `infer_standard_height`: parsea `"WxH"` (ej. `640x338` real del cliente android) antes que etiquetas; antes esos formatos se descartaban y quedaban 0 tarjetas |
| 2 | `src/infrastructure/adapters/download/ytdlp_download_engine.py` | `_build_video_format_spec`: selectores de altura **exacta** (`bestvideo[height={h}]…`) ANTES de los topes `height<={h}` en todas las ramas |
| 3 | ídem + dominio/UI/storage | Fase 5 captura `QualityDegradationError` → `task.quality_warning`; tarea **COMPLETED**, archivo conservado, advertencia ámbar inline (`DownloadCardWidget.set_quality_warning`, estilo `QLabel#CardWarningLabel`), evento `DownloadCompletedEvent.warning_message`, persistencia SQLite (migración de columna) |
| 4 | `ytdlp_download_engine.py` | Sondeo (`_probe_available_formats`) multi-estrategia y descarga de video/audio alternan `player_client` entre reintentos (default→tv→android), igual que el análisis |
| UI | `src/presentation/views/inicio_view.py` | Eliminado QMessageBox "Selección Requerida": botón **deshabilitado** + mensaje inline (`lbl_selection_summary`) cuando no hay calidades/pistas; `_update_download_availability()` único escritor del resumen cuando no se puede descargar. Se conserva el QMessageBox solo para carpeta destino inválida |
| UX | `src/domain/entities/format_option.py` | Formato sin tamaño muestra "Tamaño no disponible" en vez de omitir la línea |

## 3. Pruebas

- **Suite completa: 349 → 394 tests, todos en verde** (`python -m pytest -q`).
- Nuevas suites: `tests/unit/infrastructure/test_platform_adapter_formats.py` (8: CASO C fallback, todas-degeneradas, bot-check→siguiente estrategia, camino feliz sin llamadas extra, android capped real, solo-audio legítimo, archivo directo), `tests/unit/domain/test_format_normalizer_regression.py` (13: derivación de resolución, alturas recortadas 1074/806/476/354→buckets, format_id numérico ≠ resolución, cadenas WEBM/MP4 reales, merge video-only+audio-only, síntética "Mejor calidad" solo con ≥2 alturas, WxH→360p), `tests/unit/application/test_create_download_quality_contracts.py` (7: contratos `vq_best/vq_1440/vq_1080/vq_720/audio_*` intactos, `FormatNotFoundError` para calidad inexistente), ampliaciones en `test_download_engine.py` (+7: spec exacto, degradación=warning no error, evento con warning, reset limpia warning, fallback anti-bot de sondeo/descarga/agotamiento), `test_inicio_view_states.py` (+6: botón deshabilitado, mensaje inline, **monkeypatch verifica que QMessageBox NUNCA se invoca** para selección), `test_sqlite_repository.py` (+roundtrip de quality_warning).

## 4. Pruebas funcionales reales

| Prueba | Resultado |
|---|---|
| Análisis REAL CASO A (`F3tKutGo1Fo` OTRO AMOR) vía app corregida | ✅ Título correcto, tarjetas generadas, audio detectado (fallback android funcionó con datos reales de YouTube) |
| Análisis REAL CASO C (`eUX086mraqc` PARIS — el video del bug) | ✅ **Ya no queda vacío**: tarjeta `360p` generada desde respuesta real (antes: grid vacío). En una IP residencial aparecerá la escalera completa |
| Negativo REAL: pedir `vq_1080` cuando el servidor solo ofrece 360p | ✅ `FormatNotFoundError` temprano listando calidades disponibles; cero bytes descargados (anti-CASO-B garantizado) |
| Descarga completa REAL de YouTube | ⚠️ Bloqueada por entorno: esta IP de datacenter quedó rate-limited ("Sign in to confirm you're not a bot") en TODOS los clientes durante las pruebas; documentado. La ruta de descarga quedó cubierta por los tests de integración que simulan exactamente ese comportamiento |
| Capturas offscreen (`scratch/screenshots/`) | ✅ 01 escalera completa con "Mejor calidad"+tamaños; 02 CASO C con única tarjeta real; 03 botón deshabilitado+mensaje inline; 04 tarjeta COMPLETED con advertencia ámbar |

## 5. Pendientes / recomendaciones
1. Verificar en la máquina del usuario (IP residencial): CASO C debe mostrar escalera completa y descargar; CASO A debe mantener 1440p WEBM.
2. Reproducir CASO B real: pedir 1080p donde YouTube sirve 806p debe terminar COMPLETED con advertencia ámbar (no Error, archivo conservado).
3. Opcional a futuro: soporte de cookies del navegador para sortear bot-checks persistentes.

## 6. Cumplimiento de restricciones
Sin commit/push/tag/release ✓ · Sin cambios visuales de diseño ✓ · Contratos `vq_best/vq_{h}/audio_*` intactos ✓ · Validación de calidad conservada (diferenciando completada-con-advertencia vs fallo técnico) ✓ · Seguridad SSRF/updater/thumbnails intocadas ✓
