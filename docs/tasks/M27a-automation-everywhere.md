# M27a: Automation everywhere (v3.5, lane A)

**Goal:** the player can hand any area of the business to a person and play at whatever depth he likes, as in Football Manager. One-off decisions always come to him for approval. Each delegate works under a money limit. A monthly digest says what they did. A weak delegate makes visibly worse decisions, so whom he appoints matters.

**Formulas:** `docs/formulas.md` §40 (all; §40.7 is M27b's), with §13.10, §17, §18, §23, §24, §25.6, §27, §29 · **ADRs:** 0002, 0005, 0007, 0013 (stream `automation` 56), 0015 · **Roadmap:** `docs/roadmap.md` Phase 2 · **Depends on:** M23b (`m23b-done`) · **Lane:** A, alongside M28 (lane B) and M29 (lane C)

## Reece's decisions (2026-11-11)

- **Everything can be automated;** one-off decisions need his approval.
- **A money limit per delegate,** and **a monthly digest**.
- **Delegates can be bad,** to make staff meaningful.

## Lane

- Its own session and branch (`m27a-automation`). **Merge order:** M29 first if it is ready (it has no rule changes), then M27a, then M28. The second to merge re-parents its migration, regenerates golden snapshots with a recorded reason, and re-runs every guard.
- **M27a owns:** new `backend/tst/sim/automation/` (areas, owners, limits, one-offs, workload, digest, routine events); `backend/tst/sim/org/authority.py`, `delegates.py`, `pitches.py` and `executives.py` where they join the new layer; the Automation screen; the "Run by … · Take back" header; the digest's inbox item (kind `digest`); new lead roles in `roles.yaml`; `tst/balance/m27.py` (new).
- **M27a must not edit:** M28's world code (`rivals/`, the chain companies, commodity prices); M29's navigation, Overview and inbox layout (M27a adds one nav entry, "Automation", and M29's grouping places it).
- **Shared files:** `balance.yaml` (add only `automation.*`), `docs/formulas.md` (notes in §40 only), `CHANGELOG.md`, `docs/data-dictionary.md`, ADR-0013: keep both sides.
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

§40.7's chain areas (device production, supply, exploration, mines and refineries, fabs, government affairs, corporate development) are M27b. Pay reviews and retention offers (follow-up). The founder's personal life is never automated (the family office already is).

## Sub-tasks (commit after each)

1. **Data and the model:** `automation.*` keys with comments (unit and intent); areas with weights, lead roles, energy costs and KPIs in `balance.yaml`; new lead roles in `roles.yaml` (data only); stream `automation` in ADR-0013; the `AreaOwner` and proposal records; migration and data dictionary. **Test:** loader validation (weights sum to 1; every area has a rule).
2. **Owners and eligibility** (§40.1): seat holders, the CEO, area leads and subsidiary CEOs; one setting with §24.1's authority; taking back, with the ego rule. **Test:** eligibility for each owner kind; the founder can never be one.
3. **Limits and one-offs** (§40.2): commitment, per-decision and monthly limits, the one-off list, proposals with expiry and the 6-month cool-off, Holiday's `stop_for_approvals`, `auto_approve_cents` becoming the pitch limit. **Property tests:** no owner commits above its limit; no one-off ever runs without approval (random settings and states).
4. **Quality and workload** (§40.3): area scores, stream `automation` draws, energy per area in priority order, "no time" logs, the owner's record. **Seeded test:** the same seed gives the same decisions; a score-8 owner makes more logged mistakes than a score-15 owner over 100 trials.
5. **The new area rules** (§40.6): pricing for self-serve and devices, research, regions, cloud capacity, press and communications. Each with its right rule, its mistake and a unit test.
6. **Routine events** (§40.5): answered at Continue by the area's owner; critical events never. **Test:** a critical event is never resolved by automation.
7. **The monthly digest** (§40.4): the `digest` item, `in_digest` flags, the LLM opening (MockLLMAdapter in tests; template fallback), links to quarterly reports. **Hidden-value test:** no true score, probability or draw in the digest's prompt or API.
8. **The Automation screen** (§40.8): the table, the owner picker with fit bands, "Can't automate yet" reasons, limits, priority, **Automate everything** with confirmation, and the screen headers.
9. **API, CLI, e2e, balance and close-out:**
   - **CLI:** `tst automation` (areas and owners), `tst automate --area --owner --limit`, `tst automate --all`.
   - **Playwright:** (a) automate everything and Continue three months, then read the digest; (b) a one-off proposal stops Holiday and is approved; (c) take an area back; (d) "Can't automate yet" names how to fix it.
   - **A practice save** `pt-auto`: a stage-3 company with every seat filled, a few leads, and nothing automated yet.
   - **§40.10 targets** printed and recorded; tune only `automation.*` (rule 1). §27.5's targets re-run: if they leave their bands because one-off pitches no longer go ahead on Holiday, stop and report (that is a measurement change).
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every area in §40.1 marked M27a or existing can be automated from the Automation screen, and "Automate everything" works on `pt-auto` (e2e).
- [ ] No owner ever commits above its limit, and no one-off runs without approval (property tests).
- [ ] Critical events never resolve by automation (test).
- [ ] The digest arrives every month with at least one automated area and never blocks Continue (e2e).
- [ ] Nothing in the API or an LLM prompt reveals an owner's true score, the quality probability or a draw (hidden-value test).
- [ ] §40.9 holds: a company with no automated areas plays exactly as before (state-cache check); golden regeneration, if any, explained in CHANGELOG.
- [ ] §40.10 targets 1–6 printed and met, or carried with a recorded decision.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m27a-done`.

## Manual check (Reece, after merge)

Load `pt-auto`, press **Automate everything**, and play a year on Holiday. Read three digests. Approve or decline what reaches you. Then swap your CTO for a weaker one and watch the next year's engineering decisions.

## Decisions made

1. **Areas (§40.1).** Twelve in `automation.areas`, in a fixed order whose index keys stream `automation`: hiring, engineering, products, pricing, marketing, support, treasury, research, regions, cloud, press and events (Routine events). Each lists its seat, lead roles, energy (15–30), skill weights (sum 1), KPIs and the event categories it answers (hiring: personnel; marketing: market; support: operations; treasury: finance and lender; research; press; events: rivals). Founder, board, executive, public and geopolitics events always stay with the player.
2. **Lead roles.** Six appended to `roles.yaml` (engineering manager, sales manager, marketing manager, research scientist, site reliability engineer, communications manager), all `product_function: none`, with a new `founder_fit: false` that keeps them out of the founder's best-fit role (formulas §1), so no founder's ability or growth moves. Hiring, products, support and treasury use existing roles (recruiter, product manager, operations manager, finance manager); cloud also takes a senior DevOps engineer.
3. **One setting (§40.1).** Giving an existing seat area to its seat holder also gives the seat authority; taking it back withdraws it, and withdrawing authority takes the area back. Authority given the old way creates no area row, so such companies play exactly as before (§40.9). A seat holder running its own seat's rule keeps stream `delegate` and the rule's old key; any other owner draws from `automation` (ADR-0013 row 56, keys as built).
4. **Proposals (§40.2)** reuse `exec_proposal` with kind `auto` (the action as JSON, its area, commitment, expiry and why) and a new status `expired`; approving runs the action with the founder as actor. They expire after `automation.proposal_months` (3); the CFO's and COO's own proposals still lapse at the next Continue (24.1, unchanged). Moves 27.1 pitches (region, research team, data centre) wait as pitches.
5. **Commitment** per action (formulas §40.12): plans at the role's mid salary × 12, marketing increases × 12, repayments, research teams' monthly cost × 12, a pitched move's 12-month cost.
6. **Hiring** backfills leavers (a plan per role and unit someone is leaving or left last month); per-unit headcount targets are a follow-up.
7. **Pricing** anchors are the prices when the area was given, kept in the CRO's authority record (disabled unless the CRO seat was given). Shown churn is the product screen's.
8. **Research** stops projects whose domain feeds no live product (running projects show no months to finish). **Cloud** sells spare capacity below the band (there is no buy action: products buy the spot compute they lack) and pitches a data centre above it. **Press** uses the moments' tones: measured; bold only when allowed and revenue grew three months running.
9. **Routine events** score choices by their listed effects (cash per $10,000, morale, brand, quality and customers as points, a modifier per 5%), ties to the do-nothing or smaller choice. Open events an owner will answer no longer block Continue.
10. **Workload** is a count apart from the owner's action energy: `automation.owner_energy` (100) × the support pool's coverage.
11. **Holiday's `stop_for_approvals`** is an Interruptions setting in `ui_settings.json` (outside the save, like `stop_on`): on, an owner's `auto` proposal or a pending one-off pitch stops a holiday with reason "approval"; off, they wait. One-off pitches (sunset, data centre, plant, buyback, dividend, acquisition) no longer go ahead on Holiday whatever the limit; an owned seat area's money limit replaces `auto_approve_cents` for that seat's pitches.
12. **Digest filing (§40.4).** Hiring-pipeline items (candidates, offers, plan activity and plan filled), sales capacity, region live and "Your choices this month" are flagged `in_digest` while their area is automated; executives' monthly decisions while any area is. Quarterly reports stay in the inbox and the digest points to them in a quarter's last month.
13. **The Automation screen** is a new system in M29's unlocks (id 22): stage 3, or as soon as someone could run an area. Subsidiaries keep their CEO and mandate (31.4); the runner acts for the player's company.
14. **§40.10's one-owner arm** writes a Ceo record directly with no scopes of its own (the CEO is the only owner allowed every area; appointing one needs stage 4). It is a balance tool, not the game.

15. **§40.10 tuning (rule 1).** The area rules first pitched a region and a research team every quarter, far more often than a seat's own pitch draw (27.1), and target 1 read 3.2. New keys `automation.regions_every_months` and `research_every_months` set a cadence; then, at 10 seeds, `research_every_months` 12 → 36, `regions_every_months` 24 → 48 and `research_budget_bp` 800 → 400 took target 1 from 1.40 to 1.18 (band 0.85–1.2). Target 4's other inbox items fell from 19.5 to 10.0 a month once the hiring pipeline, region and capacity items and the month's choices were filed with the digest (decision 12). Final readings: 1.18; 0.64 and ×5.3; 0.35; 1.0 and 10.0; 95% (docs/balance-targets.md).
16. **§27.5 re-run.** With one-off pitches waiting on Holiday, §27.5's targets stay in band (target 1 7/10, 2 1.40, 3 +31 points, 4 1.7, 5 on 7+ seeds, 7 0.86), so this is not a measurement change and nothing stopped.

## Follow-ups

1. Per-unit headcount targets for Hiring (40.1); the rule backfills leavers until then.
2. Subsidiaries' areas on the Automation screen: the runner acts for the player's company; subsidiaries keep their M16 mandate CEO.
3. Targets 1 and 4 of §40.10 sit at their bands' edges (1.18 against 1.2; 10.0 against 10): the nightly test will flag drift; M27b's chain areas add decisions and inbox items, so re-read them there.
4. An owner's record on the person profile (the API's `/automation/record/{id}` is built; the screen shows it only through the Automation table).
5. Pay reviews and retention offers (out of scope here), and quarterly reports filed with the digest if Reece prefers a calmer inbox.
