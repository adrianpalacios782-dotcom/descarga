# ============================================================
# osvaldoDownloaderPro - Build de release
# Pipeline completo: tests -> PyInstaller -> firma (opcional) -> Inno Setup
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
#       Pipeline firmado (requiere scripts\signing.config.json + certificado).
#
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -SkipSigning
#       Instalador BETA NO FIRMADO: compila Inno Setup sin SignTool, genera
#       dist\SHA256SUMS.txt y termina OK. Para pruebas internas/distribucion
#       beta; NO usar para release publico (Smart App Control bloqueara el exe
#       sin firma).
#
#   Si falta signing.config.json y no se pasa -SkipSigning, el pipeline tambien
#   continua en modo BETA NO FIRMADO con el mismo aviso en consola.
#
# Codigos de salida:
#   0 = release completo (firmado, o BETA no firmado si asi se solicito)
#   1 = error de build/tests/firma
# ============================================================

param(
    # Omite la firma Authenticode (equivale a AllowUnsigned): habilita el
    # instalador BETA sin firma cuando aun no existe certificado.
    [switch]$SkipSigning
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistDir     = Join-Path $ProjectRoot "dist"
$BuildDir    = Join-Path $ProjectRoot "build"
$AppDir      = Join-Path $DistDir "osvaldoDownloaderPro"
$IsccPath    = Join-Path $Env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
$IssPath     = Join-Path $ProjectRoot "installer.iss"
$ReleaseDir  = Join-Path $BuildDir "release"

# --- Version desde la UNICA fuente de verdad: src/__init__.py ---
$SrcInitPath = Join-Path $ProjectRoot "src\__init__.py"
if (-not (Test-Path -LiteralPath $SrcInitPath)) { Write-Fail "No existe src/__init__.py"; exit 1 }
$SrcInitRaw = Get-Content -LiteralPath $SrcInitPath -Raw
if ($SrcInitRaw -match '(?m)^\s*__version__\s*=\s*"(\d+\.\d+\.\d+)"\s*$') {
    $AppVersion = $Matches[1]
} else {
    Write-Fail "No se pudo leer __version__ de src/__init__.py"; exit 1
}
$AppVersionQuad = "$AppVersion.0"
$SetupExe    = Join-Path $ProjectRoot "installer\osvaldoDownloaderPro-$AppVersion-Setup.exe"

function Write-Step($msg) { Write-Host "[BUILD] $msg" -ForegroundColor Cyan }
function Write-Fail($msg) { Write-Host "[BUILD][ERROR] $msg" -ForegroundColor Red }

Set-Location -LiteralPath $ProjectRoot

# --- 0. Herramientas ---
if (-not (Test-Path -LiteralPath $IsccPath)) {
    Write-Fail "ISCC.exe no encontrado en: $IsccPath"
    exit 1
}

# --- Modo de firma: firmado solo si NO se pidio -SkipSigning Y existe config ---
$SigningConfigPath = Join-Path $PSScriptRoot "signing.config.json"
if ($SkipSigning) {
    $DoSign = $false
} elseif (-not (Test-Path -LiteralPath $SigningConfigPath)) {
    $DoSign = $false
} else {
    $DoSign = $true
}
if (-not $DoSign) {
    Write-Host ""
    Write-Host "[AVISO] Omitiendo firma digital. Generando instalador BETA NO FIRMADO." -ForegroundColor Yellow
    if ($SkipSigning) {
        Write-Host "[AVISO] Motivo: parametro -SkipSigning solicitado explicitamente." -ForegroundColor Yellow
    } else {
        Write-Host "[AVISO] Motivo: no existe scripts\signing.config.json (certificado sin configurar)." -ForegroundColor Yellow
    }
    Write-Host ""
}

# --- 1. Tests completos ---
Write-Step "Paso 1/8: Tests completos (pytest)"
python -m pytest --tb=short -q --basetemp=scratch/pytest_tmp
if ($LASTEXITCODE -ne 0) { Write-Fail "Tests fallaron. Build abortado."; exit 1 }

# --- 2. Tests de seguridad ---
Write-Step "Paso 2/8: Tests de seguridad (tests/unit/domain/test_security.py)"
python -m pytest tests\unit\domain\test_security.py --tb=short -q --basetemp=scratch/pytest_tmp
if ($LASTEXITCODE -ne 0) { Write-Fail "Tests de seguridad fallaron. Build abortado."; exit 1 }

# --- 3. Limpieza ---
Write-Step "Paso 3/8: Limpieza de build/ y dist/"
foreach ($dir in @($BuildDir, $DistDir)) {
    if (Test-Path -LiteralPath $dir) {
        Remove-Item -LiteralPath $dir -Recurse -Force
        if (Test-Path -LiteralPath $dir) { Write-Fail "No se pudo limpiar: $dir"; exit 1 }
    }
}

# --- 4. PyInstaller ---
Write-Step "Paso 4/8: PyInstaller (osvaldoDownloaderPro.spec)"

# Sincronia de metadatos: scripts/version_info.txt debe reflejar la version
# de src/__init__.py (unica fuente de verdad). Si difieren, el exe quedaria
# con identidad distinta al instalador -> rechazo en revision de Windows.
$ExpectedQuad = "$AppVersion.0"
$VersionInfoPath = Join-Path $ProjectRoot "scripts\version_info.txt"
if (-not (Test-Path -LiteralPath $VersionInfoPath)) { Write-Fail "Falta scripts/version_info.txt"; exit 1 }
$ViRaw = Get-Content -LiteralPath $VersionInfoPath -Raw
if ($ViRaw -notmatch [regex]::Escape("StringStruct('FileVersion', '$ExpectedQuad')")) {
    Write-Fail "version_info.txt: FileVersion != '$ExpectedQuad' (desincronizado con src/__init__.py)"; exit 1
}
if ($ViRaw -notmatch [regex]::Escape("StringStruct('ProductVersion', '$ExpectedQuad')")) {
    Write-Fail "version_info.txt: ProductVersion != '$ExpectedQuad'"; exit 1
}
$VerParts = $AppVersion.Split('.')
$ExpectedTuple = "filevers=\($($VerParts[0]),\s*$($VerParts[1]),\s*$($VerParts[2]),\s*0\)"
if ($ViRaw -notmatch $ExpectedTuple) {
    Write-Fail "version_info.txt: filevers no coincide con $ExpectedQuad"; exit 1
}

python -m PyInstaller osvaldoDownloaderPro.spec --noconfirm
if ($LASTEXITCODE -ne 0) { Write-Fail "PyInstaller fallo."; exit 1 }

# --- 5. Verificacion de artefactos ---
Write-Step "Paso 5/8: Verificacion de artefactos"
if (-not (Test-Path -LiteralPath (Join-Path $AppDir "osvaldoDownloaderPro.exe"))) {
    Write-Fail "Falta osvaldoDownloaderPro.exe"; exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $AppDir "_internal"))) {
    Write-Fail "Falta _internal\"; exit 1
}

# Proveer ffmpeg/ffprobe en la raiz de dist (layout conocido-bueno que espera installer.iss).
# PyInstaller los coloca dentro de _internal; el instalador y FFmpegProcessAdapter
# los esperan tambien junto al exe. Fuente de verdad: bin\
foreach ($bin in @("ffmpeg.exe", "ffprobe.exe")) {
    $src = Join-Path $ProjectRoot "bin\$bin"
    $dst = Join-Path $AppDir $bin
    if (-not (Test-Path -LiteralPath $src)) { Write-Fail "Falta binario fuente: $src"; exit 1 }
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
foreach ($r in @("ffmpeg.exe", "ffprobe.exe")) {
    if (-not (Test-Path -LiteralPath (Join-Path $AppDir $r))) { Write-Fail "Falta artefacto requerido: $r"; exit 1 }
}

# Metadatos de version embebidos en el exe (recurso VERSIONINFO de PyInstaller).
$AppExe = Join-Path $AppDir "osvaldoDownloaderPro.exe"
$Vi = (Get-Item -LiteralPath $AppExe).VersionInfo
if ($Vi.FileVersion -ne $ExpectedQuad) {
    Write-Fail "exe FileVersion='$($Vi.FileVersion)' != '$ExpectedQuad'"; exit 1
}
if ($Vi.ProductVersion -ne $ExpectedQuad) {
    Write-Fail "exe ProductVersion='$($Vi.ProductVersion)' != '$ExpectedQuad'"; exit 1
}
if ($Vi.ProductName -ne "osvaldoDownloaderPro") {
    Write-Fail "exe ProductName='$($Vi.ProductName)' inesperado"; exit 1
}
if ($Vi.CompanyName -ne "osvaldoDownloaderPro") {
    Write-Fail "exe CompanyName='$($Vi.CompanyName)' inesperado"; exit 1
}
Write-Step "Metadatos de version OK (FileVersion/ProductVersion=$ExpectedQuad, ProductName/CompanyName OK)"

Write-Step "Artefactos OK (exe + ffmpeg + ffprobe + _internal)"

# --- 6. Firma del exe de la app (solo en modo firmado) ---
if ($DoSign) {
    Write-Step "Paso 6/8: Firma de osvaldoDownloaderPro.exe"
    $signScript = Join-Path $PSScriptRoot "sign_release.ps1"
    powershell -NoProfile -ExecutionPolicy Bypass -File $signScript
    $signExit = $LASTEXITCODE

    # En modo firmado la config existe; cualquier fallo del firmador (incluido
    # "certificado no configurado", codigo 2) es un error duro del release.
    if ($signExit -ne 0) { Write-Fail "La etapa de firma fallo (codigo $signExit). Build abortado."; exit 1 }
    Write-Step "osvaldoDownloaderPro.exe firmado y verificado"
} else {
    Write-Step "Paso 6/8: Firma omitida (modo BETA NO FIRMADO)"
}

# --- 7. Compilar instalador (Inno Setup, con o sin SignTool) ---
$IsccArgs = @("/DAPP_VERSION=$AppVersion", "/DAPP_VERSION_QUAD=$AppVersionQuad")
if ($DoSign) {
    Write-Step "Paso 7/8: Compilando instalador (Inno Setup + USE_SIGNTOOL)"
    $TimestampUrl = "http://timestamp.digicert.com"
    if (Test-Path -LiteralPath $SigningConfigPath) {
        try {
            $cfg = Get-Content -LiteralPath $SigningConfigPath -Raw | ConvertFrom-Json
            if ($cfg.timestamp_url) { $TimestampUrl = $cfg.timestamp_url }
        } catch { }
    }
    $signToolDef = '/SReleaseSigner=signtool.exe sign /fd SHA256 /tr ' + $TimestampUrl + ' /td SHA256 $f'
    $IsccArgs = @("/DUSE_SIGNTOOL", $signToolDef) + $IsccArgs
} else {
    Write-Step "Paso 7/8: Compilando instalador BETA NO FIRMADO (Inno Setup sin SignTool)"
}
& $IsccPath @IsccArgs $IssPath
if ($LASTEXITCODE -ne 0) { Write-Fail "Inno Setup fallo."; exit 1 }

# --- 8. Verificaciones finales + hashes + reporte ---
Write-Step "Paso 8/8: Verificacion final del instalador"
if (-not (Test-Path -LiteralPath $SetupExe)) { Write-Fail "No se genero el Setup.exe"; exit 1 }

$SignSubject = "N/A (BETA NO FIRMADO)"
if ($DoSign) {
    $setupSig = Get-AuthenticodeSignature -FilePath $SetupExe
    if ($setupSig.Status -ne "Valid") {
        Write-Fail "El Setup.exe NO tiene firma valida (Status=$($setupSig.Status))."
        exit 1
    }
    $SignSubject = $setupSig.SignerCertificate.Subject
    Write-Step "Setup.exe firmado y verificado: $SignSubject"
}

# SHA256SUMS junto a los artefactos publicables, en dist/.
New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
$hashes = Get-FileHash -Path $SetupExe, (Join-Path $AppDir "osvaldoDownloaderPro.exe") -Algorithm SHA256
$hashLines = $hashes | ForEach-Object { "$($_.Hash)  $(Split-Path $_.Path -Leaf)" }
$hashLines | Set-Content -LiteralPath (Join-Path $DistDir "SHA256SUMS.txt") -Encoding ASCII

$ModoFirma = if ($DoSign) { "FIRMADO" } else { "BETA NO FIRMADO" }
@"
# RELEASE REPORT - osvaldoDownloaderPro $AppVersion ($ModoFirma)
Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Tests: PASS (completos + seguridad)
PyInstaller: OK
Metadatos de version del exe: OK ($ExpectedQuad)
UPX: DESACTIVADO
Firma app exe: $(if ($DoSign) { "VALIDA ($SignSubject)" } else { "NO REALIZADA (beta)" })
Instalador: $($SetupExe)
Firma instalador: $(if ($DoSign) { "VALIDA" } else { "NO REALIZADA (beta)" })
SHA256SUMS: dist\SHA256SUMS.txt
SHA256:
$($hashLines | ForEach-Object { "  $_" })
"@ | Set-Content -LiteralPath (Join-Path $ReleaseDir "RELEASE_REPORT.md") -Encoding UTF8

if ($DoSign) {
    Write-Step "RELEASE COMPLETO Y FIRMADO. Reporte en: $ReleaseDir"
} else {
    Write-Step "RELEASE BETA NO FIRMADO COMPLETO. Instalador: $SetupExe | Hashes: dist\SHA256SUMS.txt"
    Write-Host "[AVISO] Recuerda: el beta NO FIRMADO puede ser bloqueado por Smart App Control/antivirus." -ForegroundColor Yellow
}
exit 0
