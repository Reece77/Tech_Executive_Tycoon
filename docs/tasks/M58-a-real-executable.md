# M58: A real executable (v6, lane B)

**Goal:** the game installs and runs like a normal Windows application. A `Tech Startup Tycoon` installer puts the game in its own window, with nothing else to install: no Python, uv, Node or GitHub Desktop. It updates itself from GitHub releases with a "What's new" note. Saves live in the user's documents folder and survive updates.

**Depends on:** M29's launcher and single-port server · **Lane:** B, alongside M47 (lane A). It touches packaging, not the engine.

## Reece's decisions (2026-11-22)

- **A real executable, early in v6.**
- **PyInstaller and pywebview approved** as build and runtime tools (CLAUDE.md §3 asks for approval of new dependencies; this is it). Use `pywebview` for the window and `PyInstaller` for the bundle. Ask before adding anything else.
- **Automatic updates** from GitHub releases, with a "What's new" note.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m58-executable` from `main`. It can start now.
- **M58 owns:**
  - `packaging/` (new: the PyInstaller spec, the installer script, icons);
  - a desktop entry point (`backend/tst/desktop.py`: start the server on a free local port, open a pywebview window on it, close the server with the window);
  - the update check;
  - a `release` GitHub workflow;
  - README's install section.
- **M58 must not edit** the simulation, the API's game routes or any balance file.
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (commit after each)

1. **The desktop entry point:**
   - start the API (serving the built front end, as M29's single-port server does) on a free localhost port, bound to 127.0.0.1 only;
   - open it in a pywebview window titled Tech Startup Tycoon;
   - shut the server down when the window closes;
   - a single instance (a second launch focuses the first window);
   - logs to the user's app-data folder.
2. **Where things live:**
   - saves in `Documents/Tech Startup Tycoon/saves`, settings and logs in app data;
   - on first run, offer to import saves from the repository's `saves` folder if one is found;
   - `.env` and the Anthropic API key in app data, entered once in Settings (never bundled, never logged).
3. **The bundle:**
   - a PyInstaller spec bundling Python, the backend, the data YAML and the built front end;
   - Alembic migrations run on save open, as today;
   - an installer (Inno Setup, if it's available on the GitHub Windows runner; otherwise ask) with Start-menu and desktop shortcuts and an uninstaller that keeps saves.
4. **Updates:**
   - at start, check the latest GitHub release of `Reece77/Tech_Executive_Tycoon` (public, no token);
   - if newer, show "What's new" (the release notes from CHANGELOG) with **Update now** or **Later**;
   - **Update now** downloads the installer, checks its SHA-256 against the release's published checksum, and runs it;
   - back up saves before updating;
   - never update during a turn.
5. **The release workflow:** on a pushed version tag (`v6.0.0` and so on), build on `windows-latest`, run a smoke test (start the exe headless, hit `/api/health`, open a practice save, advance one turn), attach the installer and its checksum to a GitHub release with notes from CHANGELOG. Cloud sessions can't push tags; the workflow also runs on `workflow_dispatch` with a version input, and Reece tags releases.
6. **Close-out:**
   - README's "Install" section for Reece (download the installer from Releases; the old shortcut still works for development);
   - CHANGELOG;
   - README index row.

## Acceptance criteria

- [ ] A release built by the workflow installs on a clean Windows machine (the CI smoke test on `windows-latest`) and opens the game in its own window, with nothing else installed.
- [ ] Saves survive an update and an uninstall-reinstall.
- [ ] The update check offers a newer release with its notes, verifies the checksum, and backs up saves first.
- [ ] No secret is bundled or logged, and the server listens on 127.0.0.1 only.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m58-done`.

## Manual check (Reece, after merge)

Download the installer from the repository's Releases page, install it, and start the game from the Start menu. Load a save, close the window, and reopen.

## Decisions made

1. **Branch.** Built on `claude/m58-executable-build-18bvvv` (the branch this cloud session may push to) rather than `m58-executable`; same content, merged by pull request as §6 says.
2. **Package, not one file.** The desktop entry point is the package `backend/tst/desktop/` (`main.py`, run as `python -m tst.desktop`) with one module per concern (`paths`, `instance`, `secrets`, `imports`, `update`, `context`, `version`), so the API's routes and the tests import everything but the window without pywebview.
3. **The server runs in the window's process** (uvicorn on a thread, on a socket bound to 127.0.0.1 port 0 before the server starts), not as a child process: one process to close, no port race, and closing the window ends everything.
4. **Desktop routes are not game routes.** `GET /api/health` (for the smoke test and anyone else) and `/api/desktop/*` live in a new router (`tst/api/routers/desktop.py`); `app.py` gains only its `include_router` and one middleware (`update_guard`, which refuses writes outside `/api/desktop` once an update's backup has started). Outside the installed game the routes answer `desktop: false` or 409 `not_desktop`, so the generated client and `make check-api` cover them.
5. **Never update during a turn:** Update now is refused while any save is busy (a turn, an action, a holiday: `saves_db.list_files(...).busy`); the backup then takes every save's write lock before copying (SQLite's backup API), and from that moment every write is refused, so the backup is the saves' last state.
6. **Per-user install** (`PrivilegesRequired=lowest`, `%LOCALAPPDATA%\Programs\Tech Startup Tycoon`): no UAC prompt, so the in-game update can run the installer silently. `[InstallDelete]` clears `_internal` first so no module from an older version lingers.
7. **Saves and settings outside the install folder** (Documents and `%APPDATA%`); the uninstaller removes only the install folder. Pre-update backups go to `Documents\Tech Startup Tycoon\backups\before-<version>-<stamp>`, beside the saves (the user's files, not app data).
8. **Paths:** Documents comes from Windows' `SHGetFolderPathW` (it follows OneDrive and moved folders), falling back to `%USERPROFILE%\Documents`; `TST_DESKTOP_HOME` puts both folders under one directory for tests.
9. **First-run import:** candidates are `TST_IMPORT_FROM`, then GitHub Desktop's default clone (`Documents\GitHub\Tech_Executive_Tycoon\saves`) and a few usual places. Saves (with SQLite's backup API, so a `-wal` is included), settings and mods are copied; existing names are never overwritten; the repository's `backups` folder is left where it is (hundreds of MB per save by the 2030s). Asked once: either answer is remembered in app data's `desktop.json`.
10. **The API key** is entered in Settings, written to `%APPDATA%\Tech Startup Tycoon\.env`, applied to the running process (the settings cache is cleared), never returned by the API (only `key_saved`), and masked (`sk-…` → `sk-***`) by a filter on every log handler.
11. **Versions:** the release workflow writes `packaging/version.txt`, bundled at the bundle's root; a repository run is `dev` and never checks for updates. Only `vX.Y.Z` releases with both the installer and its `.sha256` are offered; pre-releases and drafts are not.
12. **Release notes** (`packaging/release_notes.py`): a `## vX.Y.Z` section in CHANGELOG when Reece writes one; otherwise the top-level entries added since the previous release's CHANGELOG, first lines only; for the first release, the newest twelve.
13. **Inno Setup** is on GitHub's Windows images; the workflow falls back to `choco install innosetup` if a future image drops it (no need to ask).
14. **The installer is not code-signed** (no certificate); Windows SmartScreen will warn on first run, and README says how to proceed. The SHA-256 check guards the update download.
15. **Window details:** 1440 x 900, minimum 1024 x 700, the dark theme's background before the page paints, WebView2 (`edgechromium`) on Windows, and a persistent WebView profile in app data (`webview/`) so the front end's local settings survive restarts. If WebView2 is missing the game opens in the browser instead and says so.
16. **No new tunable numbers in balance files** (the brief forbids editing them): the few desktop constants (timeouts, window size, log size) are named constants in `tst/desktop`, documented where they are defined.
17. **The icon** (`packaging/icon.ico`) is drawn by `packaging/make_icon.py` (standard library only): three rising bars in the accent blue on the dark panel colour.

## Follow-ups

- **Code signing:** an Authenticode certificate would stop SmartScreen's "unknown publisher" warning on first install (needs Reece to buy one and add it as a secret).
- **WebView2 bootstrapper:** the installer could install Microsoft's WebView2 runtime when it is missing (Windows 10 machines without Edge updates); today the game falls back to the browser.
- **Release notes for players:** write a `## v6.0.0` section in CHANGELOG before the first tag; the automatic notes are milestone headlines written for developers.
- **A Settings "Check for updates" button** and a "Show saves folder" button (open Explorer at the folder).
- **macOS/Linux builds:** the spec and entry point run on Linux headless (tested); a macOS `.app` would need its own runner job and signing.
- **Delta updates:** each update downloads the full installer (about 40-50 MB).
