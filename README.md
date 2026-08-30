# osvaldoDownloaderPro

Aplicación de escritorio nativa para Windows 10/11 diseñada para el análisis, descarga, conversión y organización de contenido multimedia desde múltiples plataformas web.

---

## 🚀 osvaldoDownloaderPro v1.1.0 BETA (Última versión)

## ⬇️ DESCARGAR PARA WINDOWS

### [ ⬇️ DESCARGAR osvaldoDownloaderPro v1.1.0 (Instalador Oficial) ](https://github.com/adrianpalacios782-dotcom/descarga/releases/latest)

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

## 🌐 Plataformas Soportadas

- **YouTube** (Videos individuales, shorts, calidades hasta 4K/60fps y pistas de audio).
- **TikTok** (Videos en alta definición sin marca de agua).
- **Instagram** (Reels y publicaciones de video).
- **Facebook** (Videos públicos y transmisiones grabadas).

---

## ✨ Características Principales

### 🎯 Nueva Pantalla de Análisis y Descarga Modular (v1.0.3)
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
  - Campo editable para el nombre del archivo final con sanitización automática contra caracteres reservados (`<>:"/\|?*`).
- **Acción Principal Destacada:** Botón grande `[ ⭳ Iniciar descarga ]` de 50px con retroalimentación inmediata de estado (`Iniciando descarga…`), validación inline de errores y advertencia de que *"El tamaño es aproximado"*.

### ⚡ Motor de Descarga y Conversión
- **Selección de Calidad Dinámica:** 144p, 240p, 360p, 480p (SD), 720p (HD), 1080p (Full HD), 1440p (2K) y 2160p (4K).
- **Extracción y Conversión de Audio:** Descarga en formato MP3, M4A o WAV con tasa de bits configurable (320, 256, 192, 128 kbps).
- **FFmpeg Integrado:** Fusión automática de flujos DASH (video + audio) sin recodificación innecesaria para máxima velocidad y fidelidad.
- **Gestor de Cola Concurrente:** Control de descargas simultáneas, pausas, reanudación y reintentos automáticos.

### 🔄 Actualizador Automático Integrado
- Detección automática de nuevas versiones consultando la API de GitHub Releases.
- Descarga segura en segundo plano con validación estricta de sumas de verificación SHA-256 contra `SHA256SUMS.txt`.
- Instalación silenciosa y reinicio automático de la aplicación sin bloqueos de proceso.

---

## 🛡️ Seguridad y Resiliencia

El sistema ha sido auditado y cuenta con protecciones integradas verificadas mediante pruebas continuas:

- **Protección contra SSRF y Spoofing:** Validación estricta de `hostname` (`netloc`) en URLs, bloqueando localhost, IPs privadas, loopback y parámetros engañosos.
- **Anti-Path Traversal:** Validación y contención de rutas de descarga y nombres de archivo en el sistema de archivos.
- **Sanitización de Nombres de Archivo:** Eliminación automática de caracteres no permitidos en sistemas Windows.
- **Sanitización de Logs:** Redacción automática de tokens, credenciales y cabeceras sensibles en `osvaldo_downloader.log`.
- **Persistencia Segura:** Base de datos SQLite (modo WAL) con consultas 100% parametrizadas (historial, favoritos y configuración).
- **Thread-Safety en GUI:** Todas las tareas de red, análisis y descarga se ejecutan en hilos secundarios asíncronos comunicándose mediante `Signal` de Qt, garantizando que la interfaz nunca se congele.

---

## 🛠️ Desarrollo y Pruebas

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

El proyecto cuenta con **512 pruebas automatizadas** que cubren dominio, adaptadores de infraestructura, casos de uso, seguridad, interfaz gráfica y regresiones:

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
