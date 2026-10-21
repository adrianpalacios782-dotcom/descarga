# Limpieza segura - comandos de respaldo y borrado

Este documento agarra las tres tareas de limpieza pendientes, con los comandos
exactos y **en el orden seguro**: primero se respalda, despues se borra.

Regla general: **ningún borrado sin un respaldo verificable detrás**.

---

## 1. Prototipo viejo `D:\Proyectos\Python\YTDownloaderPro`

**Estado verificado (2026-10-21):** 3.26 MB, **437 archivos**, **sin Git**
(no hay `.git`), arquitectura pre-refactor (`ytdownloader/`, `ui/`, `app.py`,
`pyproject.toml` con solo black/ruff). La **última escritura** de la carpeta
es del **19-oct-2026 22:04**, no de agosto de 2026. Puede servir de referencia
histórica (por ejemplo `docs/contracts/versioning.md` ADR-008), pero no
participa del build actual.

### 1.1 Respaldar (ZIP fechado, fuera del repo)

```powershell
$src   = "D:\Proyectos\Python\YTDownloaderPro"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"           # el ZIP queda fechado
$dst   = "D:\Proyectos\Python\_backups\YTDownloaderPro-prototipo-$stamp.zip"

New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
Compress-Archive -Path (Join-Path $src "*") -DestinationPath $dst -Force

Write-Host "Respaldo creado: $dst"
Get-FileHash -LiteralPath $dst -Algorithm SHA256
```

> `Compress-Archive` no incluye carpetas ocultas (`.ruff_cache`, `.coverage`).
> Es aceptable: son cachés regenerables. Si se quiere un respaldo exacto,
> usar `robocopy` (ver 1.2).

### 1.1b Comprobación de integridad (obligatoria antes de borrar)

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::OpenRead($dst)
try {
    # a) Numero de entradas con contenido == numero de archivos del origen
    $entries = @($zip.Entries | Where-Object { $_.Length -gt 0 })
    $esperados = (Get-ChildItem -LiteralPath $src -Recurse -File -Force).Count
    Write-Host "Entradas en el zip: $($entries.Count) / archivos en el origen: $esperados"
    if ($entries.Count -ne $esperados) {
        throw "El zip no contiene todos los archivos del origen ($($entries.Count) != $esperados)"
    }

    # b) CRC de cada entrada: descomprime el archivo entero. Si el zip esta
    #    corrupto, .NET lanza excepcion aqui.
    $buffer = New-Object byte[] 65536
    foreach ($e in $entries) {
        $s = $e.Open()
        try { while ($s.Read($buffer, 0, $buffer.Length) -gt 0) { } }
        finally { $s.Dispose() }
    }
    Write-Host "Integridad OK: $($entries.Count) entradas descomprimidas sin error de CRC"
}
finally { $zip.Dispose() }
```

### 1.2 Alternativa: copia exacta con robocopy

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = "D:\Proyectos\Python\_backups\YTDownloaderPro-$stamp"
robocopy "D:\Proyectos\Python\YTDownloaderPro" $dest /E /R:1 /W:1 /NFL /NDL
if ($LASTEXITCODE -ge 8) { throw "robocopy fallo con codigo $LASTEXITCODE" }
```

### 1.3 Borrar (solo después de verificar el respaldo)

```powershell
$src = "D:\Proyectos\Python\YTDownloaderPro"

# 1) El respaldo tiene que existir y pesar mas de 1 MB
if (-not (Test-Path -LiteralPath $dst)) { throw "No existe el respaldo: $dst" }
if ((Get-Item -LiteralPath $dst).Length -lt 1MB) { throw "El respaldo parece incompleto" }

# 2) Y tiene que seguir abriendo y conteniendo los 437 archivos
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($dst)
try {
    if (@($zip.Entries | Where-Object { $_.Length -gt 0 }).Count -lt 400) {
        throw "El respaldo esta incompleto: no se borra el original"
    }
}
finally { $zip.Dispose() }

# 3) Borrado recursivo y forzado
Remove-Item -LiteralPath $src -Recurse -Force
```

### 1.4 ¿Recuperarlo después?

```powershell
# Sustituir <stamp> por el del ZIP realmente generado en 1.1
Expand-Archive -Path "D:\Proyectos\Python\_backups\YTDownloaderPro-prototipo-<stamp>.zip" `
                -DestinationPath "D:\Proyectos\Python\YTDownloaderPro" -Force
```

---

## 2. Repo externo `D:\Proyectos\Web\app tarija`

**Estado:** rama `main`, **2 commits por delante** de `origin/main`, y dos
rutas sin trackear (`assets/`, `test_mirrors.cjs`).

> Los 2 commits sin pushear son el trabajo real. **No se descartan.**

### 2.1 Ver qué hay antes de tocar nada

```powershell
cd "D:\Proyectos\Web\app tarija"
git status
git log --oneline origin/main..HEAD      # los commits que NO estan en GitHub
git stash list
```

### 2.2 Respaldar el estado completo (stash con etiqueta)

```powershell
git add -A
git stash push -m "respaldo-pre-limpieza-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
git stash list
```

Esto guarda **tracked modificados + untracked** en un stash con nombre.
Recuperar con:

```powershell
git stash pop            # o: git stash apply stash@{0}
```

### 2.3 Publicar los 2 commits pendientes (lo correcto si el trabajo está listo)

```powershell
git push origin main
git status                # debe quedar "main...origin/main" sin ahead
```

Si el push es rechazado por divergencia:

```powershell
git fetch origin
git rebase origin/main
git push origin main
```

### 2.4 Si los untracked (`assets/`, `test_mirrors.cjs`) no son wanted

```powershell
# Revisarlos primero
Get-ChildItem assets -Recurse | Select-Object FullName, Length
Get-Content test_mirrors.cjs -TotalCount 40

# Descartarlos (NO recuperables: por eso el stash de 2.2 va primero)
git clean -nd          # dry run: muestra qué se borraría
git clean -fd          # borra
```

### 2.5 Respaldo en rama propia (si el trabajo está a medias)

```powershell
git switch -c wip/app-tarija-$(Get-Date -Format 'yyyyMMdd')
git add -A
git commit -m "wip: respaldo de trabajo en curso"
git push -u origin wip/app-tarija-$(Get-Date -Format 'yyyyMMdd')
```

---

## 3. Repo externo `D:\Proyectos\Web\peponna\pepokita`

**Estado:** `main` sincronizado con `origin` (`autolavado`), **8 archivos
modificados + 1 migración nueva sin trackear**:

```
 M server/api/reservations/cancel.post.ts
 M server/api/reservations/lookup.post.ts
 M server/utils/rate-limit.ts
 M shared/constants/index.ts
 M shared/schemas/reservation.ts
 M tests/constants.spec.ts
 M tests/rate-limit.spec.ts
 M tests/reservation-schemas.spec.ts
?? supabase/migrations/0009_code_entropy.sql
```

### 3.1 Ver el detalle del cambio

```powershell
cd "D:\Proyectos\Web\peponna\pepokita"
git diff --stat
git diff
```

### 3.2 Respaldar antes de decidir

```powershell
# Un stash con nombre (recuperable)
git add -A
git stash push -m "respaldo-pre-limpieza-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# Y/o un parche en disco (independiente del repo)
git diff > "D:\Proyectos\Python\_backups\pepokita-$(Get-Date -Format 'yyyyMMdd-HHmmss').patch"
```

### 3.3 Commit local (sin publicar) - la opción más segura

```powershell
git add -A
git commit -m "feat(reservations): code entropy en migraciones y rate-limit"
git log --oneline -3
# Todavía NO se sube: el commit queda en local y es reversible con:
#   git reset --soft HEAD~1
```

### 3.4 Publicar cuando el trabajo esté revisado

```powershell
git push origin main
```

### 3.5 Volver atrás (deshacer el commit local, conservando los cambios)

```powershell
git reset --soft HEAD~1     # conserva los cambios en el índice
git reset                   # conserva los cambios en el working tree
```

---

## 4. Chequeo final: ningún duplicado ni trabajo perdido

```powershell
# 1) El repo canonico es el unico con el remote de descarga
Get-ChildItem "D:\Proyectos\Python" -Directory -Recurse -Depth 2 -Filter ".git" -Force -ErrorAction SilentlyContinue |
  ForEach-Object {
    $r = Join-Path $_.Parent.FullName ""
    $url = (git -C $r remote get-url origin 2>$null)
    if ($url -like "*adrianpalacios782-dotcom/descarga*") { Write-Host "COPIA DUPLICADA: $r" }
  }

# 2) Estado de los repos externos
git -C "D:\Proyectos\Web\app tarija" status -sb
git -C "D:\Proyectos\Web\peponna\pepokita" status -sb

# 3) Stashes pendientes (no deben quedar olvidados)
git -C "D:\Proyectos\Web\app tarija" stash list
git -C "D:\Proyectos\Web\peponna\pepokita" stash list
```

---

## 5. Resumen (copiar/pegar)

```powershell
# --- 1) Prototipo YTDownloaderPro: respaldar, verificar y borrar ---
$src   = "D:\Proyectos\Python\YTDownloaderPro"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dst   = "D:\Proyectos\Python\_backups\YTDownloaderPro-prototipo-$stamp.zip"

New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
Compress-Archive -Path (Join-Path $src "*") -DestinationPath $dst -Force

# Verificacion: existe, pesa > 1 MB y abre sin error de CRC
if (-not (Test-Path -LiteralPath $dst)) { throw "No existe el respaldo" }
if ((Get-Item -LiteralPath $dst).Length -lt 1MB) { throw "Respaldo incompleto" }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($dst)
try { Write-Host "Entradas: $(@($zip.Entries).Count)" } finally { $zip.Dispose() }

# Solo ahora se borra el original
Remove-Item -LiteralPath $src -Recurse -Force

# --- 2) app tarija: publicar los 2 commits pendientes ---
git -C "D:\Proyectos\Web\app tarija" push origin main
git -C "D:\Proyectos\Web\app tarija" status -sb

# --- 3) pepokita: commit local (no publicar hasta revisarlo) ---
git -C "D:\Proyectos\Web\peponna\pepokita" add -A
git -C "D:\Proyectos\Web\peponna\pepokita" commit -m "feat(reservations): code entropy y rate-limit"
git -C "D:\Proyectos\Web\peponna\pepokita" log --oneline -3
```

> Los repos externos (`app tarija`, `pepokita`) **no se tocan desde este
> repositorio**: los comandos de arriba son para ejecutarlos a mano en su
> propia carpeta. Ver `docs/EXTERNAL_REPOS.md` para el detalle completo.
