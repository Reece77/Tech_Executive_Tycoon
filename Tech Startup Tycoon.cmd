@echo off
rem Double-click to play Tech Startup Tycoon (M29). It installs what it needs on the first run,
rem builds the screens, starts the game and opens your browser. Needs uv and Node.js once.
title Tech Startup Tycoon
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed. See the page that just opened.
  start "" "%~dp0tools\launcher_missing_uv.html"
  pause
  exit /b 1
)
uv run --project backend python tools\launcher.py %*
if errorlevel 1 pause
