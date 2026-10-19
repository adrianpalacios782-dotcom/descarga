# osvaldoDownloaderPro — Desbloqueo de Calidades con Cookies (720p, 1080p, 4K, 60 FPS)

**Proyecto:** osvaldoDownloaderPro

---

## 1. POR QUÉ FALTAN CALIDADES EN YOUTUBE

Cuando YouTube no conoce tu sesión, responde como a un visitante anónimo y aplica restricciones automáticas:

- **Detección de bots:** el mensaje *"Sign in to confirm you're not a bot"* bloquea el análisis o limita los formatos disponibles.
- **Restricción de edad o videos de suscriptores:** sin cookies de una cuenta válida, YouTube no entrega los streams DASH (`hls_videos` / `dash_videos`) y solo se muestran calidades bajas (360p/720p).

La solución es indicarle a la aplicación tus cookies de sesión. Con ellas, YouTube entregará de inmediato **todas** las resoluciones disponibles: 1080p, 1440p, 4K e incluso 8K y 60 FPS.

---

## 2. MÉTODO RECOMENDADO: ARCHIVO COOKIES.TXT (MÁS RÁPIDO Y SIN CONFLICTOS)

1. Instala en tu navegador habitual (Chrome, Firefox, Edge o Brave) una extensión para exportar cookies en formato Netscape, por ejemplo: **Get cookies.txt LOCALLY** (código abierto y segura).
2. Entra a [YouTube](https://www.youtube.com) con tu cuenta, haz clic en el icono de la extensión y descarga tu archivo `cookies.txt`.
3. Abre **osvaldoDownloaderPro**, ve a la pestaña **Configuración** y, dentro de la sección **AVANZADO (SESIÓN Y CONTENIDO RESTRINGIDO)**, busca la fila **"Archivo de cookies (cookies.txt)"**.
4. Haz clic en el botón **Examinar...** 📁 y selecciona tu archivo `cookies.txt`.
5. Haz clic en **Guardar Preferencias**.
6. Regresa a la pestaña **Inicio** y vuelve a pegar el enlace del video: YouTube entregará de inmediato todas las resoluciones (1080p, 1440p, 4K, 60 FPS).

> [!TIP]
> Si ya tenías la ventana de análisis abierta, vuelve a pegar el enlace después de guardar: la configuración se aplica en caliente tanto al análisis como a la descarga, sin necesidad de reiniciar la aplicación.

---

## 3. MÉTODO ALTERNATIVO: COOKIES DIRECTAS DEL NAVEGADOR

En la misma sección **AVANZADO (SESIÓN Y CONTENIDO RESTRINGIDO)** de **Configuración** encontrarás el desplegable **"Navegador para cookies"**, con las opciones:

- Desactivado (Recomendado)
- **Chrome**
- **Edge**
- **Firefox**
- **Brave**

Selecciona el navegador donde iniciaste sesión en YouTube y pulsa **Guardar Preferencias**. La aplicación extraerá las cookies de ese navegador automáticamente.

> [!NOTE]
> **Importante (Windows):** si en lugar de un archivo `cookies.txt` prefieres seleccionar directamente Google Chrome (u otro navegador) en el desplegable, asegúrate de **cerrar por completo el navegador antes de analizar o descargar**, ya que Windows bloquea la base de datos de cookies de Chrome mientras el navegador está abierto en segundo plano.
>
> Si las cookies no se pueden leer, la aplicación lo detecta, reintenta el análisis sin cookies del navegador y muestra un mensaje claro indicando que cierres el navegador o uses un archivo `cookies.txt`.

---

## 4. CÓMO COMPROBAR QUE FUNCIONÓ

1. Pega el enlace del video en la pestaña **Inicio** y pulsa **Analizar**.
2. Abre la **tabla de formatos** de la tarjeta de previsualización.
3. Si ves resoluciones de **1080p, 1440p o 4K**, y formatos con **60 FPS** (junto a la etiqueta de códec H.264/VP9/AV1), las cookies se aplicaron correctamente.

---

## 5. PRIVACIDAD Y SEGURIDAD

- Tus cookies se leen y se usan **localmente** en tu PC; nunca se envían a servidores de terceros ni se almacenan en la nube.
- Solo se comparten con el propio motor **yt-dlp** para autenticar la petición contra la plataforma (YouTube, Twitch, etc.).
- Los registros de la aplicación **redactan automáticamente** cookies y tokens para que no queden expuestos en archivos de log.

---

## 6. PROBLEMAS COMUNES

| Síntoma | Causa probable | Solución |
|:---|:---|:---|
| Sigue apareciendo *"Sign in to confirm you're not a bot"* | Cookies caducadas o incompletas | Re-exporta el archivo `cookies.txt` estando iniciado sesión en YouTube y vuelve a seleccionarlo en **Configuración** → **Examinar...** → **Guardar Preferencias**. |
| Error indicando que Windows bloquea las cookies del navegador | El navegador sigue abierto | Cierra por completo el navegador (incluidas sus ventanas en segundo plano) o utiliza un archivo `cookies.txt`. |
| Las calidades altas no aparecen tras guardar | El análisis se hizo antes de guardar | Vuelve a pegar el enlace en **Inicio** y analiza de nuevo. |
| El archivo `cookies.txt` no se selecciona | Formato no soportado | Usa el formato **Netscape** que genera la extensión *Get cookies.txt LOCALLY*. |
| No reconoces la sección en Configuración | Versión antigua de la aplicación | Actualiza a la última versión desde **Configuración** → **ACTUALIZACIONES**. |

---

Consulta también la [Guía de Solución de Problemas](TROUBLESHOOTING.md) para otros errores frecuentes.
