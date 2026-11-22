# M43r: Codex review 9 fixes (two lanes)

**Goal:** fix the fourteen findings of Codex review 9 (no P1), each with the regression test the finding asks for, written first and seen failing.

**Review:** `docs/reviews/codex-review-9.md` · **Formulas:** §31, §32.2, §45.6, §49.7, §52.4–§52.5, §54.1, §55.4–§55.5, §56.1, §56.3, §57.2–§57.3 · **ADRs:** 0002, 0003, 0004, 0007, 0013 · **Depends on:** M43 (`m43-done`)

## Lanes

Two sessions, each in its **own clone or worktree** (never a shared folder):

| Lane | Branch | Findings | Trailer |
| --- | --- | --- | --- |
| **A** | `m43r-a` | 1, 2, 3, 4, 6, 11, 14 (turn phase order, founder and estate, conglomerate view, the pre-2040 guard) | `Milestone-Tag: m43ra-done` |
| **B** | `m43r-b` | 5, 7, 8, 9, 10, 12, 13 (government, space flights, pharma licensing, RNG keys, the money guard, caches) | `Milestone-Tag: m43rb-done` |

- **Lane A merges first,** since it changes the turn's phase order. Lane B merges `main` after `m43ra-done`, re-records fixtures on the combined code, and re-runs every guard.
- **Neither lane edits the other's findings' files.** `turn.py` is lane A's. Lane B's fixes stay inside their modules.
- **Results will change** for findings 1, 6, 9 and 11 (and possibly 7 and 8). Regenerate golden snapshots and the M28, M30, M32, M37 and M45 fixtures with the reason in CHANGELOG. Re-run every earlier guard. A guard that moves goes under rules 1–4; re-banding is a stop-and-ask.
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (each: regression test first, seen failing)

**Lane A**
1. **Salary at death** (finding 1): credit personal salary from the payroll result, and settle the estate after the deceased founder's final salary. Full-turn test with a forced January death; cold reload.
2. **The inherited foundation** (finding 2): delete removed foundation keys and upsert surviving ones within the turn's transaction. Warm and cold states must be equal, with the endowment conserved.
3. **Conglomerate committed capital** (finding 3): build allocations from the public construction projection the facility screens use. Paired-state test (only the hidden overrun varies) for every facility kind in the panel.
4. **Ownership gaps** (finding 4): query the union of actual ownership intervals, coalescing overlapping ones. Test a subsidiary held twice with a sale between; the gap reaches neither the API nor the letter prompt.
5. **Pharma's ceiling before sales** (finding 6): compute the month's level before demand, with a final clamp. Test the boundary case Codex gives (99.9 against 100).
6. **Space openings before sales** (finding 11): apply dated openings before the sales phase. Test September to November 2020 for Starlink.
7. **The pre-2040 guard** (finding 14): add a same-code differential replay with M37's rules disabled in the reference arm, alongside the mode-parity check. Mutation test: moving a rule across January 2040 is caught at its first differing month.

**Lane B**
1. **Classified contracts** (finding 5): store the awarded requirements on the contract, or keep the tender while delivery depends on it; handle existing saves explicitly. Test clearance loss after pruning, across a cold reload.
2. **Grounded vehicles** (finding 7): check grounding before consuming the backlog or drawing an outcome. Test that the backlog holds through grounding and resumes after.
3. **Out-licensed programmes** (finding 8): the rival files through the existing approval path once eligible. Seeded end-to-end test to approval, with the final milestone once and royalties reconciled in both ledgers.
4. **Stable RNG keys** (finding 9): key vehicle incidents by product and region, and bought launches by constellation and its own flight ordinal. Isolation tests per pair.
5. **The money guard and the postings** (finding 10): use exact money helpers for the postings Codex names, and any others the audit finds. Teach the guard money aliases (`revenue`, `sales`, `cost` and the like), tuple unpacking and mapping iteration. Fixtures prove the guard and the posting fail independently. Re-run the guard over all of `tst/sim/` and fix what it finds.
6. **Caches** (finding 12): keep the external inputs alive with the cached value and validate their identity, as the payroll cache does. Test a simulated reused id.
7. **Fixed-price totals** (finding 13): allocate cents by the difference between successive rounded cumulative entitlements. Test remainders on both sides of the boundary; the lifetime total is exact in the contract and the ledger.

## Acceptance criteria

- [ ] Each finding has a regression test that fails on `m43-done` and passes on its lane's branch.
- [ ] Fixtures re-recorded with reasons; every earlier guard re-run and reported under rules 1–4.
- [ ] A Resolution line per finding in `codex-review-9.md` (fixed, with the test's name).
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green on each lane; merged through pull requests per CLAUDE.md §6 with each lane's trailer.

## Decisions made (lane B)

- **Finding 5, where the requirement lives:** the contract keeps its awarded tender's clearance (`Contract.clearance`, in the contract's JSON record; no migration). A contract saved before M43r takes its tender's clearance on load while the tender is still saved (`government_io.load_government`); one whose tender was already pruned needs the **strictest level its buyer's tenders are drawn at** (`tenders.clearance_mix`: `top_secret` for defence, `secret` for civil; `delivery.requirement`), since the awarded level can't be known and the old reading (`none`) is the bug. Tender pruning is unchanged.
- **Finding 7:** a grounded line's owed launches wait untouched (no draw, no flight, no history) until `grounded_until`; they fly that month.
- **Finding 8:** a rival holding a licensed programme files with every drug regulator `can_file` allows once its trials have read out, through `approval.file` (the player's path), in the pipeline phase. A rival doesn't resubmit after a refusal (a complete response letter is final for it). Milestones reached before the licence still pay in the deal's first month, as before (see Follow-ups).
- **Finding 9:** vehicle incidents are keyed `(1, product_id, region_index)`, one generator a region; a bought launch is keyed `(1, 0, constellation_id, n)` with n the constellation's own launch that month (its launch loop's index). ADR-0013's table updated.
- **Finding 10, the guard:** a name is money when it contains `cents` or one of its `_`-separated words is `revenue(s)`, `sales`, `cost(s)`, `amount`, `fee(s)`, `spend` or `payout`; a local assigned money is money; `x[k]` and `x.get(k)` read through money and float mappings; tuple-unpacked assignments, `for` targets and comprehension targets take floatness from the value (a float mapping's `.values()`, the last element of its `.items()`, a float sequence's items). Each line it then found in `tst/sim/` is fixed with the exact helpers when it posts or stores cents, or carries a `# money-exact:` reason when it doesn't (audit table below).
- **Finding 12:** every cache keyed on an input's `id()` keeps the input with its value and checks identity before answering, as payroll's cache does: `eras.arrived`, `saturation.value_per_customer` and `saturation.ceilings` (named by the review), and the audit's module caches `platforms.fees.fee_drag` (which also left `balance` out of its key), `fabs.nodes.timeline`, and `fabs.market`'s China overlay, EUV ratios (also missing `balance` and `data`) and EUV-gated timeline.
- **Finding 13:** a fixed-price month earns installment i = round(V x (i + 1) / term) - round(V x i / term), i = months since the start; a month the company can't deliver forfeits its installment. Cost-plus and IDIQ are unchanged (their revenue is drawn work, not a price).

### Finding 10's audit (the upgraded guard over `tst/sim/`)

About 135 lines: about 55 fixed with the exact helpers (they post or store cents), about 75 carry a `# money-exact:` reason (rates in float cents rounded where posted, ratios, estimates only compared or shown), 4 wait in `DEFERRED` for lane A's merge (`founder/personal.py`, `group/conglomerate.py` x2, `pharma/demand.py`).

| Area | Fixed: posted or stored cents now exact |
| --- | --- |
| Payroll | pool salaries and tools and travel (`times` with the float headcount) |
| Pharma | rival costs (the review's 27,500,016 case), royalties and co-development shares, stage cost, redesign, partner share, quality supply cost |
| Rivals and startups | prices, poach offers, funding rounds, entrant cash |
| Founder and finance | family office gains, scandal fines, share trade costs, dividends, secondary fees (capital), fundraising values, the insolvency bridge cap |
| Chain and mining | world rivals' COGS, interest, debt repayment, expansion capex, opening cash, capex and debt; mine cash cost, unit cost, in-group sales; refinery mine payments; power rivals' plant capex |
| Other | regulation fines and FX amounts, hardware take-or-pay and COGS, CRO reference price, hosting savings, CMO marketing budgets, shared-cost allocation, constellation waiting value, car connectivity revenue, analyst targets, family answers' rounding, exploration sale price |

The five lines M36r deferred to M32 (mining sustaining capex, refinery quotes) are resolved: the posted one exact, the quote and the display figure given reasons.
