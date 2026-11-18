# M43a: Market sizes and saturation (v5, lane G; the first part of M43)

**Goal:** the game's economy stays believable for 60 years. Every market gets a ceiling tied to the size of the economy that buys from it, so growth fades instead of compounding forever. Each category's 2025 size is recalibrated against published figures. M37's runaway (an AI market hundreds of times world GDP by 2039, and money values near the integer limit by 2069) is closed.

**Formulas:** `docs/formulas.md` §54 (all), with §8, §21.4, §26.4, §37, §52 · **ADRs:** 0002, 0003 · **Research:** `docs/v5-research/market-sizes-dossier.md` · **Depends on:** M37 (`m37-done`) · **Lane:** G, alongside M39 (finishing) and the next v5 lanes

## The product manager's decision (2026-11-17)

M37 found the AI-models market at about $1.2–1.6T a year in 2025 (real-dollar equivalent) and $1,600–2,600T by 2039. This affects Reece's standard 30-year campaign, not only dynasty mode, so it is fixed now rather than in M43's final balance pass. History before 2026 **may change** where calibration needs it (§54.3), with every change listed.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m43a-markets` from `main`.
- **Merges after M39**: merge `main` after `m39-done`, then re-run everything on the combined code.
- **M43a owns:**
  - market growth and saturation (`tst/sim/markets/` demand growth; the era-boost application in `tst/sim/eras/` where it multiplies growth);
  - `categories.yaml`'s `growth_by_year` and starting sizes;
  - `markets.*` in `balance.yaml`;
  - the post-2025 GDP path in `macro_history.yaml` (seeded, from M37's continuation rules);
  - `tst/balance/m43a.py` (new);
  - `known_misses.py`'s `M37.money` entry (to close it).
- **M43a must not edit** any later lane's new code (M40, M42, M45 when they start). Merge `main` often.
- **CLAUDE.md §9's decision rules apply,** with §54.3's exception: history before 2026 may change, listed. Changing M8 target 4's band, or any earlier target's band, is still a stop-and-ask.

## Sub-tasks (commit after each)

1. **Research:** a 2025 published size (and 2010 and 2020 where available) for every category, with definition and source, from the dossier. Report the game's current 2025 sizes at real-dollar equivalent beside them, as a table in Decisions made.
2. **Ceilings and saturation** (§54.1):
   - `markets.ceiling_share.<category>` with sources;
   - the GDP path;
   - growth as `g × (1 − A / C)`;
   - era ceiling lifts;
   - long-run growth decaying to GDP plus a premium.
   - **Unit tests** of the formula. **Property test:** no market passes its ceiling.
3. **Calibration** (§54.2): recalibrate categories outside 0.5–2× their published 2025 size, keeping 2010 starts and curve shapes where possible. List every pre-2026 series that changes, with before and after values. Re-measure M8 target 4 and report it.
4. **Re-run everything** on the combined code: §54.4's targets, and every earlier guard (V1–V6, M8, M13b, M21–M23b, M28, M31–M35b, M36–M41).
   - Re-record M28's history fingerprint, M30's state cache and golden snapshots, with reasons.
   - Tune only `markets.*` and category growth (rule 1).
   - Apply rules 2–4 to anything that moves.
5. **Close-out:**
   - close `M37.money`, or report its reading;
   - CHANGELOG, data dictionary;
   - an economy note in `docs/economy-scale-audit.md` (what changed, and whether the audit's option C is still needed);
   - README index row.

## Acceptance criteria

- [ ] Every category has a sourced 2025 size and a ceiling; no market passes its ceiling in any year to 2069 (property test and target 1).
- [ ] §54.4 targets 1–6 printed and met, or carried with a recorded decision; `M37.money` closed.
- [ ] Every pre-2026 change is listed with before and after values; every earlier guard re-run, and the results reported under rules 1–4.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m43a-done`.

## Decisions made

1. **Research (sub-task 1).** `docs/v5-research/market-sizes-dossier.md` now carries a sourced 2025 size for every category (2010 and 2020 where found), with definitions and [V]/[D]/[M] tags. GDP figures are [M]: imf.org was blocked by the session's network. The game's 2025 sizes beside them are in decision 3's table and in `tools/m43a_targets.py`'s report. Categories pinned: `ai_models` = AI models and applications (Gartner AI application software $172B + GenAI models $14B = $186B; AI cloud infrastructure is `cloud_hosting` and the chip categories'); medical categories use M41's own sourced 2024 sizes (`medical.yaml`).
2. **Target 2 judges served revenue, not the addressable market (Reece, 2026-11-17).** §54.2 says "addressable", but published sizes are spending, which in the game is booked revenue (customers x price x units a month, plus medical consumables). Calibrating the addressable market would have cut AI's 2010 base by about 60x and AI-accelerator sales to $8B real (NVIDIA's game revenue about 30x lower). Reece chose served revenue. Ceilings still bound the addressable market (target 1, the property test). Target 1's technology share of world GDP is judged on served revenue too, the addressable sum printed beside it (49.9% at most: addressable counts every potential customer).
3. **Calibration (sub-task 3), seeds 1-4, full_integrator, real-dollar equivalent (game / 0.0849), $B.** Main's growth curves and 2010 starts are kept everywhere except servers. Most categories were in band on main; AI models (8.0x), cloud hosting (3.5x) and developer tools (3.7x) were too large, and the ceilings alone (shares chosen so they bind where addressable demand had run past the economy) bring them in. Servers were 0.08x: D0 x5 (30,000 / 30 -> 150,000 / 150) and growth 0.10 -> 0.15. Readings (median of seeds 1-4): SaaS 167 (0.56x of 299), dev tools 45 (1.81x of 25), consumer apps 227 (1.36x), cybersecurity 134 (0.63x), fintech 311 (0.82x), AI models 266 (1.43x of 186), cloud 335 (0.80x), devices 563 (0.75x), servers 276 (0.62x), mobile SoCs 40 (0.88x), server CPUs 28 (1.03x), AI accelerators 158 (0.69x), vehicles 350 (0.58x, M38's data), wearables 21 (1.52x), imaging 48 (1.09x), surgical robotics 6.1 (0.61x), implantables 23 (0.76x), SaMD 1.0 (0.64x). **Contract manufacturing 12 (0.02x of $648B EMS) is reported, not judged:** a spare-capacity market by design (economy-scale audit §4).
4. **Ceiling shares** (`markets.ceiling_share`, of regional GDP, on the addressable market): about 5x North America's 2025 addressable share on main's curves where served was in band (SaaS 8%, consumer apps 2.6%, cybersecurity 2.4%, fintech 7%, devices 5%, servers 6%, mobile SoCs 0.4%, server CPUs 1.2%, AI accelerators 30%, medical 0.05-0.5%, default 1%), so they barely bind in the developed regions before 2026; binding shares where main was too large (AI models 1.5%, cloud hosting 1.2%, developer tools 0.2%). Shares sit well above real spending shares because served revenue is 15-70% of addressable (4-7% for chips, whose design wins adopt slowly). `era_ceiling_lift` 0.10 an arrived era; GDP growth after 2025 3.5-6.5% nominal by region; long-run growth from 2030 decays to 4% + a premium (1% default; AI 4%, accelerators 3%, cloud and cybersecurity 2%) with a 4-year half-life.
5. **Pre-2026 changes (§54.3), seed 1, full_integrator, main -> M43a, real $B a year.** Every category's demand moves a little (saturation applies from 2010; a factor of 0.8-1.0 in the developed regions) and a lot where addressable demand had passed the region's economy (AI models in Africa and South Asia were 90-105% of their GDP in 2025). Medical served revenue changes in this table only because the measure now counts consumables; vehicles are unchanged (M38's data sets them).

| Category | addressable 2010 | 2015 | 2020 | 2025 | served 2010 | 2015 | 2020 | 2025 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ai_models | 5.6 → 5.6 | 25.5 → 25.1 | 284.5 → 238.1 | 23,826.9 → 2,022.5 | 1.2 → 1.2 | 4.1 → 4.1 | 29.8 → 27.2 | 1,494.6 → 267.4 |
| b2b_saas | 32.4 → 32.4 | 89.2 → 88.2 | 253.0 → 243.9 | 766.3 → 693.2 | 10.9 → 10.9 | 24.7 → 24.6 | 66.9 → 65.5 | 192.7 → 179.5 |
| chips_ai_accelerator | 2.6 → 2.7 | 8.9 → 9.5 | 184.1 → 188.9 | 13,475.8 → 8,359.5 | 0.9 → 0.9 | 1.2 → 1.3 | 5.6 → 5.7 | 256.0 → 191.0 |
| chips_mobile_soc | 11.9 → 11.9 | 22.4 → 21.4 | 42.4 → 38.2 | 81.5 → 67.4 | 3.8 → 3.8 | 8.6 → 8.4 | 19.3 → 17.9 | 46.7 → 40.3 |
| chips_server_cpu | 6.1 → 6.2 | 20.3 → 21.2 | 81.2 → 79.1 | 378.1 → 281.3 | 2.6 → 2.6 | 3.4 → 3.7 | 5.8 → 5.7 | 30.6 → 28.0 |
| cloud_hosting | 105.2 → 101.7 | 452.8 → 316.6 | 2,067.9 → 672.6 | 10,177.9 → 1,052.2 | 26.5 → 26.4 | 90.6 → 76.2 | 375.6 → 193.0 | 1,465.2 → 343.9 |
| consumer_apps | 8.1 → 8.1 | 42.0 → 41.3 | 165.0 → 153.8 | 811.6 → 603.3 | 2.7 → 2.7 | 16.0 → 15.8 | 62.9 → 59.8 | 278.9 → 225.9 |
| contract_manufacturing | 9.1 → 9.1 | 15.5 → 14.9 | 26.5 → 24.4 | 45.6 → 39.7 | 3.1 → 3.1 | 4.8 → 4.7 | 8.0 → 7.6 | 13.8 → 12.5 |
| cybersecurity | 37.6 → 37.4 | 81.6 → 79.2 | 198.1 → 181.9 | 543.3 → 443.4 | 14.1 → 14.1 | 27.0 → 26.7 | 57.6 → 55.2 | 153.7 → 135.3 |
| dev_tools | 12.2 → 12.0 | 42.4 → 34.8 | 155.9 → 84.1 | 593.9 → 154.8 | 3.7 → 3.7 | 9.2 → 8.6 | 27.5 → 20.2 | 91.6 → 40.9 |
| devices | 109.8 → 109.3 | 298.3 → 283.1 | 569.2 → 509.4 | 1,101.5 → 910.4 | 53.4 → 53.4 | 182.4 → 176.1 | 389.7 → 357.7 | 684.6 → 574.2 |
| fintech | 38.4 → 38.4 | 117.9 → 115.8 | 490.3 → 454.7 | 1,868.2 → 1,458.3 | 12.5 → 12.5 | 27.7 → 27.5 | 90.3 → 87.1 | 378.6 → 320.4 |
| imaging | 28.1 → 27.9 | 33.0 → 32.0 | 38.9 → 36.8 | 45.9 → 42.4 | 19.3 → 31.7 | 22.2 → 36.3 | 25.9 → 41.7 | 30.3 → 48.0 |
| implantables | 32.0 → 31.9 | 37.7 → 36.7 | 44.5 → 42.3 | 52.4 → 48.9 | 20.9 → 20.9 | 21.8 → 21.6 | 24.9 → 24.4 | 25.4 → 20.4 |
| samd | 0.1 → 0.1 | 0.2 → 0.2 | 1.3 → 1.3 | 6.9 → 6.0 | 0.0 → 0.0 | 0.1 → 0.1 | 0.2 → 0.2 | 1.1 → 1.0 |
| servers | 26.3 → 137.4 | 44.6 → 287.1 | 76.3 → 590.8 | 131.6 → 1,182.5 | 9.6 → 48.2 | 13.6 → 74.4 | 21.6 → 139.4 | 36.2 → 276.9 |
| surgical_robotics | 0.5 → 0.5 | 1.0 → 1.0 | 2.2 → 2.0 | 4.5 → 3.8 | 0.3 → 1.6 | 0.4 → 2.1 | 0.7 → 3.6 | 1.2 → 6.1 |
| wearables_diagnostics | 0.1 → 0.1 | 0.3 → 0.3 | 0.7 → 0.6 | 1.4 → 1.2 | 0.1 → 2.3 | 0.2 → 5.1 | 0.5 → 10.9 | 1.0 → 21.2 |

6. **M8 target 4 re-measured:** AI home demand January 2024 / January 2010 = **184x** with saturation (band 100-400x: met). **Flag for the PM:** M11's §21.8 target 1 (359x +-10%, `tests/unit/test_research_eras.py`) measures the growth rates without saturation and still reads 343x (passes); in the running game the figure is now 184x, because AI's ceiling binds from about 2021. The guard and its band are unchanged.
7. **M37's dynasty mature growth raised (rule 1 and 2, M37's key):** `dynasty.markets.mature_growth` default 0.01 -> 0.02, AI models, cloud hosting and AI accelerators 0.015 -> 0.025, dev tools 0.03 and devices 0.025 (new entries); vehicles unchanged. M37 had lowered them from 0.03-0.05 only to fit int64; the ceilings now bound the books (largest balance 1.48e16 cents by 2069, 1/600 of the limit). At 0.01, target 3 read 0.1-0.97% for 16 categories. Nothing before 2040 changes.
8. **Target 3 prints, not judges, data-set markets:** vehicles' demand is car sales x an EV share at its S-curve cap (M38's `vehicles.yaml`, M37's continuation), with no growth rate for 54.1 to act on: 0.21% a year in the 2060s, carried as M38's.
9. **§54.4 readings (seeds 1-4, dynasty to 2069, `tools/m43a_targets.py`):** T1 no market past its ceiling in any year, technology served revenue at most 11.6% of world GDP (2039; addressable 49.9%): met. T2 met (decision 3). T3 every growing category at least 1% a year through the 2060s: met. T4 largest balance 1.48e16 cents (Other East Asia power generators' commodity revenue; IBM's was 6.07e18): met, `M37.money` closed. T5-T6: decision 10.

10. **Earlier guards (sub-task 4), open: stopped for the PM (CLAUDE.md §9, a guard rules 1-4 can't resolve).** CI on this branch, against main's own runs (main's nightly at `m41-done` fails only M32's stale fixture; main's weekly at `m37-done` fails only M30's turn-time guard, 587 ms):

    | Guard | Main | 5x ceilings, decay from 2030 (3516fd1) | 10x ceilings, decay from 2030 (22eb72e) |
    | --- | --- | --- | --- |
    | M13 §25.9 T2 (IPOs, >= 4 of 10 a strategy) | pass | steady 3 | blitzscale 1 |
    | M14b §29.7 T4 (rivalries 5-9) | pass | 10 | pass |
    | M22 §39.4 T2 (variant loss 5-15%) | pass | miss | miss |
    | M24 §32.7 T3 (blitzscale real >= 6) | pass | pass | 5 |
    | M36 §45.8 (an heir within 80% of the CEO arm) | pass | miss | miss |
    | V2 research_heavy wins <= 4 (weekly) | pass | 5 | not run |
    | V4.T1.1 platform_owner / devices_regions 0.90-1.40x (weekly) | pass | 0.88-0.89x | not run |
    | founder value: litho_bet wins <= 4 (weekly) | pass | 6 | not run |
    | M30 2039 month <= 500 ms (weekly) | 587 ms (miss) | 651 ms (6.6 workloads against 6.1) | not run |

    Loosening the ceilings (my keys, rule 2) moved the misses rather than closing them: every category's demand changes from 2010, so strategy outcomes that depend on absolute market sizes (IPO counts, wins, ratios between strategies selling to different markets) shift. With the 10x ceilings, target 1 needed the long-run decay to start in 2026 (cee9786: 13.8% of world GDP at most, all of targets 1-4 met); the guards have not been re-run on cee9786. Fixtures (golden, M30, M28, M32, M37 legacy) are recorded for 3516fd1 and stale since.

## Follow-ups

(filled in by the agent)
