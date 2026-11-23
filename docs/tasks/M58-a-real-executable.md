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

(filled in by the agent)

## Follow-ups

(filled in by the agent)
