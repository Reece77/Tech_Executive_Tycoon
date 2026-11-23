# M50: The 2008 start (v6, lane C)

**Goal:** the game can begin in January 2008, two years before the current start. The financial crisis hits the first year, and the App Store, Android and the cloud arrive on their dates. Airbnb, Uber, WhatsApp and Square are founded on their real dates. A 2010 game stays exactly as it is.

**Formulas:** `docs/formulas.md` §60 (all), with §20, §54 · **ADRs:** **0024 (new: start years before 2010)**, 0002, 0013 · **Research:** `docs/v6-research/start-2008-dossier.md` · **Depends on:** M43r (`m43rb-done`) · **Lane:** C, alongside M46 and M48

## Reece's decision (2026-11-22)

- **Start years: 2008 first,** then 2000, then 1995.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m50-start-2008` from `main`.
- **Merges after M46 and M48.** Then merge `main` and re-run every guard.
- **M50 owns:** `tst/sim/calendar.py` and the RNG factory for negative turns; the 2008–2009 entries in every data file; the new-game start-year choice; the start-turn field; `tst/balance/m50.py`; and a sentence in CLAUDE.md §7 about negative turns.
- **M50 must not edit** M46's balance keys or M48's meetings code.
- **CLAUDE.md §9's decision rules apply.** §60.3 target 1 (a 2010 game is byte-identical to `main` before M50) is the guard everything answers to.

## Sub-tasks (commit after each)

1. **ADR-0024 and the calendar:**
   - negative turns, the save's start turn, RNG streams for negative turns;
   - every place that assumes turn 0 is the start (audit: list them in Decisions made, then fix each);
   - the migration, the data dictionary, CLAUDE.md §7's sentence.
   - **Test:** a 2010 game is byte-identical (golden snapshots and the M30 state cache).
2. **Research and data:** 2008–2009 for every series, from the dossier, with every value cited, at the game's scale. The loader rejects gaps.
3. **The crisis and the platforms** (§60.2): macro, venture climate, rates and credit; app stores, Android and the cloud on their dates; rivals at 2008 values and new ones on their founding dates; eras, nodes, commodities and power.
4. **The new game:** a start-year choice (2008 or 2010) on the new-game screen, CLI (`--start-year`) and sandbox; scenarios keep their own years.
5. **API, e2e, balance and close-out:**
   - **Playwright:** start in 2008, play through Q4 2008, and see the venture climate freeze;
   - a practice save `pt-2008`: a garage start in January 2008;
   - **§60.3 targets** printed, tuning only the 2008–2009 data's calibration;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] A 2010 game is byte-identical to `main` before M50 (golden snapshots, every state cache and every guard).
- [ ] Every data series covers 2008–2009 with a cited source; the loader rejects gaps.
- [ ] §60.3 targets 2–4 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m50-done`.

## Manual check (Reece, after merge)

Start a new game in January 2008. Try to raise a seed round in late 2008, and see whether you survive to 2010.

## Decisions made

1. **Negative turns and RNG (ADR-0024 1-3).** `calendar.START_YEARS = (2008, 2010)`, `HISTORY_START_YEAR = 2008`, `HISTORY_START_TURN = -24`, `start_turn_of(year)`. `RngFactory.stream` takes a negative turn as spawn key `2**32 + |turn|` (`rng.turn_key`); turns from 0 enter as before, so every 2010 draw is unchanged, and no reachable turn (a dynasty game ends at 719) meets a negative key.
2. **Where the start is recorded.** A 2008 campaign has `state.mode = GameMode(kind="campaign", start_turn=-24)`; a 2010 campaign keeps `mode = None`, so its state is unchanged. `modes.models.world_start_turn(mode)` is the world's first month: -24 for any game begun before 2010 (a 2008 campaign, or a Sandbox in 2008-2009, which is built on the 2008 world and played to its year), else 0. Migration `0066_m50` adds `save_meta.start_turn` (default 0) so the saves list can show a start without decoding the mode; nothing else widens (SQLite turn columns already take negatives).
3. **Campaign end.** A standard campaign is 360 turns from its start: a 2008 game reaches its standard end after December 2037 (`dynasty.mode.standard_end_turn`); continuing in dynasty mode runs to December 2069, and the dynasty systems still begin in January 2040.
4. **A 2010 game reads nothing from before 2010.** Several readers interpolate (vehicles', robotics', space's and pharma's mid-year convention reads half a year back; components and foundry capacity interpolate between anchors; "the year before" reaches 2009 in 2010's months). The rule `calendar.from_2010(points, at)`: a read at or after January 2010 ignores 2008-2009 entries (the boundary is the fractional year 2009.5, between December 2009's and January 2010's mid-year reads; pharma reads plain years, boundary 2010.0). Applied in `power.config.interp`, `vehicles.config.interp` and `RivalCarsDef.share_at`, `pharma.data.series_at` and `rivals.key_drug_b`, `facilities.config.GoodHistory.index_at`, `fabs.nodes.history_capacity`, `world.config.supply_at`, `markets.saturation._listed` (GDP), `equipment.config.year_series`; and `vehicles.cells.history_cumulative_gwh` sums 2010-2025 as its definition says. Found by diffing a 2010 game's full state against `main` month by month: the first runs differed from turn 0 (vehicles', robotics' and space's mid-year reads, a component index's float at the 2008-2010 segment's end), then from January 2026 (the cells' cumulative history); golden snapshots and M30's state cache now pass unchanged. Consequence: in a 2008 game a mid-year series steps once at January 2010 (from interpolating 2009-2010 to reading 2010 alone); small, and the price of byte identity.
5. **Data series (ADR-0024 4).** `tst/history_coverage.py` walks every parsed data file: a year-keyed mapping, month-keyed mapping or list of `[month, ...]` rows that reaches back to 2010 must start by 2008 (January 2008 for months), and an annual series (2010 and 2011 both listed) must list 2008 and 2009. Series that begin after 2010 are later facts and need nothing. Demand growth before 2010 has one source, each category's new `early_growth` (2008, 2009; may be negative: servers and contract manufacturing shrank in 2009), so `growth_by_year` and eras.yaml's `base_growth` are exempt and `research.eras.base_growth` reads `early_growth` before 2010. 329 series were filled (data agents per file group; every value tagged S/V/D/R/A with its source, as each file's convention).
6. **Markets in 2008.** `addressable_at` for a negative turn divides D0 by each earlier month's growth (`early_growth`), so a 2008 world reaches D0 in January 2010 if nothing else moves. `expected_features` before 2010 runs back geometrically at 2010's own yearly ratio, F0 x (F0 / F_exp(12))^(-t/12) (the line F0 + dF t goes below zero). The research baseline runs back at 2008-2009's `per_year`, floored at 0.
7. **Incumbents at 2008 values.** `IncumbentProduct.early_scale {2008: x}`: its January 2008 customers are x times its January 2010 customers (from revenue or users then against 2010's, R from filings); without one a product keeps its share of the smaller 2008 market. `launched: [y, m]`: GitHub (2008-04), Evernote (2008-06), Snapdragon (2008-11), FarmVille (2009-06), Galaxy (2009-06) join that month with no customers; Windows Azure (2010-02) joins in January 2010 with its share, exactly as a 2010 game has it (`rivals.launches.incumbent_launches`, at the end of the month before). Every incumbent company exists from the start (ids stay by file position). A company whose products all launch later opens with `rivals.prelaunch_cash_months` (36) months of its key people's costs (otherwise it has no revenue, so no cash, and fails before launching).
8. **New companies on their dates.** `EntrantDef.early`: Square's real founding (February 2009) for a world begun before it; a 2010 game keeps March 2010. Appended entrants Airbnb (2008-08), Groupon (2008-11), WhatsApp (2009-02), Uber (2009-03) and Tiny Speck (2009-06), all consumer apps; a 2010 game never reaches their months.
9. **The crisis.** macro_history's climate before 2010 is monthly (D from MoneyTree's quarterly dollars against 2010's quarter): 1.05 to August 2008, 0.95 in September, then falling to the first quarter of 2009 and recovering to 0.88 by December 2009. Tuned under decision rule 1 for target 2 (the brief's own 2008-2009 calibration): October 2008-June 2009 from 0.75, 0.62, 0.55, 0.50, 0.48, 0.48, 0.52, 0.56, 0.60 to 0.72, 0.58, 0.52, 0.48, 0.46, 0.46, 0.50, 0.54, 0.58 (expected seed term sheets 38.9% fewer than 2010's, then 42.2%). Fed funds and Michigan sentiment are FRED's monthly values (their 2010 rows equal the file's).
10. **The compute index before 2010** continues back at `default_change` (1/0.85 a year); its base year's change stays 0 by definition, so 2010's macro months are unchanged.
11. **Platforms.** A store with no `store_opened` ("before 2010"), an open-source base and the historical standards count from the world's first month (0 in a 2010 game, as before). The App Store (2008-07) and Android Market (2008-10) already carried their real months.
12. **Prompts.** The LLM system prompts' "began in January 2010" says January 2008 for a 2008 campaign (`modes.models.began_in`); a 2010 game's text is unchanged.
13. **Sandbox** offers 2008-2025 (`sandbox.years`): 2008 and 2009 are built on the 2008 world.

### Audit: places that assumed turn 0 is the start (sub-task 1)

Found by a sweep of `tst/` and by playing a 2008 game; each fixed as listed (2010 behaviour unchanged unless said):

| Where | Assumption | Fix |
| --- | --- | --- |
| `sim/rng.py` stream | turn < 0 raised | negative-turn spawn key |
| `sim/setup.py` new_game | START_TURN 0 | `start_year`, mode records the start |
| `db/repository.py` create_save, replay payload, dynasty mode | always turn 0; dynasty replaced the mode | `start_year` (payload only when not 2010), dynasty keeps the start |
| `sim/dynasty/mode.py`, `api/campaign_views.py` | end December 2039 | 360 turns from the start |
| `sim/finance/macro.py` last_history_turn | (last - first + 1) x 12 - 1 | from the calendar |
| `sim/data_models.py` MacroHistory, ComputeIndexFile.of | yearly climate; index flat before 2010 | monthly climate years; index runs back |
| `sim/commodities/commodity.py`, `config.py` value_at, years check, supplier window | 0 <= turn; years from 2010; no `from` = turn 0 | from HISTORY_START_TURN |
| `sim/facilities/config.py`, `goods.py` | first point 2010-01; 0 <= turn; first year turns 0-11 | first point 2008-01; 2008-2009 yearly change against a year before |
| `sim/geopolitics/config.py` tension_history | starts 2010-01 | starts 2008-01 |
| `sim/mining/risk.py` rival capacity path, event window | range(turn + 1) (IndexError before 2010) | a 2008 path from -24; from 2010 as before |
| `sim/equipment/queue.py` catch_up, december_orders | turn == 0 is the new game | the world's first month |
| `sim/platforms/data.py`, `config.py` | None store = turn 0; open source max(0); standards started 0 | the world's first month |
| `sim/products/formulas.py` expected_features | max(turn, 0) | geometric back |
| `sim/products/setup.py` addressable_at | range(turn) empty before 0 | divides back |
| `sim/research/levels.py` accrued | baseline held at 2010 | runs back |
| `sim/vehicles/config.py` launch, share_at | None = January 2010; first year 2010 | None = before the earliest start; from_2010 |
| `sim/pharma/demand.py` blocked_until -1 | every turn below -1 blocked | -1 is "never recalled" |
| `sim/state.py` group windows | root window from -1 | from -25 |
| `sim/finance/statements.py` period_bounds, `api/finance_views.py`, `api/scaleup_views.py` | periods from turn 0 | from the world's first month |
| `api/breakdowns.py`, `api/commodity_views.py`, `api/facility_views.py`, `api/capital_views.py`, `api/geopolitics_views.py`, `api/vehicle_views.py`, `api/equipment_views.py`, `api/platform_views.py`, `api/routers/automation.py` | turn < 0 empty, max(0, ...), 2010 as the first year, ge=0 | the world's first month |
| `advisor/build.py` | since max(0, ...), turn < 0 | the world's first month |
| `advisor/prompt.py`, `events/context.py`, `events/coo.py` | "began in January 2010"; first-month date | `began_in`; the month's label |
| `db/conglomerate.py` | SQLite `turn / 12` truncates toward zero | shifted a century first |
| `db/backup.py`, `db/saves.py` | `turn-(\d{3,})` names | negative turns match |
| `db/history.py` prune, peaks | from month 0 | from the save's first month |
| `loader.py` platform shares, vehicle/robot shares, named shares | from 2010 / turn 0 | from 2008 |

Left as they are (checked, no effect on a 2008 game or by design): `exploration/draws.py` GEOLOGY_TURN 0 and `research/levels.py` stream(0, ...) (fixed seeds, not starts); `fabs/market.py:334` clamps a node's data price month to 2010 (a data month, not the game's); `regulation`, `government` and dynasty draws run from 2026 or 2040; `api/history_views.py` `closed_turn or 0` sorts (labels only); `db/history.py` prune_candidates skips while its cutoff is negative (catches up).

## Follow-ups

(filled in by the agent)
