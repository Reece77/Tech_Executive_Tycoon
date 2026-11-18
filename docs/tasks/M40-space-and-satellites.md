# M40: Space and satellites (v5, lane I)

**Goal:** the player can go to orbit. It builds launch vehicles, with reusability as a long R&D path that cuts the cost per kg. It builds satellites and constellations on its own chips, and sells satellite broadband, then direct-to-device service, region by region under licences. It's capital-heavy and launches fail, with SpaceX, Blue Origin, Rocket Lab, CASC, OneWeb and Kuiper as rivals.

**Formulas:** `docs/formulas.md` §56 (all), with §21, §22, §26, §39, §46, §54 · **ADRs:** 0002, 0003, 0013 (stream `space` 68), 0020 · **Research:** `docs/v5-research/space-dossier.md` · **Depends on:** M32 (power), M43a's market sizes for calibration · **Lane:** I, alongside M43a (lane G) and M42 (lane H)

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m40-space` from `main`.
- **Merges after M43a and M42.** Then merge `main`, re-parent the migration, re-record fixtures with reasons, and re-run every guard.
- **M40 owns:**
  - new `backend/tst/sim/space/` (vehicles, launches, failures, reusability, satellites, constellations, coverage, broadband, direct-to-device, licences);
  - `space.yaml` (new);
  - the `launch`, `satellite_broadband` and Earth-observation categories;
  - the satellite-plant and launch-site facility kinds;
  - the `reusability` domain;
  - the Space screens;
  - `tst/balance/m40.py` (new).
- **M40 must not edit:** M43a's market-growth code and keys (size space markets through M43a's mechanism, and merge `main` often); M42's `pharma/`.
- **Shared files:** `categories.yaml`, `tech_frontier.yaml`, `chain_companies.yaml` and `incumbents.yaml`, `balance.yaml` (add `space.*`), `docs/formulas.md` (notes in §56 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** A company without space must play exactly as before.

## Out of scope

Defence and government contracts (M44); crewed spaceflight and tourism (follow-up); space mining (follow-up); automating space decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `space.yaml` from the dossier (cost per kg by vehicle and year, launches a year by provider, reuse milestones, early failure rates, Starlink's satellites and subscribers by year, OneWeb, Kuiper, direct-to-device dates, market sizes), with every value cited;
   - `space.*` keys and stream `space`;
   - migration and data dictionary.
2. **Launch** (§56.1): vehicles, cadence, the reusability domain, failures (a critical event with the player's own satellites aboard), launch sites.
   - **Hidden-value test:** no failure draw reaches the API or a prompt.
3. **Satellites and constellations** (§56.2): satellite plants, shells, coverage, replacements, debris rules.
4. **Connectivity and services** (§56.3): broadband subscribers with terminals and licences, capacity and congestion, direct-to-device from its era, Earth observation; rivals.
   - **Property test:** books balance through launches, losses with insurance, and subscriptions.
5. **Screens:**
   - a **Space** screen (vehicles, launches, cost per kg, constellations and coverage maps, subscribers by region, licences);
   - M29 unlocks;
   - glossary entries (LEO, cost per kg, reusability, constellation, shell, direct-to-device);
   - Explain on a launch's price and a constellation's payback.
6. **API, CLI, e2e, balance and close-out:**
   - `tst space`;
   - **Playwright:** (a) design a vehicle and launch a satellite, (b) a launch failure with own satellites aboard arrives as a critical event, (c) broadband coverage opens a region once a shell is complete;
   - **a practice save** `pt-space`: a chip and devices group in 2026 with $20B cash and a reusability research lead;
   - **§56.4 targets** printed and recorded, tuning only `space.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `space.yaml` cites a source for every value.
- [ ] A company without space plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No launch-failure draw, seeded policy or rival plan reaches the API or a prompt (hidden-value test).
- [ ] §56.4 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m40-done`.

## Decisions made

1. **Workspace and branch (2026-11-18).** This session's own clone, on `m40-space` (the brief's name) from main. PR #82 (docs-m42-m40) waited hours on a stuck e2e run, so the branch was cut from main before it and committed for safety, then main was merged in once the M42 session merged #82 (the branch never carried the docs branch itself). M43a (`m43a-markets`), M42 and M45 run in their own branches; none of their files were edited. Shared files (categories.yaml, incumbents.yaml, tech_frontier.yaml, balance.yaml's `space.*`, formulas §56 notes, CHANGELOG, data dictionary, ADR-0013) keep both sides.
2. **Research.** This session could fetch only en.wikipedia.org (CSIS, the Space Foundation, SIA, the FCC and the companies' sites did not resolve), so space.yaml's S figures are Wikipedia's, quoted in the file's comments; R are recalled from a named source and A assumptions. Corrections to the dossier: the Space Shuttle's cost a kg is $1.642B a launch over the whole programme (2012 dollars) for 27.5 t, about $59,700 a kg (the dossier's $54,500 is CSIS's, R); Electron's list price over its payload is $25,000 a kg ($19,039 in the launch-market table); world orbital launch attempts were 74 (2010), 87 (2015), 114 (2020), 223 (2023), 261 (2024) and 330 (2025), not "about 259" in 2024; Starlink's May 2019 batch is "operational" on its page but "test satellites" on the launch list; Starlink had 8.9 million subscribers by December 2025; Kuiper is now Amazon Leo (November 2025). T-Satellite's July 2025 opening, the FCC's five-year disposal rule, OneWeb's and SES's subscriber counts, ULA's, Arianespace's, ISRO's and Rocket Lab's yearly launches are R or A (follow-up: re-check against the operators' filings and the FCC when reachable).
3. **Scale.** `space.scale` 0.085 = `robotics.scale` (M34's `economy_scale.money`), applied to launches, subscribers and constellations' shells (a shell is Starlink's first 1,584 x 0.085 = 135 satellites), at real prices in 2010 dollars, so a constellation costs about what a real one would at the game's scale.
4. **Markets through M43a's mechanism.** The three categories are ordinary markets (`growth_by_year` from space.yaml's history: launches 3% a year to 2016, 8% to 2019, 24% to 2025; broadband prospects 3%, 10% from 2019, 15% from 2021; then 10% and 6% a year), so M43a's ceilings and long-run fade apply to them once merged (`markets.ceiling_share.<category>` added at the merge, decision 18). Launch providers' customers are their share of the world's launches and operators' their subscribers x `space.scale`, pinned to December 2025 (`tst.sim.space.history`); no price before a provider's first launch, an operator's service or direct-to-device's opening (July 2025).
5. **Rivals.** Thirteen incumbents appended: SpaceX (Falcon 9 and Starlink lines), United Launch Alliance, Arianespace, Rocket Lab, CASC, ISRO, Blue Origin, Eutelsat OneWeb, Amazon Kuiper, Viasat, SES, Planet Labs and Maxar (Earth observation needs sellers, which the brief's list lacks). Kuiper is a company of its own ("Amazon Kuiper") because appending a line to Amazon Web Services would move every later product id (M39 decision 4's reason). They hold to the history before 2026 and are never failed for cash on it. The three categories are `family: space`: no startups, executive pitches or angel starts in them (a broadband startup with no satellites, and pitches that would change a game without space).
6. **Launch through the hardware production path.** A `launch` unit is a launch; a launch line's sales are capped by its launch sites (`launch_site` is its plant kind; a site unit flies `space.reuse.<level>.pad_rate` launches a month at its company's best level) and its cost of goods is its vehicle's flight cost (`unit_bom_cents`), not a BOM. Sold launches fly in the same month (fractions owed until whole), each with a failure draw; customers' payloads are their own insurers', so a failure moves no money but grounds the line (no sales, no flights) and costs brand.
7. **Reusability is lead plus programme time.** A level needs its lead in the new `reusability` domain **and** months since the company's programme began (the month its lead first rose): recovery 20 points and 30 months (SpaceX's landing attempts from 2013 to the December 2015 landing and March 2017 reflight), full reuse 45 points and 84 months. With 21.3's research, a large team reaches 45 points in under two years, so the brief's "at least 6 years" needs the time rule; it is shown on the Space screen with each level's requirement.
8. **Failure model.** `floor + (new_rate - floor) x 0.5 ** (flights / half_flights) x (1 + quality_k x (60 - quality) / 100)`: 40% on a first flight (Falcon 1 3 of 5, Astra 6 of 7, Firefly 4 of 7), toward 1% (Falcon 9 3 of 582, Soyuz-2 5 of 172). A bought launch flies at the floor. The API shows the model's chance as a +-30% range around the deterministic rate (no draw), with the record (flights, failures, reliability).
9. **Constellations are facility-like records.** Satellites are built in the group's satellite plants (or bought at x1.6), capitalized (1500), launched on an own line (its flight cost, pads left after customer launches) or bought (Falcon 9's price and payload), and serve in cohorts for their life, depreciated straight line (6700 / 1510). A failed launch writes its satellites off (6700) and the insurer pays 90% (4900) if insured (7% premium). Replacements are built and launched `replace_ahead_months` (9) before a cohort retires, into the shell that will be shortest; a shell opens its regions at 90% full. Disposal costs `deorbit_cents`; the seeded debris rule (1-6 years after 2026, hidden) doubles it and charges each satellite in orbit.
10. **Services gate through M31's `Effects`.** A broadband line sells in a region only where a complete shell covers it and a licence is granted (appeal 0 elsewhere); over capacity (Gbps x `subs_per_gbps`, split over served regions by addressable demand) its appeal falls with `congestion_k` and phase 9 trims subscribers to capacity. Direct-to-device needs a D2D constellation and the segment's opening: a new `Effects.segment_appeal` (product, region, segment), read in `run_markets`' segment loop beside M31's region appeal (one engine line; identity for every other product). A broadband line's base churn is x0.3 from 2026 (satellite ISPs lose 1.5-2% a month against the consumer segment's 6%). Earth observation sells everywhere once an EO constellation has 10 satellites up. A terminal's cost (space.yaml's by year, with the player's learning) is a cost of goods for each new subscriber; its price, set by the player, is revenue and is weighed by buyers over 24 months.
11. **Licences** are reviewed for the region's least months and then decided monthly with the region's approval chance (stream space (2, ...)); refused licences may be reapplied for. M22's relations are not read (follow-up).
12. **The failure event** (`launch_failure_payload`, `launch_failure_upper_stage`, trigger `space`, effect `space_step`): `review` halves the grounding left at $300,000, `rebuild` puts the lost satellites back on the ground at $400,000 each, `claim` contests the insurer ($200,000; 40% that the uninsured 10% is paid). Unanswered, review applies.
13. **Unlock ids.** Space is system 33 (32 is left for M42, which merges first; renumbered at the merge if M42 took 33).
14. **The constellation's cash flow** (target 3) is its line's booked revenue in every region less its subscribers' hosting (the category's `hosting_cents`, the ground segment and support, booked in phase 6), less satellites, launches, premiums, ground stations, disposal, debris fees and terminals' cost, plus terminal sales and insurance. Phase 5's flows carry only the home region, so revenue is read from the segments and new subscribers abroad are scaled from the home segment's.
15. **Tuning (rule 1, `space.*` only).** Target 3 missed at the first values (median payback 7.0 years, none never) and after correcting the cash flow to include hosting with `satellite.gbps_per_kg` 0.06 (80% never). Final: `satellite.gbps_per_kg` 0.08 (unchanged from the first value; Starlink v1.0 about 0.07), `constellation.ground_station_cents` $50,000 -> $500,000 a covered region a month (Starlink's 2025 costs of about $7B, revenue $11.4B less operating income $4.4B (S), about $600M a year at the game's scale). Readings below.
16. **Readings (56.4), seeds 1-10 (`tools/m40_targets.py`):**

| Target | Reading | Band | |
| --- | --- | --- | --- |
| 1 History holds | world launches, providers' launches, Starlink's subscribers, vehicles' prices and openings follow space.yaml to 2025 (`tests/unit/test_m40_space_data.py`); a company without space plays as before (decision 17) | the data | met |
| 2 Reuse changes everything | full reuse after **84 months** of programme on every seed (a team of output 12), **x6.2** cheaper a kg than the same design expendable (x5.0-6.2 across payloads 5-100 t, `test_full_reuse_is_far_cheaper_a_kg`) | >= 6 years, >= x5 | met |
| 3 Constellations are capital-heavy | four-shell constellation started Apr 2026-Sep 2030, own satellite plant, own new vehicle: median payback **12.8 years** (11.2-13.2 for those that pay back), **40%** never by December 2039 (starts from December 2028) | >= 8 years, >= 20% never | met |
| 4 Launches fail | the model's first 10 flights **21.2%** against **1.01%** after 50 (x21); flown records on these seeds 0-40% over the first ten | >= x3 | met |
| 5 Turn time | **270 ms** a turn (median, 2026-2035, these worlds with a constellation, four at once on 4 cores); `make check-timing` (decision 19) | 500 ms median | met |
17. **History holds (target 1).** Appending thirteen incumbents moves later companies' ids by 13, and the new markets, products and companies add lines to every fingerprint, so M28's history fingerprint and M30's state-hash fixture change. With the space companies' lines left out and later ids moved back (`tools/m40_history_diff.py`, M41's normalisation), seeds 1-4 to December 2025 equal main's fixture in prices, wafers, capacities and every company's books; events differ only in January "Top 50 by revenue" profile stories (seed 1: 2011 Kaspersky enters at #50 and Tesla at #47 rather than #44; 2025 Huawei Ascend enters at #32 and CoreWeave at #50 rather than #49), as M39 decision 5 and M42 found. A company without space plays as before: `test_a_company_without_space_plays_as_before`.

## Follow-ups

- Re-check space.yaml's R and A rows (ULA's, Arianespace's, ISRO's and Rocket Lab's yearly launches, CASC's share of China's, OneWeb's and SES's subscribers, T-Satellite's July 2025 opening, the FCC's disposal rule, satellite and terminal costs) against the operators' filings, CSIS, SIA and the FCC when those hosts are reachable.
- Licences reading M22's relations (`licence.relation_cut` is kept, unused); carrier partnerships as negotiated deals rather than a switch; a coverage map drawn on the world map rather than a table.
- Satellite failures in orbit; spare satellites per shell; constellations for Earth-observation tasking by region; satellites made from the group's own fab chips as an internal sale rather than a cost cut.
- Own launch lines sold to rivals' constellations (rival constellations are data-driven, not customers); rivals' vehicles reusing and failing by the same model after 2025.
- Defence and government contracts (M44); crewed flight, tourism and space mining; an automation area for space decisions.
- 56.4 target 3 reads 40% never: a latecomer competing with Starlink and Kuiper rarely pays back by 2039. If Reece wants constellations kinder, `constellation.ground_station_cents` is the lever (M43's v5 balance).
