# ============================================================
# osvaldoDownloaderPro - Firma de release
# Firma dist\osvaldoDownloaderPro\osvaldoDownloaderPro.exe con
# Authenticode (SHA256 + timestamp RFC3161) y verifica el resultado.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\sign_release.ps1
#
# Requisitos:
#   - signtool.exe (Windows SDK) en PATH o en la ruta indicada en el config.
#   - scripts\signing.config.json con los datos del certificado.
#     Ver scripts\signing.config.example.json para el formato.
#
# Codigos de salida:
#   0 = firmado y verificado OK
#   1 = error real (signtool ausente, firma invalida, etc.)
#   2 = certificado NO configurado (estado esperado antes de adquirirlo)
#
# REGLAS:
#   - NUNCA firma ffmpeg.exe ni ffprobe.exe (binarios de terceros).
#   - NUNCA continua silenciosamente si la firma no se puede verificar.
# ============================================================

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConfigPath  = Join-Path $PSScriptRoot "signing.config.json"
$AppExe      = Join-Path $ProjectRoot "dist\osvaldoDownloaderPro\osvaldoDownloaderPro.exe"

function Write-Step($msg)  { Write-Host "[SIGN] $msg" }
function Write-Fail($msg)  { Write-Host "[SIGN][ERROR] $msg" -ForegroundColor Red }

# --- 1. Configuracion de certificado ---
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    Write-Host ""
    Write-Host "CERTIFICATE NOT CONFIGURED - BUILD PREPARED BUT RELEASE SIGNING NOT PERFORMED." -ForegroundColor Yellow
    Write-Host "Esperado: scripts\signing.config.json no existe todavia (no se ha adquirido certificado)."
    Write-Host "Plantilla disponible en: scripts\signing.config.example.json"
    exit 2
}

try {
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
} catch {
    Write-Fail "signing.config.json no es JSON valido: $_"
    exit 1
}

# --- 2. Localizar signtool.exe ---
$SigntoolPath = $null
if ($config.signtool_path -and (Test-Path -LiteralPath $config.signtool_path)) {
    $SigntoolPath = $config.signtool_path
} else {
    $cmd = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($cmd) { $SigntoolPath = $cmd.Source }
}
if (-not $SigntoolPath) {
    $kits = @("C:\Program Files (x86)\Windows Kits\10\bin", "C:\Program Files\Windows Kits\10\bin")
    foreach ($kit in $kits) {
        if (Test-Path $kit) {
            $found = Get-ChildItem $kit -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
                     Sort-Object FullName -Descending | Select-Object -First 1
            if ($found) { $SigntoolPath = $found.FullName; break }
        }
    }
}
if (-not $SigntoolPath -or -not (Test-Path -LiteralPath $SigntoolPath)) {
    Write-Fail "signtool.exe no encontrado. Instala Windows SDK o define 'signtool_path' en signing.config.json."
    exit 1
}
Write-Step "signtool: $SigntoolPath"

# --- 3. Validar bloque de certificado ---
$cert = $config.certificate
if (-not $cert -or -not $cert.type) {
    Write-Fail "signing.config.json no define 'certificate.type' ('store' o 'pfx')."
    exit 1
}

$signtoolArgs = @("sign")
switch ($cert.type.ToLower()) {
    "store" {
        if     ($cert.thumbprint) { $signtoolArgs += @("/sha1", $cert.thumbprint) }
        elseif ($cert.subject)    { $signtoolArgs += @("/n", $cert.subject) }
        else {
            Write-Fail "certificate.type='store' requiere 'thumbprint' o 'subject'."
            exit 1
        }
        if ($cert.machine_store -eq $true) { $signtoolArgs += "/sm" }
    }
    "pfx" {
        if (-not $cert.pfx_path -or -not (Test-Path -LiteralPath $cert.pfx_path)) {
            Write-Fail "certificate.type='pfx' requiere 'pfx_path' existente."
            exit 1
        }
        $envVarName = if ($cert.pfx_password_env) { $cert.pfx_password_env } else { "ODP_PFX_PASSWORD" }
        $pfxPassword = [Environment]::GetEnvironmentVariable($envVarName)
        if (-not $pfxPassword) {
            Write-Fail "La variable de entorno '$envVarName' (password del PFX) no esta definida."
            exit 1
        }
        $signtoolArgs += @("/f", $cert.pfx_path, "/p", $pfxPassword)
    }
    default {
        Write-Fail "certificate.type '$($cert.type)' no soportado. Usar 'store' o 'pfx'."
        exit 1
    }
}

# --- 4. Timestamp RFC3161 + digest SHA256 ---
$TimestampUrl = if ($config.timestamp_url) { $config.timestamp_url } else { "http://timestamp.digicert.com" }
$signtoolArgs += @("/fd", "SHA256", "/tr", $TimestampUrl, "/td", "SHA256")

# --- 5. Objetivo: SOLO el exe de la app ---
if (-not (Test-Path -LiteralPath $AppExe)) {
    Write-Fail "No existe el ejecutable a firmar: $AppExe"
    exit 1
}

$forbidden = @("ffmpeg.exe", "ffprobe.exe")
foreach ($f in $forbidden) {
    if (($AppExe -split "\\")[-1] -ieq $f) {
        Write-Fail "REGLA VIOLADA: no se permite firmar $f con nuestro certificado."
        exit 1
    }
}

Write-Step "Firmando: $AppExe"
& $SigntoolPath @signtoolArgs $AppExe
if ($LASTEXITCODE -ne 0) {
    Write-Fail "signtool fallo con codigo $LASTEXITCODE."
    exit 1
}

# --- 6. Verificacion post-firma ---
$sig = Get-AuthenticodeSignature -FilePath $AppExe
if ($sig.Status -ne "Valid") {
    Write-Fail "La firma de osvaldoDownloaderPro.exe NO es valida (Status=$($sig.Status))."
    if ($sig.StatusMessage) { Write-Fail "Detalle: $($sig.StatusMessage)" }
    exit 1
}

$certInfo = $sig.SignerCertificate
Write-Step "Firma VERIFICADA: $($certInfo.Subject)"
Write-Step "  NotBefore=$($certInfo.NotBefore.ToString('yyyy-MM-dd')) NotAfter=$($certInfo.NotAfter.ToString('yyyy-MM-dd'))"
Write-Step "  Thumbprint=$($certInfo.Thumbprint)"

exit 0
