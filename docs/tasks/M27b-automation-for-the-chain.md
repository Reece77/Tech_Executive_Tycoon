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

(by the M27b session, 2026-11-14; formulas.md §40.13 has the rules as built)

1. **Branch.** Built on `claude/m27b-chain-automation-ytaaeq`, the branch this cloud session may push to, in place of `m27b-chain-automation`.
2. **Docs PRs.** #55 (docs-v35b) merged with a merge commit after check and e2e went green. #52 (docs-v4-outline) was brought up to date with `main` here and went green; it was then merged by another session (14:53) before this one could, so nothing more was needed.
3. **What a subsidiary can automate.** Hiring and the seven chain areas (flag `subsidiary` in `automation.areas`). The seat rules (engineering, products, pricing, marketing, support, treasury) and the pitched moves (regions, research, cloud) stay the player's: a subsidiary has no executive seats, and 27.1's pitches are filed against the company whose seats pitch them. The Automation screen shows only a subsidiary's automatable areas.
4. **A subsidiary's CEO** is its leader as 29.4/31.4 already name it (`rival_ceo_id`). "Default owner of every area" is Automate everything ordering it first, subject to its energy like any owner (40.3); other areas go to the subsidiary's own leads.
5. **The mandate as guardrail.** Its capex limit (when set) caps each owner's money limit; a move naming a category or region outside the mandate becomes a proposal.
6. **Subsidiary proposals** are filed with the player (company id the player's, a `company_id` param naming the subsidiary) so they reach the inbox and the proposals list; approving one runs the action as the proposing owner (still on the subsidiary's staff), else its CEO, so it posts to the subsidiary's own books.
7. **Founder-only chain actions** (the group's mines, foundry contracts, lobbying, another group company's facilities and projects, a mine's development) are carried out in the founder's name, with the founder's energy restored after: the cost is the owner's workload. The chain modules are unchanged (the brief's "reads but does not change").
8. **Device cover.** The engine has no finished-goods stock (units are made and sold the same month), so "weeks of cover" is next month's supply (contracts plus the plants' share) over the shown demand (units plus those lost to the cap) × 52/12. An order brings it to 5 weeks (`order_weeks`, near the script's 1.2× headroom) for 24 months. There is no plant production-plan action to call, so plants are staffed and their spare capacity sold.
9. **Supply.** The gap is closed to the band's middle (0.8). Options rank group supply (a group mine routed at cost plus), then offtakes from the company's bloc, then everything else by displayed price; the traders' 12-month contract counts as outside the bloc. Offtakes are 3 years (the minimum). Wafer starts use the same band. `SignRefiningDeal` is not signed by the rule (a follow-up): no area need maps cleanly to a refinery's spot feed without reading the refining module's internals.
10. **Exploration** continues the fronts the player opened (desk studies) and does not start new fronts; its budget is counted as the area's committed decisions over the last 12 months. The grade guardrail is relative (× the commodity's median grade, default 0.5) because grades differ by orders of magnitude across commodities. The stage mistake ("the second-best stage") is a pre-feasibility study where a definitive one was right.
11. **Mines.** Safety is an index into mining's levels (default 1, "normal": the brief's "standard"). "Then contracts" is a guardrail, `contract_share` (default 0: with no group need everything sells at spot, as the scripts do).
12. **Fabs.** The margin guardrail is over the cash cost a start (fixed, materials, power and staff over starts run), not the fab card's full cost: with depreciation a new fab's full cost exceeded the slot price, so no contract would ever pass, while the spot slots that take the rest pay less than a contract.
13. **Government.** Lobbying spends the yearly budget's monthly rate split evenly over the regions the company sells in, for the player's company only (influence is the founder's, 32.5). A tool licence is applied for in each fab country; the action itself refuses where none is needed.
14. **Corporate development.** "Best target": an independent rival sharing a selling category, affordable from cash, ranked by customers in those categories per dollar of displayed value. Budget default 0 (off), as exploration. A bid is pitched once per target within `automation.repropose_months`.
15. **Headcount targets** are per unit and role (a plan needs a role); free to set, like an area's settings.
16. **Area settings** gained a yearly budget and per-area guardrails (`area_owner.budget_cents`, `area_owner.guardrails`), the defaults in `balance.yaml`.
17. **Chain targets' measurement** (my own targets; no earlier band moves): the arms fork from each seed's full_integrator game at January 2025 (turn 180, the ladder's "whole chain by year 15") and run to December 2039. In every arm the six seats are set to the arm's score (as 40.10's base hires score-15 holders); the automated arms add twelve senior leads (M27a's five and the chain's seven roles) and a CEO and plant manager in each subsidiary, Automate everything in every group company, and an exploration budget of $20M a year. The founder approves proposals whose central case is positive or absent, and pitches likewise. ARR is 12 × the group's last month's revenue (M23b).
18. **M27a's e2e flow (a)** counts 19 area rows now (the chain's seven appended); nothing else in it changed.
19. **Targets as measured** (`tools/m27b_targets.py`, 10 seeds, fork January 2025, to December 2039; run on this branch at 6532fbe's rules):

    | Target | Reading | Band | Result |
    | --- | --- | --- | --- |
    | (a) auto_15 / scripted median year-30 group ARR | 1.31 ($548B / $420B) | 0.85-1.2 | **miss (high), carried** |
    | (a) fewest owners in auto_15 | 9 | at least 8 | met |
    | (b) auto_8 / auto_15 median year-30 ARR | 0.95 | at most 0.8 | **miss, carried** |
    | (c) delegate grey routes and terminations | 0 (and the property tests) | 0 | met |
    | (d) proposals a month in auto_15 (median) | 1.0 | at most 3 | met |

    Per seed (year-30 ARR, $B, scripted / auto_15 / auto_8): 1: 457 / 646 / 639; 2: 406 / 613 / 509; 3: 412 / 517 / 668; 4: 330 / 0 (the board removed the founder in 2036) / 508; 5: 479 / 654 / 642; 6: 333 / 564 / 528; 7: 437 / 492 / 503; 8: 427 / 433 / 500; 9: 534 / 785 / 691; 10: 397 / 531 / 388. Logged mistakes: auto_15 48-95 a run, auto_8 131-311.

    **Why carried, not tuned.** Both automated arms run well ahead of the script, and close to each other. On seeds 2 and 4 the automated arms ended with 9-11 live products against the script's 6-7 (the CPO area's pitched new categories, approved on their central case) and with every device order sized to the demand the cap lost, which the script's renewals (1.2 × last month's units sold) never see. The software side is M27a's rules (40.10 target 1 already reads 1.18 over 5 years and compounds over 15); the chain's own mistakes (an order 20% short, a month late, the second-best supplier) correct themselves within a month or two, so score 8 against 15 moves a $500B group by about 5%. The keys this brief owns (`automation.*` cadence, the chain guardrails) would have to make the right rule under-serve demand, or move M27a's quality curve and its own targets 1-2, to land (a) and (b) in band; neither is a tuning of what M27b built. Recorded as misses for the product manager, with the targets' measurement unchanged. 40.10 targets 1 and 4 re-read in the branch's nightly (run 43610930568): `test_40_10_targets` passed.
20. **An earlier guard on the branch's nightly**: `test_m21_balance::test_38_5_targets` target 3 fails, and fails identically on `main`'s own nightly (run 43586223483, at m28-done): rule 3, the M28r fix's (lane: `tst/balance/m21.py`). Not added to `known_misses.py`.

## Follow-ups

1. **Refining deals** in the supply rule: a refinery's spot-bought input covered by `SignRefiningDeal` (needs a sim-side view of each plant's monthly feed need).
2. **Subsidiaries' seat and pitched areas**: subsidiaries have no seats; pitches inside one would need filing with the player (27.1 is per company).
3. **New exploration fronts**: the rule continues desk-study fronts the player opened; starting fronts for the group's needs (which region, which commodity) is a design question.
4. **A sim-side planning view**: the 12-month cover is computed twice (the API's planning view and the supply rule); one shared function would keep them from drifting.
5. **CLI**: `tst automation` and `tst automate` take no `--company` yet.
6. **Lobbying inside subsidiaries**: influence is the founder's (32.5), so a subsidiary's government area applies for licences but does not lobby.
