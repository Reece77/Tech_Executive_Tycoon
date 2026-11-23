; Inno Setup script for the installed game (M58 sub-task 3). The release workflow runs
;     iscc /DAppVersion=6.0.0 packaging\installer.iss
; after PyInstaller has built packaging\dist\Tech Startup Tycoon\. Output:
; packaging\out\TechStartupTycoon-Setup-<version>.exe.
;
; Per-user install (no administrator prompt, so the game can update itself silently) to
; %LOCALAPPDATA%\Programs\Tech Startup Tycoon. Saves live in Documents\Tech Startup Tycoon and
; settings in %APPDATA%\Tech Startup Tycoon: neither is in the install folder, so an update, an
; uninstall and a reinstall all keep them.
;
; Command-line extras: /NOLAUNCH=1 skips starting the game after a silent install (the CI
; smoke test); without it a silent install (the in-game update) starts the new version.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Tech Startup Tycoon"
#define AppExe "Tech Startup Tycoon.exe"

[Setup]
AppId={{24CA260E-A855-4F5A-900E-F25840C45DD6}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Reece
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=out
OutputBaseFilename=TechStartupTycoon-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; An update replaces the whole bundle, so no module from the old version lingers.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall; Check: ShouldLaunch

[UninstallDelete]
; Only the install folder: saves (Documents) and settings (app data) stay.
Type: filesandordirs; Name: "{app}"

[Code]
function ShouldLaunch: Boolean;
begin
  Result := ExpandConstant('{param:NOLAUNCH|0}') <> '1';
end;
