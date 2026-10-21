# Setup local — Carpeta canónica

Este proyecto tiene **una única copia local**. Todo el trabajo y todos los pushes
deben salir desde esta carpeta.

## Carpeta canónica

```
D:\Proyectos\Python\descarga
```

- **Remote:** `https://github.com/adrianpalacios782-dotcom/descarga.git`
- **Rama principal:** `main`

### Por qué existe este archivo

Históricamenteconvivieron **4 clones** del mismo repo en el PC:

| Carpeta | Estado |
|---|---|
| `D:\Proyectos\Python\descarga` | ✅ **CANÓNICA** (esta) |
| `D:\Proyectos\Python\osvaldoDownloaderPro` | ❌ eliminada (tenía repos anidados y 1.5 GB de installers viejos) |
| `C:\Users\qyt95\AppData\Local\Temp\opencode\descarga` | ❌ eliminada (era la carpeta de trabajo temporal) |
| `C:\Users\qyt95\AppData\Local\Temp\descarga` | ❌ eliminada (obsoleta, v1.5.0) |

Con varias copias, cualquier `git push` desde cualquiera de ellas publicaba al
mismo repo y era imposible saber desde cuál se venía trabajando.

## Reglas

1. **Nunca clones este repo fuera de `D:\Proyectos\Python\descarga`.**
   Si necesitas working space extra, usa un *worktree*:
   ```powershell
   git -C D:\Proyectos\Python\descarga worktree add D:\Proyectos\_wt\mi-rama -b mi-rama
   ```
   (después bórralo con `git worktree remove`).
2. **El hook `pre-push` está activo** y muestra el destino en cada push.
   Está versionado en `.githooks/pre-push` y se activa con:
   ```powershell
   git config core.hooksPath .githooks
   ```
   Si alguna vez se desactiva, restáuralo con ese mismo comando.
3. Antes de publicar una release, verificá que estás en la carpeta correcta:
   ```powershell
   git rev-parse --show-toplevel
   ```

## Entorno de desarrollo

El `.venv` **no** es portable entre carpetas. Si clonás en otro lado, recrealo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Build y release

### En local

```powershell
# 1) Tests + empaquetado + instalador (valida version_info.txt vs src/__init__.py)
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -SkipSigning

# 2) Publicar en GitHub (crea o actualiza la release y sube los assets)
powershell -ExecutionPolicy Bypass -File scripts\publish_release.ps1
```

### En GitHub Actions (recomendado)

Hay dos workflows:

| Workflow | Cuándo corre | Qué hace |
|---|---|---|
| `.github/workflows/ci.yml` | push/PR a `main` | ruff + mypy `--strict` + pytest. Es el gate de calidad. |
| `.github/workflows/release.yml` | tag `v*` o manual (`workflow_dispatch`) | quality → build (PyInstaller + Inno Setup) → publish con gates |

Publicar una release con CI:

```powershell
# 1) Subir los cambios
git add -A
git commit -m "release: v1.5.4"
git push origin main

# 2) Crear y subir el tag (dispara el workflow)
git tag v1.5.4
git push origin v1.5.4
```

El workflow **falla** (y no publica) si:

- ruff, mypy o pytest fallan,
- la versión del tag no coincide con `src/__init__.py::__version__`,
- falta `installer\osvaldoDownloaderPro-<version>-Setup.exe` o `dist\SHA256SUMS.txt`,
- tras subir, la API de GitHub no devuelve los 2 assets.

El instalador que produce CI sale **sin firma** (no hay certificado en el
runner). Ver `docs/SIGNING.md`.

> En CI, `bin/ffmpeg.exe` y `bin/ffprobe.exe` se descargan automáticamente
> (están en `.gitignore`); en local se conservan.

El paso 2 produce/usa estos dos archivos:

- `installer\osvaldoDownloaderPro-<VERSION>-Setup.exe`
- `dist\SHA256SUMS.txt`

> La release **debe** tener ambos assets. Si se publica el tag sin ellos, la
> app instalada detecta "actualización disponible" pero no puede instalarla
> (ver `src/infrastructure/updater/` y `docs/TROUBLESHOOTING.md`).
> Eso fue exactamente lo que pasó con la v1.5.3, publicada sin assets.
> `publish_release.ps1` se niega a publicar si falta alguno.

## Carpetas pesadas regenerables

Estas no se versionan (están en `.gitignore`) y se pueden borrar sin miedo:

| Carpeta | Qué es |
|---|---|
| `.venv/` | entorno virtual de Python |
| `build/`, `dist/` | salida de PyInstaller |
| `installer/` | Setup.exe generados |
| `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `scratch/` | cachés |

**Excepción:** `bin/` contiene `ffmpeg.exe` / `ffprobe.exe`, que **no** se
regeneran solos y son necesarios para empaquetar. No lo borres.
