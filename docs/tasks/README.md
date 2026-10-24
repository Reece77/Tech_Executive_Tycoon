# Task briefs

Each brief is a self-contained prompt for a coding agent. Hand one brief to Claude Code at a time.

## How to run a brief with Claude Code

1. Start a fresh Claude Code session in the repo root (it reads `CLAUDE.md` automatically).
2. Paste: `Read docs/tasks/<brief>.md and implement it. Follow CLAUDE.md. Work through the sub-tasks in order, committing after each. Stop and ask if anything in the brief conflicts with the spec or ADRs.`
3. When it finishes, run `make check` yourself, then play through the brief's "Manual check" steps.
4. Optional second opinion: give ChatGPT (or a fresh Claude session) `AGENTS.md`, the brief, and `git diff <start>..HEAD`, and ask for a review per the "reviewer" section of `AGENTS.md`.
5. Tag the release: `git tag m0-done` (and so on).

## Order

| Brief | Milestone | Depends on |
| --- | --- | --- |
| [M0-foundation.md](M0-foundation.md) | Repo, tooling, schema v1, seeded RNG, turn runner, API and UI shell | — |
| [M1a-people-model.md](M1a-people-model.md) | People model, generator, founder creation, reveal, monthly growth | M0 |
| [M1b-hiring-rules-and-api.md](M1b-hiring-rules-and-api.md) | Hiring, offers, payroll, morale, resignations, inbox: rules, API, and CLI | M1a |
| [M1c-screens.md](M1c-screens.md) | New-game setup, Inbox, Overview, People, Profile, Recruitment screens | M1b |
| [M2a-org-rules-and-api.md](M2a-org-rules-and-api.md) | Org units, managers, span, raises and promotions, remote policy, delegated hiring: rules, API, CLI | M1c |
| [M2b-org-screens.md](M2b-org-screens.md) | Org screen and the profile, people, recruitment, inbox and overview additions | M2a |

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
