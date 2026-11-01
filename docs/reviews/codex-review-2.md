# Codex QA review 2 — m9-done

Reviewed commit: `b4406c24b73e8c9a2f9a1c368045b287fb0e5302`.
Annotated tag object: `276d36634cbc7cfc0ea5b9064c10632825d36403`.
Comparison: `m8r-done` (`af16ece18a893d0c7cbaa72e669f101d99f38388`) to this commit: 25 commits, 171 changed files.

I read AGENTS.md and CLAUDE.md first, the ADR index and relevant decisions, M7c/M9/M10 material and formulas, review 1 including its Resolution, and balance-targets.md. The seven resolved review-1 findings are not repeated. Recorded balance misses are not findings.

No code, commits, pushes or existing branches were changed. This report is returned as a standalone artifact instead of creating `review/codex-2`. Git cloning failed because the configured workspace proxy was unavailable. The review used a SHA-pinned GitHub connector snapshot, not a local Git checkout. All 524 files in the snapshot manifest matched their Git blob hashes, including a second verification after executing the checks.

## Findings, ranked by severity

No P1 was confirmed within the checks below. There are five P2 findings and one P3 finding.

### 1. P2 — Between-turn lender fees incorrectly reduce operating profit used by bank gates and covenants

**Location:** [backend/tst/sim/turn.py:333](https://github.com/Reece77/Tech_Executive_Tycoon/blob/b4406c24b73e8c9a2f9a1c368045b287fb0e5302/backend/tst/sim/turn.py#L333), especially line 334. See also `backend/tst/db/repository.py:752` (`month_flow_so_far`) and `backend/tst/sim/events/effects.py:96` (waiver posting).

**What is wrong:** `_debt_history` adds `prior_flow`, a cash-flow total, to operating profit. That total includes a waiver fee paid through ChooseEvent before Continue. The fee correctly posts to `7000_interest`, which §20.3 puts below operating profit, but this addition puts it back above the line in `CompanyState.op_history`. Monthly interest posted inside the turn is classified correctly, so answering the lender event manually exposes a different accounting path.

**Concrete failure scenario:** A company has operating profits of $1,000, $1,000 and $5,000 in the relevant three months. It manually pays a $10,000 waiver on a $1M bank loan. True three-month operating profit is +$7,000, but the stored total becomes −$3,000. Despite sufficient cash, the bank profit covenant can breach; subsequent breaches can call a loan that should satisfy this covenant. A falsely negative individual month also blocks the bank-loan eligibility gate.

**Evidence:** Called the unchanged `_debt_history` with a $5,000 revenue posting and `prior_flow={1: -1000000}` representing the separately posted $10,000 interest fee. It recorded `-500000` cents; the correct operating result is `500000`. Source inspection traced that scalar to `month_flow_so_far` and the fee to `INTEREST`. This was an isolated production-function check, not a SQL transaction test.

**Expected correction:** Carry prior operating profit separately from prior operating/investing cash flow, using account classification for the complete month's ledger. Keep the existing burn calculation separate. Test manual waiver payment followed by Continue against both bank eligibility and covenant history.

### 2. P2 — Division operating profit includes and allocates loan interest

**Location:** [backend/tst/sim/finance/divisions.py:62](https://github.com/Reece77/Tech_Executive_Tycoon/blob/b4406c24b73e8c9a2f9a1c368045b287fb0e5302/backend/tst/sim/finance/divisions.py#L62), `_add` at line 67 and allocation selection at line 125.

**What is wrong:** `_add` puts interest in `tools_ga`; `is_operating_cost` also treats it as a shared operating expense. With M10 loans present, the division report's company operating profit is therefore lower than the financial statement's operating result, and central divisions inherit a share of financing costs. This violates §20.3's below-operating-profit classification and §18.1's reconciliation requirement. The existing helper predates this diff; the new interest postings activate the problem.

**Concrete failure scenario:** A company has $100,000 revenue and $31,250 loan interest, with equal corporate and Platform headcounts and no other costs. The financial statement correctly shows $100,000 operating profit. The division report shows $68,750 for the company and charges Platform $15,625 of interest through shared services. Leasing an office does not repair the discrepancy: ordinary rent should reduce both operating statements equally, while interest should reduce neither.

**Evidence:** Executed `division_report` and `profit_and_loss` on those same account lines. Results were respectively `6875000` and `10000000` cents; Platform's operating profit was `-1562500`. Adding the Berlin 50-seat rent yielded `8987500` cents company operating profit versus `5862500` in both the division company total and the sum of division/corporate columns. Inspected the division property test: its `TYPES`/`EXPENSES` generator omits `INTEREST`, so its reconciliation assertion cannot exercise M10 interest.

**Expected correction:** Exclude below-operating items from operating columns and shared-service allocation, or show them explicitly below operating profit if needed. Extend reconciliation coverage to interest, alongside office rent and division-tagged payroll/product costs, comparing against the actual company P&L rather than only the division report's own company total.

### 3. P2 — Closing an inherited foreign office silently relocates child teams to HQ

**Location:** [backend/tst/sim/actions/geo.py:129](https://github.com/Reece77/Tech_Executive_Tycoon/blob/b4406c24b73e8c9a2f9a1c368045b287fb0e5302/backend/tst/sim/actions/geo.py#L129).

**What is wrong:** `close_office` changes only units whose own `office_id` equals the closed office. A child team may inherit that office from its parent while retaining an explicit `office` policy. Closing the parent office makes the parent remote, but leaves that child's policy unchanged. Its office resolves to flexible HQ, and the action's subsequent city settlement moves its staff there. §19.2 requires occupants of a closed non-HQ office to become remote in that city.

**Concrete failure scenario:** A San Francisco company assigns its Engineering department to Berlin. Its Core child team inherits the lease and has an explicit office policy. Close Berlin: Core's employees move from Berlin to San Francisco, remain office workers, and acquire the HQ's work-city rates and geography. This is a relocation the player did not request and can change morale, costs and regional reach.

**Evidence:** Reproduced through `apply_action` with legitimate LeaseOffice, CreateUnit, MovePerson, SetPolicy, SetUnitOffice and CloseOffice actions. Before closing: home/work city `berlin`, policy `office`. Afterwards: home/work city `san_francisco`, policy still `office`, `is_remote=False`. The existing close-office test covers direct assignment, not this inherited assignment plus explicit child policy.

**Expected correction:** Identify effective occupants before detaching the lease, including descendants inheriting it. Make affected non-HQ occupants remote while preserving their existing city; preserve separately assigned child offices. Add this hierarchy regression.

### 4. P2 — Product summaries omit overseas customers, revenue and hosting

**Location:** [backend/tst/api/product_views.py:380](https://github.com/Reece77/Tech_Executive_Tycoon/blob/b4406c24b73e8c9a2f9a1c368045b287fb0e5302/backend/tst/api/product_views.py#L380); `_hosting` at line 474 and portfolio customer counting at line 503.

**What is wrong:** Product-level current MRR/customers and hosting iterate only home `ProductSegment` rows. Portfolio customer counts do too, although portfolio snapshot MRR and `product_costs` include regional sales. The Regions panel can therefore disagree with the product's headline and the Products screen can show overseas revenue with no corresponding customers. The documented decision that `product_month` history stays home-only does not make unqualified current product/portfolio totals accurate.

**Concrete failure scenario:** A live B2B SaaS product has no home customers and 1,000 European SMB customers paying $45/month. Regional MRR is $45,000 and hosting is $4,000. Its product response reports zero MRR, customers and hosting; the portfolio reports zero paying customers while charging the $4,000 hosting and eventually including the foreign MRR in its snapshot totals.

**Evidence:** Executed the original `product_out`, `_hosting`, `portfolio_out` and simulation `product_costs` on this state. ProductOut returned `(0, 0.0, 0)`; portfolio paying customers were `0.0`; simulation hosting was `400000` cents. To import the view without SQLAlchemy, the harness omitted unrelated view imports and supplied empty breakdown-formatting results and a name formatter; the counting and monetary functions were unchanged.

**Expected correction:** Aggregate live regional segments into current product and portfolio totals. Keep documented home-only historical series explicitly scoped/labeled, or extend their data deliberately. Test that current product totals equal the home-plus-regional rows and agree with company totals at the same measurement point.

### 5. P2 — Regional price paths still round binary floats and charge wrong cents

**Location:** [backend/tst/sim/geo/formulas.py:70](https://github.com/Reece77/Tech_Executive_Tycoon/blob/b4406c24b73e8c9a2f9a1c368045b287fb0e5302/backend/tst/sim/geo/formulas.py#L70), consumed at line 80; also `backend/tst/sim/rivals/startups.py:182` and `backend/tst/sim/rivals/decisions.py:509`.

**What is wrong:** `relative_row` divides binary floats for the price-index ratio. `regional_price_cents` converts that already-rounded result to Fraction. Exact arithmetic after the conversion cannot recover the intended decimal ratio. New regional rival-price paths also multiply integer cents by the floating personality factor before rounding. Both break CLAUDE.md's money arithmetic rule and ADR-0003's rounding behavior at half-cent boundaries.

**Concrete failure scenario:** An East Asia HQ launches a product with a 5,000-cent reference price into South/Southeast Asia. The intended calculation is `5000 × 0.35 / 0.80 = 2187.5` cents, which half-even rounds to 2,188. The float ratio is `0.43749999999999994`, so the game sets 2,187 cents. Every subsequent customer is charged a cent less than the stated formula. This also affects the default North American HQ: a cost-leader AI startup entering Europe prices its consumer offering at `45 × .7`, which returns 31 cents instead of the exact half-even result of 32.

**Evidence:** Called `regional_price_cents(5000, 'south_southeast_asia', 'east_asia', data)` with the tagged data: `2187`. Computing the original decimal indexes as Fractions and rounding once returned `2188`. The same result reproduced under both Python hash seeds used for the determinism check. A scan of the tagged category/index/personality values found seven binary-multiplier discrepancies; the original `sell_first_in` reproduced the 31-versus-32-cent European consumer price.

**Expected correction:** Convert both original price indexes to exact decimal fractions before dividing, and convert rival personality multipliers before multiplying cents; keep each specified price calculation exact through its final rounding. Use the same exact ratio for the regional appeal/reference-price path as well. Test half-cent cases across non-US HQ/target pairs. The floating size ratio can remain separate from the monetary calculation.

### 6. P3 — The full repayment test skips its critical assertions when a regression ends the game

**Location:** [backend/tests/unit/test_debt.py:62](https://github.com/Reece77/Tech_Executive_Tycoon/blob/b4406c24b73e8c9a2f9a1c368045b287fb0e5302/backend/tests/unit/test_debt.py#L62).

**What is wrong:** The new 36-month repayment test calls `pytest.skip` on an early game end, before checking repaid status, total principal, zero debt and accumulated interest. This is not one of the recorded statistical balance exceptions. An erroneous interest charge or premature loan call that bankrupts this fixture can suppress the very assertions meant to catch a repayment regression.

**Concrete failure scenario:** A repayment change overcharges cash but keeps journal entries balanced. The fixture ends early; `_ledger_ok` passes, then the test skips instead of failing for the incomplete repayment or unexpected bankruptcy.

**Evidence:** The unchanged normal 36-month test body completed successfully in the direct harness. In a separate controlled check, its game wrapper marked the state ended after the first real turn; the unchanged test took the skip path before the final repayment assertions. This demonstrates a coverage weakness, not a claim that the current seed actually skips.

**Expected correction:** Use a fixture with sufficient ledger-backed cash and controlled covenant conditions for the full schedule, and assert it reaches repayment. Test bankruptcy/loan calls separately instead of allowing them to skip the schedule test.

## Checks performed, in the requested order

1. **Sim rules:** scanned all sim Python files for forbidden layer imports, clock/filesystem access and random calls, and reviewed new money paths. No forbidden layer or clock/filesystem use was found. NumPy generator construction remains in RngFactory. Finding 5 is the confirmed monetary arithmetic break. No mutation of an existing frozen state object was identified.
2. **Determinism:** AST-enumerated literal `.stream` calls: 22 stream names, no duplicate literal-name call sites. Checked ADR-0013 and IDs `macro=21`, `rival_region=22`; their call sites are macro.py:144 and startups.py:154. Checked fixed data indexes, sorted state upserts and database load order for cities/offices/regional rows. Two original in-memory games with a Berlin lease and venture debt, seed 3, through 12 turns, under `PYTHONHASHSEED=1` and `917`, yielded the same canonical state-and-ledger SHA-256: `a3498f691df2a1c05a2c07fe770bbe1389096869cb81a833ee8a6b98cca45132`. This is a bounded check, not proof for every possible ordering.
3. **Hidden information:** inspected new geo/office/region, loan and macro view builders and schemas, former-profile snapshots, event context and the planted-value tests. The new regional team view requests `estimate=True`. No new true-attribute, hidden-tag, seat-score, rival-internal or future-macro leak was confirmed. Directly planted a future stored MacroMonth with distinctive values for all four indicators: the unchanged `macro_out` JSON was byte-identical before and after planting it. HTTP planted-value tests were not executed.
4. **Ledger:** traced fit-out/rent/closure to RENT, relocation to RECRUITING, localization to RESEARCH, drawdown/repayment to DEBT/CASH, and interest/waivers to INTEREST/CASH. Warrants change cap-table shares rather than cash. Executed original early-repayment, waiver/rate, breach/call and full-schedule test bodies, including their ledger assertions. Also executed the original debt-invariant assertion body for 108 fixed grid cases × 40 months, varying amount (including an odd-cent principal), repayment timing/share and burn; all passed. Findings 1–2 concern accounting classification and statement reconciliation, not unbalanced journal entries.
5. **Code/formulas:** see the table below.
6. **Regional isolation:** executed the original home-region-v1 replay and launch tests, regional live-price gating, foreign presence/awareness, seller weighting and seeded startup-region tests. Source inspection verified home two-part market keys, foreign three-part keys, separate state updates, presence threshold/awareness and neighbor-seller weighting. Inspected the foreign-only-product guard in rival `candidates` and directly checked that foreign-only SAP has no v1 `enter_segment` candidate; it uses `enter_region` to enter home instead. Findings 3–5 cover confirmed geographic/reporting defects.
7. **Macro/debt:** checked 10 seeds across 360 months each; historical indicators through December 2025 match loaded history, historical paths are seed-independent, future paths vary and same-seed paths replay exactly. Checked old climate values against the m8 snapshot and confidence normalization. The $6M/6.25% schedule starts with $31,250 monthly interest, has 12 interest-only months then $250,000 principal monthly, and ends at zero. Original covenant/event tests passed, including cure followed by a second breach and a called-loan event. A separate direct phase check called a loan with insufficient cash: the balanced postings left cash negative, insolvency counted months 1/2/3 and the third ended in bankruptcy. The original 50-seed future target also passed: 41/50 paths had a downturn, and 2030 venture-climate standard deviation was 0.171 (minimum 0.15).
8. **Tests:** reviewed changed seeds/xfails/skips/tolerances. The rival replay source documents the intermediate 7→6→7 seed history; the final tagged seed is 7. Recorded xfails are accounted for below; no intentional miss is reported as a defect. Finding 6 identifies the additional skip weakness. Important missing combined cases are: manual waiver versus operating-profit history; interest in division reconciliation; inherited-office closure; foreign totals in existing product views; exact regional pricing for non-US HQs; and planted true-value checks on the new geographic views. Existing broad upgrade tests run through the new migrations, but do not explicitly assert HQ/home-city backfill values.
9. **Persistence/transactions:** read migration chain 0020→0021→0022→0023, old-schema table/column guards, HQ and home-city backfill, regional seeding, loan/macro synchronization and the write-session/turn/Holiday boundaries. New office/loan state and ledger writes share the caller's transaction; no new partial-commit path was confirmed by source review. Actual SQLite upgrades, rollback fault injection and concurrent saves were **not run**. In particular, old-save HQ/home-city values and replay after migration are not runtime-verified here.

## Formula checks

| Formula | Evidence/result |
| --- | --- |
| §19.1 work-city pay × geo.pay_level | Direct Bangalore example: $115,000 × .30 × .876 = $30,222. Reviewed morale, exec and rival rate callers. |
| §19.2 lease, fit-out, closing, crowding | Berlin 50 seats: $10,125 rent; $30,375 fit-out/penalty. Original lease, move, direct closure and −4 crowding test bodies passed. Inherited closure fails: finding 3. |
| §19.3 relocation | Original relocating-hire test passed: $15,000 RECRUITING posting, city updated, no second fee. |
| §19.4 cross-region output | Checked 1.00 / .95 / floor .85 arithmetic and team integration. |
| §19.5 regional demand, price, localization | Europe SMB: 320,000 demand and 4,500-cent price. Cybersecurity localization rounds to 4,666,667 cents (the document displays whole dollars). Non-US half-cent pricing fails: finding 5. |
| §20.1 AR(1), confidence, downturns | Climate worked step 1.30→1.31; confidence 81→.90 adoption factor. Historical/future seeded checks above; reviewed downturn impulses, minimum gap, duration and January AI updates. |
| §20.2 Series C/D | Original gates/order, seven-seat limit and investor-start-year test bodies passed, including SoftBank absent before 2017 and present afterwards. |
| §20.3 loan schedules, covenants | Exact interest/principal example and original full 36-month repayment passed. Original breach, waiver/rate, early-repayment and cure/call tests passed. Manual waiver accounting fails: finding 1. |
| §11 awareness (touched product path) | Rechecked brand 10 → .05 worked arithmetic and regional awareness multiplier integration. |
| §14 SAFE conversion (touched finance path) | Rechecked worked share counts: FD 16,347,827; SAFE 1,034,783; pool top-up 1,226,087; new-round shares 4,086,957. |
| §18 seat effect (touched product/geo path) | Rechecked score 14 → effect .5 → 1.05 multiplier; inspected estimate/true separation in the affected views. |

## Recorded xfail checks

These are direct guard outcomes, not pytest-generated XFAIL/XPASS statuses. All use the tagged scripts/data and original thresholds. Completed simulation results were also supplied to the original guard bodies, without rerunning their expensive fixtures. The standard batch was four strategies × 10 seeds, up to 120 turns; M10 used three arms × 10 seeds, up to 120 turns; M8 used 10 seeds for each paired arm. The easy/hard difficulty batches and all other nightly targets were not run.

| Recorded guard | Measured | Original assertion outcome |
| --- | --- | --- |
| T2: no strategy wins >6/10 | Steady 8, bootstrap-frugal 2, others 0 | Assertion failure as recorded; no execution error |
| T3: blitzscale succeeds ≥3/10 | 5/10 | Pass; XPASS-equivalent, as documented for combined M9/M10 |
| T7: startup survival at five years, 20–60% | 58/94 = 61.7% | Assertion failure as recorded; no execution error |
| M8 seats, ≥1.15 | 1.0048277378 | Assertion failure as recorded; no execution error |
| M8 support, ≥1.08 | 1.1126342441 | Pass; XPASS-equivalent, as documented for combined M9/M10 |
| Executive at default salary stays | Seed 3: approach “might go”; seeds 4 and 8: CTO left | Assertion failure for retention reasons, not an error; 10 seeds, six months after appointment |
| M10 debt saves ≥5 founder points | +4.83 points | Assertion failure as recorded; no execution error. Its separate bankruptcy-risk assertion passed: +0 points. |
| M10 covenant breach share, 20–60% | 90% | Assertion failure as recorded; no execution error |
| M5 living-market launches, ≥1.0 | 0.925 per v1 category per seed | Assertion failure, not an error; 10 seeds × 120 turns. Its separate share guard held: zero breached seeds, observed ratios .57–1.65. |
| Potential spotting, ≥3 PA points | +2.83 (141.32 versus 138.49 mean true PA; 690/691 hires) | Assertion failure as recorded; no execution error; original body, 400 seeds × two judgment levels × three turns |

The intentional misses above are excluded from the findings. Timing under concurrent review harnesses is not a valid performance benchmark.

## Execution limits and reproducibility

`python -m pytest -q` from the backend directory exited 1 immediately with `No module named pytest`. Dependency probes also confirmed hypothesis, SQLAlchemy, Alembic, Anthropic SDK and Typer are absent. Python 3.12, NumPy, YAML, Pydantic, FastAPI and httpx were available. No packages were installed and no source files were changed to make checks pass. No frontend build, browser/Playwright, live Anthropic call, CLI integration, SQL-backed API test, actual migration or concurrency test was executed.

For pure checks I imported the original simulation and loaded the tagged YAML data. For tests needing the production mock game, a placeholder satisfied the unused Anthropic SDK import; constructing a real Anthropic client raised an error. Original strategy, simulation, event and MockLLMAdapter functions remained unchanged. For selected original test bodies, an AST loader removed pytest imports/decorators only; assertions and fixtures' simulation logic remained unchanged. This is direct assertion execution, **not** a pytest pass count. Checks requiring pytest helpers were omitted rather than silently treated as passes. View/fault-injection substitutions are identified in the relevant evidence above.

The focused commands executed were `python /tmp/m9-focused.py`, `python /tmp/m9-findings.py`, `python /tmp/m9-public.py`, `PYTHONHASHSEED=1 python /tmp/m9-hash.py`, the same hash command with seed 917, `python /tmp/m9-skip-check.py`, `python /tmp/m9-debt-grid.py`, `python /tmp/m9-called-shortfall.py`, `python /tmp/m9-result-assertions.py`, and the `potential`, `living`, `exec`, `schedule` modes of `/tmp/m9-extra-guards.py`. The balance modes were `python -u /tmp/m9-balance-check.py v1`, `m8`, and `m10`. Additional inline Python commands ran the listed original geo/Series C/D/future-macro bodies, source-hash checks and stream AST inventory.

The review harnesses are outside the snapshot (`/tmp/m9-focused.py`, `/tmp/m9-findings.py`, `/tmp/m9-public.py`, `/tmp/m9-hash.py`, `/tmp/m9-skip-check.py`, `/tmp/m9-extra-guards.py`, `/tmp/m9-balance-check.py`). The report and these checks do not constitute full-suite validation.

## Resolution (M10r, 2026-11-01)

Each finding was fixed on branch `claude/m9-cities-regions-horg5m` (restarted from `main` after `m9-done`). Its regression test was written first and seen failing on the unfixed code, then passing after the fix. No golden snapshot moved.

| # | Finding | Fix commit | Regression test |
| --- | --- | --- | --- |
| 1 | P2 Lender fees paid before Continue counted as operating | 12a8b65, 3d0e12b | `backend/tests/unit/test_m10r_lender_fee.py`: Codex's case ($5,000 revenue, $10,000 fee before Continue) stores +$5,000, keeps the $10,000 in burn, and passes the bank gate and profit covenant (stored −$5,000 before); a breach, the waiver (choice A) answered before Continue, then Continue: the stored month equals the P&L of every line the month posted (−$5,100 against −$1,100 before). `backend/tests/integration/test_m10r_month_operating.py`: the same through a save (`month_operating_so_far`, `run_turn`) |
| 2 | P2 Division reports include and allocate interest | 2ea8438 | `backend/tests/unit/test_m10r_division_interest.py`: $100,000 revenue and $31,250 interest give $100,000 company operating profit and Platform 0 (were $68,750 and −$15,625); Berlin rent lowers both statements equally. `backend/tests/property/test_division_statements.py` now draws interest, rent, R&D and division-tagged payroll and product costs and compares the company column with the real P&L |
| 3 | P2 Closing an inherited office moves child teams to HQ | 4e18cfd | `backend/tests/unit/test_m10r_close_office.py`: Engineering in Berlin, its Core team inheriting with an explicit office policy; after closing, Core's people are remote in Berlin (were office workers in San Francisco); a child with its own London office keeps it |
| 4 | P2 Product totals leave out overseas sales | 4075c8e, 5d6b4af | `backend/tests/unit/test_m10r_overseas_totals.py`: 1,000 European SMBs at $45 and no home customers: the product shows $45,000 MRR, 1,000 customers and the hosting phase 6 posts (were 0, 0, 0); the portfolio's customers agree with company totals. Home-only series carry `series_scope`/`series_label` ("Home region"), shown in the UI once a product sells abroad (`frontend/src/components/products.test.tsx`) |
| 5 | P2 Regional prices round binary floats | 7d6a24f | `backend/tests/unit/test_m10r_regional_prices.py`: East Asia HQ, 5,000 cents into South and Southeast Asia gives 2,188 (was 2,187); a cost-leader AI startup's consumer price in Europe is 32 through `sell_first_in` and `enter_region` (was 31). `backend/tests/property/test_regional_prices.py`: every region pair and personality factor against exact decimal arithmetic, Hypothesis plus every reference up to 400 cents |
| 6 | P3 The repayment test can skip | 4cf4ed4 | `backend/tests/unit/test_debt.py::test_schedule_interest_then_equal_principal_to_zero`: a ledger-backed $100M reserve; asserts no game end, no breach and full repayment. With a temporary plugin that ends the game after one turn, the old test skipped and the new one fails ("the game ended in month 1") |

Decisions and follow-ups are in `docs/tasks/M10r-review-fixes.md`.
