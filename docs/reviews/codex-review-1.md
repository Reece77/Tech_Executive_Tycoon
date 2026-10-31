# Codex QA review 1 — m8-done

Reviewed commit: `f904478e965d4716b829ca1391b0342537590291`.
Annotated tag object: `d9903bb3848454c470c5f27b82e2ec96884c1ae0`.

Read AGENTS.md and CLAUDE.md first, followed by the ADR index, relevant ADRs, M8 brief, cited spec sections and formulas. No repository code, commits, remote branches, main or m7c branches were changed. This report is returned as an artifact rather than pushed to review/codex-1.

Git cloning failed because the workspace proxy was unavailable. I reviewed a snapshot downloaded through the GitHub connector at the exact commit above; all 365 downloaded files were checked against their Git blob hashes. This was not a local Git checkout.

## Findings, ranked by severity

### 1. P1 — Publishing the state cache after releasing the write lock can lose a committed action

**Location:** [backend/tst/db/repository.py:252](https://github.com/Reece77/Tech_Executive_Tycoon/blob/f904478e965d4716b829ca1391b0342537590291/backend/tst/db/repository.py#L252), with the caller at line 829 and lock release at line 349. Whole employment rows are merged in `backend/tst/db/state_io.py:690`.

**What is wrong:** `write_session` releases the save lock before `run_action` calls `remember`. `remember` associates its supplied state with the file's stamp at the time of that later call. Another request can commit in between. The older state can therefore be cached with the newer database's stamp, and `_recall` accepts it as current. The same pattern exists after turns and event writes.

**Failure scenario:** A renames a unit and commits, then pauses before `remember`. B moves an employee, commits, and caches B's state. A resumes and replaces that cache with A's older state, stamped with B's database version. C raises the employee's salary using that stale cached employment; merging the entire employment row restores the old unit as well. B's successful movement disappears although its decision-log record remains. Energy and cached ledger balances can also become stale.

**Evidence:** Executing the unchanged `_stamp`, `remember` and `_recall` functions with this publication order accepted A's old employee unit after the file had advanced to B's version. This was a controlled cache interleaving, not a live SQLite concurrency test.

**Required correction:** Publish/invalidate the cache as part of the same serialized write operation; do not stamp an older state with an independently observed later file version. Add a controlled two-writer regression.

### 2. P1 — Continue can return a retryable busy error after committing, so one click advances two months

**Location:** [backend/tst/db/repository.py:769](https://github.com/Reece77/Tech_Executive_Tycoon/blob/f904478e965d4716b829ca1391b0342537590291/backend/tst/db/repository.py#L769); recovery at lines 765–767. Automatic retry is in `frontend/src/hooks/api.ts:127` and configured globally in `frontend/src/main.tsx:73`.

**What is wrong:** `_play_turn` commits and releases its write lock before `write_pending` acquires another one. A competing save write can make that second acquisition raise `SaveBusyError`. The frontend retries all mutations with this error on the stated assumption that nothing changed. Here a month has already committed. On retry, `run_turn` finishes pending text and then plays another turn.

**Failure scenario:** Continue commits January. An overlapping inbox write acquires the lock before January's event text is written. Continue returns `save_busy`; its automatic retry writes the pending text and commits February too. The player loses the opportunity to act between those months. During Holiday, a post-commit event-service exception can also leave a committed month uncounted because `done` increments only after `run_turn` returns.

**Evidence:** Fault injection into the unchanged `run_turn` control flow produced `save_busy` with committed turn 1, followed by committed turn 2 on retry. Database operations were substituted in this harness; actual SQL rollback was not tested.

**Required correction:** Distinguish an initial refusal from a failure after a committed turn, and make retry/recovery resume the same operation rather than advance again. Test the post-commit failure boundary for Continue and Holiday.

### 3. P2 — A poached executive keeps their old company's seat and bonuses

**Location:** [backend/tst/sim/org/upkeep.py:70](https://github.com/Reece77/Tech_Executive_Tycoon/blob/f904478e965d4716b829ca1391b0342537590291/backend/tst/sim/org/upkeep.py#L70); `backend/tst/sim/org/executives.py:44`.

**What is wrong:** Departure cleanup uses the set of staff across all companies. Phase 1 calls `join_rivals` before cleanup, so a poached executive is already on the rival's staff and is not detached. `effect_of` likewise checks only for any employment, not employment by the seat's company.

**Failure scenario:** A CTO with score 14 accepts a rival's approach and finishes notice. They now work for company 2, but company 1 still lists them as CTO, blocks a replacement appointment, and receives their +5% output/quality-cap effect instead of the vacancy penalty. Similar company-membership checks affect unit leaders and hiring-plan owners.

**Evidence:** Direct execution of `end_notices → join_rivals → detach_departed` returned employer `2`, player CTO holder `2`, effect `0.5`, and no executive-departure note.

**Required correction:** Check membership in the relevant company, including when deriving seat effects. Add a seat-holder poaching regression; firing alone does not cover this path.

### 4. P2 — Support and layer-tax responses disclose the COO's true effect

**Location:** [backend/tst/api/scaleup_views.py:120](https://github.com/Reece77/Tech_Executive_Tycoon/blob/f904478e965d4716b829ca1391b0342537590291/backend/tst/api/scaleup_views.py#L120), used at lines 135 and 161–170; the Overview support tile repeats it at lines 330–337.

**What is wrong:** These responses use `ex.k_coo`, derived from the holder's true skills. They expose numerical support penalties and layer-tax percentages rather than estimates based on revealed ranges. With coverage and tax coefficients known, these percentages constrain the hidden COO effect and score. This bypasses the estimates-only seat rule in §18.8.

**Failure scenario:** A player appoints a poorly scouted COO and reads the support penalty. In a 41-person central pool with one support employee, true scores 11.00 and 11.12 produced identical displayed COO skill ranges and displayed score 10.7, but returned penalties of −8.9% and −8.8%. The response distinguishes hidden values that the revealed information cannot distinguish.

**Evidence:** Direct execution of the view logic also returned a −5.1% support penalty and a 1.6% layer tax for planted true score 17.3456, while the seat card's displayed estimate implied a different effect. View execution isolated imports requiring unavailable database dependencies; this was not an HTTP integration run.

**Test gap:** `backend/tests/integration/test_api_scaleup.py:141` appoints only a CFO and checks literal substrings. It never exercises an occupied COO, deep division or under-covered pool. Rounded transformations of a planted value also evade its string list.

**Required correction:** Derive explanatory seat-related percentages from displayed estimates and label them accordingly. Compare responses for states with identical displayed knowledge but different hidden values.

### 5. P2 — Price previews omit the CRO modifier on the proposed price

**Location:** [backend/tst/api/product_views.py:488](https://github.com/Reece77/Tech_Executive_Tycoon/blob/f904478e965d4716b829ca1391b0342537590291/backend/tst/api/product_views.py#L488), contrasted with line 497.

**What is wrong:** The proposed price score uses the unmodified reference price, while the current appeal uses `pricing_power`. Actual sales also apply CRO pricing power in sales-led segments. The two sides of the preview therefore use different formulas. The displayed current price score also omits the modifier.

**Failure scenario:** At stage 3, with a score-14 CRO and a mid-market product priced at its $800 reference price, previewing the unchanged $800 price showed appeal 65.5 versus current appeal 66.125 and choice share 23.234% versus 23.746%, despite a 0% price change. With the CRO vacant, the error reverses direction.

**Evidence:** Reproduced by directly executing the unchanged preview logic and original simulation functions with database-dependent imports isolated.

**Required correction:** Use the same segment-specific reference-price modifier for current, proposed and actual-sales calculations. Test an unchanged-price preview with both an occupied and vacant CRO seat.

### 6. P2 — Event raises perform monetary arithmetic in binary floats and round cents incorrectly

**Location:** [backend/tst/sim/events/effects.py:201](https://github.com/Reece77/Tech_Executive_Tycoon/blob/f904478e965d4716b829ca1391b0342537590291/backend/tst/sim/events/effects.py#L201). Cash effects also travel through floats in `backend/tst/sim/events/formulas.py:69–84`.

**What is wrong:** `round(salary_cents * (1 + value / 100))` converts the monetary calculation to binary floating point, violating CLAUDE.md §2.3. Converting back to an integer afterward does not restore exact half-to-even rounding.

**Failure scenario:** An employee earns 5,242,895 cents ($52,428.95) annually and receives a 10% event raise. The exact result is 5,767,184.5 cents, which rounds half-to-even to 5,767,184. The engine computes `5767184.500000001` and stores 5,767,185 instead.

**Evidence:** Reproduced through `apply_choice` with a major `salary_change` event and compared with exact `Fraction` arithmetic. The final salary is an integer, but it is the wrong integer. No unbalanced ledger entry was found from this path.

**Required correction:** Preserve exact decimal/rational percentages through monetary rounding. Add a half-cent regression at a realistic salary.

### 7. P3 — The documented burn formula disagrees with the stored burn metric

**Location:** [backend/tst/sim/turn.py:266](https://github.com/Reece77/Tech_Executive_Tycoon/blob/f904478e965d4716b829ca1391b0342537590291/backend/tst/sim/turn.py#L266); `docs/formulas.md:876` (§14.1).

**What is wrong:** §14.1 defines burn as negative operating cash flow. The snapshot stores the decrease in total cash, including financing. `backend/tst/api/breakdowns.py` explicitly describes the latter definition, so the project has conflicting definitions rather than one consistently documented metric. This predates M8.

**Failure scenario:** A month with $10,000 of operating outflow and $100,000 of SAFE proceeds stores zero monthly burn, while the cash-flow statement reports −$10,000 operating cash flow. A player comparing burn before and after funding sees apparent improvement without an operating change.

**Evidence:** Direct statement/snapshot execution returned documented burn 1,000,000 cents and stored burn 0.

**Required correction:** Resolve the semantic discrepancy and test a funding month against the chosen definition. This finding does not imply the ledger is unbalanced or the separately projected runway is wrong.

## Coverage in the requested order

1. **Simulation rules:** scanned all 78 Python files under `backend/tst/sim`. No imports of `tst.db/api/llm`, clock/filesystem/network operations, or production global-random calls were found. NumPy generator construction is confined to RngFactory. Frozen-model `object.__setattr__` uses observed were construction-time normalization, not mutation of existing input objects. Monetary float defects are described above.
2. **Determinism:** enumerated 20 literal RNG-stream call sites; no duplicate stream names were found. Inspected helper key namespaces and set/dict traversal. A stage-3 scenario with divisions, embedded services and executives ran 12 turns under `PYTHONHASHSEED=1`, `77` and `999`; the serialized TurnResults matched with SHA-256 `fdd677aca7a9e93dbca1acffeff74d245126d2c9f639312d255f8df25783a06f`. This is a focused check, not proof over every state.
3. **Hidden information:** inspected API views/schemas, event prompt allowlists and COO briefing, and compared planted-value tests. The concrete new leak is finding 4; no additional direct potential/hidden-tag/rival-internal field leak was confirmed in the inspected paths.
4. **Ledger:** inspected posting sites and integer/balance checks. In the 12-month scenario, all entries balanced with integer amounts, division plus corporate operating profit matched company P&L each month, and allocations summed to zero. No missing cash posting or division/company total mismatch was confirmed. Findings 1 and 6 concern stale cached state and incorrect rounding rather than an inherently unbalanced entry.
5. **Formulas:** the ten groups below were executed as direct assertions against tag-pinned code and loaded YAML. All passed their listed worked examples; findings 5 and 7 are additional integration/definition discrepancies.
6. **Tests:** reviewed the M8 test diff against m7b-done. No added skips/xfails or loosened approximation tolerances were found. Most changes update IDs/counts for the five new incumbents. The rival replay fixture reduces staff from 6 to 5 to avoid bankruptcy; it retains its replay assertions. Important missing cases are post-commit retry/cache interleavings, a poached executive, unchanged-price previews with CRO effects, and exact monetary half-cent rounding. The hidden-seat test's specific weakness is described in finding 4.
7. **Transactions/persistence:** inspected write_session, turn/action persistence, event completion and Holiday. Core state/ledger/snapshot writes share the transaction boundary. Findings 1 and 2 concern coordination outside that boundary. Actual SQLite fault-injection/rollback tests were not run here.

## Ten formula groups checked

| Formula | Code | Executed worked-example result |
| --- | --- | --- |
| §11.3–11.4 builder output and quality | `sim/products/formulas.py` | Output 3.222; Q_cap 53.148; quality 13.5 / 27.1 / 37.4 at turns 0 / 5 / 11 |
| §11.6–11.7 appeal and choice shares | `sim/products/formulas.py` | Appeals 43.375 / 62.962 / 69.75; shares 10.71% / 32.77% / 44.55% |
| §14.3 investor base valuation | `sim/finance/formulas.py` | g6 1.20219; value $15.9439M |
| §14.5 SAFE conversion and priced-round dilution | `sim/finance/formulas.py` | Seed/A/B fully diluted shares 16,347,827 / 23,436,973 / 31,561,822; all X/C/N values matched |
| §15.3 rival need and utility | `sim/rivals/formulas.py` | Zoho share drop 47%→41% gives need 1 and utility 1.4 |
| §15.6 poaching probability | `sim/rivals/formulas.py` | Priya example score −1.08512, probability 10.2455%, matching rounded documentation |
| §16.1 event candidate weight | `sim/events/formulas.py` | Morale 31 gives strength 0.2 and repeat-category weight 0.1 |
| §16.3 event caps | `sim/events/formulas.py` | Major morale +15→+10; $40,000 cost→$15,000 |
| §18.3 executive strength and multipliers | `sim/org/formulas.py` | Score 14→e 0.5; CTO ×1.05; vacancy ×0.95 |
| §18.4 support coverage and shortfall | `sim/org/formulas.py` | Coverage 0.625; output ×0.94375 or ×0.9578125 with COO; morale −2.25 |

Also executed the remaining §18.10 worked examples: layer factors 0.97/0.9775; allocation 47,542,857 cents with corporate retaining 4,457,143; redesigned CTO/CPO/CMO/CRO effects and brand cap; support churn 1.15/1.1125; delegate energy 62. All matched.

## Validation limits and recorded exceptions

`make check`, pytest, HTTP integration tests and Playwright were not run: this workspace lacks pytest, Hypothesis, SQLAlchemy and other project dependencies, and its network proxy prevented cloning/install setup. Direct Python checks used available Python 3.12, NumPy, Pydantic and YAML support. Isolated view/control-flow harnesses are identified above and are not represented as full integration tests.

The brief explicitly records Reece's approval of the T2 balance-target miss and the 50% AI growth tuning for 2016–2019. Those are recorded exceptions, not new findings here. The old-save omission of the new incumbents/earlier scheduled entrants is also explicitly recorded in the brief. No balance re-run or full acceptance-criteria pass is claimed.

## Resolution (M8r, 2026-10-31)

Each finding was fixed on branch `m8r-review-fixes`. Its regression test was written first and seen failing on the unfixed code, then passing after the fix.

| # | Finding | Fix commit | Regression test |
| --- | --- | --- | --- |
| 1 | P1 State cache published after the lock is released | bd60a32 | `backend/tests/integration/test_m8r_cache.py`: writer A commits and pauses before publishing, writer B moves an employee, writer C gives a raise; B's move survives (failed before: the stale employment row put the employee back in their old unit) |
| 2 | P1 Continue can answer busy after committing | 751c4fd | `backend/tests/integration/test_m8r_continue.py`: fault after commit, one click with retries plays one month; events stay pending and are written next; a competing write is refused while the month's events are written; a Holiday counts a month whose events failed. `frontend/src/hooks/retry.test.ts`: only `retryable` busy answers are retried |
| 3 | P2 A poached executive keeps their seat | 6dbdea2 | `backend/tests/unit/test_m8r_seats.py`: a score-14 CTO and team leader accepts Salesforce's approach, serves notice and joins; the seat is vacant with the vacancy effect, the notes arrive, the team loses its leader, and a replacement can be appointed |
| 4 | P2 Support and layer-tax numbers disclose the COO's true effect | a557ab5 | `backend/tests/integration/test_api_scaleup.py::test_hidden_coo_skill_changes_no_response`: an occupied COO, a deep division and an under-covered pool; two COOs with identical displayed ranges but different true skills give byte-identical scale-up, Org, Overview, product, portfolio and profile responses |
| 5 | P2 Price preview omits the CRO | 08c585e | `backend/tests/unit/test_m8r_price_preview.py`: an unchanged price previews the current price score, appeal and share exactly, with the CRO occupied and vacant |
| 6 | P2 Event raises use floats | 22901c4 | `backend/tests/unit/test_m8r_event_money.py`: a 10% raise on 5,242,895 cents gives 5,767,184; Hypothesis property tests compare raises, cash shares, cash clamps and the cash base with exact rational arithmetic |
| 7 | P3 Two definitions of burn | 24cc565 | `backend/tests/unit/test_m8r_burn.py`: $10,000 of operating outflow and a $100,000 SAFE store a burn of $10,000; money spent before Continue counts. Golden snapshots regenerated (only `monthly_burn_cents`) |

Decisions and follow-ups are in `docs/tasks/M8r-review-fixes.md`.
