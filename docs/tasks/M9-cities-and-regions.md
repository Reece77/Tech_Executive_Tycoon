# M9: Cities, offices and regions (lane A)

**Goal:** geography matters. A company has an HQ city, can lease offices in about 15 real tech hubs, and hires there at local wages and talent levels. It can launch its products region by region into new markets with their own size, prices and local rivals. v1's market becomes the home region, so expanding adds demand rather than splitting it.

**Spec sections:** §9 (regions), §5.4 (hiring) · **ADRs:** 0002, 0007, 0011 (named cities in v2), 0013 (stream `rival_region` id 22, reserved), 0017, 0019 · **Formulas:** `docs/formulas.md` §19 (all), with §2, §8, §11, §13.9 and §15 · **Wireframes:** `docs/wireframes.md` (M9 screens) and `docs/wireframes/source/Offices.dc.html`, `ProductRegions.dc.html` · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M8r (`m8r-done`)

## Lane

- **Lane A.** It runs at the same time as M10 (lane B) in its own Claude Code session, git worktree and branch (for example `git worktree add ../tst-m9 -b m9-cities-regions main`).
- **Merge order: M10 merges first.** Before merging M9:
  1. merge `main` (with M10) into this branch;
  2. re-parent M9's unmerged Alembic migrations onto `main`'s head. They aren't on `main`, so no save has applied them;
  3. call M10's `macro.adoption_factor(state, segment_key)` from the regional market code;
  4. regenerate golden snapshots, with both milestones' reasons in CHANGELOG;
  5. re-run `make balance` and the M8 and M10 guards on the combined code. If an M10 target moves, report it rather than tune M10's keys.
- **M9 owns:**
  - new `backend/tst/sim/geo/` (cities, offices, regional markets);
  - the market phase's regional code, recruitment's city logic, and the rivals' `enter_region` and startup region;
  - `backend/data/cities.yaml`, and the regional additions to `categories.yaml` and `incumbents.yaml`;
  - screens: Offices (new), the product profile's Regions panel, the market view's region picker, and recruitment's city filter.
- **M9 must not edit:** `backend/tst/sim/finance/`, `investors.yaml`, `climate.yaml`, `accounts.yaml`, or the Finance screen. Those belong to M10.
- **Shared files:**
  - `balance.yaml`: add only `office.*`, `markets.*` (regional keys), `hiring.relocation_cents` and `geo.*`;
  - `docs/formulas.md`: notes in §19 only;
  - `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **RNG:** stream `rival_region` (id 22), reserved in ADR-0013. Move its row into the main table. City draws for candidates stay in `people_gen`.

## Out of scope

Macro, debt and later rounds (M10). Regulation, tax, currencies and export controls (v3 geopolitics). Relocating existing staff between cities, beyond moving a unit to another office. Rival offices (rivals sell by region without offices).

## Sub-tasks (commit after each)

1. **Data and formula tests:**
   - `cities.yaml` (§19.1 table and growth multipliers), regional sizes and price indexes, regional incumbents and per-region shares (M3a steady-state method; record the values);
   - `office.*`, `markets.*`, `geo.*` keys;
   - every §19.9 worked example as a unit test.
2. **Cities, HQ and market rates** (§19.1):
   - HQ chosen at new game; migration for existing saves (HQ San Francisco; each person's home city is the first city of their region); market rates by work city.
   - **Test:** a San Francisco-HQ game with no offices plays exactly as before (golden seeds unchanged by this sub-task).
3. **Offices** (§19.2): lease and close actions, fit-out and penalty, `unit.office_id`, flexible space at the city rate, crowding morale, rent posting. Migration; data dictionary. Tests for each.
4. **Hiring by city** (§19.3): the search city, relocators, talent bonus, the "anywhere" option for remote units, the relocation fee. A seeded test of city draws and talent bonus (§19.8 target 4).
5. **Regional markets** (§19.4, §19.5, §19.6):
   - The home region unchanged; other regions' markets with their own RNG keys.
   - `launch_in_region` with localization cost, time and slowdown; regional prices; foreign awareness and local presence; seller capacity by region and neighbour; the cross-region output factor.
   - Regional incumbents; rivals' `enter_region`; startups' founding region on `rival_region`.
   - **Tests:** the home region replays v1 exactly; each reach rule; region entry by rivals.
6. **API, CLI and screens** (per the wireframes):
   - **Offices screen:** cities with indexes; offices with seats, members, cost per head and crowding; Lease and Close dialogs.
   - **Product profile:** a **Regions** panel (status, prices, customers and revenue by region, Launch in region dialog).
   - **Market view:** region picker.
   - **Recruitment:** city filter and the "anywhere" option.
   - **People table:** a City column.
   - **Supporting work:** glossary entries and driver breakdowns for new numbers; History entries for offices and launches.
   - **CLI:** `tst cities`, `tst offices`, `tst lease --city --seats`, `tst launch-region --product --region`.
7. **Balance, merge and e2e:**
   - The §19.8 targets, printed and recorded. Tune only M9's keys.
   - The merge steps above, after M10 is on `main`.
   - **Playwright:**
     - (a) lease a Berlin office, move a team there, and see costs and market rates change;
     - (b) launch a product in Europe and see it go live after 3 months;
     - (c) search for engineers in Bangalore and see city and salary on candidates.
   - **Close-out:** CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every §19.9 worked example passes as a test.
- [ ] A San Francisco-HQ company that never leases or launches abroad plays exactly as before M9 (home region replays v1; §19.8 target 1).
- [ ] Offices, crowding, market rates by city, hiring by city and relocation work as specified.
- [ ] Products launch per region with localization; reach follows the awareness and seller-region rules; rivals enter regions.
- [ ] §19.8 targets 2–5 met (printed, values recorded).
- [ ] Merged after M10, with migrations re-parented, golden snapshots regenerated on the combined code and both milestones' guards passing.
- [ ] `make check` green; `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m9-done`.

## Manual check (Reece, after merge)

On a stage-3 save, open an engineering office in Bangalore or Berlin and a sales office in London. Launch your main product in Europe, and compare costs, hiring and revenue after a year.

## Decisions made

Engineering and design gaps the spec left open (also in `docs/formulas.md` §19.10):

- **Storage.** Other regions' markets, launches and segments are new tables (`regional_market`, `product_region`, `regional_segment`); the home region keeps v1's rows and `market` keys, so its code path is v1's. M9's other values live in side tables (`company_hq`, `person_city`, `unit_office`, `search_city`, `candidate_relocation`, `office`), as M8's did, because migration 0013 loads the older tables through the current models.
- **Existing saves** (migration `0023_geo`): HQ San Francisco, home cities from regions, every other region's market grown to the save's turn, and v1 incumbents' Europe presence. The six regional incumbents come with new games only (M8's precedent for its incumbents).
- **Africa has no hub** in 19.1's table: its people's home city is London (`cities.yaml` `home_city_region`). Africa is still a market (reached from Europe's sellers at 50%, foreign awareness without presence).
- **`talent_weight`** per city (not in the spec) drives relocators' and "anywhere" candidates' cities; values roughly follow each hub's tech workforce.
- **Pay where you work, at v1's level.** A candidate's ask uses the multiplier of the city they would work in (the search's; their own for "anywhere"), so hires are not underpaid against their market rate on day one. Every city's multiplier is x `geo.pay_level` 0.876 for asks and all market rates (Reece, 2026-11-01): v1 drew 45% of candidates from cheaper regions, and without the calibration a San Francisco company's hiring cost 12-20% more, which broke v1 guards (the ten-year run bankrupt at month 27, funding diagnostic (c) 3/10). The 19.9 market-rate example becomes $30,222. Sub-task 2's "golden seeds unchanged" still could not hold: the regional incumbents shift product and company ids, and candidates are drawn by city.
- **The talent bonus** goes on every role skill after the CA target is drawn; target 4's "role-skill score" is CA / 10. All of a search's candidates get the search city's bonus.
- **People live where they work**: after every player action and phase 1's hires, office workers' home city becomes their office's city (a relocating hire pays `hiring.relocation_cents`; moving a unit to another office is free). Closing an office outside the HQ city makes its units remote, working from that city.
- **Office inheritance**: a unit's office is its own, else its parent's, up to flexible HQ space; the company root works in flexible space. Setting a unit's office sets its policy to office. Unit office changes cost `office.assign_energy` (2), as assigning a unit to a product.
- **Sellers by region at home too**: sales capacity in every region (home included) counts the player's sellers working there plus half its neighbour's. A company whose sellers all work in North America has v1's capacity. Rivals sell everywhere with full awareness (they have no offices).
- **Rivals' `enter_region`**: candidates come after v1's in the `rivals` draw order (v1's draws unchanged); weighted as `enter_segment`; rivals enter at once, without localization, at `p_ref x index x` their price factor. **A rival enters at most one region a year** (`geo.region_entry.cooldown_turns`, an M9 key): without it, region entries were a third of all rival actions and crowded out price cuts, pushes and poaching. Startups may enter regions too (including home, when founded abroad).
- **Regional incumbents' shares** (M3a steady-state method, served-share drift under 1.4 points over 24 months): SAP mid-market 1,400 bp, enterprise 2,100; Kaspersky SMB 1,900, mid-market 2,200; Tencent, Alibaba, Baidu and Infosys keep the table's shares (no rival in their region at the start).
- **Regional history**: `product_month` stays home-only; the Regions panel shows current customers and MRR by region, and the inbox notes launches and go-lives (`region_launched`, `region_live`), which History lists.
- **Offices screen** is `/game/:save/org/offices`, linked from Org; moving a unit is a control on that screen ("Move a unit … To … Move").
- **19.8 target 2's measure** follows balance-targets.md's rule that a removed founder or a bankrupt company scores 0; the last-month ARR ratio is printed beside it.
- **`rival_replay` test**: seed 7 no longer brings a rival approach in 24 months (rivals spend some months entering regions); seed 8 does, with a startup and the player's own poach.

## Guards before and after M9 (2026-11-01)

| Guard | Before M9 (main, M10 merged) | After M9 (combined) | Result |
| --- | --- | --- | --- |
| T1 do-nothing fails | 10/10 | 10/10 | pass |
| T2 wins per strategy | steady 10 | steady 8, bootstrap-frugal 2 | recorded xfail (stays) |
| T3 succeeds: bootstrap-frugal / steady / blitzscale | 7 / 10 / 4 of 10 | 8 / 10 / 5 of 10 | pass (blitzscale's xfail passes) |
| T4a-c seed, Series A, Series B | 4 and 1; 29 and 19; 37 on 8/10 | 4 and 1; 28.5 and 18; 36 on 9/10 | pass |
| T5 bankruptcy: steady easy/std/hard; blitzscale; bootstrap-frugal | 0/0/0%; 20%; 30% | 0/0/0%; 10%; 20% | pass |
| T6 tenure; leaving a year; first-year leavers | 21 months; 12%; 11% | 23 months; 11%; 10% | pass |
| T7 incumbents in business | 17/17 | 23/23 | pass |
| **T7 rival startups alive 5 years on (20-60%)** | 58% of 91 | **62% of 94** | **fail** |
| S2 worker-minutes, run alone | 12.4 | 18.8 | pass |
| M8 target 2 (seats) | 1.097 | 1.005 | recorded xfail (stays) |
| M8 target 3 (support) | 1.069 | 1.113 | recorded xfail, now passes |
| M8 target 5 (blitz Fintech) | pass | 1.317 | pass |
| **§20.5 target 2 (debt saves dilution, needs +5)** | +5.2 points | **+4.8 points** (bankruptcy +0) | **fail** |
| §20.5 target 3 | 90% | 90% | recorded xfail (stays) |
| §20.5 target 4; target 5 | 41/50, sd 0.171; 8/10 | 41/50, sd 0.171; 9/10 | pass |
| Ten-year run through the API (v1 acceptance) | pass | pass | pass |
| Funding diagnostics (a), (b), (c) | pass | pass | pass |
| M5 poaching felt, not crushing | pass | pass | pass |
| **M5 living market: share ratios; launches per category (needs 1.0)** | 0.56-1.65; 1.0 | 0.57-1.65; **0.925** | **fail** (ratios pass) |
| **Potential spotting gap (needs 3.0 PA points)** | 3.04 | **2.83** | **fail** |
| Executive at the default salary stays | xfail | xfail | recorded xfail (stays) |
| §19.8 target 2 (expansion, needs 1.4) | - | 7.014 (last-month ARR 3.44x) | pass |
| §19.8 target 3 | - | $119,331 against $304,020, 60.7% less; split x0.95 | pass |
| §19.8 target 4 (0.8-1.2) | - | 0.850 | pass |
| §19.8 target 5 | - | 10/10 seeds | pass |


M9 keys tuned to get here: `geo.pay_level` 0.876 (Reece); `geo.region_entry.unserved` 0.4 → 0.8 and `.span` 0.4 → 0.2 (rivals entered the served home market and squeezed v1 incumbents: Salesforce's SMB share fell to 0.47 of its start); `geo.region_entry.cooldown_turns` 12; and a product that sells only abroad comes home through `enter_region` only, not v1's per-segment `enter_segment`. Four guards that passed on main still miss after tuning M9 keys (bold above). Reece recorded them for M15 as `xfail(strict=False)` with their values and causes (balance-targets.md, M9) and approved the merge.

## Follow-ups

- **TOP PRIORITY for the next balance pass:** expansion is too strong (7.0x vs 1.4x target; home-only blitzscale fails every seed).
- **M15:** the four recorded misses: T7 startups alive (62%), §20.5 target 2 (+4.8), M5 launches per category (0.925), potential spotting gap (2.83).
- Levers for expansion (M15): `markets.foreign_awareness`, regional sizes, localization cost, `markets.presence_people`.
- `geo.pay_level` keeps v1's average pay; a later pass may prefer candidates from abroad who ask less than the search city's rate (and then feel underpaid), as v1 had.
- Rival offices and regional pools; rivals' localization time.
- A segment added at home after a regional launch is not added abroad automatically.
- Per-region product history (`product_month` by region) for charts.
- Hiring plans could carry a city (they use the plan unit's office city today).

