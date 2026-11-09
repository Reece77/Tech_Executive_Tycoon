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
| [M10r-review-fixes.md](M10r-review-fixes.md) | Fixes from Codex review 2: lender fees below operating profit, interest out of division statements, inherited offices on closure, overseas sales in product totals, exact regional prices, a repayment test that cannot skip | M9 |
| [M10b-feel-fixes.md](M10b-feel-fixes.md) | Reece's playtest: the inbox archives and blocks on major events, event modifiers shown as numbers, critical crises, explanations that say what to do, self-serve abroad and marketing by region, former staff stories | M10r |
| [M10c-executive-authority.md](M10c-executive-authority.md) | Executives with authority: guardrails per seat, executives acting each month through the player's actions with decision quality from their true score, CFO and COO proposals that block Continue, quarterly reports, executive events, Ask my COO from the COO's report | M10b |
| [M12a-cloud-and-data-centres.md](M12a-cloud-and-data-centres.md) | Data centres as the first kind of a generic facility model, compute units on spot or own capacity, component goods with history then seeded shocks and contracts, Cloud and GPU hosting selling spare capacity, outages as critical events, the Infrastructure screen (lane B, merges after M11) | M10d |
| [M11-rnd-tree.md](M11-rnd-tree.md) | R&D tree and era milestones: domain levels, research projects, the tech factor on quality and features, eight eras on their dates or early by threshold with a first-mover window, licensing, leaks and rivals' research, the Research screen (lane A, merges before M12a) | M10d |
| [M13b-executive-ambition.md](M13b-executive-ambition.md) | Executive ambition and visible eras: CPO authority, executives' and the CEO's quarterly pitches with a Holiday spend limit and follow-through records, decision-led reports in the executive's voice, a stronger and visible first-mover window with an era report, market size, the research lead's wording | M12r |
| [M14-mergers-and-acquisitions.md](M14-mergers-and-acquisitions.md) | Mergers and acquisitions (lane A): valuation of every company, diligence and hidden problems, private and listed offers and hostile tenders, antitrust with remedies, kept brands with directives and consolidation, integration with culture clash and severance, rivals buying startups, acquisition pitches, and the exit ending | M13b |
| [M15a-v2-balance.md](M15a-v2-balance.md) | v2 balance and long campaigns (lane A, merges second): nine scripted strategies, eras to 2039, 30-year runs and a weekly workflow, the 2039 turn-time test, rival startups that keep launching, the v2 targets V1-V7 and the known misses | M14 |
| [M15b-modes-and-polish.md](M15b-modes-and-polish.md) | Modes and polish (lane B, merges first): the company score, a world built at any start year, Sandbox, five historical scenarios, industry rankings, Continue until, polish, and the playtest 3 addendum (negotiation, serial founder, rival CEO profiles and storylines, tenure reveal, promise hint, Deals in the top bar) | M14 |
| [M24-the-founders-life.md](M24-the-founders-life.md) | The founder's life (lane C, beside v3; merges before M16): stress and burnout with a top-bar meter, the founder's own personal book, a foundation for a cause, a public persona of four traits, lobbying with influence by region and hidden scandal risk, and the legacy score | M15a |
| [M16-holding-company.md](M16-holding-company.md) | The holding company and subsidiaries (v3): group membership and consolidation by period (Codex review 4 findings 2 and 3), the holding company with the Group screen and a company switcher, NCI, the equity method and fair value, subsidiaries' mandates, reviews and capital requests, stake sales, buyouts, carve-outs, spin-offs, stakes in rivals and venture investing, transfer prices with minority complaints, and the conglomerate discount | M15a, M24, M15r |
| [M25-quality-of-life.md](M25-quality-of-life.md) | Quality of life (lane C, beside M17 and M18): Explain on every main-screen number with its driver breakdown, trend and a template explanation, Ask why from the chief of staff; achievements across games in a profile file, with toasts and a screen; and a data editor saving named mods that new games use, validated by the loader and copied into each save | M16 |
| [M18-prospecting-and-exploration.md](M18-prospecting-and-exploration.md) | Prospecting and exploration (v3, lane B; merges after M17): regions' geology from the dossier, 60 blocks a region with hidden deposits, the pipeline (desk study, licence, survey, sampling, drilling, resource estimate, feasibility, permitting), geologists and the range rule, ranges that hold their confidence, protests and permits as critical events, selling a project to a supplier, and the Exploration screen | M16, M17 |

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
