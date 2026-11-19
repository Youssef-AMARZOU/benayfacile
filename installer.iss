; Installateur Windows de Bénayfacile (Inno Setup 6) — compilé par build_exe.bat
#define AppName "Bénayfacile"
#define AppVersion "0.3.0"
#define AppExe "Benayfacile.exe"

[Setup]
AppId={{5B7D3C1E-6A2F-4E8B-9C41-B3E5A1D0F7A2}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Youssef AMARZOU — Digital & AI Engineer
AppCopyright=© 2026 Youssef AMARZOU
VersionInfoCompany=Youssef AMARZOU
VersionInfoDescription=Bénayfacile — calcul BAEL 91 / RPS 2011
DefaultDirName={autopf}\Benayfacile
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=Benayfacile-Setup-{#AppVersion}
SetupIconFile=assets\benayfacile.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Installation possible sans droits administrateur (choix proposé à l'utilisateur)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "dist\Benayfacile\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Résultats (notes et DXF)"; Filename: "{localappdata}\Benayfacile\output"
Name: "{group}\Désinstaller {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Dirs]
Name: "{localappdata}\Benayfacile\output"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

; Les données de l'utilisateur (%LOCALAPPDATA%\Benayfacile : bureau.json, notes, DXF)
; sont volontairement conservées à la désinstallation.
