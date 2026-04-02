; Inno Setup script for JellyRip
; Compile with: ISCC installer\JellyRip.iss

#define MyAppName "JellyRip"
#define MyAppVersion "1.0.10"
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

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RoamingDir: String;
  LocalDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RoamingDir := ExpandConstant('{userappdata}\JellyRip');
    LocalDir := ExpandConstant('{localappdata}\JellyRip');

    if DirExists(RoamingDir) or DirExists(LocalDir) then
    begin
      if MsgBox('JellyRip has been removed.' + #13#10 + #13#10 +
        'Do you also want to remove your settings and data?' + #13#10 +
        '(config, logs, cache in AppData)' + #13#10 + #13#10 +
        'Choose No to keep them for a future reinstall.',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        if DirExists(RoamingDir) then
          DelTree(RoamingDir, True, True, True);
        if DirExists(LocalDir) then
          DelTree(LocalDir, True, True, True);
      end;
    end;
  end;
end;
