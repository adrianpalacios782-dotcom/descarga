[Setup]
; La versión se inyecta desde build_release.ps1 leyendo src/__init__.py
; (única fuente de verdad). El default permite compilar standalone.
#ifndef APP_VERSION
#define APP_VERSION "1.0.4"
#endif
#ifndef APP_VERSION_QUAD
#define APP_VERSION_QUAD "1.0.4.0"
#endif
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=osvaldoDownloaderPro
AppVersion={#APP_VERSION}
VersionInfoVersion={#APP_VERSION_QUAD}
VersionInfoProductVersion={#APP_VERSION}
VersionInfoProductName=osvaldoDownloaderPro
VersionInfoDescription=osvaldoDownloaderPro Setup
VersionInfoCompany=osvaldoDownloaderPro
VersionInfoCopyright=Copyright © 2026 osvaldoDownloaderPro
AppPublisher=osvaldoDownloaderPro Team
DefaultDirName={autopf}\osvaldoDownloaderPro
DefaultGroupName=osvaldoDownloaderPro
OutputDir=installer
OutputBaseFilename=osvaldoDownloaderPro-{#APP_VERSION}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon.ico
UninstallIconFile=assets\icon.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableDirPage=no
DisableProgramGroupPage=yes
LicenseFile=
SetupLogging=yes
CloseApplications=force
RestartApplications=no
DiskSliceSize=max

; ---------------------------------------------------------------------------
; Firma digital (preparada, inactiva hasta existir certificado).
; Compilar SIN firmar:  iscc installer.iss
; Compilar CON firma :  iscc /DUSE_SIGNTOOL /S$ReleaseSigner="<comando signtool>" installer.iss
; El comando se define en build_release.ps1 / sign_release.ps1 cuando el
; certificado este configurado (scripts\signing.config.json).
; SignTool firma: Setup.exe final + motor interno extraido a %TEMP% (Setup.tmp)
; + desinstalador (SignedUninstaller). Esto resuelve el bloqueo Error 4551
; de Smart App Control en maquinas con SAC activo.
; ---------------------------------------------------------------------------
#ifdef USE_SIGNTOOL
SignTool=ReleaseSigner
SignedUninstaller=yes
#endif

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application
Source: "dist\osvaldoDownloaderPro\osvaldoDownloaderPro.exe"; DestDir: "{app}"; Flags: ignoreversion
; FFmpeg binaries
Source: "dist\osvaldoDownloaderPro\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\osvaldoDownloaderPro\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion
; Internal directory (PySide6, yt-dlp, curl_cffi, Python runtime, etc.)
Source: "dist\osvaldoDownloaderPro\_internal\*"; DestDir: "{app}\_internal"; Flags: recursesubdirs createallsubdirs ignoreversion
; Assets (iconos y recursos de marca)
Source: "dist\osvaldoDownloaderPro\assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\osvaldoDownloaderPro"; Filename: "{app}\osvaldoDownloaderPro.exe"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\{cm:UninstallProgram,osvaldoDownloaderPro}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\osvaldoDownloaderPro"; Filename: "{app}\osvaldoDownloaderPro.exe"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\osvaldoDownloaderPro.exe"; Description: "{cm:LaunchProgram,osvaldoDownloaderPro}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\assets"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    { Create app data directory }
    CreateDir(ExpandConstant('{userappdata}\osvaldoDownloaderPro'));
    CreateDir(ExpandConstant('{userappdata}\osvaldoDownloaderPro\logs'));
  end;
end;
