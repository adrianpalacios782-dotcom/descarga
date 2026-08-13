# osvaldoDownloaderPro — Guía de Solución de Problemas (Troubleshooting)

**Proyecto:** osvaldoDownloaderPro  

---

## 1. PROBLEMAS COMUNES Y SOLUCIONES

### A. YouTube Solicita Verificación ("Sign in to confirm you're not a bot")
- **Causa:** YouTube aplica restricciones temporales a IPs o solicitudes sin cookies.
- **Solución:** La aplicación incluye rotación automática de `player_client` (`["web", "android", "mweb"]`) y fallback a `cookiesfrombrowser` para cargar cookies del navegador (Chrome, Edge, Firefox, Brave, Opera).

### B. Error `ModuleNotFoundError: No module named 'src'` al ejecutar `python src/main.py`
- **Causa:** Ejecución directa desde terminal sin incluir el directorio raíz del proyecto en `sys.path`.
- **Solución:** `src/main.py` incluye resolución automática de `sys.path` al inicio. Se puede ejecutar con `python src/main.py` o `python -m src.main`.

### C. FFmpeg No Detectado
- **Causa:** El ejecutable `ffmpeg.exe` no se encuentra en el `PATH` del sistema ni en `bin/ffmpeg.exe`.
- **Solución:** Colocar `ffmpeg.exe` dentro de la carpeta `bin/` en la raíz del proyecto o agregarlo a las variables de entorno de Windows. La app cambiará a modo streaming básico si no se detecta FFmpeg.
