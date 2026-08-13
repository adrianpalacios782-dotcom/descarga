# osvaldoDownloaderPro — Historial de Cambios (Changelog)

Todos los cambios notables realizados en este proyecto se documentan en este archivo.

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
