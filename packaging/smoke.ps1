# The release smoke test (M58 sub-task 5), on a clean windows-latest runner:
#   pwsh packaging/smoke.ps1 -Installer packaging/out/TechStartupTycoon-Setup-6.0.0.exe -Version 6.0.0
# 1. Install silently; start the exe headless; /api/health; a practice game; one turn; the
#    server listens on 127.0.0.1 only; no secret in the bundle or the log.
# 2. Open the real window (--smoke-window): the page loads in WebView2, then it closes.
# 3. Install again over it (an update): the save is still there, at the same month.
# 4. Uninstall, then reinstall: the save is still there.
# 5. (M57r-B) The in-game update, end to end: a fake release server on 127.0.0.1 offers
#    -NextInstaller (the same bundle as -NextVersion); the running game downloads it, backs up
#    the saves, runs it and closes; the new version answers its health check with the save.
# 6. (M57r-B) Setup refuses an install folder overlapping the saves; an install into a folder
#    holding the player's own file, then uninstalled, leaves that file.
param(
  [Parameter(Mandatory = $true)][string]$Installer,
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$NextInstaller = '',
  [string]$NextVersion = ''
)
$ErrorActionPreference = 'Stop'
$App = Join-Path $env:LOCALAPPDATA 'Programs\Tech Startup Tycoon'
$Exe = Join-Path $App 'Tech Startup Tycoon.exe'
$Saves = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Tech Startup Tycoon\saves'
$Log = Join-Path $env:APPDATA 'Tech Startup Tycoon\logs\desktop.log'
$Instance = Join-Path $env:APPDATA 'Tech Startup Tycoon\instance.json'
$Downloads = Join-Path $env:APPDATA 'Tech Startup Tycoon\updates'
$Backups = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Tech Startup Tycoon\backups'
$Repo = 'Reece77/Tech_Executive_Tycoon'
$FakePort = 8772
$Port = 8771
$Base = "http://127.0.0.1:$Port"

function Step($text) { Write-Host "::group::$text" }
function EndStep { Write-Host '::endgroup::' }
function Fail($text) {
  if (Test-Path $Log) { Get-Content $Log -Tail 80 | Write-Host }
  $setupLog = Join-Path $env:APPDATA 'Tech Startup Tycoon\logs\update-install.log'
  if (Test-Path $setupLog) { Write-Host '== the in-game update''s setup log'; Get-Content $setupLog -Tail 120 | Write-Host }
  throw $text
}

# Start-Process joins its arguments with spaces and quotes none: a folder with a space goes in
# as "/DIR=`"<folder>`"" or setup reads only its first word.
function Run-Installer([string[]]$Extra = @()) {
  $argv = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOLAUNCH=1') + $Extra
  $p = Start-Process -FilePath $Installer -ArgumentList $argv -PassThru -Wait
  return $p.ExitCode
}

function Install-Game {
  $code = Run-Installer
  if ($code -ne 0) { Fail "installer exited $code" }
  if (-not (Test-Path $Exe)) { Fail "no $Exe after install" }
}

function Uninstall-From($folder) {
  $uninstaller = Join-Path $folder 'unins000.exe'
  $exe = Join-Path $folder 'Tech Startup Tycoon.exe'
  Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -PassThru -Wait | Out-Null
  for ($i = 0; $i -lt 60 -and (Test-Path $exe); $i++) { Start-Sleep -Milliseconds 500 }  # the uninstaller finishes from a copy of itself
  if (Test-Path $exe) { Fail "the uninstaller left the game behind in $folder" }
}

function Start-Headless([switch]$UpdateCheck) {
  $argv = @('--headless', '--port', $Port)
  if (-not $UpdateCheck) { $argv += '--no-update-check' }
  $p = Start-Process -FilePath $Exe -ArgumentList $argv -PassThru
  for ($i = 0; $i -lt 120; $i++) {
    try {
      $h = Invoke-RestMethod "$Base/api/health" -TimeoutSec 2
      if ($h.status -eq 'ok') { return $p }
    } catch { }
    if ($p.HasExited) { Fail "the game exited with $($p.ExitCode) before answering" }
    Start-Sleep -Milliseconds 500
  }
  Fail 'no answer on /api/health within 60 s'
}

function Stop-Game($p) {
  Stop-Process -Id $p.Id -Force
  $p.WaitForExit(30000) | Out-Null
  Start-Sleep -Seconds 1
}

function Get-PracticeTurn {
  $save = Invoke-RestMethod "$Base/api/saves/practice"
  return [int]$save.turn
}

Step 'Install and play one turn'
Install-Game
$p = Start-Headless
$h = Invoke-RestMethod "$Base/api/health"
if ($h.version -ne $Version) { Fail "version $($h.version), expected $Version" }
$body = @{ name = 'practice'; seed = 7; scenario = 'garage_bootstrap'; company_name = 'Practice Co' } | ConvertTo-Json
Invoke-RestMethod "$Base/api/saves" -Method Post -ContentType 'application/json' -Body $body | Out-Null
$o = Invoke-RestMethod "$Base/api/saves/practice/advance" -Method Post
if ($o.date_label -ne 'Feb 2010') { Fail "after one turn the date is $($o.date_label)" }
$listen = Get-NetTCPConnection -LocalPort $Port -State Listen
$addresses = @($listen | ForEach-Object { $_.LocalAddress } | Sort-Object -Unique)
if ($addresses.Count -ne 1 -or $addresses[0] -ne '127.0.0.1') { Fail "listening on $($addresses -join ', ')" }
$desktop = Invoke-RestMethod "$Base/api/desktop"
if (-not $desktop.desktop) { Fail '/api/desktop says this is not the installed game' }
if ($desktop.saves_dir -ne $Saves) { Fail "saves in $($desktop.saves_dir), expected $Saves" }
Stop-Game $p
if (-not (Test-Path (Join-Path $Saves 'practice.tst.sqlite'))) { Fail "no save in $Saves" }
EndStep

Step 'No secret bundled or logged'
$envFiles = @(Get-ChildItem -Path $App -Recurse -Force -Filter '.env' -ErrorAction SilentlyContinue)
if ($envFiles.Count -ne 0) { Fail ".env bundled: $($envFiles.FullName -join ', ')" }
if (Select-String -Path $Log -Pattern 'sk-ant-' -Quiet) { Fail 'the log holds an API key' }
EndStep

Step 'Open the window'
$w = Start-Process -FilePath $Exe -ArgumentList '--smoke-window', '--no-update-check' -PassThru
if (-not $w.WaitForExit(180000)) { Stop-Process -Id $w.Id -Force; Fail 'the window did not load and close within 3 minutes' }
if ($w.ExitCode -ne 0) { Fail "the window run exited $($w.ExitCode)" }
if (-not (Select-String -Path $Log -Pattern 'window loaded' -Quiet)) { Fail 'the page never loaded in the window' }
EndStep

Step 'Update over the installed game keeps the save'
Install-Game
$p = Start-Headless
if ((Get-PracticeTurn) -ne 1) { Fail 'the save lost its month after an update' }
Stop-Game $p
EndStep

Step 'Uninstall and reinstall keeps the save'
Uninstall-From $App
if (-not (Test-Path (Join-Path $Saves 'practice.tst.sqlite'))) { Fail 'the uninstaller removed the save' }
Install-Game
$p = Start-Headless
if ((Get-PracticeTurn) -ne 1) { Fail 'the save lost its month after a reinstall' }
Stop-Game $p
EndStep

if ($NextInstaller) {
  Step "In-game update to $NextVersion from a fake release"
  if (-not $NextVersion) { Fail '-NextInstaller needs -NextVersion' }
  $site = Join-Path $env:RUNNER_TEMP 'fake-release'
  $name = "TechStartupTycoon-Setup-$NextVersion.exe"
  $tag = "v$NextVersion"
  $assets = Join-Path $site "$Repo/releases/download/$tag"
  New-Item -ItemType Directory -Force -Path $assets, (Join-Path $site "repos/$Repo/releases") | Out-Null
  Copy-Item $NextInstaller (Join-Path $assets $name)
  $hash = (Get-FileHash (Join-Path $assets $name) -Algorithm SHA256).Hash.ToLower()
  "$hash  $name" | Set-Content -Path (Join-Path $assets "$name.sha256") -NoNewline -Encoding ascii
  $fake = "http://127.0.0.1:$FakePort"  # its own name: PowerShell variable names ignore case
  $latest = @{
    tag_name = $tag; draft = $false; prerelease = $false; body = "## What's new`n- The smoke test's update"
    html_url = "$fake/$Repo/releases/tag/$tag"
    assets = @(
      @{ name = $name; size = (Get-Item (Join-Path $assets $name)).Length; browser_download_url = "$fake/$Repo/releases/download/$tag/$name" },
      @{ name = "$name.sha256"; size = 0; browser_download_url = "$fake/$Repo/releases/download/$tag/$name.sha256" }
    )
  } | ConvertTo-Json -Depth 5
  Set-Content -Path (Join-Path $site "repos/$Repo/releases/latest") -Value $latest -Encoding utf8
  $server = Start-Process -FilePath python -ArgumentList '-m', 'http.server', $FakePort, '--bind', '127.0.0.1', '--directory', $site -PassThru
  (New-Item -ItemType Directory -Force -Path $Downloads | Out-Null)
  Set-Content -Path (Join-Path $Downloads "TechStartupTycoon-Setup-0.0.1.exe") -Value 'an older installer'
  try {
    $env:TST_UPDATE_SOURCE = $fake
    $p = Start-Headless -UpdateCheck
    Remove-Item Env:TST_UPDATE_SOURCE
    $oldPid = $p.Id
    $state = ''
    for ($i = 0; $i -lt 120 -and $state -ne 'available'; $i++) {
      $state = (Invoke-RestMethod "$Base/api/desktop").update_state
      if ($state -ne 'available') { Start-Sleep -Milliseconds 500 }
    }
    if ($state -ne 'available') { Fail "the fake release was not offered (state $state)" }
    $token = (Get-Content $Instance -Raw | ConvertFrom-Json).token
    # Without the token the update is refused (M57r-B)
    $refused = $false
    try { Invoke-RestMethod "$Base/api/desktop/update" -Method Post | Out-Null }
    catch { $refused = ($_.Exception.Response.StatusCode.value__ -eq 403) }
    if (-not $refused) { Fail 'Update now was not refused without the instance token' }
    Invoke-RestMethod "$Base/api/desktop/update" -Method Post -Headers @{ 'X-TST-Instance' = $token } | Out-Null
    if (-not $p.WaitForExit(180000)) { Fail 'the game did not close for the update within 3 minutes' }
    # The installer runs silently and starts the new version on a port of its own.
    $newBase = $null
    for ($i = 0; $i -lt 600 -and -not $newBase; $i++) {
      Start-Sleep -Milliseconds 500
      try {
        $info = Get-Content $Instance -Raw -ErrorAction Stop | ConvertFrom-Json
        if ($info.pid -ne $oldPid) {
          $h = Invoke-RestMethod "http://127.0.0.1:$($info.port)/api/health" -TimeoutSec 2
          if ($h.version -eq $NextVersion) { $newBase = "http://127.0.0.1:$($info.port)"; $newPid = $info.pid }
        }
      } catch { }
    }
    if (-not $newBase) { Fail "version $NextVersion never answered its health check after the update" }
    $save = Invoke-RestMethod "$newBase/api/saves/practice"
    if ([int]$save.turn -ne 1) { Fail 'the save lost its month in the in-game update' }
    $made = @(Get-ChildItem $Backups -Directory -Filter "before-$NextVersion-*")
    if ($made.Count -ne 1 -or -not (Test-Path (Join-Path $made[0].FullName 'practice.tst.sqlite'))) { Fail 'no pre-update backup of the save' }
    $left = @(Get-ChildItem $Downloads -File | ForEach-Object { $_.Name })
    if ($left.Count -ne 1 -or $left[0] -ne $name) { Fail "old installers kept: $($left -join ', ')" }
    Stop-Process -Id $newPid -Force
    Start-Sleep -Seconds 2
  } finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
  }
  EndStep
}

Step 'Setup refuses a folder overlapping the saves; uninstall keeps the player''s own files'
Uninstall-From $App
$docsGame = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Tech Startup Tycoon'
foreach ($bad in @($docsGame, (Join-Path $docsGame 'game'))) {
  $code = Run-Installer @("/DIR=`"$bad`"")
  if ($code -eq 0) { Fail "setup installed into $bad, which overlaps the saves" }
  if (Test-Path (Join-Path $bad 'Tech Startup Tycoon.exe')) { Fail "setup wrote the game into $bad" }
}
if (-not (Test-Path (Join-Path $Saves 'practice.tst.sqlite'))) { Fail 'a refused install touched the save' }
$custom = Join-Path $env:RUNNER_TEMP 'TST custom folder'
New-Item -ItemType Directory -Force -Path $custom | Out-Null
$sentinel = Join-Path $custom 'my own notes.txt'
Set-Content -Path $sentinel -Value 'the player''s file'
$code = Run-Installer @("/DIR=`"$custom`"")
if ($code -ne 0) { Fail "installer into $custom exited $code" }
if (-not (Test-Path (Join-Path $custom 'Tech Startup Tycoon.exe'))) { Fail "no game in $custom" }
Uninstall-From $custom
if (-not (Test-Path $sentinel)) { Fail 'the uninstaller deleted a file it did not install' }
if (-not (Test-Path (Join-Path $Saves 'practice.tst.sqlite'))) { Fail 'the uninstaller removed the save' }
EndStep

Write-Host "Smoke test passed for $Version"
