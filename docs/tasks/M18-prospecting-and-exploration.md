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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
