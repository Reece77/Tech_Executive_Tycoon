# Tech Startup Tycoon — starter kit

Pre-build documents for a Football Manager-style tech-industry management sim. Drop these into the root of a new git repository before running any coding agent.

## What is here

| Path | Purpose |
| --- | --- |
| `CLAUDE.md` | The rules every coding session follows (Claude Code reads it automatically) |
| `AGENTS.md` | Pointer for ChatGPT/Codex, plus a reviewer checklist |
| `.cursor/rules/*.mdc` | The same rules for Cursor, scoped by folder |
| `docs/adr/` | 12 architecture decision records |
| `docs/tasks/` | Task briefs for M0, M1a, M1b and how to run them |
| `docs/spec/` | Where the exported game design spec goes |

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
