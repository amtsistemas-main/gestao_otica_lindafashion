; Inno Setup — compiled by packaging\build.ps1, which passes /DAppVersion from config\version.py.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Ótica Linda Fashion"
#define AppExe "OticaLindaFashion.exe"
#define Publisher "AMT Sistemas & Soluções"

[Setup]
AppId={{6F2B8C1E-4D7A-4C3B-9E51-0A8D2F7C5B19}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL=https://www.amtsistemas.com.br
AppSupportURL=https://www.amtsistemas.com.br
DefaultDirName={autopf}\OticaLindaFashion
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install: automatic updates run silently, without administrator rights.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=OticaLindaFashion-Setup-{#AppVersion}
SetupIconFile=..\assets\images\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#Publisher}
VersionInfoProductName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\OticaLindaFashion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Automatic update chosen as "Atualizar agora": reopen the app after the silent install.
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;
