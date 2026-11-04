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

## Status (2026-11-04, after the product manager's rulings): stopped before merging

Sub-tasks 1-7 are built and tested, sub-task 8's Playwright specs (a)-(c) pass and the close-out docs are written. After the rulings, targets 1-5 pass and **target 7 misses**, and `pitch.*` cannot bring it into its band while target 1 holds, so per the instructions this branch is not merged (values in `docs/balance-targets.md`, M13b):

| Target | Value | Band |
| --- | --- | --- |
| 1 new product and new region | 8/10 seeds | ≥ 7/10 |
| 2 ARR, pitches / pitches off | 2.22 | ≥ 1.10 |
| 3 hit rate, score 15 / score 8 | 67% / 39% (+28 points) | ≥ +10 points |
| 4 pitches a year, median | 5.5 | ≤ 8 |
| 5 the window alone | +30% to +56% on 7 of 8 seeds (+80% on seed 5) | +25-60% on ≥ 7 |
| 5 (information) early era / on schedule | +237% to +392% | none |
| **7 ARR, pitches / steady script** | **2.32** | **≤ 1.2** |

- **Why target 7 misses.** Region launches cause the whole gap. With the CRO's region pitches removed, ARR is $81.2M against steady $72.2M (×1.12, though target 1 then fails at 0/10). With them, a launch adds about $15-40M ARR by month 36: East Asia $25-42M, Europe $17-36M, against about $72M at home. Target 1 needs a region on 7 of 10 seeds, so the median seed has at least one launch, and that alone is more than the 20% target 7 allows. Lowering the pitch rate trades target 1 for target 7, but never reaches both. The sweep (team 6, region capture 1.7):

  | Setting | T1 | T7 |
  | --- | --- | --- |
  | `base` 0.45, `per_ambition` 0.04 (shipped) | 8/10 | 2.32 |
  | `base` 0.2, `per_ambition` 0.02, clamp [0.05, 0.9] | 8/10 | 1.94 |
  | `base` 0.15, `per_ambition` 0.01, clamp [0.05, 0.9] | 8/10 | 1.74 |
  | the same with `auto_approve_cash_bp` 200 | 8/10 | 1.72 |
  | `base` 0.1, `per_ambition` 0.01, clamp [0.03, 0.9] | 6/10 | 1.49 |
  | a flat 7% a quarter (0.7 pitches a year) | 6/10 | 1.41 |

  `pitch.*` frequency is left as shipped until Reece decides. Options:
  - narrow target 1 to a new product or a region;
  - re-band target 7 (×2.3 now; about ×1.7 at the lowest frequency that keeps target 1);
  - compare against a founder script that also enters regions;
  - make a region launch smaller or slower for the founder and executives alike (an M9 regional-economy change, outside `pitch.*`).

Every other check:
- golden snapshots unchanged (11 passed);
- backend lint, format and mypy clean;
- the backend suite: 1,360 passed and 1 xfailed (the existing T2 xfail). The only failure is `tests/balance/test_m13b_balance.py`, on target 7 (2.32 > 1.2), as reported above.

The front end has not changed since the last run of its checks and of e2e flows (a)-(c), which passed.

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
- **Product manager's rulings (2026-11-04).**
  - Target 3: every pitch is scored hit against its central case from displayed estimates, the same for every executive. Execution follows the executing executive's true seat score through the 18.3 seat factor: a new product's builders' output, and a region launch's regional awareness and capacity. The band is now at least +10 points.
  - Target 5: the first-mover window is measured alone: the same seed with the era forced to the same early month, with and without the window, at the window's end. Band +25-60%. The early era against on schedule is printed as information.
  - New target 7: target 1's median ARR at month 36 is at most 1.2× the founder's steady script on the same seeds.
- **Target 3 calibration** (so the central case reads what moves reach):
  - `pitch.region_capture` 1.7 scales the CRO's case, which is now grown 24 months at the category's growth.
  - The CPO pitches only self-serve segments (a builders-only team cannot sell to sales-led ones), with `pitch.team_builders` 3 → 6 so the product can launch inside the record window.
  - A campaign's case adds the category's 24-month organic growth.
  - An office's measure is the staff living in its city above the count at approval, and an approved office moves the active hiring plans' units into it, so their hires join there.
- **Target 5 tuning:** `rnd.first_mover_cap` 8 → 5, `first_mover_brand` 15 → 6, `first_mover_appeal` 1.15 → 1 (no bonus; the mechanism and its tests stay, run at ×1.15). The arrival item names the appeal only above ×1.

## Follow-ups

- Target 7 above (Reece's decision).
- New products' central case is still far above what a launch reaches in 24 months (measured/central 0-0.23 at `pitch.new_product_share` 0.25), so they are misses at any score; they do not decide target 3.
- Modify could prefill every move's dialog (region, research, data centre, office, plant), not only a new product.
- A product's quarter-start quality and customers could be kept so reports read "41 -> 47" rather than "now 47".
- Rivals' executives do not pitch (out of scope); M14 adds acquisitions as a pitch kind.
