# ============================================================
# osvaldoDownloaderPro - Publicacion de release en GitHub
#
# Sube los assets de una release ya construida por build_release.ps1.
# Existe porque la v1.5.3 se publico SIN assets (el tag existia pero no
# habia ni Setup.exe ni SHA256SUMS.txt). La app instalada detectaba
# "actualizacion disponible" pero no podia instalarla porque el
# actualizador exige esos dos archivos.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\publish_release.ps1
#       Publica la version de src\__init__.py (detecta si el tag ya existe).
#
#   powershell -ExecutionPolicy Bypass -File scripts\publish_release.ps1 -Version 1.5.3
#       Fuerza una version concreta.
#
#   powershell -ExecutionPolicy Bypass -File scripts\publish_release.ps1 -DryRun
#       Verifica todo y muestra lo que haria, SIN subir nada.
#
#   powershell -ExecutionPolicy Bypass -File scripts\publish_release.ps1 -Repo owner/repo
#       Publica en otro repositorio (lo usa el workflow de GitHub Actions, que
#       pasa el repo del checkout y autentica con la variable GH_TOKEN).
#
# Codigos de salida:
#   0 = release publicada y verificada
#   1 = error / faltan artefactos / fallo de subida o verificacion
# ============================================================

param(
    [string]$Version,
    [string]$Repo = "adrianpalacios782-dotcom/descarga",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistDir     = Join-Path $ProjectRoot "dist"
$SetupName   = "osvaldoDownloaderPro-{0}-Setup.exe"
$SumsName    = "SHA256SUMS.txt"

function Write-Step($msg) { Write-Host "[PUBLISH] $msg" -ForegroundColor Cyan }
function Write-Fail($msg) { Write-Host "[PUBLISH][ERROR] $msg" -ForegroundColor Red }
function Write-Warn($msg) { Write-Host "[PUBLISH][AVISO] $msg" -ForegroundColor Yellow }

Set-Location -LiteralPath $ProjectRoot

# --- 0. gh CLI ---
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Fail "No se encontro la CLI 'gh'. Instala GitHub CLI y ejecuta 'gh auth login'."
    exit 1
}
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "gh no esta autenticado. Ejecuta 'gh auth login'."
    exit 1
}

# --- 1. Version desde src/__init__.py (unica fuente de verdad) ---
if (-not $Version) {
    $SrcInit = Get-Content -LiteralPath (Join-Path $ProjectRoot "src\__init__.py") -Raw
    if ($SrcInit -notmatch '(?m)^\s*__version__\s*=\s*"(\d+\.\d+\.\d+)"\s*$') {
        Write-Fail "No se pudo leer __version__ de src/__init__.py"
        exit 1
    }
    $Version = $Matches[1]
}
$Tag     = "v$Version"
$SetupExe = Join-Path $ProjectRoot ("installer\" + ($SetupName -f $Version))
$SumsTxt = Join-Path $DistDir $SumsName

Write-Step "Version : $Version  (tag: $Tag)"

# --- 2. Existencia y validez de los assets (GATE) ---
$problems = @()

if (-not (Test-Path -LiteralPath $SetupExe)) {
    $problems += "Falta el instalador: $SetupExe  (ejecuta scripts\build_release.ps1 primero)"
}
if (-not (Test-Path -LiteralPath $SumsTxt)) {
    $problems += "Falta el archivo de hashes: $SumsTxt  (lo genera build_release.ps1)"
}

if ($problems.Count -gt 0) {
    foreach ($p in $problems) { Write-Fail $p }
    Write-Fail "No se publica una release sin assets completos. Esto fue exactamente el fallo de la v1.5.3."
    exit 1
}

# El nombre del asset DEBE coincidir con el patron que exige el actualizador.
if ((Split-Path $SetupExe -Leaf) -notmatch '^osvaldoDownloaderPro-(\d+\.\d+\.\d+)-Setup\.exe$') {
    Write-Fail "El nombre del instalador no cumple el patron que espera el actualizador de la app."
    exit 1
}

$SetupHash = (Get-FileHash -LiteralPath $SetupExe -Algorithm SHA256).Hash
$SetupSize = [math]::Round((Get-Item -LiteralPath $SetupExe).Length / 1MB, 1)
Write-Step "Instalador OK: $(Split-Path $SetupExe -Leaf)  ($SetupSize MB)"
Write-Step "SHA256     : $SetupHash"
Write-Step "Hashes     : $SumsTxt"

# --- 3. Tag y release ---
$tagExists = $false
gh release view $Tag --repo $Repo 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { $tagExists = $true }

if ($DryRun) {
    Write-Step "--- DRY RUN: no se sube nada ---"
    if ($tagExists) {
        Write-Step "La release $Tag ya existe en GitHub: se van a SUBIR/REEMPLAZAR sus assets."
    } else {
        Write-Step "La release $Tag NO existe: se va a CREAR con tag $Tag."
    }
    Write-Step "Assets a subir:"
    Write-Step "  - $(Split-Path $SetupExe -Leaf)  ($SetupSize MB)"
    Write-Step "  - $SumsName"
    exit 0
}

if (-not $tagExists) {
    Write-Step "Creando release $Tag (tag + notas)..."
    $notes = @"
## osvaldoDownloaderPro $Version

- **Instalador:** ``$($SetupName -f $Version)`` ($SetupSize MB)
- **SHA256 del instalador:** ``$SetupHash``
- **SHA256SUMS.txt** incluido para verificacion.

Verificacion:
``````powershell
Get-FileHash .\$(Split-Path $SetupExe -Leaf) -Algorithm SHA256
``````
"@
    gh release create $Tag --repo $Repo --title "osvaldoDownloaderPro $Version" --notes $notes 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "No se pudo crear la release $Tag."
        exit 1
    }
    Write-Step "Release $Tag creada."
} else {
    Write-Step "La release $Tag ya existe: se actualizan sus assets."
}

# --- 4. Subir assets (--clobber reemplaza si ya estaban) ---
$assets = @($SetupExe, $SumsTxt)
foreach ($a in $assets) {
    Write-Step "Subiendo $(Split-Path $a -Leaf)..."
    gh release upload $Tag $a --repo $Repo --clobber 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Fallo al subir $(Split-Path $a -Leaf)."
        exit 1
    }
}

# --- 5. Verificacion post-subida ---
Write-Step "Verificando assets publicados..."
$remote = gh release view $Tag --repo $Repo --json assets 2>&1 | ConvertFrom-Json
$names = @($remote.assets | ForEach-Object { $_.name })

$missing = @()
if ($names -notcontains ($SetupName -f $Version)) { $missing += ($SetupName -f $Version) }
if ($names -notcontains $SumsName) { $missing += $SumsName }

if ($missing.Count -gt 0) {
    foreach ($m in $missing) { Write-Fail "Asset ausente en GitHub tras la subida: $m" }
    Write-Fail "La release quedo incompleta. La app instalada no podra actualizarse."
    exit 1
}

foreach ($asset in $remote.assets) {
    $mb = [math]::Round($asset.size / 1MB, 1)
    Write-Step ("  {0}  ({1} MB)  descargas: {2}" -f $asset.name, $mb, $asset.downloadCount)
}

Write-Step ""
Write-Host "[PUBLISH] OK - release $Tag publicada con TODOS los assets." -ForegroundColor Green
Write-Host "[PUBLISH] La app instalada (v$Version anterior) ya puede actualizarse." -ForegroundColor Green
exit 0
