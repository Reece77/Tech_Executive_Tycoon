# Task briefs

Each brief is a self-contained prompt for a coding agent. Hand one brief to Claude Code at a time.

## How to run a brief with Claude Code

1. Start a fresh Claude Code session in the repo root (it reads `CLAUDE.md` automatically).
2. Paste: `Read docs/tasks/<brief>.md and implement it. Follow CLAUDE.md. Work through the sub-tasks in order, committing after each. Stop and ask if anything in the brief conflicts with the spec or ADRs.`
3. When it finishes, the agent merges its own branch once `make check`, `make e2e` and the GitHub check are green (CLAUDE.md §6, Merging) with a `Milestone-Tag: mX-done` trailer and pushes; the `tag-milestone` workflow then tags it. Play the brief's "Manual check" every two or three milestones.
4. Optional second opinion: give ChatGPT (or a fresh Claude session) `AGENTS.md`, the brief, and `git diff <start>..HEAD`, and ask for a review per the "reviewer" section of `AGENTS.md`.
5. The `tag-milestone` workflow tags each merge `mX-done` once `check` is green on `main`.

## Order

| Brief | Milestone | Depends on |
| --- | --- | --- |
| [M0-foundation.md](M0-foundation.md) | Repo, tooling, schema v1, seeded RNG, turn runner, API and UI shell | — |
| [M1a-people-model.md](M1a-people-model.md) | People model, generator, founder creation, reveal, monthly growth | M0 |
| [M1b-hiring-rules-and-api.md](M1b-hiring-rules-and-api.md) | Hiring, offers, payroll, morale, resignations, inbox: rules, API, and CLI | M1a |
| [M1c-screens.md](M1c-screens.md) | New-game setup, Inbox, Overview, People, Profile, Recruitment screens | M1b |
| [M2a-org-rules-and-api.md](M2a-org-rules-and-api.md) | Org units, managers, span, raises and promotions, remote policy, delegated hiring: rules, API, CLI | M1c |
| [M2b-org-screens.md](M2b-org-screens.md) | Org screen and the profile, people, recruitment, inbox and overview additions | M2a |
| [M3a-products-and-market.md](M3a-products-and-market.md) | Products, development, markets with 2010 incumbents, revenue, founder scouting: rules, API, CLI | M2b |
| [M3b-product-screens.md](M3b-product-screens.md) | Products screen, product profile, market view, and the org, overview, recruitment and inbox additions | M3a |
| [M4a-finance-rules-and-api.md](M4a-finance-rules-and-api.md) | Statements, cap table and options, SAFEs, priced rounds, board, bankruptcy: rules, API, CLI | M3b |
| [M4b-finance-screens.md](M4b-finance-screens.md) | Finance screen (statements, cap table, fundraising, board), game over screen and additions | M4a |
| [M4c-playtest-fixes.md](M4c-playtest-fixes.md) | Fixes from Reece's first playtest: energy, "what you learned", interview potential, investor heat, board nominee, inbox cleanup | M4b |
| [M5-rivals.md](M5-rivals.md) | Rival AI for incumbents, rival startups, poaching both ways, Competitors screen (one milestone) | M4c |
| [M6-events.md](M6-events.md) | Event director, templates and LLM pipeline, storylines, relationships, critical events, headlines, Settings (one milestone) | M5 |
| [M7a-speed-and-balance.md](M7a-speed-and-balance.md) | Turn speed, balance targets, strategy runner (nightly), 20 templates, balance pass | M6 |
| [M7b-history-saves-holiday.md](M7b-history-saves-holiday.md) | Holiday, saves manager, History, tooltips, saved column views, Ask my COO, the 10-year run (finishes v1) | M7a |
| [M8-divisions-and-new-markets.md](M8-divisions-and-new-markets.md) | Divisions and division P&L, executive seats, support and shared services, Fintech and AI markets, scheduled entrants (first v2 milestone) | M7b |
| [M10-capital-and-macro.md](M10-capital-and-macro.md) | Macro layer (history to 2025, then seeded cycles and downturns), Series C and D with growth investors, venture debt and bank loans with covenants and the lender event (lane B) | M8r |
| [M9-cities-and-regions.md](M9-cities-and-regions.md) | Cities and HQ, offices, hiring by city, regional markets and launches, regional incumbents and rivals' region entry (lane A, merges after M10) | M8r |

Briefs for M2 onward are written after the previous milestone's retrospective, so they reflect what was actually built.

## Brief template

```markdown
# Mx: Title
Goal (one sentence) · Spec sections · ADRs
## Context
## Out of scope
## Sub-tasks (each ends in a commit)
## Acceptance criteria (checkboxes, each testable)
## Manual check
## Decisions made (filled in by the agent)
## Follow-ups (filled in by the agent)
```
