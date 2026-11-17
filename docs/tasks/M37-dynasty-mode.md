# M37: Dynasty mode, the second 30 years (v5, lane E)

**Goal:** the game can continue to December 2069. A standard campaign ends in December 2039 with a summary, and the player can carry on. Every system's data continues past its last entry by seeded rules: new eras, slowing process nodes, maturing markets. Rival leaders age and hand over, new rivals keep arriving, and founders can die, which triggers M36's succession and estate tax. Nothing changes before 2040.

**Formulas:** `docs/formulas.md` §52 (all), with §9, §13, §21, §26.4, §32.6, §33, §38, §45, §46 · **ADRs:** 0002, 0013 (stream `dynasty` 65), 0019 · **Research:** `docs/v5-research/dynasty-dossier.md` · **Outline:** `docs/v5-outline.md` · **Depends on:** M35b (`m35b-done`), M36 · **Lane:** E, alongside M38 and M41

## Reece's decisions (2026-11-14)

- **An optional dynasty mode to 2069,** with seeded eras beyond history.
- **The player plays the heir** (M36).

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m37-dynasty` from `main`.
- **Merges after M38 and M41.** Then merge `main`, re-parent the migration, re-record the M30 fixture with `--update-state-cache` and the reason, and re-run every guard.
- **M37 owns:**
  - new `backend/tst/sim/dynasty/` (the mode, the standard end and its summary, continuation rules, rival leaders' ageing and succession, mortality);
  - the post-2039 sections of `eras.yaml`, `nodes.yaml` and `tech_frontier.yaml`;
  - `dynasty.*` in `balance.yaml`;
  - the campaign summary screen and the new-game setting;
  - `tst/balance/m37.py` (new).
- **M37 must not edit:** M38's `vehicles/` and M41's `medical/`. Their seeded post-2025 curves continue by their own rules; if one stops before 2069, note it for that milestone or M43.
- **Shared files:** `balance.yaml`, the data files above (append only), `docs/formulas.md` (notes in §52 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** §52.5 target 1 (nothing moves before 2040, with dynasty mode on or off) is the guard everything answers to.

## Out of scope

Sandbox play after 2069; a third generation of new industries (eras only); rewriting any system's rules for the long run beyond §52.2's continuations.

## Sub-tasks (commit after each)

1. **Data and the mode:**
   - the new-game setting and switching an existing save;
   - `dynasty.*` keys with comments;
   - the post-2039 eras with windows, and seeded node and frontier successors;
   - stream `dynasty`, migration and data dictionary.
   - **Test:** loader validation; a standard game is unchanged to December 2039.
2. **The standard end** (§52.1): the December 2039 summary (Hall of Fame, legacy and dynasty scores), and the choice to end or continue; December 2069's final summary and read-only browsing.
3. **Continuations** (§52.2) for every series that ends before 2069. First, audit every data series with an end date or a last seeded entry, as a table in Decisions made: series, last entry, continuation rule. Then implement each rule.
   - **Seeded test:** the same seed continues the same way.
4. **Rivals age** (§52.3): leaders with ages, retirement and successors (and personality changes), entrants after 2039, relaunching failed brands.
5. **The founder's lifetime** (§52.4): mortality from 75, M36's succession and estate tax at once, the family-head and no-family endings.
   - **Hidden-value test:** no mortality draw reaches the API or a prompt.
6. **Performance:** a 2069 turn on the `full_integrator` save under the 500 ms guard on the CI runner, and the save under 400 MB. Use M30's retention rules, extended to the longer game, with identical results to 2039.
7. **API, CLI, e2e, balance and close-out:**
   - `tst advance --until 2069-12`;
   - **Playwright:** (a) a standard game's December 2039 summary offers to continue, (b) a dynasty game shows a post-2039 era arriving;
   - **a practice save** `pt-dynasty`: a dynasty game in December 2039 with a founder aged 68, two adult heirs, and a group across chips, cloud and cars;
   - **§52.5 targets** printed and recorded, tuning only `dynasty.*` (rule 1);
   - long runs dispatched on GitHub (rule 7; a 720-turn run is about twice a 360-turn one);
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every game state and guard to December 2039 is identical to `main` before M37, with dynasty mode on or off (state-cache and golden checks).
- [ ] Every data series with an end before 2069 has a continuation rule (the audit table) and runs to 2069 without error on seeds 1–10.
- [ ] No mortality, succession or seeded-date draw reaches the API or a prompt before it happens (hidden-value test).
- [ ] §52.5 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m37-done`.

## Manual check (Reece, after merge)

Load `pt-dynasty`, read the 2039 summary, and continue. Play a decade: watch a new era arrive, a rival's founder hand over, and decide when to step back.

## Decisions made

Engineering and design gaps the spec, ADRs and brief left open (CLAUDE.md §9), decided and recorded here.

1. **Target 1 rules over §52.3's "from 2026".** §52.3 says rival leaders retire "from 2026"; the brief makes §52.5 target 1 (nothing moves before 2040, mode on or off) the guard everything answers to. Every M37 rule (leaders, entrants, mortality, eras, successor nodes, frontier and market continuations, carbon) starts in January of `dynasty.start_year` (2040). Before 2040, rival staff (their CEOs included) still age and retire by §10's existing rule, so leaders already hand over in the standard years.
2. **Rules are gated on the year, not the mode.** A game reaches 2040 only in dynasty mode (a standard campaign stops at its end) or as a Sandbox (no end before 2069), so the post-2039 rules run in any game from 2040, and a standard and a dynasty game are the same until then. Every game that reaches January 2070 ends (`dynasty_end`): no data continues past 2069 (sandbox after 2069 is out of scope).
3. **The standard end is derived, never stored.** A standard campaign with December 2039 played (turn 360) waits at its end: `advance_turn` and every action except the choice raise `CampaignEndError` (409, code `campaign_end`), and the API reports `game_state` `campaign_end` with `can_continue`. Storing a state change in the December 2039 month would have changed that month's state (target 1). Ending writes `campaign_end` with `ended_turn` 359; continuing writes the mode. Continue-until and Holiday stop there as at a game over.
4. **The mode is `GameMode.length`.** A dynasty campaign has a `GameMode(kind="campaign", length="dynasty")`; a standard campaign keeps no mode (every save before M37), so its state is untouched. Only a campaign has a dynasty mode; a standard game may switch any time before or at its end (a one-off).
5. **How target 1 is proved.** `tst/balance/m37.py` replays M30's nine state-cache runs to December 2039, mode off and on, with the fields M37 added left out of the digest (`GameState.dynasty`, `GameMode.length`; the dynasty campaign's mode read as None). Each month must equal the digests recorded before M37 (`tests/fixtures/m37_pre_2040_hashes.json`, main's `m30_state_hashes.json` when M37 branched). Nightly: `tests/balance/test_m37_balance.py`. Then M30's own fixture is re-recorded for the new field (CHANGELOG).
6. **Eras.** Seven eras appended to eras.yaml with windows 2040-2065 (fusion power, brain-computer interfaces, general-purpose humanoids, quantum advantage at scale, space industry, molecular manufacturing, ambient AI), drawn as §26.4's (stream `era_window`, their eras.yaml index): they are data with windows, not continuations. None can arrive early, be aimed at by rivals' research or shown before January 2040 (`levels.in_play`).
7. **Nodes: the successors follow A3, not A10.** The brief names A10 as the last node, but nodes.yaml's last future node is A3 (window 2037-06 to 2040-06). The six successors (A2, A1, Atomic-scale 1-4) follow A3: windows centred `gap_years` (3) after A3's midpoint, each gap x1.2, 24 months wide, never before January 2040, derived at load (`tst/sim/dynasty/nodes.py`). Their months, wafer price (x1.08-1.18), capital (x1.10-1.25) and density gain (1.25-1.40 for the first step, the gain's excess x0.85 a step) are drawn on stream `dynasty` at turn 0. No player, script or API is offered a successor before 2040 (`fabs.market.offered`: building, converting, the Fabs screen). Cost per transistor uses that density ladder (A3 = 1).
8. **Frontier and markets continue at load.** Each domain's baseline gains a rate for each decade from 2040 (the 2039 rate x0.85^k), and research budgets per researcher grow 3% a year from 2040. Each category's base growth gains a rate for each year from 2040 that decays toward `dynasty.markets.mature_growth` with a 6-year half-life; eras' boosts still add on top. Regions have no population series: regional demand is category growth x a fixed regional factor, so maturity carries into every region.
9. **Carbon.** From 2040 a priced region's carbon reverts to a seeded long-run level ($120-300/t, one uniform a region) at 15% of the log gap a year, with M32's own yearly noise and no more policy steps; the same draws as before, so earlier years are unchanged.
10. **Rival leaders.** A rival's leader is 29.4's CEO (the startup's founder, else the top-leadership key person), or the latest successor recorded. Each January from 2040 a leader retires with chance 0.06 x (age - 61) (0 below 62), plus 0.10 after a losing 12 months. The successor is an heir (25%: a new exec with the leader's surname), an insider (45%: the next in leadership, promoted) or an outside hire (30%). The rival's personality changes with chance 0.2 / 0.1 / 0.5. Names are kept in the record: a retired leader leaves the live state. Chain companies keep M28's own CEO changes (named characters, not people).
11. **Entrants and relaunches.** Each January from 2040 a category with fewer than 4 active rivals (in business, a live product there, not the player's group) gets a seeded entrant (6-14 senior people, 24-48 months of their pay), launched at once at the category's median rival quality and selling first in North America. With chance 0.3, and a failed rival of the category, it carries that rival's brand ("<name> II"). Rival key `(3, category index, year)`.
12. **Mortality.** Each January from 2040, the player's founder (the family head) from age 75: q = SSA 2021 male period life table (rounded, latest at or below the age) x 0.70 (wealth) x 0.85-1.25 (stress 0-100) x up to 0.90 (family time). The family members, the adviser and rival leaders have no mortality draw (the adviser retires at 80; rivals retire): a follow-up.
13. **A death hands over at once.** With a family the estate pays its tax at once (45.6) and the readiest eligible heir takes over at once, without the critical choice (`hand_to_heir(how="death")`: no adviser seat for the dead, who keep no seat). With no heir ready, the eldest living child, else the partner, becomes the head (a founder employment if they had none) and the board appoints a professional CEO (45.5's family-head mode). With no family, or no one left, the game ends `founder_died`. A founder without a family may retire in dynasty years (`retire_founder`: `founder_retired`).
14. **Scripts that play past 2039 continue.** M19's mine-life run (to 2049) and the weekly M30 and V6 timing tests and `tools/bench.py`, which play on from a 360-month save, now continue in dynasty mode first, as a player would (§9 rule 2; the game unchanged). M8's `growth_in(2040)` check and M15a's "the eras appended last" check pinned post-2039 behaviour M37 changes on purpose: each now checks its own milestone's years (2039, and M15a's five eras by position); nothing before 2040 is checked less.
15. **pt-dynasty is at the standard end.** The manual check reads the 2039 summary and then continues, so the practice save is full_integrator's group played to December 2039 in a standard campaign at its end, with a founder of 68, a partner and two adult heirs (the elder in the company), a car line and a cloud data centre with Cloud hosting added; continuing makes it the dynasty game.

16. **The continuation audit (sub-task 3).** Every data series with a last dated or seeded entry, and its rule to 2069. No engine reader stops or raises at turn 360-719 (the two that raise past their history, `commodities.config.value_at` and `facilities.config.index_at`, are guarded or clamped by every caller); the only fixed-length table, the foundries' capacity draws, covers 2026-2085.

    | Series | File | Last entry | Rule to 2069 |
    | --- | --- | --- | --- |
    | Eras | eras.yaml | practical quantum's window, 2034-2039 | **M37:** seven eras with windows 2040-2065 (decision 6) |
    | Base demand growth | eras.yaml `base_growth`, categories.yaml `growth`/`growth_by_year` | 2030 (AI models), else 2020-2021 or flat | **M37:** decays toward `dynasty.markets.mature_growth` from 2040 (decision 8); eras renew it |
    | Technology frontier | tech_frontier.yaml `per_year` | 2016 | **M37:** x0.85 a decade from 2040; budgets +3% a year (decision 8) |
    | Process nodes | nodes.yaml `nodes`, `future` | A3, window to 2040-06 | **M37:** six seeded successors (decision 7) |
    | Foundry capacity | nodes.yaml `foundries.capacity` | 2025 | seeded yearly growth (M21), drawn to 2085 |
    | EUV shipments | nodes.yaml `euv` | 2025 | +5% a year (M21), open-ended |
    | Equipment generations | equipment.yaml | 2025-2028 | M33's December rule and price growth, open-ended |
    | China's EUV-class tools | equipment.yaml `china_tools` | window to 2031 | drawn once (M33) |
    | Compute index, macro | compute_index.yaml, macro_history.yaml | 2024-2025 | seeded AR(1) and downturns (M10), clamped |
    | Commodity and power prices | commodities_history.yaml, power_history.yaml | 2025-12 | seeded AR(1) toward the long-run level with shocks (M17); target 2 reads them |
    | Components indexes | components_history.yaml | 2025-12 | seeded supply path (M12b) |
    | Carbon prices | power.yaml `carbon` | 2025 | M32's seeded path to 2039; **M37:** reverts to a seeded long-run level from 2040 (decision 9) |
    | Grid intensity, queues, plant costs, SMR era | power.yaml | 2023-2036 | decarbonise to 0, clamped queues, learning (M32) |
    | Platforms' shares, fees, developers | platforms.yaml | 2024-2025 | M31's model; developers +3% a year |
    | Regulators, designations, cases | regulation.yaml | 2025 | seeded strictness path and cases (M34, M35b) |
    | Tariffs, export controls, tension | tariffs.yaml, export_controls.yaml, countries.yaml | 2025 | last step holds; AR(1) tension; seeded rules (M22: all six in force eventually) |
    | Nationalisation | nationalization_history.yaml | 2025-12 | seeded monthly (M19) |
    | World supply, suppliers | chain_companies.yaml, suppliers.yaml | 2025 | the world's own capacity (M28) |
    | Incumbents, entrants | incumbents.yaml, entrants.yaml | 2021 | **M37:** seeded entrants and relaunches from 2040 (decision 11); rival leaders (decision 10) |
    | Vehicles (shares, sales, subsidies, tariffs) | vehicles.yaml | 2024-2028 | M38's seeded S-curve; car sales and steps hold their last value: **M38/M43 follow-up** (M37 may not edit `vehicles/`) |
    | Estate tax, M&A strictness | balance.yaml | 2026, 2020 | the last change holds (M36, M14) |
    | Regions' populations | (none) | — | no series: regional demand is category growth x a regional factor, so it matures with it |

## Follow-ups

(filled in by the agent)
