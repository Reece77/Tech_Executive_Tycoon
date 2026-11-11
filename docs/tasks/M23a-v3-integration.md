# M23a: v3 integration and accounting (lane A)

**Goal:** make v3's systems work together as one group in one world. Fabs, mines and refineries supply any company in the player's group at transfer price; rivals fall under the same export controls; facilities and suppliers sit in real countries; contracts can be terminated, and foundry capacity can be sold under contract. Fix Codex review 5's twelve findings, most of which are the same gap: one company owns an asset while its group uses it.

**ADRs:** 0002, 0003, 0004, 0007, 0013, 0020 · **Formulas:** §31–§39 · **Review:** `docs/reviews/codex-review-5.md` · **Playtest:** `docs/playtests/reece-playtest-5.md` · **Roadmap:** `docs/roadmap.md` (Phase 1) · **Depends on:** M22 (`m22-done`) · **Lane:** A, alongside M23c (lane C) and M23b (lane B)

## Lane

- Its own session and branch (`m23a-integration`). **Merge order:** M23c and M23a in either order; **M23b merges last** (it measures balance on the combined code).
- **M23a owns** the simulation code under `sim/group/`, `sim/mining/`, `sim/refining/`, `sim/fabs/`, `sim/geopolitics/`, `sim/commodities/`, `sim/founder/personal.py`, `finance/consolidation.py`, `db/mappers.py` and the tests and API endpoints these fixes need.
- **M23a must not edit** screen layouts, the shell (top and side bars), exploration's screen or the practice-save tools (M23c's), or `tst/balance/` (M23b's).
- **CLAUDE.md §9's decision rules apply.** Each Codex fix comes with the regression test the finding asks for, written first and seen failing.

## Sub-tasks (commit after each)

1. **A shared group-ownership layer** (findings 1, 4, 5, 7, and M21's follow-up): one function moves a facility between group companies and updates every kind-specific record (mine, refinery, fab), its staffing and its books; one routing rule sends a subsidiary's critical events to the player's inbox, naming the affected company and facility; every facility kind can **supply any group company** at the flow's transfer price (fabs to a sister company's chips, M20's wafers into the group's fabs, mines and refineries to any group buyer); materials flows feed the minority-fairness monitor and the intra-group share. **Tests:** Codex's reproductions for findings 1, 4, 5 and 7; a three-company chain (mine → refinery → fab → device company) supplying at transfer price, with every posting on the right entity.
2. **Mines, fabs and accounting** (findings 2, 3, 6): depletion and capitalized exploration tracked per deposit across mine lifetimes (no rebuild with restored reserves); NCI attribution computed before intercompany elimination; fixed fab costs follow the facility's lifecycle, not its staffing. Regression tests as the findings ask.
3. **Money, identity, hidden values and tests** (findings 8, 9, 10, 11, 12): stable keys for entity-list and appeal draws; public planning estimates (or no economics) in fab quotes for unarrived nodes, with a differential test; offtake prepayments and every new v3 money path through `money.exact` (an audit of mining, refining, fab and tariff money), with rational-reference tests; the founder's salary monthly; the tariff property test made meaningful (non-empty taxed cases, independent expected amounts, own-fab and mixed-origin cases).
4. **Rivals under export controls** (M22 follow-up; playtest 5): rival chip and equipment companies in the controlling bloc lose sales to restricted destinations as the player does (NVIDIA's China revenue after October 2022, with compliant variants where history had them: A800, H20); Chinese rivals gain share where they can supply. Rival foundries and suppliers obey tool and input controls. **Test:** a software-only company still plays exactly as before; §39.4's targets re-run with rivals controlled.
5. **Countries everywhere** (M22 follow-up; playtest 5): a country choice for new facilities and subsidiaries (no silent default to China for East Asia); suppliers carry a country (Dowa: Japan) shown wherever a supplier is listed; tariffs carried in transfer prices between group companies.
6. **Contracts** (playtest 5):
   - **Terminate** on every contract and offtake: a fee of the remaining months' take-or-pay minimum, discounted at the base rate, plus `contracts.break_penalty` (10%), quoted before confirming; the counterparty's willingness to deal falls (a supplier relationship score that later offers read).
   - **Foundry contracts** (playtest 5, fab card): a fab's owner can sign multi-month slot contracts with rival fabless designers at a price and volume, with take-or-pay on the buyer, instead of selling only spot slots by chance.
   - **Offtakes protect production:** volume under a group's offtakes or own supply keeps 100% allocation in shortages (M19 follow-up 3; playtest 5's "I lost production").
7. **Close-out:** a Resolution section in `docs/reviews/codex-review-5.md`; CHANGELOG; data dictionary; golden snapshots regenerated only if a fix moves them (reason in CHANGELOG); the nightly guards once.

## Acceptance criteria

- [ ] All twelve Codex review 5 findings fixed, each with a regression test that failed first.
- [ ] A three-company group chain supplies at transfer price with every posting on the right entity, and NCI attributed correctly with intercompany trade (property tests).
- [ ] Rivals in the controlling bloc lose restricted sales; a software-only company plays exactly as before.
- [ ] Every contract can be terminated at a quoted fee; offtake and own-supply volumes keep allocation in shortages.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m23a-done`.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
