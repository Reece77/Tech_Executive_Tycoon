# The release smoke test (M58 sub-task 5), on a clean windows-latest runner:
#   pwsh packaging/smoke.ps1 -Installer packaging/out/TechStartupTycoon-Setup-6.0.0.exe -Version 6.0.0
# 1. Install silently; start the exe headless; /api/health; a practice game; one turn; the
#    server listens on 127.0.0.1 only; no secret in the bundle or the log.
# 2. Open the real window (--smoke-window): the page loads in WebView2, then it closes.
# 3. Install again over it (an update): the save is still there, at the same month.
# 4. Uninstall, then reinstall: the save is still there.
param(
  [Parameter(Mandatory = $true)][string]$Installer,
  [Parameter(Mandatory = $true)][string]$Version
)
$ErrorActionPreference = 'Stop'
$App = Join-Path $env:LOCALAPPDATA 'Programs\Tech Startup Tycoon'
$Exe = Join-Path $App 'Tech Startup Tycoon.exe'
$Saves = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Tech Startup Tycoon\saves'
$Log = Join-Path $env:APPDATA 'Tech Startup Tycoon\logs\desktop.log'
$Port = 8771
$Base = "http://127.0.0.1:$Port"

function Step($text) { Write-Host "::group::$text" }
function EndStep { Write-Host '::endgroup::' }
function Fail($text) {
  if (Test-Path $Log) { Get-Content $Log -Tail 80 | Write-Host }
  throw $text
}

function Install-Game {
  $p = Start-Process -FilePath $Installer -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOLAUNCH=1' -PassThru -Wait
  if ($p.ExitCode -ne 0) { Fail "installer exited $($p.ExitCode)" }
  if (-not (Test-Path $Exe)) { Fail "no $Exe after install" }
}

function Start-Headless {
  $p = Start-Process -FilePath $Exe -ArgumentList '--headless', '--port', $Port, '--no-update-check' -PassThru
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
$uninstaller = Join-Path $App 'unins000.exe'
$u = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -PassThru -Wait
for ($i = 0; $i -lt 60 -and (Test-Path $Exe); $i++) { Start-Sleep -Milliseconds 500 }  # the uninstaller finishes from a copy of itself
if (Test-Path $Exe) { Fail 'the uninstaller left the game behind' }
if (-not (Test-Path (Join-Path $Saves 'practice.tst.sqlite'))) { Fail 'the uninstaller removed the save' }
Install-Game
$p = Start-Headless
if ((Get-PracticeTurn) -ne 1) { Fail 'the save lost its month after a reinstall' }
Stop-Game $p
EndStep

Write-Host "Smoke test passed for $Version"
