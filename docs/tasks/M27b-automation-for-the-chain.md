# M27b: Automation for the chain (v3.5, lane A)

**Goal:** the v2 and v3 parts of the business (device production, supply and commodities, exploration, mines and refineries, fabs and foundry customers, government affairs, corporate development) join M27a's automation layer. A whole vertically integrated group, subsidiaries included, can then run under delegates, with one-offs still coming to Reece.

**Formulas:** `docs/formulas.md` §40 (as M27a built it, including §40.12's commitments), with §28, §31, §33–§39 and §41 · **ADRs:** 0002, 0013 (stream `automation` 56), 0020 · **Depends on:** M27a (`m27a-done`), M28 (`m28-done`) · **Lane:** A, alongside M31 (lane C) and M28r if it is still open

**Revised 2026-11-14** against what M27a built: twelve areas in a fixed order, owners through `SetAreaOwner` and `SetAreaSettings`, proposals as `exec_proposal` kind `auto`, commitments per action in §40.12, lead roles with `founder_fit: false`, and the digest's `in_digest` filing.

## Lane

- Its own session and branch (`m27b-chain-automation`) from `main`.
- **M27b owns** `backend/tst/sim/automation/` (new area rules and the subsidiary scope); `automation.*` in `balance.yaml`; new lead roles in `roles.yaml`; the Automation screen and owner records on the person profile; `tst/balance/m27.py` and a new `m27b.py`.
- **M27b reads but does not change** the chain's own rules (`exploration/`, `mining/`, `refining/`, `fabs/`, `contracts/`, `geopolitics/`, `mna/`, `world/`). It calls their existing actions. A rule gap in one of them is a note for the product manager, not a fix here.
- **M27b must not edit** M31's platform code or M28r's fix branch files (`tst/balance/m21.py`, `world.*`).
- **Shared files:** `balance.yaml` (add only `automation.*`), `docs/formulas.md` (notes in §40 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.**

## Rules for every new area

- **Order.** New areas are **appended** after M27a's twelve (indices 12 onward), so stream `automation` keys for existing areas don't move.
- **Data.** Each area lists in `balance.yaml`: its seat (if any), lead roles, energy (15–35), skill weights summing to 1, KPIs and the event categories it answers.
- **Rules and mistakes.** Each area's right rule and its mistake (second-best option, a step off by 20%, or a month late) are as below. The quality draw is §40.3's.
- **Commitment and limits.** Each action's commitment follows §40.12 and is added there for the new actions. Under the limit the owner acts; at or above it the action becomes a proposal. Everything in §40.2's one-off list stays a proposal.

## Sub-tasks (commit after each)

1. **Subsidiaries on the Automation screen** (M27a follow-up 2). The screen's company switcher covers every group company.
   - Inside a subsidiary, its CEO is the default owner of every area. The player may appoint another owner from that subsidiary's own staff.
   - The mandate (§31.4) is the guardrail, and one-offs inside a subsidiary come to the player as proposals.
   - The runner acts for each company in its own books.
   - **Test:** a subsidiary's area decisions post to its own ledger, and a one-off inside it reaches the player.
2. **Device production** (seat COO; leads: manufacturing engineer, operations manager).
   - Keep each device's finished-goods cover between guardrails (default 4–10 weeks of the shown demand plan) through contract-manufacturer orders (`SignManufacturingContract` within standard terms) and own-plant production plans.
   - A new contract longer than 36 months is a one-off.
   - Mistake: an order 20% off.
3. **Supply and commodities** (seat COO; lead: procurement manager, new).
   - Keep each input's 12-month cover (contracts, offtakes and group supply, from M23c's planning view and M23r's fixed own-supply count) within a band (default 60–100%).
   - Below the band, sign the standard contract or offtake with the best displayed terms (`SignCommodityContract`, `SignOfftake`, `SignWaferContract`, `SignRefiningDeal`). Prefer group supply, then allied-bloc suppliers (§39), then price.
   - Above the band, let contracts lapse at expiry rather than terminate. `TerminateContract` stays a one-off.
   - Mistake: a supplier one place lower in the ranking.
4. **Exploration** (no seat; lead: geologist at senior or above).
   - Run licensed projects through the pipeline within a yearly budget the player sets (default 0, meaning off until set): `StartDeskStudy`, `OrderDrilling`, `StartStage`, `RenewLicence`.
   - Licence the best block that the desk studies show (`TakeLicence`) when the budget allows.
   - Relinquish a project whose displayed range falls entirely below a grade guardrail (`RelinquishProject`).
   - `SellProject` and the development decision (`BuildMine`) are one-offs.
   - Mistake: the second-best block or stage.
5. **Mines and refineries** (no seat; leads: mining engineer and plant manager, new).
   - Staffing (`StaffMine`, `StaffFacility`) to the facility's need.
   - Safety (`SetMineSafety`): the guardrail level, default "standard".
   - Sales routing (`SetMineSales`, `SignMineSale`, `SellPlantCapacity`): group needs first, then contracts, then spot.
   - Closures, sales and expansions are one-offs.
   - Mistake: routing a month late.
6. **Fabs and foundry customers** (seat CTO; leads: process engineer and fab manager, new).
   - Wafer starts go to own and group demand first.
   - Spare starts go under `SignFoundryContract` at or above a margin guardrail (default 20% over cost per start), up to the player's cap on contracted share (default 80%), with the rest sold at spot (`SellCapacity`).
   - `UpgradeFab`, conversions, new nodes and `SellFacility` are one-offs.
   - Mistake: a contract 20% under the best displayed price.
7. **Government affairs** (no seat; leads: legal counsel and public policy manager, new).
   - Lobbying by region (`SetLobbying`) within a yearly budget the player sets.
   - Licence applications for blocked sales and tools (`RequestLicence`, `RequestToolLicence`) when a sale or tool is blocked.
   - Proposing compliant variants (`LaunchVariant`), which is a proposal because it is a product decision.
   - `TakeLocalPartner` and `SetGreyRoute` are always one-offs. The grey route is risky and is never taken by a delegate.
   - Mistake: a month late.
8. **Corporate development** (seat CFO; lead: corporate development manager, new).
   - Each quarter, screen targets (`StartDiligence` within budget) and pitch the best as a proposal with §28.1's displayed range.
   - Every bid (`BidForCompany`) and `AbandonDeal` is a one-off.
   - Mistake: the second-best target.
9. **Hiring headcount targets** (M27a follow-up 1): per-unit headcount targets the player sets, which Hiring fills (as well as backfilling leavers).
10. **Owner records on the person profile** (M27a follow-up 4).
11. **Targets, e2e and close-out:**
    - **§40.10 targets 1 and 4 re-read** with the new areas. Both sit at their bands' edges (1.18 against 1.2; 10.0 against 10). Tune `automation.*` cadence if they drift (rule 1).
    - **The chain targets (printed):**
      - **(a)** M23b's `full_integrator` with every area automated by score-15 owners spread over at least eight people, the founder approving positive-central-case proposals only, over 30 years: median year-30 ARR between 0.85× and 1.2× the scripted integrator.
      - **(b)** The same with score-8 owners: at least 20% lower.
      - **(c)** No delegate ever takes `SetGreyRoute` or terminates a contract (property test).
      - **(d)** Proposals at most 3 a month (median) in run (a).
    - **Playwright:** (a) automate a mining subsidiary's areas and Continue three months; (b) a supply cover shortfall gets a contract signed under the limit and a proposal above it; (c) a corporate-development pitch arrives as a proposal.
    - **A practice save** `pt-auto-chain`: an integrator with a mining subsidiary and a fab, staffed with leads, nothing automated yet.
    - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every area in sub-tasks 2–8 can be automated, in the player's company and in each subsidiary.
- [ ] No owner commits above its limit, no one-off runs without approval, and no delegate takes a grey route or terminates a contract (property tests over the new areas).
- [ ] Existing areas' stream keys are unchanged, and a company with no automated areas plays exactly as before (state-cache check).
- [ ] Targets (a)–(d) and §40.10's targets printed and met, or carried with a recorded decision.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m27b-done`.

## Manual check (Reece, after merge)

In your campaign, or on `pt-auto-chain`, automate the mining subsidiary and the fab, set an exploration budget, and play two years on Holiday. Read the digests.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
