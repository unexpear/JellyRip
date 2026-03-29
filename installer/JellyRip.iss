; Inno Setup script for JellyRip
; Compile with: ISCC installer\JellyRip.iss

#define MyAppName "JellyRip"
#define MyAppVersion "1.0.9"
#define MyAppPublisher "unexpear"
#define MyAppURL "https://github.com/unexpear/JellyRip"
#define MyAppExeName "JellyRip.exe"

[Setup]
AppId={{A3E2F5D5-5BA2-4A26-8C0A-4D88D22D87A8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\JellyRip
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=JellyRipInstaller
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\JellyRip.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\JellyRip"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\JellyRip"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch JellyRip"; Flags: nowait postinstall skipifsilent
