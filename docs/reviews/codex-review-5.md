Codex QA review 5 — m22-done
Reviewed main at m22-done, commit 2fc5f6d859f52ead370ee9e20feb64a936b4ee96, against m15a-done, commit 4f42e2a3f71c38692a808816cbfd6e2e11b9804c.

Result: 10 P2 findings and 2 P3 findings. Findings from reviews 1–4 and recorded balance-target misses are excluded. References below are pinned to the reviewed commit. This was a read-only review: no source edits, commits or pushes.
Findings
1. P2 — Facility transfers leave fab and refinery ownership behind
Location: backend/tst/sim/mining/actions.py:406.

Wrong: transfer_asset moves the facility and its books, then updates only a possible Mine record. A Fab or Refinery keeps its old company_id. Refinery operations use the refinery record's owner, while staffing and depreciation use the facility's owner; fab supply also selects by the stale fab owner.

Breaks: ADR-0020 §1–2; formulas §35.1/§35.7's transfer of facilities at book value; ADR-0003's per-entity books.

Scenario/evidence: Ordered a fab through production actions, founded subsidiary 41, and transferred the fab through transfer_asset. The resulting facility belonged to 41, but its fab record still belonged to 1. A refinery transferred the same way can continue charging operating costs to its former owner after its PP&E has moved.

Fix: Make transfer a shared lifecycle operation that updates every kind-specific record and handles the staffing assignment consistently. Test subsequent operations, production and cold reload for mines, refineries and fabs, asserting the owning entity of every posting.
2. P2 — Rebuilding a closed mine restores its deposit and capitalizes exploration again
Location: backend/tst/sim/mining/actions.py:473, with reserve initialization at line 547 and capitalization at line 573.

Wrong: The build gate rejects only a non-closed mine on the project. Closing leaves the project permitted. A second build copies the original deposit tonnage into a new mine with zero cumulative extraction and credits the project's original exploration expense again.

Breaks: Formulas §35.2–§35.3: a mine consumes finite deposit reserves and capitalizes the project's exploration spend; ADR-0003's faithful asset/expense accounting.

Scenario/evidence: In a production mining fixture, represented an exhausted deposit by setting cumulative ore mined to its full 29.102957 Mt, closed mine 1 through CloseMine, then executed BuildMine on the same project. It accepted mine 2 with 29.102957 Mt remaining, and credited 6600_exploration another 4,500,000 cents. The same gate permits rebuilding after ordinary chosen closure.

Fix: Track depletion and capitalized exploration at project/deposit level across mine lifetimes. Reject rebuilding exhausted or disposed projects; any supported replacement mine must inherit remaining reserves and capitalize only previously uncapitalized expenditure. Test close/rebuild and depletion/rebuild sequences.
3. P2 — Intercompany elimination assigns NCI the wrong profit
Location: backend/tst/sim/finance/consolidation.py:167.

Wrong: Intercompany accounts are deleted from each member's contribution before that contribution reaches nci_by_turn. NCI therefore loses the subsidiary's internal-sale revenue or internal-purchase expense when its share of profit is calculated. The residual equity adjustment keeps the consolidated trial balance balanced, concealing the attribution error.

Breaks: Formulas §31.3 and §31.8: outside holders receive their share of subsidiary profit; CLAUDE.md §2.3 and ADR-0003's reconciling statements.

Scenario/evidence: A group owns 80% of a supplier. In one month the supplier sells services to the parent for 100 cents, incurring 80 cents of external costs. Its profit is 20 and NCI's share is 4 cents. Production consolidation instead emits −16 cents on 4990_nci_share_of_profit, while all consolidated lines still sum to zero. The existing consolidation property tests do not generate intercompany trades or independently verify this profit allocation.

Fix: Preserve entity profit information for NCI attribution, applying the appropriate consolidation adjustments separately from elimination of group revenue/expenses. Add independent upstream and downstream transfer cases with minorities at multiple ownership levels.
4. P2 — A subsidiary's refinery incident never reaches the player
Location: backend/tst/sim/refining/events.py:130; queue consumption at sim/events/director.py:347.

Wrong: An incident is queued for ref.company_id, but the director consumes only the operating player's queue. Unlike the mining event path, refining does not route subsidiary incidents to that inbox. The incident remains open, preventing another incident at that plant; its fine and stop/compensate/contest decision never execute.

Breaks: ADR-0020 §1; formulas §36.4/§36.7's critical plant incidents and their consequences; M20 sub-task 5.

Scenario/evidence: With a live subsidiary-owned plant and normal incident parameters, seed 261 generated chemical_release for subsidiary 41. Calling the production director left its queue record undone, emitted no refinery incident event, and left incident_turn open. Ordinary player events were emitted instead.

Fix: Route group incidents through the player inbox while retaining an explicit affected company and facility ID. Resolve costs on the affected entity. Test an incident from a refinery built directly for a subsidiary through presentation, choice, fine and incident closure.
5. P2 — Own-fab chips escape origin tariffs
Location: backend/tst/sim/geopolitics/tariffs.py:68.

Wrong: Chip origin is derived exclusively from running wafer contracts, weighted by contracted capacity. Own fabs are omitted. A chip product can launch and produce from its own fab without a wafer contract, so its origin becomes empty and its tariff is zero. With contracts present, their origins incorrectly represent the entire product.

Breaks: Formulas §39.3's origin-based chip tariffs, integrated with §38.2/§38.6's own-fab production; M22's requirement to wire to M21.

Scenario/evidence: Exercised product_tariff_cents on a nonzero production-month fixture with a China fab, no wafer contracts, 100 chips, 1,000,000 cents COGS, and North American customers. made_in returned {} and the tariff was 0, rather than 220,000 cents at the 2021 US rate of 25% and US demand share of 88%. This is a direct-function production-row reproduction, not a completed HTTP campaign.

Fix: Record actual production origins, including own-fab starts and delivered contract starts, and weight tariffable costs by the output actually used. Test own-only and mixed-origin chip production with an independent expected tariff.
6. P2 — Removing a fab's crew eliminates its fixed operating costs
Location: backend/tst/sim/fabs/plants.py:339, especially line 349.

Wrong: Settlement defines live as month.available > 0, which requires staffing, and charges fixed running costs only under that condition. A completed fab with no crew thus loses its maintenance/site fixed costs. Variable output costs should vanish with production; fixed costs should follow the live facility's lifecycle.

Breaks: Formulas §38.6's fixed running cost of paid capex per year; ADR-0020 §2's common lifecycle and distinction between staffing/utilization and facility status.

Scenario/evidence: Built and completed a 28 nm fab, removed its staffing assignment, and played its month. It remained live, with 101,445,063,783 cents paid capex and 1,690,751,063 cents depreciation, but fixed cost was 0, versus 507,225,319 cents under the documented 6% annual rate. The no-staff test verifies depreciation and zero revenue but misses this expense.

Fix: Determine fixed-cost eligibility from lifecycle status, independently of available production starts. Specify conversion treatment explicitly. Test a live unstaffed fab against the documented fixed-cost formula.
7. P2 — Materials transfer prices bypass minority protection
Location: backend/tst/sim/group/transfer.py:139.

Wrong: materials is an accepted transfer flow and refining applies its price, but the fairness monitor recognizes only compute and chips accounts. Materials therefore receive market = 0, never accumulate unfair months, and even have an existing complaint cleared. Their actual transfer value also never enters the flow's trailing totals.

Breaks: Formulas §31.6's protection for minority-held sellers/buyers, §31.7's intra-group revenue share, and §36.7's use of materials transfer prices.

Scenario/evidence: An 80%-owned materials seller can transfer below the 10% fairness band indefinitely without the six-month complaint or legal costs. In a direct production-function check, a materials flow with five unfair months and an open complaint was reset to 0 months / no complaint, despite buyer COGS being supplied. M20 acknowledges this as a follow-up; it remains an unmet functional requirement, separate from recorded balance-target misses.

Fix: Feed actual settled materials volume, market value and transfer consideration into the shared fairness/trailing-value monitor. Test six consecutive unfair months through real refinery supply, followed by correction to market.
8. P2 — Entity-list RNG uses an allocation-dependent company ID
Location: backend/tst/sim/geopolitics/listing.py:76.

Wrong: The new listing draw keys geopolitics by raw company.id, although founded subsidiaries already have stable rival_key identities. Their IDs come from max(company.id) + 1, so an unrelated company changes regulatory outcomes. Listing appeals similarly use the raw company ID in geopolitics/events.py.

Breaks: CLAUDE.md §2.2; ADR-0013's stable-identity amendment. This is a new M22 consumer, not review 4's repaired serial-founder identity allocation.

Scenario/evidence: Founded the same subsidiary with and without an unrelated company appended beforehand. The subsidiary retained stable key (6, 0), but its ID changed 41 → 42. At the same turn, with the same grey-route exposure and RNG seed 6, production listing_month returned not listed → listed.

Fix: Key company-level listing and appeal draws by the persisted stable company key, retaining separate use tags. Add an append-unrelated-company regression that compares outcomes, not just replay of identical IDs.
9. P2 — A rejected fab quote exposes seeded future node economics
Location: backend/tst/sim/fabs/actions.py:116, exposed by api/fab_views.py:272 and /fabs/quote.

Wrong: The timeline withholds a future node's seeded capital until arrival, but the quote endpoint computes and returns that same capital through capex_cents even when the node cannot yet be planned. The cost-per-start calculation also reads the future node's seeded wafer price for chemicals. Returning allowed = false does not hide those numbers.

Breaks: ADR-0007's hidden-information boundary; §38.1's future seeded node information and the node view's explicit pre-arrival withholding contract (api/fab_views.py:220).

Scenario/evidence: In January 2014, requesting an A16 quote for 10,000 starts returned 473,739,523,236 cents for seed 1 and 466,406,350,006 cents for seed 2, both with allowed = false. These are calculated from the actual future timeline's random capital, while /nodes intentionally returns no capital for unarrived future nodes. This finding concerns future economics, not disclosure of the exact arrival date.

Fix: Use public planning estimates/ranges for unarrived nodes, or omit quote economics until legitimately available. Add a differential quote test changing only unrevealed timeline economics; covering /nodes alone misses this path.
10. P2 — Offtake prepayments round binary floating-point money
Location: backend/tst/sim/commodities/offtake.py:142; monetary value_cents also returns float at line 54.

Wrong: A known integer annual purchase value is multiplied by a binary float prepayment share. Rounding to integer cents afterward does not restore exact half-even arithmetic. The incorrect amount then becomes the actual prepaid asset and cash payment.

Breaks: CLAUDE.md §2.3 and §8; ADR-0003. This is M17's new offtake path, distinct from earlier reviews' repaired monetary paths.

Scenario/evidence: Executed offtake_quote for a five-year copper agreement with annual value 100,000,000,100 cents and a permitted 8.5% prepayment. Production returned 8,500,000,009 cents; exact decimal/rational half-even arithmetic gives 8,500,000,008 cents. The resulting ledger entry still balances.

Fix: Keep prices and monetary calculations exact, using scaled integers/rationals and money.exact at rate boundaries; round only at the posting boundary. Audit the new mining, refining, fab and tariff money calculations for the same pattern. Add independent rational-reference half-cent cases.
11. P3 — The personal salary helper credits an annual salary every month
Location: backend/tst/sim/founder/personal.py:111; incorrect test expectation at tests/unit/test_m24_founder.py:216.

Wrong: Employment salary is annual, and company payroll pays monthly_salary_cents(salary). The personal helper instead credits the whole annual salary less tax each month. Its unit test encodes that same wrong expectation.

Breaks: Formulas §32.2's salary-after-tax income, together with §8's monthly salary rule and ADR-0003's correct cash accounting across the separate books.

Scenario/evidence: For a founder employment with 12,000,000 cents annual salary, production salary_month credited 7,800,000 cents in one month instead of 650,000 cents. This is a helper-level nonzero-salary fixture: ordinary founders currently start at zero and the standard raise action excludes them, so this is a latent supported-income-path defect, not a claimed default-game cash exploit.

Fix: Apply the normal monthly salary conversion, then exact tax arithmetic. Test a full year's company payroll against personal after-tax receipts using an independently calculated annual total.
12. P3 — The tariff property test passes with tariff calculations disabled
Location: backend/tests/property/test_m22_invariants.py:57.

Wrong: all(x > 0 for x in taxed) accepts an empty list. The expected tariff is then calculated by calling the same production helper used to post it. Consequently, the test does not establish its claimed schedule/origin invariant when the helper silently returns zero.

Breaks: CLAUDE.md §6's meaningful tests; M22 sub-task 1 and the test's own claim that every tariff equals the schedule's rate on taxed production.

Scenario/evidence: Temporarily replaced tariffs.product_tariff_cents with a function returning zero in the review process, then executed the property's test body for 2020, 20,000 device units, one month. It passed, although that is a tariff-bearing China-to-US case. No repository file was changed for this mutation check.

Fix: Require positive taxable production and a nonempty tariff posting in applicable cases; compute expected amounts independently from declared rates, origins and destination shares. Keep separate explicit pre-tariff zero cases and add own-fab/mixed-origin coverage.
Verification and limits
- Consulted CLAUDE.md, including §9; the requested ADRs; formulas §31–§39 and their implementation notes; M16–M22 and M24–M26 briefs; prior review findings/resolutions; and the relevant source, API and test paths. Documented design decisions were considered, including M22's explicit permission to show public base licence approval rates. That public rate is not reported as a leak.
- Compared the requested tags. The clone succeeded after retrying outside the initial sandbox's unavailable proxy connection; no snapshot fallback was needed. Verified all 1,356 tracked file blobs against m22-done: zero mismatches. main and the peeled target tag matched the commit above, and the tracked working tree remained clean.
- 65 focused tests passed: 37 covering the dictionary, consolidation properties, fab properties and geopolitics; 28 covering migration/model agreement, older-save upgrade/backup, simulation purity and RNG call sites. No full make check, frontend suite, Playwright campaign or statistical balance-suite pass is claimed.
- Checked migrations 0039–0047 against dictionary/ORM/schema checks. No additional physical-schema mismatch was confirmed. Those checks do not certify every JSON payload semantic or every historical populated-save upgrade.
- Numerical and behavioral reproductions used production functions and repository fixtures. The NCI ledger, depleted-mine state, subsidiary incident and nonzero chip production cases include explicitly constructed states; they are not claims of complete player-driven HTTP playthroughs. The nonzero founder salary limitation is stated in finding 11.
- No additional confirmed direct leak of deposit truths, scandal risk, regulatory risk, adjusted licence probabilities or exact future rule/node dates is asserted. No new partial-transaction or direct personal-account/company-account mixing defect was confirmed. These are limits of the evidence, not guarantees that untested paths are correct.