# Tech Startup Tycoon — starter kit

Pre-build documents for a Football Manager-style tech-industry management sim. Drop these into the root of a new git repository before running any coding agent.

## How to play

On Windows, double-click **Tech Startup Tycoon** in the repository folder (`Tech Startup Tycoon.cmd`). That is all:

- The first time, it installs what the game needs and builds its screens (a few minutes; later starts take seconds). It needs **uv** and **Node.js 22** installed once; if either is missing, a page opens saying how to get it.
- Your browser opens at the Main menu. **Continue** opens the game you played last; **New game** starts one. The Saves list shows each game's last-played date, and Backups → **Back up now** keeps a copy you can restore later.
- Keep the black window open while you play; close it to stop the game. Double-clicking again while it runs just opens the browser.
- Want it on the desktop? Double-click **Make desktop shortcut** once.
- If something goes wrong, `saves/launcher.log` says what happened, and the error page names the step that failed.

In the game: press **Space** to Continue a month, **Ctrl+K** to jump to any screen, person, product, facility or rival by name, and **?** for every shortcut. New screens appear in the side bar as your company reaches them (Settings → Show everything turns that off), and a Getting started checklist on the Overview walks you through the first year.

On macOS or Linux, run `make dev` and open http://localhost:5173.

## What is here

| Path | Purpose |
| --- | --- |
| `CLAUDE.md` | The rules every coding session follows (Claude Code reads it automatically) |
| `AGENTS.md` | Pointer for ChatGPT/Codex, plus a reviewer checklist |
| `.cursor/rules/*.mdc` | The same rules for Cursor, scoped by folder |
| `docs/adr/` | 12 architecture decision records |
| `docs/tasks/` | Task briefs for M0, M1a, M1b and how to run them |
| `docs/spec/` | Where the exported game design spec goes |
| `Tech Startup Tycoon.cmd`, `tools/launcher.py` | Double-click to play on Windows (M29): installs, builds, serves the game on one port and opens the browser |
| `Make desktop shortcut.cmd` | Adds a Tech Startup Tycoon shortcut to the Windows desktop (M29) |

## Getting started

```bash
mkdir tech-startup-tycoon && cd tech-startup-tycoon
git init
# copy this kit's contents here, then export the spec into docs/spec/game-design-spec.md
git add . && git commit -m "Add project rules, ADRs, and task briefs"
claude   # then: Read docs/tasks/M0-foundation.md and implement it. Follow CLAUDE.md.
```

Prerequisites on your machine: Python 3.12, `uv`, Node 22 LTS, `pnpm`, `make`, git.

## Playtest tools

- `make quickstart-saves` (`tools/quickstart_saves.py`, M7c) plays the balance strategies headless on seed 1 and leaves two saves in the save folder, listed in the Saves screen: `quick-stage2` (steady at turn 36, January 2013) and `quick-stage3` (blitzscale with its second product at its first month of stage 3, so divisions and executive seats can be tried at once). Running it again replaces them. It takes about a minute and a half.
- `make playtest` (`frontend/e2e/playtest/`, M7c) has the agent play a new game for 120 months through the browser, saving yearly screenshots in `docs/playtests/agent-m7c/` and a journal in `frontend/test-results/playtest/journal.json`. It is not part of `make e2e`.
