# M18: Prospecting and exploration (v3, lane B)

**Goal:** the hunt for the minerals under the tech industry. Each region has real geology; blocks hide deposits whose true size and grade are never shown. You spend through a pipeline (desk study, licence, survey, sampling, drilling, resource estimate, feasibility, permitting) and every stage narrows the estimate. Geologists make the difference. Communities protest and permits stall. At the end you hold a permitted project worth building (from M19) or selling.

**Spec sections:** §8 (value chain, prospecting) · **ADRs:** 0002, 0005, 0007 (hidden truths), 0013 (streams `geology` 48, `exploration` 49), 0015, 0019, 0020 · **Formulas:** `docs/formulas.md` §34 (all), with §32 (persona), §33 (price deck) · **Data:** `docs/v3-research/v3-data-dossier.md` §2, §6 · **Depends on:** M16 (`m16-done`) · **Lane:** B, alongside M17 (lane A)

## Lane

- Its own session and branch (`m18-exploration`). **Merge order: M18 merges second.** Before merging: merge `main` (with M17), re-parent migrations, switch feasibility studies from the stub to `commodity.deck`, regenerate golden snapshots once with both milestones' reasons in CHANGELOG, re-run every guard and both milestones' targets on the combined code.
- **M18 owns:** `geology.yaml`, new `backend/tst/sim/exploration/` (geology, blocks and deposits, the pipeline, estimates, permits, project sales), the `geologist` role and its skills, `cities.yaml` additions (Perth, Santiago, Johannesburg), `data/events/exploration.yaml`, and an **Exploration** screen (a region map with blocks and heat-map bands, licences, the pipeline per project, ranges, permits).
- **M18 must not edit:** M17's commodity, supplier and power files or code.
- **Until M17 merges:** code feasibility against M17's published `commodity.deck` interface on its branch, or a stub with the same signature returning dossier 2015–2025 medians; never copy M17's history file.
- **Shared files:** `balance.yaml` (add only `geology.*`, `exploration.*`), `docs/formulas.md` (notes in §34 only), `CHANGELOG.md`, `docs/data-dictionary.md`.
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Building and running mines (M19), refining (M20), gallium and germanium as by-products (M20), export controls (M22), rivals exploring actively (suppliers hold licences abstractly; active rival exploration is a follow-up).

## Sub-tasks (commit after each)

1. **Data and formula tests:** `geology.yaml` (prospectivity per region and commodity from dossier §2, each with its basis), `exploration.*` keys with stage costs and times (dossier §6, scaled to the game and labelled as assumptions), the `geologist` role and skills, the three cities, event templates; streams in ADR-0013; unit tests for the range rule and the estimate convergence arithmetic.
2. **Geology** (§34.1): blocks and hidden deposits at game start (also for Sandbox and scenario starts), suppliers' starting licences.
3. **The pipeline** (§34.2): each stage, its costs, time and geologist-months; drilling draws and running estimates; resource categories; feasibility with capex, operating cost and NPV ranges at the price deck; permitting by region; selling a project. **Property tests:** estimates' ranges contain the truth at their stated confidence (on 30 seeds); the ledger balances.
4. **Events** (§34.3): protests and permits as critical events with their choices (M24's persona hook), minor events.
5. **Hidden values** (§34.5): the differential test (two blocks with the same revealed results but different truths give identical responses through the API), and the hidden-value test extended to deposits.
6. **API, CLI, screens:** the Exploration screen; the geologist on People and Recruitment; projects on the Finance and Group screens. **CLI:** `tst geology --region`, `tst licence --block`, `tst survey|sample|drill --project [--holes]`, `tst feasibility --project --level`, `tst permit --project`, `tst sell-project --project`. Glossary entries.
7. **Balance, merge and e2e:** §34.6 targets printed and recorded; tune only `geology.*` and `exploration.*`. **Playwright:** (a) a desk study, a licence and a survey on a fixture; (b) drill 20 holes and watch the grade range narrow; (c) a protest event during permitting with its choices; (d) sell a project to a supplier. The merge steps above. Close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] No deposit truth reaches the API or a prompt (differential and hidden-value tests).
- [ ] Estimates contain the truth at their stated confidence (property test over 30 seeds).
- [ ] A company that never explores plays exactly as before.
- [ ] §34.6 targets met (printed, values recorded), on the combined code with M17.
- [ ] `make check` and CI `e2e` green; merged after M17 through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m18-done`.

## Manual check (Reece, after merge)

Form an exploration subsidiary, hire two geologists in Perth, desk-study lithium in Oceania and Latin America, and take one block all the way to a permit. How did it feel to watch the estimate narrow, and was the protest a real decision?

## Decisions made

Engineering and data decisions the spec, ADRs and brief did not settle (CLAUDE.md §9). Balance values are before → after, tuned only in `geology.*` and `exploration.*` (decision rule 1).

1. **Branch.** Built on `claude/m18-exploration-q21bxw`, the branch this cloud session may push (the brief's `m18-exploration`).
2. **No new skills.** The geologist's three skills are the existing `geology` (field geology) and `data`: geophysics and resource estimation read the mean of geology and data. Adding skills to `skills.yaml` would redraw every person in every game (ADR-0013) and break "a company that never explores plays exactly as before". The role is appended to `roles.yaml` (product function none).
3. **Mining cities** Perth, Santiago and Johannesburg are appended with talent weight 0, so "anywhere" and relocating candidates of every other role are drawn exactly as before; their geology and mining-engineering bonus applies to geologist searches there. Toronto gains the same bonus (it touches no other role's skills).
4. **Truth is stored, revealed results are stored, ranges are derived.** `exploration_block` holds the true_* fields (ADR-0007); each stage stores what it revealed (a reading, a sample centre and half-width, holes' assays, the estimate's and study's centres and half-widths). Everything the API shows is computed from those revealed numbers and public data only, so the differential test holds by construction; the indicative sale price uses typical depth and infrastructure, never the block's own.
5. **Estimate convergence by finite-population sampling.** With independent holes, `1/sqrt(n)` cannot give both ±15% at 20 holes and ±8% at 40. An ore body has `geology.cells` (66) drill positions, a hole samples one not yet drilled, and the true grade is their geometric mean, so the finite-population correction gives the brief's convergence while every range keeps its 90% confidence (property test, 30 seeds).
6. **Desk studies and surveys compound two skills** (noise × f_field × f_est); every estimate range uses one factor. Without this, target 2 stayed at 1.1–1.3×.
7. **Geologists' time:** desk studies and the geology stages (survey, sampling, drilling, estimate) each need a free geologist; feasibility studies and permitting do not (they occupied geologists for 12–18 months and licences lapsed unsurveyed).
8. **Stage costs and times, scaled to the game** (sub-task 1; tuned for target 3's $20–60M and 3–8 years): survey $1.5M, 6 months → $1M × region index, 4 months; sampling $2M, 6 → $1M, 3; estimate 3 → 2 months; feasibility $2M/$8M/$20M, 6/12/18 months → $1M/$4M/$8M, 4/8/12; holes $120k + $500/m → $90k + $350/m (about $90–350k with the region index). With the brief's own costs the scripted explorer spent a median $116–159M per permitted project over about 100 months.
9. **Other tuning:** `geology.deposit_rate` 0.16 → 0.08; new `geology.grade_scale` 1.0 → 0.7; `geology.size_lift` 1.0 → 2.0 (the most allowed; target 4); `geology.blocks_per_region` 40 → 60 (target 4: with 40, ties cost copper and lithium seeds); geology.yaml `hole_sd` × 1.35 (target 1, measured narrower than the target); Latin America's lithium prospectivity 0.45 → 0.35 (target 4); `exploration.skill_slope` 0.03 → 0.05 (target 2's "25–40% narrower" needs at least 0.037; 0.05 gives 39%); `desk.high_share` 0.2 → 0.1; `desk.noise_sd` 1.0 → 2.0; `survey.noise_sd` 1.0 → 1.5.
10. **Measuring target 2 (for review).** "Per dollar" is read per dollar of discovery spend (desk studies, licences, surveys, sampling, drilling, estimates: the dossier's "$111M per discovery" is exploration spend); the ratio per dollar of all spend, which also counts the definitive studies of what was found, is printed beside it. Target 3 is read for a team at skill 12, target 2 for teams of six geologists at 8 and 15; target 4 counts deposits whose true NPV at the deck is above zero (a tie counts for no region). The scripted explorer (`tst/balance/m18.py`) desk-studies twelve (region, commodity) pairs, licenses the four best "high" blocks of each, surveys them, samples anomalies, drills 20 holes where the sample's upper grade could pay, scopes, infills to 40 holes and goes straight to a definitive study when the scoping NPV midpoint is positive, then applies for the permit and answers protests with a benefit agreement.
11. **34.1's "roughly 1 in 25 surveyed blocks becomes feasible"** is a tuning aim, not a §34.6 target; at the brief's (scaled) costs, reaching it would push target 3's spend over $60M. The measured ratio is recorded with the targets.
12. **Sale prices** take `sale.share[stage]` of the NPV at the low end of the revealed ranges (the latest study's low NPV, else the low grade and tonnage with typical costs), so drilling that narrows the range raises the price; the buyer is the commodity's supplier based in the region, else its first, else the copper majors for tin, tantalum and quartz, which no M17 supplier produces.
13. **Who explores:** any company in the player's group (operating, holding or a subsidiary) once the group has reached stage 3; the founder acts for each. M16 has no action that founds a new subsidiary, so the manual check's "form an exploration subsidiary" has no button yet (follow-up 1).
14. **Protests** are queued at most one a company a month; the decision waits while one is open. Consult: $500k and 3 months. Benefit agreement: $3M, refusal chance and protest chance × 0.5. Push on: persona Ruthless +5 (M24's `raise_trait`), a 25% chance of an injunction ($1M, 6 months), +10 points of refusal chance per push. The event links to its project by (company, month shown).
15. **Minor events** (accident, bonanza intercept, dry streak) are inbox items, the accident with a fine and a month's pause; no choices.
16. **Account 6600_exploration** (expense) takes every exploration cost; a sale posts to `4930_gain_on_disposal` (exploration is expensed, so the book value is nil).
17. **Saves from before M18** get their geology at migration 0042, drawn as a new game of the same seed would draw it.
18. **M17 interface until it merges:** `tst/sim/exploration/m17.py` holds `deck(state, key, data, balance)` with M17's signature returning the dossier's 2015–2025 medians, and a list of M17's miners; it is the one module switched at the merge.
19. **Migrations:** M25 merged first with `0040_m25`; M18's `0042_m18` revises it, and is re-parented onto M17's migration at the merge.

## Follow-ups

1. **Found a new subsidiary** (an "exploration subsidiary" from scratch): M16 offers carve-outs and spin-offs of existing companies only. Exploration already works for any group company.
2. Rivals exploring actively (out of scope): suppliers hold licences abstractly.
3. Hiring for a subsidiary from the player's Recruitment screen (geologists are hired into the founder's company today).
4. The heat map could show the desk study's month and fade old bands.
5. The scripted explorer could choose blocks by expected value per dollar; it now takes high-band blocks in index order.
