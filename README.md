# osvaldoDownloaderPro

Aplicación de escritorio nativa para Windows 10/11 diseñada para la descarga, conversión y organización de contenido multimedia desde múltiples plataformas web (YouTube, TikTok, Instagram, Facebook).

---

## 🌟 Características Principales

- **Arquitectura Hexagonal + Event-Driven Modular Monolith:** Estricto desacoplamiento en 4 capas (Domain, Application, Infrastructure, Presentation).
- **Rediseño UI/UX Multimedia Oscuro:** Inspirado en aplicaciones modernas (estilo Spotify), con paleta de acento verde esmeralda (`#1db954`), tarjetas elevadas y cero emojis.
- **Normalización Inteligente de Formatos:** Exclusión total de storyboards, MHTML, thumbnails y duplicados.
- **Selección Dinámica VIDEO / AUDIO:**
  - **Modo Video:** Muestra únicamente resoluciones reales, FPS, contenedor, indicación de audio y tamaño estimado.
  - **Modo Audio:** Oculta resoluciones de video y permite elegir formato (`MP3`, `M4A`, `WAV`) y tasa de bits (`320`, `256`, `192`, `128` kbps).
- **Procesamiento Sidecar FFmpeg:** Fusionado transparente de flujos DASH (video + audio sin re-codificación) y extracción/conversión de audio.
- **Persistencia Relacional SQLite WAL:** Historial completo, favoritos y configuración sin bloqueos de concurrencia.
- **Análisis Asíncrono no Bloqueante:** Operaciones de red en segundo plano que mantienen la GUI fluida a 60 FPS.

---

## 🚀 Instalación y Ejecución

### Requisitos Previos
- Python 3.11 o superior.
- PySide6, yt-dlp, pytest.

### Ejecución Directa

```powershell
python src/main.py
```

o:

```powershell
python -m src.main
```

---

## 🧪 Suite de Pruebas (`pytest`)

Para ejecutar los 50 tests unitarios, de integración y E2E de la GUI:

```powershell
python -m pytest
```

---

## 📚 Documentación Técnica

- [`docs/AUDIT_REPORT.md`](file:///d:/osvaldoDownloaderPro/docs/AUDIT_REPORT.md): Informe de Auditoría Integral.
- [`docs/ARCHITECTURE.md`](file:///d:/osvaldoDownloaderPro/docs/ARCHITECTURE.md): Especificación de Arquitectura de Capas.
- [`docs/TESTING.md`](file:///d:/osvaldoDownloaderPro/docs/TESTING.md): Estrategia y Cobertura de Pruebas.
- [`docs/TROUBLESHOOTING.md`](file:///d:/osvaldoDownloaderPro/docs/TROUBLESHOOTING.md): Solución de Problemas Frecuentes.
- [`docs/CHANGELOG.md`](file:///d:/osvaldoDownloaderPro/docs/CHANGELOG.md): Historial de Cambios.
