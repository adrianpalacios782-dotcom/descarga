# Firma de codigo (Authenticode) - osvaldoDownloaderPro

Estado actual: **NO HAY CERTIFICADO CONFIGURADO**.
`scripts\signing.config.json` no existe, por lo que `scripts\build_release.ps1`
compila en modo **BETA NO FIRMADO** y todas las releases publicadas hasta hoy
salen sin firma.

Consecuencias de no firmar:

- **Smart App Control** (Windows 11 22H2+, activo por defecto en equipos
  nuevos) puede bloquear la instalacion con el error *4551* o mostrarla como
  "aplicacion no reconocida".
- **Antivirus / Defender SmartScreen** marca el instalador como "no deseado".
- El usuario ve el aviso de "Editor desconocido" al ejecutar el Setup.exe.

Este documento explica las dos rutas:

- [A. Certificado real](#a-certificado-real-recomendado-para-publicacion)
- [B. Autofirmado de pruebas](#b-autofirmado-de-pruebas-solo-desarrollo-local)

---

## A. Certificado real (recomendado para publicacion)

### A.1 Que comprar

Un certificado **OV (Organization Validation)** de una CA con presencia en la
"lista de confianza de root de Windows". Opciones habituales:

| CA | Tipo | Nota |
|---|---|---|
| DigiCert | OV/EV | El timestamp por defecto ya apunta a `http://timestamp.digicert.com` |
| Sectigo | OV | Alternativa economica |
| GlobalSign | OV | |

> Smart App Control exige **OV o EV**. Un certificado de bajo coste sin
> presença en la lista de confianza no sirve.

### A.2 Instalar el certificado en el almacen de Windows

Instalar el `.pfx` (con clave privada) en el almacen **Personal** del usuario
actual:

```powershell
# Importar (interactivo: pide la contraseña del PFX)
Import-PfxCertificate -FilePath "C:\ruta\a\certificado.pfx" `
                      -CertStoreLocation "Cert:\CurrentUser\My"

# Ver el thumbprint del certificado recien importado
Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*osvaldo*" } |
    Select-Object Subject, Thumbprint, NotAfter, HasPrivateKey
```

### A.3 Crear `scripts\signing.config.json`

El archivo esta en `.gitignore` (nunca se commitea: contiene el thumbprint).

```jsonc
{
  "signtool_path": "",                       // vacio = se busca en PATH / Windows Kits
  "timestamp_url": "http://timestamp.digicert.com",

  "certificate": {
    "type": "store",
    "thumbprint": "A1B2C3D4E5F6...  (el que copiaste del paso A.2)",
    "subject": "",                           // alternativa al thumbprint
    "machine_store": false                   // true = almacen de la maquina (/sm)
  }
}
```

Variante con **PFX** (util si el certificado NO esta instalado en el store):

```jsonc
{
  "signtool_path": "",
  "timestamp_url": "http://timestamp.digicert.com",
  "certificate": {
    "type": "pfx",
    "pfx_path": "C:\\ruta\\a\\certificado.pfx",
    "pfx_password_env": "ODP_PFX_PASSWORD"
  }
}
```

La contraseña del PFX **nunca** va en el JSON: se lee de la variable de
entorno `ODP_PFX_PASSWORD` (o la que indiques en `pfx_password_env`).

```powershell
# Guardar la contraseña de forma persistente en el usuario (Windows)
[Environment]::SetEnvironmentVariable("ODP_PFX_PASSWORD", "TU_CONTRASENA", "User")
```

### A.4 Instalar `signtool.exe`

`signtool.exe` viene con el **Windows SDK**. Instalar "Windows SDK for
Build Tools" o el paquete de Visual Studio. Si queda en una ruta que el script
no encuentra, declararla en `signtool_path`:

```powershell
# Buscar signtool.exe
Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter signtool.exe |
    Select-Object -First 1 -ExpandProperty FullName
```

### A.5 Firmar y verificar

```powershell
# Firmar SOLO el exe de la app (el instalador lo firma Inno Setup)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sign_release.ps1

# Build completo (ya firmado; sin -SkipSigning)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

Salida esperada:

```
[SIGN] signtool: C:\Program Files (x86)\Windows Kits\10\bin\...\signtool.exe
[SIGN] Firmando: ...\dist\osvaldoDownloaderPro\osvaldoDownloaderPro.exe
[SIGN] Firma VERIFICADA: CN=osvaldoDownloaderPro, O=..., C=...
```

Verificacion manual:

```powershell
Get-AuthenticodeSignature .\dist\osvaldoDownloaderPro\osvaldoDownloaderPro.exe |
    Select-Object Status, StatusMessage, SignerCertificate
# Status debe ser "Valid"
```

### A.6 Reglas que el pipeline ya respeta

- **Nunca** se firma `ffmpeg.exe` ni `ffprobe.exe` (binarios de terceros):
  `sign_release.ps1` lo aborta si se intenta.
- El instalador `Setup.exe` lo firma Inno Setup via `SignTool=` +
  `SignedUninstaller=yes` (esto es lo que resuelve el error 4551 de Smart App
  App Control).
- Digest **SHA256** y timestamp **RFC3161** (`/fd SHA256 /tr <url> /td SHA256`).
- Si la firma no se puede verificar, el build aborta. No hay firma "a medias".

### A.7 Publicar la release firmada

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\publish_release.ps1
```

> En CI (`.github\workflows\release.yml`) el instalador sale **sin firma**
> porque el runner no tiene el certificado. Para publicar firmado hay que
> cargar el `.pfx` como secret (`CODESCELLING_PFX_BASE64` + `ODP_PFX_PASSWORD`)
> y reconstruir el paso de firma. Ver "A.8".

### A.8 Firma en GitHub Actions (opcional)

1. Guardar el PFX como secret:
   ```powershell
   $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("certificado.pfx"))
   gh secret set CODESCELLING_PFX_BASE64 --body $b64
   gh secret set ODP_PFX_PASSWORD --body "TU_CONTRASENA"
   ```
2. En el workflow, antes del build, reconstruir el PFX y escribir
   `scripts\signing.config.json` (que esta en `.gitignore`).
3. Quitar `-SkipSigning` del paso de build.

---

## B. Autofirmado de pruebas (solo desarrollo local)

Sirve para **verificar el flujo completo** (que el script firma, que Inno Setup
firma el Setup, que los hashes se generan) sin gastar un certificado real.

> Un certificado autofirmado **no es confiable** para los usuarios finales:
> Windows mostrara "Editor desconocido" y Smart App Control seguira bloqueando.
> Solo usalo en tu maquina.

### B.1 Crear el certificado autofirmado

```powershell
# Requiere permisos de administrador (certificados en el almacen del usuario
# no siempre habilitan la firma de Authenticode en instaladores).
New-SelfSignedCertificate `
    -Subject "CN=osvaldoDownloaderPro DEV, O=osvaldoDownloaderPro DEV" `
    -Type CodeSigningCert `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -KeyUsage DigitalSignature `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3") `
    -NotAfter (Get-Date).AddYears(2) `
    -FriendlyName "osvaldoDownloaderPro DEV CodeSigning"
```

Guardar el thumbprint:

```powershell
$dev = Get-ChildItem Cert:\CurrentUser\My |
       Where-Object { $_.FriendlyName -eq "osvaldoDownloaderPro DEV CodeSigning" } |
       Select-Object -First 1
$dev.Thumbprint
```

### B.2 Confiar en el certificado en la maquina

Para que Windows acepte la firma en esta maquina, el certificado raiz debe
estar en "Personas de confianza de racine de confianza" (Trusted Root
Certification Authorities):

```powershell
$root = New-SelfSignedCertificate -Type Custom -Subject "CN=osvaldoDownloaderPro DEV ROOT" `
        -KeyExportPolicy Exportable -KeyUsage CertSign,CRLSign,DigitalSignature `
        -KeySpec Signature -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears(5) -TextExtension @("2.5.29.19={text}CA=true")

Export-Certificate -Cert $root -FilePath "$env:TEMP\odp-dev-root.cer"
Import-Certificate -FilePath "$env:TEMP\odp-dev-root.cer" `
    -CertStoreLocation "Cert:\CurrentUser\Root"     # aviso del sistema: Si

```

O, mas simple, instalar el PFX exportado en el almacen **Personal** y marcarlo
como de confianza:

```powershell
$password = ConvertTo-SecureString -String "DEV-PASSWORD" -Force -AsPlainText
Export-PfxCertificate -Cert $dev -FilePath "$env:TEMP\odp-dev.pfx" -Password $password
Import-PfxCertificate -FilePath "$env:TEMP\odp-dev.pfx" `
    -CertStoreLocation "Cert:\CurrentUser\My" -Password $password
```

### B.3 Generar `scripts\signing.config.json`

```jsonc
{
  "signtool_path": "",
  "timestamp_url": "",
  "certificate": {
    "type": "store",
    "thumbprint": "<THUMBPRINT DEL PASO B.1>",
    "subject": "",
    "machine_store": false
  }
}
```

> `timestamp_url` vacio hace que `sign_release.ps1` use
> `http://timestamp.digicert.com` por defecto. Si se quiere SIN timestamp
> (tipico en pruebas, porque el timestamp es un servicio externo), poner
> `"timestamp_url": ""` **no** funciona: el script aplica el valor por defecto.
> En ese caso, quitar el timestamp a mano al ejecutar `signtool` o dejar el
> valor por defecto (un certificado autofirmado con timestamp publico tampoco
> es confiable, pero el flujo se parece mas al real).

### B.4 Firmar y compilar

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sign_release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

### B.5 Limpiar la configuracion de pruebas

Para volver al modo "BETA NO FIRMADO":

```powershell
Remove-Item -LiteralPath "scripts\signing.config.json" -Force
```

El certificado en el almacen de Windows es independiente del archivo de
configuracion: se puede dejar (no afecta a los builds) o borrarlo con:

```powershell
Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.FriendlyName -like "osvaldoDownloaderPro DEV*" } |
    Remove-Item -DeleteKey
```

---

## Diagnostico rapido

| Sintoma | Causa | Solucion |
|---|---|---|
| `[SIGN][ERROR] signtool.exe no encontrado` | Windows SDK no instalado | Instalar Windows SDK o definir `signtool_path` |
| `[SIGN][ERROR] La variable de entorno 'ODP_PFX_PASSWORD' no esta definida` | Falta la password del PFX | `[Environment]::SetEnvironmentVariable("ODP_PFX_PASSWORD", "...", "User")` y reabrir la terminal |
| `[SIGN][ERROR] La firma ... NO es valida (Status=UnknownError)` | Certificado autofirmado no confiable | Instalar la raiz en `Cert:\CurrentUser\Root` (B.2) |
| `[BUILD][AVISO] Omitiendo firma digital` | No existe `scripts\signing.config.json` | Configurar A.3 o B.3 |
| Instalador bloqueado por Smart App Control (4551) | Sin firma OV/EV | Comprar certificado (A.1) |

## Referencias

- `scripts\sign_release.ps1` - implementacion de la firma y sus gates.
- `scripts\signing.config.example.json` - plantilla versionada (segura).
- `scripts\build_release.ps1` - pipeline de 8 pasos que invoca al firmador.
- `installer.iss` - bloque `#ifdef USE_SIGNTOOL` + `SignedUninstaller=yes`.
- <https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-cert-manage> - gestion de certificados de firma.
