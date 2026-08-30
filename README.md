# osvaldoDownloaderPro

Aplicación de escritorio nativa para Windows 10/11 diseñada para el análisis, descarga, conversión y organización de contenido multimedia desde múltiples plataformas web.

---

## osvaldoDownloaderPro v1.1.0 BETA (Última versión)

##  DESCARGAR PARA WINDOWS

### [  DESCARGAR osvaldoDownloaderPro v1.1.0 (Instalador Oficial) ](https://github.com/adrianpalacios782-dotcom/descarga/releases/latest)

En la página de lanzamientos, dirígete a la sección **Assets** y descarga:

> **`osvaldoDownloaderPro-1.1.0-Setup.exe`** (114 MB — incluye instalador, nuevo icono oficial, motor y dependencias completas)

**Instalación rápida en 4 pasos:**

1. Haz clic en el enlace de descarga superior o visita [Releases](../../releases/latest).
2. Descarga `osvaldoDownloaderPro-1.1.0-Setup.exe`.
3. Ejecuta el instalador (no requiere permisos de administrador).
4. Sigue los pasos del asistente y listo.

**Compatibilidad del sistema:**
- Windows 10 x64 (versión 1809 o superior)
- Windows 11 x64
- *No compatible con versiones de Windows de 32 bits.*

**No requiere instalaciones adicionales:**
- ✅ No requiere Python.
- ✅ No requiere instalar FFmpeg por separado (incluido y verificado automáticamente).
- ✅ No requiere .NET Runtime adicional.

> **⚠️ Aviso sobre Windows SmartScreen:** Como esta versión BETA es de código abierto y no cuenta con certificado de firma comercial de pago, Windows puede mostrar la pantalla *"Windows protegió tu PC"*. Para continuar, simplemente pulsa en **Más información** y luego en **Ejecutar de todas formas**.

---

##  Plataformas Soportadas

- **YouTube** (Videos individuales, shorts, calidades hasta 4K/60fps y pistas de audio).
- **TikTok** (Videos en alta definición sin marca de agua).
- **Instagram** (Reels y publicaciones de video).
- **Facebook** (Videos públicos y transmisiones grabadas).

---

##  Características Principales

### Pantalla de Análisis y Descarga Modular
- **Previsualización Inteligente (`ContentPreviewCard`):** Miniatura real con relación de aspecto 16:9 preservada, esquinas redondeadas y badge de duración superpuesto.
- **Metadatos Técnicos Claros:** Chips visuales para plataforma, tipo de contenido (*Vídeo / Audio*), duración formateada, año de publicación y calidad máxima disponible.
- **Sinopsis Colapsable:** Resumen compacto con botón interactivo `[Ver más]` / `[Ver menos]` para optimizar el espacio vertical.
- **Tabla Estructurada de Formatos (`FormatTableRow`):**
  - Cabecera con columnas técnicas alineadas: `ELEGIR` | `CALIDAD` | `FORMATO` | `TAMAÑO` | `CÓDEC` | `FPS` | `ESTADO`.
  - Selector circular visible y estilizado con acento moderno.
  - Selección de fila completa con realce en hover y borde de acento.
  - Altura mínima garantizada de 48px por fila y contenedor montado sobre un `QScrollArea` responsive que previene el colapso visual en pantallas de baja resolución.
  - Badge distintivo `Recomendado` para la mejor opción de calidad detectada.
- **Configuración de Descarga Personalizada (`DownloadConfigWidget`):**
  - Selector de carpeta de destino con explorador nativo de Windows (`QFileDialog`).
  - Campo editable para el nombre del archivo final con sanitización automática contra caracteres y nombres reservados de Windows.
- **Acción Principal Destacada:** Botón grande `[ ⭳ Iniciar descarga ]` de 50px con retroalimentación inmediata de estado (`Iniciando descarga…`), validación inline de errores y advertencia de que *"El tamaño es aproximado"*.

###  Subtítulos y Accesibilidad (Subtitles / CC)
- **Detección Automática:** Identificación en tiempo real de subtítulos manuales y autogenerados para múltiples idiomas.
- **Opciones de Integración:** Incrustación directa en el video vía FFmpeg (`FFmpegEmbedSubtitle`) o descarga como pista externa en formatos `.srt` y `.vtt`.
- **Selector Intuitivo:** Selector visual integrado directamente en la tarjeta de previsualización del contenido.

###  Descargas Masivas por Lotes (Batch Downloads)
- **Diálogo Modal Multilínea (`BatchDownloadDialog`):** Procesamiento de múltiples URLs simultáneas desde la barra de herramientas.
- **Importación de Listas:** Carga de listas de enlaces desde archivos de texto `.txt`.
- **Configuración Global:** Calidad y formato unificados aplicables a toda la lista de reproducción o conjunto de enlaces.
- **Gestión Concurrente:** Encolamiento secuencial o concurrente respetando los límites de descarga configurados.

###  Sistema de Favoritos Persistente
- **Persistencia en SQLite (`user_favorites`):** Registro seguro en base de datos local en modo WAL.
- **Guardado en 1 Clic:** Botón dinámico (`♡ Guardar` / `♥ En Favoritos`) disponible desde la vista previa.
- **Pantalla Dedicada (`FavoritosView`):** Exploración, búsqueda rápida, eliminación y re-descarga directa de enlaces favoritos.

###  Bandeja del Sistema (System Tray) y Notificaciones
- **Integración Nativa en Windows (`SystemTrayComponent`):** Icono residente en la barra de tareas con soporte para minimizar la aplicación al cerrar.
- **Notificaciones Toast:** Alertas emergentes nativas al completar o fallar una descarga.
- **Menú Contextual Oscuro Fusion:** Menú contextual rápido para restaurar ventana, pausar todas las descargas o cerrar la aplicación.

###  Historial Interactivo Mejorado
- **Menú Contextual Avanzado (`QMenu`):** Clic derecho sobre cualquier registro para reproducir el archivo descargado con el reproductor del sistema, abrir la carpeta contenedora en el Explorador de Windows, copiar URL, agregar a favoritos o eliminar.

###  Configuración Avanzada y Cookies de Navegador
- **Persistencia en SQLite (`user_settings`):** Ajustes guardados de directorio de descarga, límite de concurrencia, calidad predeterminada y preferencias de inicio.
- **Soporte de Cookies de Navegador:** Integración con navegadores locales (Chrome, Edge, Firefox, Brave) para descargar contenido protegido o con restricciones de edad.

###  Motor de Descarga y Conversión
- **Selección de Calidad Dinámica:** 144p, 240p, 360p, 480p (SD), 720p (HD), 1080p (Full HD), 1440p (2K) y 2160p (4K).
- **Extracción y Conversión de Audio:** Descarga en formato MP3, M4A o WAV con tasa de bits configurable (320, 256, 192, 128 kbps).
- **FFmpeg Integrado:** Fusión automática de flujos DASH (video + audio) sin recodificación innecesaria para máxima velocidad y fidelidad.
- **Gestor de Cola Concurrente:** Control de descargas simultáneas, pausas, reanudación y reintentos automáticos.

###  Actualizador Automático Blindado
- **Detección Automática:** Consulta de versiones en tiempo real contra la API de GitHub Releases.
- **Instalación Segura en Segundo Plano:** Ejecución desacoplada mediante script de actualización sin bloqueos de proceso (`taskkill` seguro).
- **Reinicio Automático:** La aplicación se cierra, aplica la nueva versión silenciosamente y se vuelve a abrir sola.
- **Verificación Criptográfica:** Comprobación estricta de sumas SHA-256 antes de permitir cualquier ejecución.

### Identidad Visual Oficial (ODP PRO)
- **Nuevo Icono Oficial:** Diseño squircle moderno dark neon con hexágono cian y flecha de descarga, integrado en el ejecutable (.exe), instalador, accesos directos y barra de título.
- **Tema Oscuro Profesional:** Estilos QSS oscuros optimizados con acentos de color consistentes y menús contextuales adaptados.

---

##  Seguridad y Resiliencia

El sistema ha sido auditado exhaustivamente y cuenta con protecciones verificadas mediante pruebas automatizadas:

- **Protección contra SSRF y Spoofing:** Validación estricta de `hostname` (`netloc`) en URLs, bloqueando localhost, IPs privadas, loopback y parámetros engañosos.
- **Anti-Path Traversal:** Validación y contención de rutas de descarga y nombres de archivo en el sistema de archivos.
- **Protección de Archivos Reservados de Windows:** Sanitización contra nombres de dispositivo especiales (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) y caracteres inválidos (`<>:"/\|?*`).
- **Sanitización de Logs:** Redacción automática de tokens, credenciales y cabeceras sensibles en `osvaldo_downloader.log`.
- **Persistencia Segura:** Base de datos SQLite (modo WAL) con consultas 100% parametrizadas (historial, favoritos y configuración).
- **Tipado Estricto:** Código validado con MyPy modo `--strict` y linter Ruff sin advertencias.
- **Thread-Safety en GUI:** Todas las tareas de red, análisis y descarga se ejecutan en hilos secundarios asíncronos comunicándose mediante `Signal` de Qt, garantizando que la interfaz nunca se congele.

---

##  Desarrollo y Pruebas

### Requisitos previos
- Python 3.11 o superior (probado en Python 3.13)
- PySide6 (Qt6)
- Git

### Instalación en entorno de desarrollo

```powershell
# Clonar el repositorio
git clone https://github.com/adrianpalacios782-dotcom/descarga.git
cd descarga

# Crear entorno virtual e instalar dependencias
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Ejecutar la aplicación
python src/main.py
```

### Ejecución de Pruebas Automatizadas

El proyecto cuenta con **560 pruebas automatizadas** que cubren dominio, adaptadores de infraestructura, casos de uso, seguridad, interfaz gráfica y regresiones:

```powershell
python -m pytest
```

### Compilación del Instalador (.exe)

Para compilar el binario ejecutable con PyInstaller y generar el instalador con Inno Setup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -SkipSigning
```

El script genera automáticamente:
- `dist\osvaldoDownloaderPro\`: Binario portable desempaquetado.
- `installer\osvaldoDownloaderPro-1.1.0-Setup.exe`: Instalador ejecutable para Windows.
- `dist\SHA256SUMS.txt`: Sumas de comprobación SHA-256 de los artefactos.

---

## 📂 Documentación Adicional

- [`docs/CHANGELOG.md`](docs/CHANGELOG.md): Historial cronológico detallado de versiones y correcciones.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Arquitectura hexagonal, capas de dominio y contratos.
- [`docs/TESTING.md`](docs/TESTING.md): Estrategia de pruebas, cobertura y suites E2E.
- [`docs/BETA_TESTING.md`](docs/BETA_TESTING.md): Guía de instalación y pruebas para beta testers.
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md): Solución de problemas comunes de red, permisos y FFmpeg.

---

**osvaldoDownloaderPro Team © 2026** — Software libre para la gestión y descarga multimedia.
