# M42: Pharmaceuticals (v5, lane H)

**Goal:** the hardest science business in the game. The player discovers molecules (with its own AI models, if it has them) and takes them through preclinical work and Phase I–III trials, at historical odds and costs. It submits them through the health regulators M41 built, prices them by region, and lives through the generics cliff when exclusivity ends. Biologics plants, licensing and partnering, and twelve big-pharma rivals round it out.

**Formulas:** `docs/formulas.md` §55 (all), with §21, §28, §48, §50, §54 · **ADRs:** 0002, 0003, 0005, 0013 (stream `pharma` 67), 0020 · **Research:** `docs/v5-research/pharma-dossier.md` · **Depends on:** M41 (`m41-done`), M43a's market sizes for calibration · **Lane:** H, alongside M43a (lane G) and M40 (lane I)

## Reece's decisions

- **Pharmaceuticals, as realistic as medical devices** (2026-11-14).
- **M41's clinical mechanics approved as built** (2026-11-17), and M42 reuses them.
- **Reece reviews the clinical mechanics:** a one-page plain-language summary of the trial, approval, pricing and cliff rules goes in the pull request.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m42-pharma` from `main`.
- **Merges after M43a** (which changes market sizes). Then merge `main`, re-parent the migration, re-record fixtures with reasons, and re-run every guard.
- **M42 owns:**
  - new `backend/tst/sim/pharma/` (programmes, stages, readouts, AI discovery, submissions, exclusivity, demand, pricing, generics, plants, licensing);
  - `pharma.yaml` (new);
  - the pharma categories and the `drug_discovery` domain;
  - pharma-specific kinds in M41's regulator data;
  - the Pharma screens;
  - `tst/balance/m42.py` (new).
- **M42 must not edit:**
  - M43a's market-growth code and keys (size pharma's markets through M43a's mechanism once it lands, and merge `main` often);
  - M40's `space/`;
  - M41's `medical/` beyond reusing it through its interfaces.
- **Shared files:** `categories.yaml`, `regulation.yaml`, `chain_companies.yaml` and `incumbents.yaml`, `balance.yaml` (add `pharma.*`), `docs/formulas.md` (notes in §55 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** A company without pharma must play exactly as before.

## Out of scope

Vaccines' public-health deals beyond ordinary pricing; diagnostics (M41's); pharmacy retail; automating pharma decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `pharma.yaml` from the dossier (transition rates by area and stage, durations, costs per patient, exclusivity terms, generic erosion, pricing rules and the IRA's dates, patient populations by indication and region, rivals' portfolios, pipelines and expiries, contract manufacturers), with every value cited;
   - `pharma.*` keys and stream `pharma`;
   - migration and data dictionary.
2. **Molecules and the pipeline** (§55.1): programmes with hidden efficacy and safety, stages, costs, readouts, and the `drug_discovery` domain.
   - **Hidden-value test:** no true efficacy, safety or pending readout reaches the API or a prompt.
3. **AI-driven discovery** (§55.2).
4. **Approval and exclusivity** (§55.3) through M41's regulators.
5. **Revenue, pricing and the cliff** (§55.4).
   - **Property test:** books balance through approval, pricing changes and loss of exclusivity.
6. **Manufacturing, licensing and rivals** (§55.5).
7. **Screens:**
   - a **Pharma** screen (pipeline by stage and area, readouts, submissions, exclusivity clock, revenue by drug);
   - programme pages;
   - plant pages;
   - M29 unlocks;
   - glossary entries (Phase I/II/III, NDA/BLA, LOE, biosimilar, orphan, priority review);
   - Explain on a programme's chance to approval and its expected value (rNPV).
8. **API, CLI, e2e, balance and close-out:**
   - `tst pharma`;
   - **Playwright:** (a) start a programme with AI discovery and see its preclinical stage shortened, (b) a Phase II readout fails and the programme can be redesigned or stopped, (c) loss of exclusivity cuts a drug's revenue;
   - **a practice save** `pt-pharma`: an AI and devices company in 2026 with an ML research team and $5B cash;
   - **the one-page summary for Reece** in the pull request;
   - **§55.6 targets** printed and recorded, tuning only `pharma.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `pharma.yaml` cites a source for every value.
- [ ] A company without pharma plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No true efficacy, safety, pending readout or seeded rule reaches the API or a prompt (hidden-value test).
- [ ] §55.6 targets 2–6 printed and met, or carried with a recorded decision.
- [ ] The summary for Reece is in the pull request.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m42-done`.

## Decisions made

1. **The research** (`backend/data/pharma.yaml`, every value with its source, est. or A; a test checks every line with a number). The dossier's *(verify)* figures:
   - **Confirmed:** BIO 2021's rates (Phase I→II 52.0%, II→III 28.9%, III→NDA 57.8%, NDA→approval 90.6%, LOA 7.9%) and by area (oncology 5.3%, haematology 23.9%, metabolic 15.5%, infectious disease 13.2%, autoimmune 10.7%, neurology 5.9%, psychiatry 7.3%, cardiovascular 4.8%, rare disease 17.0%; each area's four rates multiply to its quoted LOA within 0.1 point), its durations (Phase II 3.6, III 3.3, review 1.3, 10.5 years from Phase I; Phase I 2.3 derived); Paul et al. 2010 (preclinical 69%); DiMasi 2016 ($2,558M); Wouters 2020 (median $985M, mean $1,336M; corrected 2022 to about $1,142M/$1,559M, est.); Moore 2018/2020 (pivotal median $19.0M; $41,413 a patient); Martin 2017 (Phase I/II/III medians $3.4M/$8.6M/$21.4M); Hatch-Waxman, BPCIA, orphan and EU 8+2+1 terms; FDA 2019 generic prices (-39% with one generic, -79% with four, over -95% with six); Humira $14.4B (2023), $9.0B (2024), $4.5B (2025); the IRA's first two rounds (22% and 44% net savings; prices from January 2026 and 2027); RAND 2024 (US 278% of the OECD); PDUFA VII's goals; FDA's 2024 approvals (50; 56% priority, 36% breakthrough, 14% accelerated); EMA 2023 (465 days); Jayatunga 2024 (Phase I 80-90%, Phase II about 40%); Isomorphic's 2024 deals; company revenues for 2010, 2024 and 2025 (FY sources in the YAML), with FX from the Federal Reserve (2010) and the IRS (2024-2025).
   - **Changed from the dossier:** urology (3.6%), not oncology, is BIO 2021's lowest area (oncology 5.3% is used); world prescription spending is about $1.8T at list (IQVIA 2025), not $1.5-1.6T; the FDA's erosion figures are by number of competitors, not "within a year"; EMA takes about 15 months, not a year; Eliquis's US LOE is April 2028 (EU 2026); BIOSECURE became law on 18 Dec 2025 (no companies named); NICE's threshold rises to GBP 25-35k from April 2026.
   - **Estimates and A:** indications' branded markets (sums of named drugs), list prices, standard-of-care weights and Medicare shares; area gross-to-net (around Drug Channels' 50%); region shares and price indexes; plants' capex, build months and capacity; CMOs' capacities; licensing terms by stage (calibrated on Isomorphic's deals); several 2024 BMS drug figures, AstraZeneca and Sanofi 2025, GSK's 2010 pharmaceuticals segment.
2. **Money at the game's scale.** §55 says "markets and money at the game's scale": game patients and all pharma money (sales, trials, plants, deals, fees) are real x `pharma.scale` (0.085, the devices, vehicles and robotics convention). M41 kept study costs real; with pharma's fixed costs (about $1B real an approval) against scaled sales, real costs would make every drug a loss, so trials scale too and a trial's cost stands in its real proportion to a drug's revenue. Trial patients are shown real.
3. **Drugs are programmes, not products.** The seven areas are pseudo-categories (family `pharma`, no market segments, as M31's `os` and M39's `mobility`), so the market engine, rivals and every per-category loop never see them; a generic product cannot be created in them. Demand is by indication and region (§55.4's formula, 55.8), booked by `tst.sim.pharma`, and joins the month's MRR so rankings, valuations and stages read it.
4. **Rivals.** Sixteen incumbents with no products (twelve big pharma, four generic makers; J&J's medicines arm is its own company beside M41's MedTech; AbbVie and Sandoz exist from 2010 as Abbott's and Novartis's businesses, Viatris as Mylan). Their revenue to 2025 is their reported revenue; after it their portfolio, cliffs, IRA cuts and seeded approvals. They make no product decisions and never fail (`pharma.rivals.holds`, as M38's and M39's makers). `IncumbentCompany.products` may be empty for a pharma rival only (a loader check). A payout share of revenue (dividends and buybacks) keeps their cash believable.
5. **Regulators.** Drug reviews go through four new `drug_regulators` (M34's record with kind `drugs`: FDA CDER/CBER, EMA, PMDA, NMPA) using M34's part-share helper and M41's reliance rule; M41's `health_regulators` are untouched (devices go through notified bodies in the EU, drugs through the EMA). Inspections and recalls reuse M41's data (medical.yaml's finding shares and quality multipliers, `medical.inspection.*`), and coverage by HTA reuses `medical.coverage.no_coverage_share`.
6. **Contract manufacturers are named counterparts, not companies.** Lonza, Samsung Biologics, WuXi Biologics and Catalent are pharma.yaml records with capacity by kind and a quality level; a drug not made in an own plant is made by the chosen CMO at `cmo_share` (cash leaves the game, as suppliers' does). Making them chain companies needs M28's world code to carry a non-commodity good (a follow-up).
7. **AI discovery** (55.2) is what the spec lists: more discovery slots, a shorter preclinical stage and a small logit lift at Phase I and II, plus a small lift to the efficacy prior; discovery itself is not shortened (an earlier draft's `discovery_cut` made it 40% cheaper and put target 5 at +55%; removed).
8. **Unlock** `pharma` is M29 system 32 (31 is M39's `mobility`): a programme or deal of the group's, or an AI or medical product at stage 3. Assets for licence are listed from then each January.
9. **API names** are prefixed `Rx` (`RxProgrammeOut`, ...): ten of the natural names (`PlantOut`, `DealOut`, `RangeOut`, ...) already existed, and FastAPI would have renamed both sides in the generated client. Fields named `chance` and `capacity` are forbidden API names (earlier milestones' hidden values), so the public ranges are `to_approval`, `shown` and `patient_years_k`.
10. **§55.6 targets** (`tools/m42_targets.py`, seeds 1-30), tuning only `pharma.*` (rule 1):

    | # | Target | Result (seeds 1-30) | Band |
    | --- | --- | --- | --- |
    | 1 | History holds | unit tests; golden and fixtures re-recorded (below) | identical for the player |
    | 2 | Phase I to approval | 11.6% (median) | 6-12% |
    | 2 | Oncology below the average | 48% below (6.0%) | 30%+ |
    | 3 | Phase I start to approval | 10.2 years (median) | 7-11 |
    | 4 | The cliff: revenue lost in 24 months | 88% (median) | 70%+ |
    | 5 | AI: approvals per dollar | +25% (median) | +10-40% |
    | 6 | Turn time | `make check-timing` | within guards |

    Tuning (before -> after): `readout.efficacy_weight` Phase I/II/III 0.3/0.8/0.8 -> 0.2/0.3/0.3 and `readout.safety_weight` 0.6/0.9/0.4/0.4 -> 0.4/0.5/0.2/0.2 (target 2: the hidden values' selection on survivors raised the cohort above 12% on seeds 11-30: 13.1%); `ai.transition_lift` 0.30 -> 0.15 and the efficacy and safety `ai_lift` 0.02 -> 0.01 (target 5: +55%); `approval.resubmit_factor` 0.5 -> 0.3 (BIO's submission rate already counts approvals after a complete response letter); `approval.accelerated_margin` added at 0.20 (oncology filed after Phase II too often at `priority_margin`). Target 2's cohort is equal across the seven areas, whose BIO rates average 10.4%; the remaining gap is selection on the hidden values. Target 4 is measured as revenue 24 months after exclusivity has ended in every region against the month before it ends in any (the US, the EU and elsewhere end on their own dates; measured on the US alone it reads the same 88%).
11. **CI fix after M39 (PR #84).** `main`'s `e2e` was red since PR #83 on `m25.spec.ts` (c): saving a mod validates every data file and the pure-Python YAML parser took 2.3-2.9 s locally, past the 5 s wait on CI. PR #82 (docs only) failed the same way. PR #84 parses with libyaml's C loader (identical documents, a test over every data file), 0.4-0.9 s a save; rule 5 (the slow step made faster, no wait loosened).

## Follow-ups

- **CMOs as chain companies** (decision 6): their books from 2026, the player's fees as their revenue, and BIOSECURE's designations once OMB lists companies (due December 2026).
- **Acquisitions of biotechs through §28:** today a biotech's programme is in-licensed or acquired outright as an asset; buying the company (its team and several assets) would use M14's M&A.
- **The EU pharma package** (agreed 2025-26, from about 2028): baseline market protection cut to 1 year, modulated orphan exclusivity, as a dated rule change.
- **Rival biosimilars and generics' entry dates by settlement** (Eliquis 2028, Humira's staggered 2023 launches) per drug, and rivals' own programmes visible as pipelines with readouts.
- **Pharma automation:** a delegate or division that runs trials and filings by policy (out of scope).
- **Existing saves** gain no pharma rivals or records (as M41's medical makers).
