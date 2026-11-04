# M13b: Executive ambition and visible eras

**Goal:** executives and the CEO grow the company, not only keep it running. With authority they pitch big moves (a new product, a new region, a research project, a data centre, an office or plant, a campaign) for the founder to approve, and on Holiday the small ones go ahead. Their reports read like a person explaining their quarter. The CPO finally has something to run. Eras pay the company that pulls them forward, and say so.

**Spec sections:** §5 (people), §6 (org) · **ADRs:** 0005, 0013 (stream `pitch` 36), 0015 (delegates use displayed knowledge), 0019 · **Formulas:** `docs/formulas.md` §27 (all), with §21.4, §23, §24, §25.6 · **Playtest:** `docs/playtests/reece-playtest-2.md` · **Depends on:** M12r (`m12r-done`)

## Context

Reece's playtest 2 (2026-11-03) on `m12b-done`: everything worked and turns were quick, but on Holiday the executives and CEO "did not seem to make big decisions or start new products", reports were "kind of lifeless", "the CPO doesn't have anything to be delegated", and eras "did not push my product over the edge as much as I thought". His decisions: propose-and-approve with a Holiday spend limit; stronger and visible eras; this milestone before M14, so M14's CEO pitches acquisitions through the same system.

## Out of scope

Acquisitions as pitches (M14 adds the kind). Rivals' executives pitching (rivals keep their own decision code). Press and public promises, recruiter replacements, candidate search by interest, leadership fit in the org chart (the people-and-press milestone; `docs/ideas-backlog.md`).

## Sub-tasks (commit after each)

1. **Data and formula tests:** `pitch.*` keys (base, per ambition, morale on decline, record window, auto-approve default) and the stronger `rnd.first_mover_*` keys with `first_mover_appeal`, all in `balance.yaml` with comments; stream `pitch` (36) in ADR-0013's main table, key `(person_id,)`; report templates with personality variants. Unit tests for §27.1's probability, the quality rule and the auto-approve rule.
2. **CPO authority** (§27.1): the CPO seat gets authority with guardrails (headcount cap for new product teams, categories it may enter, protected products it may not sunset), shown in the Executive team panel like the other five.
3. **Pitches** (§27.1): candidate scoring per seat from displayed knowledge, the quarterly draw, the pitch inbox item (Approve, Modify, Decline), approval through the normal actions as the executive, the Holiday spend limit and "stop for big pitches", follow-through scoring (hit, miss, too early) and the executive's record; the CEO pitches across functions.
   - **Tests:** a seeded test of pitch timing; approval spends the executive's energy, not the founder's; guardrails hold; the auto-approve limit; a declined pitch's morale effect; differential tests that two executives with the same displayed skills but different true skills give the same pitch text and numbers (only which candidate is chosen may differ, through the seeded quality draw).
4. **Reports** (§27.2): the decision-led quarterly report and the CEO's letter, LLM within budget from engine facts only (prompt allowlist test: no hidden values) and templates otherwise. **Test:** each report names at least one action and one number; template output for every seat.
5. **Eras** (§27.3): the stronger window and appeal bonus, the arrival item, the window-end era report, and the chart markers.
6. **Small items** (§27.4): market size on the Market screen and New product dialog; the Research screen's lead wording.
7. **API, CLI and screens:** pitches in the inbox and on the Executive team panel (open pitches, record); the auto-approve limit in Holiday settings; executive profiles show their pitch record; `tst pitches`, `tst approve-pitch`, `tst decline-pitch`. Glossary entries.
8. **Balance and e2e:**
   - §27.5 targets printed and recorded; tune only `pitch.*` and `rnd.first_mover_*`.
   - **S2 re-band (product manager, 2026-11-03):** M12r measured S2 at 50–52 worker-minutes on `main` and on its branch alike (the runners got slower). Re-band S2 to **under 65 worker-minutes** on CI (CI's measured need plus 25%), recorded in `docs/balance-targets.md`.
   - **Playwright:** (a) a CPO with authority pitches a new product; approve it and see the team and hiring plan; (b) Holiday with a spend limit: a small pitch goes ahead and is reported, a big one waits; (c) pull an era forward on a fixture save and see the arrival item and the chart marker.
   - No new xfails; any guard that fails against `main` and that M13b's keys can't fix is reported with values, and you stop before merging.
   - Close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] §27.5 targets 1–5 met (printed, values recorded); target 6 holds.
- [ ] Pitches use displayed knowledge only (differential tests), and no hidden value reaches the API or an LLM prompt.
- [ ] A company that gives no authority plays exactly as before.
- [ ] `make check` green; `make e2e` passes; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m13b-done`.

## Manual check (Reece, after merge)

On `quick-stage3`, give every seat authority, set auto-approve to 5% of cash, and Holiday three years. Did they start a product and enter a region? Read one quarter's reports: do they sound like people? Then pull an era forward on `pt-ai` and read the era report.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
