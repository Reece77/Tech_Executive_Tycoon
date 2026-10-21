# Tech Startup Tycoon — starter kit

Pre-build documents for a Football Manager-style tech-industry management sim. Drop these into the root of a new git repository before running any coding agent.

## What is here

| Path | Purpose |
| --- | --- |
| `CLAUDE.md` | The rules every coding session follows (Claude Code reads it automatically) |
| `AGENTS.md` | Pointer for ChatGPT/Codex, plus a reviewer checklist |
| `.cursor/rules/*.mdc` | The same rules for Cursor, scoped by folder |
| `docs/adr/` | 11 architecture decision records |
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
