# osvaldoDownloaderPro — Historial de Cambios (Changelog)

Todos los cambios notables realizados en este proyecto se documentan en este archivo.

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
