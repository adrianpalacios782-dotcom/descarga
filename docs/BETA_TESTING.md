# Guía de Prueba Beta — osvaldoDownloaderPro 1.0.1

Gracias por probar la beta. Esta guía explica cómo instalar la aplicación, descargar contenido y reportar problemas.

---

## 0. Requisitos del sistema

**Sistemas operativos compatibles:**

- Windows 10 x64 versión 1809 o superior
- Windows 11 x64

**No se garantiza compatibilidad con:**

- Windows 10 LTSB/LTSC 2016 o anteriores
- Windows 32-bit

---

## 1. Descargar el instalador

1. Abre la página del repositorio en GitHub.
2. Entra a la sección **Releases** (columna derecha).
3. Descarga el archivo:

   ```
   osvaldoDownloaderPro-1.0.1-Setup.exe
   ```

4. (Opcional) Verifica que tu copia es idéntica a la publicada comparando el hash SHA256 con el valor publicado junto al release.

## 2. Instalar

1. Haz doble clic en `osvaldoDownloaderPro-1.0.1-Setup.exe`.
2. Sigue el asistente. **No necesita permisos de administrador** (se instala para tu usuario).
3. Al terminar, la aplicación puede iniciarse sola si marcaste esa opción.

### Avisos de Windows (importante)

El instalador de la beta **no está firmado digitalmente** todavía, por eso Windows puede avisar:

- **SmartScreen** ("Windows protegió tu PC"): haz clic en **Más información** → **Ejecutar de todas formas**.
- **Smart App Control (solo Windows 11):** si está en modo *Enforcement*, Windows bloqueará la ejecución de apps sin firma y no se podrá abrir la aplicación. Esto es una política del sistema, no un error de la app. Si te ocurre, avísanos; con certificado de firma digital desaparece.

Installer currently unsigned. Code-signing certificate required for production distribution.

## 3. Abrir osvaldoDownloaderPro

- Desde el menú Inicio: **osvaldoDownloaderPro**, o
- Desde el acceso directo en el escritorio (si lo creaste durante la instalación).

## 4. Pegar una URL

1. Copia el enlace del video que quieres (barra de direcciones o botón "Compartir" → "Copiar enlace").
2. Pégalo en el campo de URL de la pantalla principal.
3. Pulsa **Analizar**. La app consultará las calidades disponibles para ese contenido.

## 5. Seleccionar calidad

- **Modo VIDEO:** elige entre las resoluciones listadas (por ejemplo 1080p, 720p...). La lista muestra formato, FPS y tamaño estimado cuando está disponible.
- **Modo AUDIO:** elige formato (**MP3**, M4A o WAV) y tasa de bits (320 / 256 / 192 / 128 kbps).

## 6. Descargar

1. Elige la carpeta de destino (por defecto: tu carpeta **Descargas**).
2. Pulsa **Descargar**.
3. Verás progreso, velocidad y ETA en tiempo real. Al terminar, el archivo queda en la carpeta elegida.

## 7. Plataformas soportadas

| Plataforma | Estado en beta | Notas |
|---|---|---|
| YouTube | Funcional | Calidades reales validadas hasta 1080p+ |
| TikTok | Funcional | Videos públicos |
| Instagram | Funcional | Posts/reels públicos; contenido privado requiere sesión y no está soportado |
| Facebook | Funcional | Calidades SD/HD aproximadas según el video |

Si una plataforma cambia algo internamente, alguna descarga puede fallar temporalmente hasta actualizar el motor.

## 8. Qué hacer si falla una descarga

1. Reintenta una vez: muchas fallas son temporales (red o límite temporal de la plataforma).
2. Prueba otra calidad distinta (algunas URLs solo ofrecen ciertas resoluciones).
3. Revisa que la URL sea pública y abra correctamente en tu navegador.
4. Consulta el log técnico si quieres ver el detalle:
   `%USERPROFILE%\.osvaldoDownloaderPro\logs\osvaldo_downloader.log`

## 9. Cómo reportar un error

Envíame por el canal que uses (WhatsApp/Discord/correo) un mensaje breve con lo siguiente:

## 10. Información a incluir en el reporte

- **Plataforma:** YouTube / TikTok / Instagram / Facebook
- **URL del contenido:** solo si es público y te parece apropiado compartirlo
- **Calidad seleccionada:** ejemplo: "MP3 320 kbps" o "1080p"
- **Mensaje de error exacto:** tal como apareció en pantalla
- **Versión de la aplicación:** 1.0.1 (visible en la sección Acerca de)
- **Tu versión de Windows:** ejemplo: "Windows 11" o "Windows 10"

No envíes capturas con datos personales, contraseñas ni contenido privado.

---

Gracias por ayudar a probar osvaldoDownloaderPro.
