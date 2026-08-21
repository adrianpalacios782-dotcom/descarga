# osvaldoDownloaderPro

**Versión 1.0.0 · Estado: BETA**

Aplicación de escritorio nativa para Windows 10/11 diseñada para la descarga, conversión y organización de contenido multimedia desde múltiples plataformas web.

---

## Compatibilidad

**Sistemas operativos compatibles:**

- Windows 10 x64 versión 1809 o superior
- Windows 11 x64

**No se garantiza compatibilidad con:**

- Windows 10 LTSB/LTSC 2016 o anteriores
- Windows 32-bit

> La compatibilidad fue auditada estáticamente sobre los componentes, dependencias y binarios empaquetados (Qt 6.11 requiere Windows 10 1809+; Python 3.13 requiere Windows 10+). La ejecución del EXE empaquetado en un equipo físico con Windows 10 queda como prueba ambiental pendiente, no disponible en el entorno de desarrollo.

---

## Plataformas soportadas

- YouTube
- TikTok
- Instagram
- Facebook

## Características

- Descarga de **video** con selección dinámica de calidad (144p hasta la máxima disponible, según el contenido).
- Descarga de **audio MP3** (también M4A y WAV) con selección de tasa de bits (320 / 256 / 192 / 128 kbps).
- **Selección de calidad** real basada en los formatos que el servidor ofrece para cada URL.
- Procesamiento con **FFmpeg** embebido: fusión de flujos DASH (video + audio) sin re-codificación y extracción de audio.
- Persistencia local con **SQLite** (modo WAL): historial, favoritos y configuración.
- Arquitectura Hexagonal + Event-Driven: capas Domain, Application, Infrastructure y Presentation estrictamente desacopladas.
- Interfaz moderna en modo oscuro construida con PySide6.

## Seguridad

El proyecto incorpora las siguientes protecciones, cubiertas por una suite automatizada de pruebas:

- **Protección SSRF:** bloqueo de localhost, direcciones IP privadas, loopback IPv6, rangos reservados y puertos peligrosos.
- **Allowlist de dominios:** solo se aceptan URLs de las plataformas soportadas.
- **Protección contra path traversal:** validación de rutas de destino y contención de archivos resultantes.
- **Validación de formatos:** sanitización de `format_id` y nombres de archivo contra inyección.
- **Validación del binario FFmpeg:** solo se ejecutan binarios con nombre esperado ubicados en rutas controladas.
- **Sanitización de logs:** tokens, credenciales y cabeceras sensibles se redactan antes de escribirse al log.
- **SQLite parametrizado:** todas las consultas usan consultas preparadas.

Nota: el software se ofrece como BETA. Analiza siempre los resultados de tus descargas y úsalo respetando los términos de servicio de cada plataforma.

## Instalación (usuarios)

1. Ve a la sección [Releases](../../releases) del repositorio.
2. Descarga `osvaldoDownloaderPro-1.0.0-Setup.exe`.
3. Ejecuta el instalador y sigue el asistente (no requiere permisos de administrador).
4. Guía completa paso a paso: [`docs/BETA_TESTING.md`](docs/BETA_TESTING.md).

> **Nota:** el instalador de la beta no está firmado digitalmente. Windows SmartScreen puede mostrar un aviso ("Windows protegió tu PC"); usa "Más información" → "Ejecutar de todas formas". En Windows 11 con Smart App Control en modo de enforcement, la ejecución de aplicaciones sin firma puede bloquearse por política del sistema.
>
> Installer currently unsigned. Code-signing certificate required for production distribution.

Los datos de la aplicación (base de datos y logs) se guardan en `%USERPROFILE%\.osvaldoDownloaderPro\`. Las descargas, por defecto, en la carpeta `Downloads` del usuario.

## Desarrollo

### Requisitos previos

- Python 3.11 o superior
- FFmpeg y ffprobe accesibles (colocar `ffmpeg.exe` y `ffprobe.exe` en `bin\`, o disponibles en PATH)

### Puesta en marcha

```powershell
pip install -e ".[dev]"
python src/main.py
```

### Suite de pruebas

166 tests unitarios, de integración y E2E (incluye 83 tests de seguridad):

```powershell
python -m pytest
```

### Build del instalador

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

Pipeline: tests → PyInstaller (`osvaldoDownloaderPro.spec`) → verificación de artefactos → firma opcional → Inno Setup (`installer.iss`). Sin certificado configurado, el pipeline se detiene antes de firmar con código de salida 3.

## Documentación técnica

- [`docs/BETA_TESTING.md`](docs/BETA_TESTING.md): guía de prueba para beta testers.
- [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md): informe de auditoría integral.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): especificación de arquitectura de capas.
- [`docs/TESTING.md`](docs/TESTING.md): estrategia y cobertura de pruebas.
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md): solución de problemas frecuentes.
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md): historial de cambios.
