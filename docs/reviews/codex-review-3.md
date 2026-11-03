# Codex QA review 3 — m12a-done

Reviewed commit: `8bfd026afb5920b795f7c7972dc53f9730ce0f86`.
Annotated tag object: `ba35f28177bb7ca83e4b420b501bc2492b724146`.
Comparison: `m10d-done`, commit `024cd3f34a7a702cd921fe215cabd12fd0c5ceae` (tag object `c60bc8f4fba40bf76e6bedbcea3a4427c472327c`), to the reviewed commit: 37 commits, 161 changed files.

This was a read-only review. No source changes, commits, pushes, branches or remote comments were made. The resolved findings in reviews 1 and 2 are excluded, as are the balance misses and xfails recorded in `docs/balance-targets.md`.

Cloning failed because the shell could not connect to its configured proxy. The review instead used a GitHub-connector snapshot pinned to the full commit SHA. All 715 downloaded source/documentation files matched their Git blob hashes. The recursive tree metadata was also checked: all 63 directory trees reconstruct correctly, with root `c55f34a3e48650eea1928b0319f3274268ec48c8`, matching the commit's tree. This was a selected textual snapshot, not a local Git checkout or a complete dependency installation.

## Findings

No P1 was confirmed. There are six P2 findings and three P3 findings.

### 1. P2 — Licence failures reveal a rival's exact research lead without spending anything

**Location:** [backend/tst/sim/actions/research.py:175](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/sim/actions/research.py#L175), with the distinguishable errors at lines 156 and 179.

**What is wrong:** Licence validation compares arbitrary requested fractional points against the rival's true lead before checking cash or spending energy. Above the hidden limit it returns “more than the licence allows”; below the limit it can return the licence price/insufficient-cash error. Omitting the numeric limit from the first error does not hide it: these responses provide a binary-search oracle. The POST schema permits positive fractional points without a public increment or conservative range-based ceiling.

**Breaks:** CLAUDE.md §8, ADR-0007, and formulas §21.7/§21.10's requirement that rival leads remain ranges. The read view correctly uses a range-based limit, but the action bypasses that protection.

**Concrete scenario and evidence:** With the player's devices lead at 0, IBM's planted lead at `23.4567`, margin 10, and zero available cash, 32 direct calls to the unchanged `license_in` function narrowed IBM's true lead to `[23.456699997652322, 23.456700002076104]`. Every call failed: 21 with insufficient cash and 11 with the licence-limit error. No licence, cash movement, energy expenditure or turn advance was needed. The route forwards these actions and exposes their errors; this check executed the production action, not HTTP requests.

**Suggested fix:** Validate purchasable quantities against a ceiling derived solely from information already disclosed to the observer, consistently with the Research screen. Ensure requests outside that public offer cannot distinguish hidden limits through error wording or validation order. Add a differential POST test using two rival leads with identical displayed ranges; include failed, unaffordable and fractional requests. The current planted-value GET test at `backend/tests/integration/test_api_research.py:134` checks literal number strings and cannot detect this inference channel.

### 2. P2 — Research estimates retain hidden executive effects

**Location:** [backend/tst/sim/research/estimates.py:61](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/sim/research/estimates.py#L61); true modifiers originate at `backend/tst/sim/research/projects.py:85` and reach the response through `backend/tst/api/research_views.py:103`.

**What is wrong:** `lab` builds researcher output with `modifiers(..., estimate=False)`. `shown_lab` substitutes displayed researcher skills and known tags, but only rescales those two factors. The true CTO multiplier and any true COO-dependent support/layer factors survive in the estimated output. `gain_per_month` and potentially `months_to_era` therefore distinguish hidden executive skills.

**Breaks:** CLAUDE.md §8, ADR-0007, and formulas §21.10's displayed-skill estimate rule, together with §18.8's estimates-only executive effects.

**Concrete scenario and evidence:** In a stage-3 company with a six-person AI lab, two CTO variants had every displayed skill range identical. Changing the CTO's true skills from 12.0 to 12.1 changed the production `projects_out` response's `gain_per_month` from **3.07 to 3.08**. The researchers, knowledge, budgets and other state were unchanged. This was direct execution of the original view and simulation functions, without substituted view calculations.

**Suggested fix:** Build the displayed lab with estimated executive modifiers, rather than attempting to sanitize an output that already includes hidden factors. Add byte-equality checks for research responses under identical displayed knowledge and different true CTO/COO skills. This is a new M11 endpoint and estimate path; it does not repeat review 1's resolved leak in the older scale-up views. The existing executive noninterference test does not request `/research`.

### 3. P2 — Future stored component rows can become the Infrastructure screen's current values

**Location:** [backend/tst/db/state_io.py:879](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/db/state_io.py#L879), and [backend/tst/api/facility_views.py:48](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/api/facility_views.py#L48). The history query in `backend/tst/api/routers/facilities.py:52` also lacks an upper bound.

**What is wrong:** `_load_facilities` selects the greatest `supply_month.turn` in the database without restricting it to played months. After 2025, the view derives its visibility cutoff from those loaded rows, without bounding it by the save's current turn. A future row consequently authorizes its own disclosure. `goods.current` also accepts the loaded latest row, affecting quotations/contracts as well as display.

**Breaks:** Formulas §22.6/§22.9 and the M12a acceptance criterion “no API response shows a future value.”

**Concrete scenario and evidence:** At save turn **210** (July 2027), plant server and GPU `GoodMonth` records for turn **230** with index `7.654321` and allocation `0.4321`. Direct execution of `components_out` returned that index for both goods and included history points through turn 230. Source inspection shows how future SQL rows enter this state through the unbounded maximum. This is a planted-future-row failure, not a claim that ordinary turns currently generate future database rows; no SQL integration run was performed.

**Suggested fix:** Load only played supply months, bound the history query above as well as below, and enforce the current/last-played cutoff independently in the view and quote path. Add a persistence-level planted-future-row test. `test_no_future_index_after_2025` currently computes the next month separately and searches for its rounded value in an earlier response; it never inserts that future row, so it passes despite this disclosure path.

### 4. P2 — Overseas Cloud hosting customers escape outage churn

**Location:** [backend/tst/sim/facilities/outages.py:107](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/sim/facilities/outages.py#L107).

**What is wrong:** Own-product outage losses iterate both home and regional segments, but the separate Cloud hosting branch applies its additional churn only to `state.segments_of(cloud.id)`. It never processes `regional_segments_of(cloud.id)`, even though allocation explicitly sells capacity overseas.

**Breaks:** Formulas §22.5 and §22.9: Cloud customers churn at the outage multiplier in the outage month. There is no home-region exception.

**Concrete scenario and evidence:** A 500-CU European data centre serves 100 European SMB Cloud customers, using 400 CU, with zero home customers. Calling the unchanged `apply_outages` for that site leaves all **100 overseas customers** untouched and records **0.0 customers lost**. At SMB base churn 0.03 and the configured multiplier 3, the extra outage deduction should remove 6 customers from those 100 remaining customers under the implementation's immediate-extra-churn convention. The function still queues an outage event because the zero-customer home row becomes its target.

**Suggested fix:** Apply the Cloud outage branch to regional rows too, with the appropriate segment churn and complete loss accounting. Include a foreign-only Cloud product and a mixed home/foreign product in the outage tests. The current outage unit test covers an ordinary home-region product, so it cannot catch this omission.

### 5. P2 — A six-month rival research project pays its premium for only five months

**Location:** [backend/tst/sim/research/rivals.py:120](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/sim/research/rivals.py#L120), with payroll later in `backend/tst/sim/turn.py:230`.

**What is wrong:** In the final project month, phase 3 grants the sixth research increment and immediately restores the builder pool to its normal size. Phase 6 then computes payroll from that restored pool. The final research month is therefore free of the 10% builder-pool premium.

**Breaks:** Formulas §21.6 and §21.10: the six-month action incurs the larger builder pool while it runs.

**Concrete scenario and evidence:** Start Salesforce's research at turn 0 with `end_turn=5`. After the production research function runs in turns 0–5, the builder headcounts seen by the later cost phase are **1.1, 1.1, 1.1, 1.1, 1.1, 1.0** times the original pool. All six months still earn lead. The baseline final-month payroll follows directly from `monthly_cost_lines`, which prices the current pool headcount.

**Suggested fix:** Retain the premium through the final month's payroll, then restore the pool, or represent the research surcharge separately from pool headcount. Extend `backend/tests/unit/test_research_licensing.py:110` to assert six monthly cost premiums and their sum. That test currently checks the initial increase, six lead gains and eventual restoration, but never charges a month's payroll; it passes despite this timing defect.

### 6. P2 — The new AI research budget path rounds binary floating-point money

**Location:** [backend/tst/sim/research/projects.py:70](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/sim/research/projects.py#L70).

**What is wrong:** Multiplying integer budget cents by the floating AI index before `round` violates the money rule and can produce the wrong half-even cent. The resulting integer is then used in project needs and actual R&D postings; converting to an integer at the end does not repair the rounding.

**Breaks:** CLAUDE.md §2.3 and ADR-0003; this is M11's new research-budget calculation, not a repetition of the resolved event-raise or regional-price findings.

**Concrete scenario and evidence:** With the loaded AI budget of **600,000 cents** per researcher and a post-2025 AI index of `0.5000075`, `researcher_cost_cents` returns **300,005 cents**. Exact decimal arithmetic gives **300,004.5**, which half-even rounds to **300,004 cents**. The binary multiplication instead produces `300004.50000000006`. The production function was executed with that MacroMonth and compared against `Fraction('0.5000075')`.

**Suggested fix:** Use the existing exact-money helper on the budget and index before multiplication, then round once at the chosen budget boundary. Test half-cent cases against rational arithmetic. The current budget test derives its expected amount from `researcher_cost_cents` itself, so it cannot detect an incorrect result inside that helper.

### 7. P3 — Compute-specific consumers treat every generic facility as a data centre

**Location:** [backend/tst/sim/facilities/compute.py:171](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/sim/facilities/compute.py#L171), and `equivalent` at line 216. See also `backend/tst/sim/facilities/lifecycle.py:196` and `backend/tst/sim/facilities/outages.py:41`.

**What is wrong:** The shared lifecycle is generic, but its consumers assume every live facility produces a compute good. `live_facilities` returns all kinds; spare-capacity ranking with `good=None` admits them all; `equivalent` then looks up their output in `balance.compute.goods`. Cloud reliability and the data-centre outage roller likewise include every kind without dispatch or filtering.

**Breaks:** ADR-0020 §2–4 and the M12a “Design for v3” requirement that data centres be one kind of a facility model, with kind-specific behavior separated from the shared lifecycle.

**Concrete scenario and evidence:** Add a kind using the existing schema with unit `device` and output good `devices`, and give the company one live facility of that kind. Calling the original `compute.spare_by_region` raises **`KeyError: 'devices'`**. The Infrastructure view calls this path even when the company has not started selling Cloud hosting. Registering a non-compute facility therefore requires changes to existing compute consumers instead of adding its data and own rules. This is an extension-boundary finding; both currently shipped kinds produce compute.

**Suggested fix:** Filter compute allocation/reliability to kinds that supply compute goods and dispatch outage/output behavior by kind. Keep payment, depreciation and sale in the shared lifecycle. Add a minimal non-compute-kind contract test that runs the generic lifecycle and verifies it contributes neither Cloud capacity nor Cloud quality and does not crash the view.

### 8. P3 — New research and infrastructure views still select one player company internally

**Location:** [backend/tst/api/facility_views.py:312](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/api/facility_views.py#L312), [backend/tst/api/research_views.py:96](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/backend/tst/api/research_views.py#L96), and `backend/tst/sim/research/eras.py:116`.

**What is wrong:** The new view builders and era-news routing repeatedly select `state.player.id` rather than accepting the entity being viewed or using `player_companies` when addressing the player. Although the helper was added and is used by the Cloud phase loops, changing it to return a group would not update these paths.

**Breaks:** ADR-0020 §1 and both briefs' explicit requirement to accept `company_id` and use the group helper wherever “the player” is meant.

**Concrete failure scenario:** Extend the helper at M16 to return parent A and controlled company B, as the ADR anticipates. Give B a research project and a data centre. These views still return only A's projects, facilities and contracts, and their signatures offer no way to request B. If B causes an era, `era_news` compares it only with A, describes B as an external company and sends the note only to A. This is demonstrated by source tracing, not a claim that M12a already offers subsidiaries.

**Suggested fix:** Parameterize per-company view builders now; resolve the current single UI company at the route boundary. Route player/group news through `player_companies` and distinguish the causing legal entity from the observing company. Add two-company builder tests without implementing subsidiary gameplay.

### 9. P3 — The merged data dictionary assigns several tables the wrong columns

**Location:** [docs/data-dictionary.md:1144](https://github.com/Reece77/Tech_Executive_Tycoon/blob/8bfd026afb5920b795f7c7972dc53f9730ce0f86/docs/data-dictionary.md#L1144), with additional misplaced blocks at lines 1162, 1188 and 1216; the facility migration heading is wrong at line 1081.

**What is wrong:** The M11 and M12a additions were interleaved during the merge. `research_project` is followed by the supply-contract columns (`good`, `price_index`, `volume`, etc.); its own columns appear beneath `facility_outage`. `research_license` receives the outage columns, while the actual licence columns appear after “New accounts.” `supply_contract` has no column table beneath its heading. The facility migration is still named `0028_facilities`, although the applied chain is `0028_research` → `0029_facilities`.

**Breaks:** CLAUDE.md §6's requirement to keep the column-level dictionary current with migrations, and both briefs' instruction to preserve both lanes' dictionary additions.

**Concrete failure scenario:** A follow-on developer using the dictionary to query research projects looks for `good`, `volume` or `price_index`, none of which migration 0028 creates on that table. A migration audit looking for `0028_facilities` follows a nonexistent revision. The actual migration definitions and ORM columns inspected are consistent with one another; the confirmed defect is the reference document.

**Suggested fix:** Restore one uninterrupted column table per heading, move the displaced blocks to their proper tables, and update the facility migration name to `0029_facilities`. Check every listed column/type/nullability against migrations 0028/0029 and the ORM models after reordering.

## Verification and limits

Read `CLAUDE.md`, the ADR index and decisions, including 0002–0005, 0013 and its stable-key amendment, 0019 and 0020; formulas §21/§22 and their implementation notes; both milestone briefs; the prior reviews and resolutions; the balance exceptions; relevant wireframes; and the data dictionary. Inspected the research/facility modules, three new data files, hosting allocation and posting path, API schemas/views/routes, event-prompt allowlists, state synchronization, migrations, Infrastructure/Research screens, and associated unit, property, integration and browser tests.

The checks executed against the unchanged snapshot included:

- **Rules and RNG:** AST-scanned all 116 simulation Python files. No forbidden layer/I/O imports were found by that scan. Enumerated 27 literal RNG stream names with no duplicate literal-name call sites. Traced `rival_research`, `rivals`, rival hires and poaching to stable rival keys; project and facility streams use their entity IDs, and supply uses data-file indexes. The explicitly exempted `lead_reveal` key remains as documented. No additional unstable-rival-key defect was confirmed.
- **Determinism:** ran a combined 14-month scenario with an AI lab, an ordinary product, construction, facility completion and balanced postings under `PYTHONHASHSEED=1` and `917`. Canonical state/result hashes matched: `984992f296e7e054b0dcc00ef266e12d02e8e07729ac4ba97404c14366c8ae85`. This is a bounded scenario, not proof over every game state.
- **Worked formulas:** directly asserted §21.9's progress at leads 0/30, weighted quality cap, Transformers threshold, January-2016 baseline and licence price; §22.8's full/40%-use costs, reliability/outage example, capex at the example's supplied index, and allocation delay. These passed using the documented example coefficients, separately from the approved tuned coefficients. The GPU worked-example arithmetic supplies index 1.60; it does not establish that the history loader returns that index in July 2023.
- **Facility accounting:** executed a deterministic 120-case grid across both kinds, two sizes, three input indexes, full/short allocation and five sale timings, up to 90 months. Entries balanced; book values and depreciation stayed bounded; PP&E less accumulated depreciation reconciled with the live facility's book value and cleared on sale. This was a direct function grid, not a Hypothesis run.
- **Hidden information:** executed the paired CTO-view check, licence-error bisection and planted-future component-view check described above. Inspected event/text prompt allowlists; no additional direct research lead, project-output or future-macro disclosure through those prompt builders was confirmed. Facility reliability is explicitly public under §22.9 and was not treated as a leak merely because it derives from staff skills.
- **Persistence:** inspected the linear migration chain, table definitions, past-era backfill and state/ledger write paths. No new partial-commit path was confirmed by source inspection. Actual SQLite migration, rollback and concurrency tests were not executed.
- **Tests:** the identified gaps concern assertions that miss their stated behavior, particularly the GET-only rival-lead string guard, the future-index test that never persists a future row, and the rival research test that never charges payroll. Recorded balance exceptions were not recast as findings. Browser tests were read but not run.

`make check` was attempted with its environment/cache directed outside the snapshot and offline resolution enabled. It stopped before lint/tests because Alembic was unavailable in the package cache. The installed Python also reports `No module named pytest`; SQLAlchemy and Hypothesis are absent. The shell proxy failure prevented normal dependency setup. Therefore this report does **not** claim a pytest, typecheck, frontend, Playwright, SQL-backed API or full balance-suite pass. Direct Python checks used available Python 3.12, NumPy, Pydantic and YAML packages; API-view checks imported the original view functions successfully, without replacing their computations.

The source snapshot remained unchanged after verification. Harnesses and this report were written outside it.