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
11. **Entrants and relaunches.** Each January from 2040 a category with fewer than 4 active rivals (in business, a live product there, not the player's group) gets as many seeded entrants as it takes to reach 4 (first built as one a year: chips, cloud and devices, down to one or two rivals by 2039, stayed under 3 for years) (6-14 senior people, 24-48 months of their pay), launched at once at the category's median rival quality and selling first in North America. With chance 0.3, and a failed rival of the category, it carries that rival's brand ("<name> II"). Rival key `(3, category index, year, k)`.
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

17. **Tuning (rule 1, `dynasty.*` and M37's own eras only).** Readings on seeds 1-4 locally, then the nightly's ten:
    - *Target 3:* `nodes.density` [1.25, 1.40] -> [1.15, 1.25] and `nodes.wafer_mult` [1.08, 1.18] -> [1.03, 1.08] (a first attempt at [1.05, 1.15] went the wrong way: the band caps how far the cost falls). Cost per transistor 2069/2040 was 0.49-0.64 on seeds 1-4; now 0.53-0.88 on seeds 1-30 from the timeline alone, falling on every seed.
    - *Target 2 (rivals):* one entrant a year left chips, cloud and devices under 3 rivals for years (they had one or two in 2039): a January now founds as many as it takes. `rivals.min_active` 4 -> 3 and `rivals.entrant_staff` [6, 14] -> [4, 8] for turn time (below). Startup names run out (40 in names.yaml): entrants then take a pool name with a suffix ("Labs", "Systems", ...).
    - *The books must fit SQLite's integers.* The weekly 2069 save crashed: SQLite's SUM overflowed int64 on IBM's subscription revenue. AI models' leader already books about 2.3e16 cents ($230T) a year by 2040 on main's curves, and growing it at 2040s rates passes 9.2e18 cents by the mid-2050s. `markets.half_life_years` 6 -> 3, `markets.mature_growth` 0.03-0.05 -> 0.01-0.015, and the seven eras' growth boosts 0.10-0.25 -> 0.03-0.05. Seed 1's largest balance by 2069 went 1.2e19 -> 5.6e18 cents. The rest of that growth is adoption and share (IBM's regional customers keep ramping), not demand. A new reading, the largest ledger balance, must stay under two thirds of int64 (6.1e18).
18. **Turn time in dynasty years.** CI's weekly V6 jobs play their 2039 save's next months, now 2040 in dynasty mode. Main read 351-353 ms a month and a 4.4 s Holiday year (runner x1.20); the first branch run read 490-497 ms and 6.2 s (runner x1.36-1.42), so the Holiday missed M30's 6.0 s. Profiled locally on the same months with the dynasty rules switched off: dynasty months were 15-20% slower, spread across the turn, because of the larger world (the January entrants' companies, products and people). Separately, eras.yaml's seven new eras made the boost loops 39% longer in every month, before 2040 too. Fixes: the arrived eras are cached per state in eras.yaml order (identical sums: `research.eras.arrived`), and fewer, smaller entrants (decision 17). Locally the remaining gap is about 10% (median 448 ms against 395 ms); January's founding takes 0.13 s.

19. **Target 5 is carried: the 2069 median, and since M41 merged the save's size.** After merging main at `m41-done` the 2069 save reads **409 MB** (400 MB), its month 572 ms at x1.21 (6.8 workloads); it has no free pages, so the size is people's records (below), M41's medical world adding to them. CI's weekly-m37 builds a full_integrator dynasty save with a family to January 2069 (708 months) and plays its next ten months. The save is **397 MB** (<= 400 MB). A month's median is 718-749 ms on runners at x1.58-1.65, which is **6.5 workloads** (tests/calibration.py's unit; a 2039 month on main is 4.9). That is about 455 ms on the reference runner and 546 ms at CI's usual x1.2, so M30's 500 ms is not met; the worst month (788-820 ms) is inside the 1.0 s budget. Profiled at 2069 locally: no dynasty rule stands out. The cost is the 60-year world's people and segment lookups (`state.person`'s bisect over about 100k people, 108k calls a month; segment scans). M30's retention rows are not what makes the save large: people are (person_reveal and person_skill hold about 80% of a 2039 save). **PM ruling (2026-11-17): the 2069 turn time (546 ms at CI's usual x1.2) is carried to M45**, with these numbers; the save's size goes with it. `tests/integration/test_m37_perf.py` asserts the 1.0 s budget and prints the median and the size. After M41, weekly-m37 on d4fd03f (run 44092224791) landed on a x1.84 runner: median 948 ms, worst month **1,022 ms**, 7.3 workloads (about 515 ms and 555 ms on the reference runner), so on the slowest runners the 2069 worst month also goes over M30's 1.0 s budget; that is the same carried 2069 turn time (M45). The test was not changed.
20. **M30's guards on the V6 saves after 2039.** After decisions 17-18 and the two indexes (year tables, rival cooldowns), the plain V6 save passes on CI. The integrator save's 500 ms median depends on the runner it lands on. Run side by side (weekly runs 44057653845 on main and 44057659354 on the branch, the same 12 months from turn 360):

    | | median | runner | workloads a month | Holiday year |
    | --- | --- | --- | --- | --- |
    | main | 330 ms | x0.89 | 5.3 | 4.1 s (66 workloads) |
    | branch | 519 ms | x1.37 | 5.4 | 6.7 s (70 workloads) |

    Per unit of work the branch matches main within 2% (the Holiday year within 6%). In memory, main against the branch on the same months is within 5-8%: the dynasty years' entrants are a bigger world. On a x1.37 runner main's 5.3 workloads would read about 509 ms, also over 500 ms. Earlier branch runs read 531, 635 and 551 ms on x1.37-1.84 runners. The guard was not changed and no retries were added (rule 5). After the M41 merge (main at `m41-done` b0c844a, branch at d4fd03f; weekly runs 44092218791, 44096696384 on main and 44092224791, 44096702488 on the branch, dispatched together):

    | | median | runner | workloads a month | Holiday year | result |
    | --- | --- | --- | --- | --- | --- |
    | main | 393 ms | x0.95 | 5.9 | 4.8 s | pass |
    | main | 414 ms | x0.97 | 6.1 | 5.2 s | fail: worst month 1428 ms (1.0 s) |
    | main | 729 ms | x1.85 | 5.6 | 8.9 s | fail: median (500 ms) and Holiday (6.0 s) |
    | branch | 482 ms | x1.22 | 5.6 | 6.07 s | fail: Holiday (6.0 s) |
    | branch | 640 ms | x1.60 | 5.7 | 8.1 s | fail: median and Holiday |
    | branch | 790 ms | x1.85 | 6.1 | 9.9 s | fail: median and Holiday |

    Per unit of work the two match (main 5.6-6.1 workloads a month, the branch 5.6-6.1); on the same x1.85 runner class main reads 729 ms and the branch 790 ms, and main fails the median and Holiday guards there the same way. This is rule 3 under the ruling below (runner calibration in the table); the fix is the CI-fix lane's runner-adjusted time.

    **PM ruling (2026-11-17):** a slow-runner miss of this guard that main shows the same way side by side is rule 3. Both readings are recorded with the runner ratio and the milestone merges; the guard moves to runner-adjusted time in the CI-fix lane.

21. **§52.5 readings (final code, seeds 1-10, `tools/m37_targets.py`; nightly `tests/balance/test_m37_balance.py` green on CI).** Target 1: M30's nine runs to December 2039 identical to the digests before M37, month by month, dynasty mode off and on (18 of 18, locally and in the nightly). Target 2: eras arriving 2040-2069, median **7** (>= 4). Every category had 3+ active rivals in every decade on **10 of 10** seeds (9 of 10). The longest run of a commodity outside a third to three times its 2030s mean was **26** months (<= 60). Target 3: node gaps lengthen on every seed; cost per transistor 2069/2040 was **0.55-0.73** (>= 0.50, falling). Target 4: a succession by 2069 on **10 of 10** (9 of 10): 1-2 successions a seed, a death on 4. Target 5: decision 19 (carried: the median, and the save's size since M41). The largest ledger balance by 2069 was **6.07e18 cents**, inside two thirds of int64 (6.1e18) but with little headroom: decision 22.

22. **The 6.0e18-cents figure (PM ruling, 2026-11-17).** `tst.balance.m37.diagnosis` on seeds 1-10 (final code, the nightly's dynasty runs). Real dollars are cents / 100 / `economy_scale.money` (0.0849).
    - **What it is.** On every seed, company IBM (a 2010 incumbent; its arm is AI models), account `4000_revenue_subscriptions`: a **cumulative ledger total**, the subscription revenue booked since January 2010 (a credit balance, never closed to equity). It is not a balance of cash, a single year's revenue or a valuation. Its cash (`1000_cash`) is the next largest, the same order.
    - **December 2039 and December 2069.** 1.4e16-2.3e16 cents in December 2039 (seed 4: 2.31e16), 4.0e18-6.1e18 in December 2069 (seed 4: **6.07e18**, the largest), about 260x in 30 years.
    - **The AI market** (`market_revenue` x 12, every company's, cents a year):

      | | 2025 | 2039 | 2069 |
      | --- | --- | --- | --- |
      | AI models | 1.0e13-1.4e13 ($1.2T-1.6T real) | 1.4e16-2.2e16 ($1,600T-2,600T real) | 7.7e17-1.07e18 ($90,000T-126,000T real) |
      | top three | vehicles $25.1T, devices $17-19T, AI models or cloud hosting $1.2-1.6T | AI models, devices $550-600T, cloud hosting $130-250T | AI models, devices $2,400-2,900T, consumer apps $740-800T |

      So the scale problem starts before 2040: in 2039 the AI-models market alone is over ten times a real world economy (about $100T-150T), a 1,500-fold rise from 2025, and M37 may not change anything before 2040 (target 1). The dynasty years' 1.5% mature growth plus seven eras' boosts add about 50 times by 2069.
    - **Guard.** `tests/balance/test_m37_balance.py`'s money guard fails, naming the company and the account, when any value passes 1.0e18 cents in a dynasty run to 2069. It fails today, so it is the known miss `M37.money`, owned by **M43** (`backend/tst/balance/known_misses.py`; `docs/balance-targets.md`), bound 9.2e18 (int64). No balance key was changed and no integer type widened (the ruling).

## Follow-ups

- **M45 (performance; PM ruling 2026-11-17):** a 2069 month at about 6.5 workloads (decision 19). The 60-year world's people and segment lookups dominate: `state.person` is a bisect over about 100k people, called about 108k times a month; product and regional segments are scanned linearly. The save's size is people's records (person_reveal, person_skill), mostly departed strangers': thinning them would keep long saves well under 400 MB (409 MB at 2069 since M41).
- **M43 (balance), a real risk:** the largest ledger balance by 2069 reaches 6.07e18 cents of int64's 9.2e18 on seeds 1-10 (now the known miss `M37.money`, decision 22); a longer-lived or bigger game could overflow SQLite (every rival's cash is in its month-end snapshot). The largest AI incumbent books about $230T a year by 2040 on main's curves (base growth 25% a year to 2039), which forced dynasty-years growth down to 1-1.5% to keep the books inside SQLite's int64 (decision 17). Damping the 2030s would let dynasty years grow more.
- **Mortality beyond the head:** the partner, children and the adviser have no mortality draw (decision 12); a family member's death needs a status on `FamilyMember` (M36's model).
- **M38's vehicles past 2025:** car sales and subsidy steps hold their last values (the audit, decision 16). Dynasty years may want a continuation; M37 may not edit `vehicles/`.
- **Rival leaders' personalities** change the company's personality type only; successors' own traits do not yet steer the rival's decisions beyond it.
- **Chain companies' leaders** keep M28's monthly CEO changes (named characters); they have no ages.
- **Hall of Fame:** the December 2039 and 2069 summaries reuse the game-over screen with the legacy and the dynasty score. A Hall of Fame entry written at the end, with a "Dynasty" column for 2069 games, is not built.
