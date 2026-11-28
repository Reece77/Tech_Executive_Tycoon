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
;
; M57r-B (review 10 item 1): the uninstaller removes only what setup installed (Inno Setup's own
; log of tracked files) and the bundle folder `_internal`; anything else in the install folder
; stays. Setup refuses an install folder that is, holds or sits inside the game's saves
; (Documents\Tech Startup Tycoon) or its app data, or the Documents or profile folder itself.
; /DDistDir=<folder> builds from another bundle (the smoke test's fake "next version").

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "dist\Tech Startup Tycoon"
#endif
#ifndef OutputName
  #define OutputName "TechStartupTycoon-Setup-" + AppVersion
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
OutputBaseFilename={#OutputName}
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
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall; Check: ShouldLaunch

[UninstallDelete]
; Only the bundle setup put there (its files are tracked anyway; this catches anything Python
; writes inside it). Never the whole install folder: a player who picked a folder holding
; their own files keeps them (M57r-B). Saves (Documents) and settings (app data) stay.
Type: filesandordirs; Name: "{app}\_internal"

[Code]
function ShouldLaunch: Boolean;
begin
  Result := ExpandConstant('{param:NOLAUNCH|0}') <> '1';
end;

{ The folder without a trailing backslash, lower-cased, for comparing. }
function Norm(const Path: String): String;
begin
  Result := Lowercase(RemoveBackslashUnlessRoot(ExpandFileName(Path)));
end;

{ True when A is B or inside it. }
function Within(const A, B: String): Boolean;
begin
  Result := (A = B) or (Pos(AddBackslash(B), AddBackslash(A)) = 1);
end;

{ The install folder may not overlap the game's data, nor be a folder that holds the player's
  own files wholesale: an uninstall must never be able to reach them. }
function OverlapsGameData(const Dir: String): String;
var
  D, Saves, AppData, Docs, Profile: String;
begin
  Result := '';
  D := Norm(Dir);
  Saves := Norm(ExpandConstant('{userdocs}\{#AppName}'));
  AppData := Norm(ExpandConstant('{userappdata}\{#AppName}'));
  Docs := Norm(ExpandConstant('{userdocs}'));
  Profile := Norm(ExpandConstant('{%USERPROFILE}'));
  if Within(D, Saves) or Within(Saves, D) then
    Result := 'the game''s saves folder (' + Saves + ')'
  else if Within(D, AppData) or Within(AppData, D) then
    Result := 'the game''s settings folder (' + AppData + ')'
  else if (D = Docs) or (D = Profile) or (Length(D) <= 3) then
    Result := 'a folder that holds your own files (' + D + ')';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Why: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Why := OverlapsGameData(WizardDirValue);
    if Why <> '' then
    begin
      SuppressibleMsgBox('Choose another folder: this one overlaps ' + Why + '.', mbError, MB_OK, IDOK);
      Result := False;
    end;
  end;
end;

{ Silent installs (the in-game update, /DIR=) skip the folder page: refuse here as well. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Why: String;
begin
  Why := OverlapsGameData(WizardDirValue);
  if Why <> '' then
    Result := 'The install folder overlaps ' + Why + '. Choose another folder.'
  else
    Result := '';
end;
