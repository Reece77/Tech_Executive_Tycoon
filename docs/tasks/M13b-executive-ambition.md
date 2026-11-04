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

## Status (2026-11-04): stopped before merging

Sub-tasks 1-7 are built and tested; sub-task 8's Playwright specs (a)-(c) pass and the close-out docs are written, but **two §27.5 targets miss and the allowed keys cannot fix them**, so per the instructions this branch is not merged (values in `docs/balance-targets.md`, M13b):

- **Target 3** (hit rate score 15 against 8, ≥ +15 points): 62% against 63%. The hit rate does not move with `pitch.spread`; outcomes are all-or-nothing, and the 27.1 quality rule (best or second best) does not make the second best less likely to work. Options: score executives against a central case instead of the low case; make the outcome depend on the executive's true skill (for example the CPO's new product team built with the seat's builder factor), or narrow the target.
- **Target 5** (first mover +15-35% customers against the era on schedule): +481% to +799%. With M11's lab from 2014 the era arrives three years early; with the head start switched off the early arm is still +171% to +292% ahead from the era's demand boosts alone. Options: measure the head start itself (the same early era with and without the first-mover window: now about x2.4, which `rnd.first_mover_*` can tune down), or a scenario that pulls the era only a few months forward.

Every other check: targets 1, 2 and 4 pass (8/10 seeds; x2.07; 5.2 a year); golden snapshots unchanged; the backend suite and frontend checks pass locally.

## Decisions made

- **Who pitches.** Executives with authority (the CPO now takes authority too) and the CEO for the functions no seat holder with authority covers. Kinds by seat: CPO new product and sunset; CRO region; CTO research team and data centre; COO office and assembly plant; CMO campaign; CFO buyback (once listed; rounds and loans stay 24.1 proposals). A dividend is not pitched (the buyback covers "return cash").
- **When.** In a quarter's first month: two uniforms on stream `pitch` (36), key `(person id,)`: whether (true ambition), then which (true score). A pitch still pending at the executive's next draw lapses (no morale cost), so a long Holiday does not jam a seat.
- **Scores and numbers.** Every candidate's score and number comes from displayed knowledge: displayed skill midpoints (category fit), public market sizes and prices, the company's own customers, costs and quotes. Candidates of all kinds rank on one scale, an estimated 24-month value in cents (a monthly case x 24; research by the cap lift on the revenue it feeds; an office by the builder pay of the roles it fills x talent weight; a campaign by its customers' revenue; a buyback last). The low and high case are central x (1 -+ spread), spread = max(0.15, 0.6 - 0.025 x the displayed seat score). A buyback's case is its amount, without a spread.
- **Approval.** Through the normal actions as the executive (the CEO for its pitches), all or nothing; a buyback runs as the founder (a Chair's decision). On Holiday and in scripts (no `block_major`) a pitch under the limit goes ahead in phase 2; at the controls every pitch waits and blocks Continue. Approved pitches are Chair decisions, so the M13 property "the CEO takes only CEO actions" is measured on the CEO's own monthly decisions (`at_controls=True` in that test).
- **Campaign.** A one-off spend posted to marketing now, plus awareness +25% and brand target +10% modifiers (23.2) on the product for 3 months (`pitch.campaign_*`).
- **Sunset rule.** The state keeps no per-product customer history, so "below maintenance and shrinking for 6 months" is read as live, nobody working on it (`rotting`) and launched at least `pitch.sunset_months` ago.
- **Follow-through measures.** New product: its MRR; region: its MRR there; data centre: spot minus own cost on the CU it serves; plant: its case; office: people in it; research: lead points gained; campaign: customers gained; sunset: the saving once sunset; buyback: its amount. "Too early" when what it created is not yet operating.
- **Reports.** The four parts of 27.2 in one of four voices (`exec_voices.yaml`: blunt, cautious, warm, plain) chosen from displayed personality midpoints. "What I did" groups decisions by the product they name and adds where that product stands now (quality, customers): the state keeps no quarter-start product history for a before-and-after. The CEO's letter is an `exec_report` item with seat "CEO". The LLM rewrite keeps the voice, every action and every number.
- **Eras.** The appeal bonus applies wherever segment appeal is computed (the market month and the screens), for any company holding a first-mover window. The arrival item is labelled Critical in the inbox (inbox items have no severity of their own). The era report's baseline is stored when a player company causes an era (`era_window`). The Market screen had no demand chart and no demand history is stored, so its new chart plots customers of every product in the category by month (from `product_month`), with era marks; both charts also list the marks as text.
- **Modify.** Closes the pitch as `modified` and opens the move's own screen; the New product dialog is prefilled (`?new=<category>&segment=<segment>`), other screens open on the right page.
- **Baselines kept.** M10c's and M13's balance arms set the pitch limit to 0 (pitches wait unanswered) so their targets read as before; 27.5 target 2's "pitches off" arm does the same.
- **S2** re-banded to under 65 worker-minutes on CI (`S2_BUDGET`), as the brief says.

## Follow-ups

- The two target misses above (Reece's decision).
- Modify could prefill every move's dialog (region, research, data centre, office, plant), not only a new product.
- A product's quarter-start quality and customers could be kept so reports read "41 -> 47" rather than "now 47".
- Rivals' executives do not pitch (out of scope); M14 adds acquisitions as a pitch kind.
