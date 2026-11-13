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

(filled in by the agent)

## Follow-ups

(filled in by the agent)
