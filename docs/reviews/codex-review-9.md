# Codex QA review 9 — `m43-done`

Reviewed `main` at `80a380792db2a4a63b01cfe880f48b62614ebeec` against `m35b-done` at `50aa1d3d81b64655060c2d15859819a9f0918108`. GitHub resolved both `main` and `m43-done` to the reviewed commit and confirmed the baseline was its ancestor. [Commit comparison](https://github.com/Reece77/Tech_Executive_Tycoon/compare/50aa1d3d81b64655060c2d15859819a9f0918108...80a380792db2a4a63b01cfe880f48b62614ebeec)

This was a read-only source review against `CLAUDE.md`, the ADRs, and the milestone briefs. I checked the findings against reviews 1–7 and the recorded known misses. Review 8 was unavailable on the reviewed tree, so I could not verify deduplication against it. The workspace had no checkout and shell access to GitHub failed. I read the pinned source through GitHub and ran isolated arithmetic and in-memory SQLite checks. The repository test suite, full historical replays, and Windows/Linux parity runs remain unverified. No files were written.

## P1 findings

No P1 finding established.

## P2 findings

### 1. Mortality can credit the heir with salary paid to the deceased founder

Payroll runs in phase 6, mortality can change the founder in phase 10, and the personal salary entry in phase 12 resolves the founder and salary again. The company therefore pays one person while the personal books credit another. The estate also settles before the deceased founder’s final salary reaches it. This breaks formulas §32.2 and §52.4. [Payroll](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/turn.py#L390-L395) · [Mortality phase](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/turn.py#L534-L545) · [Personal salary](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/founder/personal.py#L104-L118)

Use a January dynasty fixture with a salaried founder, an employed heir on a different salary, and a forced mortality draw. Compare the payroll recipients with the personal salary entries and estate cash. Credit personal salary from the payroll result before estate settlement. The regression should run a full turn, assert the exact net salary included in the estate, and cold-reload the save to check both books.

### 2. An inherited foundation comes back under the deceased founder after a cold reload

Estate settlement replaces the foundation’s `person_id` with the heir’s ID. `sync_founder` writes that new primary key and leaves the old row in SQLite. A cold load retrieves both. The duplicate can carry the old foundation record into subsequent calculations, and the cold state disagrees with the committed state held in memory. This breaks formulas §45.6 and §52.4 and ADR-0004’s persisted-state contract. [Estate transfer](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/family/estate.py#L311-L353) · [Foundation load and sync](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/db/founder_io.py#L41-L44) · [Foundation upsert](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/db/founder_io.py#L94-L96)

Endow the founder’s foundation, force a January death with an eligible heir, and reopen the save cold. Compare the foundation keys and endowment balances with the turn result. Delete removed foundation keys and upsert the surviving keys within the existing turn transaction. The regression should assert one surviving foundation, conserved endowment, and equality between the warm and cold states.

### 3. The conglomerate view exposes hidden construction overruns

The capital-allocation panel calculates committed capital from `Facility.capex_cents - capex_paid_cents`. For a cell plant, `capex_cents` already includes the hidden overrun drawn at order time. The Vehicles screen deliberately shows the estimate and payments made. When an industry has one building facility, the conglomerate response and those payments disclose its exact final construction cost. This breaks ADR-0007, formulas §49.7, and M43’s displayed-values requirement. [Conglomerate allocation](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/api/conglomerate_views.py#L79-L101) · [Cell-plant order](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/vehicles/actions.py#L184-L188) · [Vehicles response](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/api/vehicle_views.py#L337-L355)

Use a group with an active vehicle industry and one cell plant under construction. Hold the public quote and payments fixed while varying only the hidden overrun. `/conglomerate` changes. Build the allocation from the same public construction projection as the facility screens. Add a paired-state response test and apply it to every facility kind mapped into the panel.

### 4. The conglomerate view and shareholder letter include activity during gaps in ownership

The read model collapses all ownership runs for a company into a single interval using the earliest start and latest end. After a sale and reacquisition, the ledger query includes the months when the company belonged to someone else. The same read model feeds the shareholder letter. This breaks formulas §31.1 and M43’s requirement to report the group’s own books. [Interval construction and ledger query](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/db/conglomerate.py#L35-L56) · [Ledger query](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/db/conglomerate.py#L80-L102) · [Shareholder letter](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/db/events.py#L179-L196)

Use a subsidiary held in two disjoint periods and post a distinctive sale in the intervening year. The group’s revenue and the letter facts include that sale after reacquisition. Query the union of actual ownership intervals, coalescing overlapping intervals when the operating and holding-company paths both reach the subsidiary. Test that entries inside either interval count exactly once and that the gap sale reaches neither the API response nor the letter prompt.

### 5. Classified contracts lose their clearance requirement when the tender is pruned

An active contract stores its tender ID and delivery dates, but no clearance level. The tender is removed 36 months after award by default, even if the contract is still active. On the next delivery month, the missing tender becomes `"none"` and the company can book revenue without cleared staff or a cleared facility. This breaks formulas §57.2–§57.3. [Contract creation](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/government/delivery.py#L45-L65) · [Delivery check](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/government/delivery.py#L126-L149) · [Tender pruning](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/government/tenders.py#L204-L220)

Award a seeded five-year classified contract, retain the required clearances through the tender’s retention window, then remove the last qualifying clearance while delivery is still active. The next month still pays. Preserve the awarded requirements on the contract or retain the tender while delivery depends on it. Handle existing saves whose tenders are already gone explicitly. Test clearance loss after the pruning boundary, across a cold reload, and assert zero delivery revenue followed by default after the configured lapse.

### 6. Pharmaceutical sales use the previous month’s market ceiling adjustment

Phase 5 books pharmaceutical sales using the stored market level. Phase 12 computes the level for that same month from that month’s data and ceiling. Thus demand can use an addressable base above the ceiling even when the later update pulls it back under. This breaks formulas §54.1 and §55.4. [Sales phase](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/turn.py#L375-L384) · [Ceiling update call](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/pharma/month.py#L51-L59) · [Level calculation](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/pharma/ceilings.py#L61-L77)

Use a post-2025 area-region at 99.9 against a ceiling of 100 with 1% uncapped monthly growth. The stale level gives sales a base of 100.899. The later saturation calculation gives 99.900999. Compute the current month’s level before demand, apply a final clamp, and retain the documented treatment of markets already above their ceiling at the historical boundary. Test the level actually read by sales at the boundary and during a later near-ceiling month.

### 7. Customer flights can launch while their vehicle is grounded

A failure puts the remaining whole flights back into `pending`. On the next month the customer-flight loop sees the backlog and attempts a launch without checking `grounded_until`. Blocking new sales does not stop the backlog. That flight can change the vehicle’s reliability, grounding period, and flight history during the investigation. This breaks formulas §56.1. [Customer-flight loop and backlog](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/space/flights.py#L33-L86) · [Grounding rule](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/docs/formulas.md#L4081-L4086)

Sell at least two whole flights and force the first to fail. Advance the next grounded month with no new sales. The pending flight can fly. Check grounding before consuming the backlog or drawing an outcome. The regression should assert that pending work, flight counts, and launch history stay unchanged throughout grounding and that the backlog resumes after clearance.

### 8. A successful out-licensed programme can stall before its approval milestone

Out-licensing transfers the programme to the rival. The rival advances trials automatically, but after a successful Phase III `next_trial()` returns `None` and the rival takes no further action. The player can no longer file because actions require ownership. Consequently an unapproved out-licensed programme can finish Phase III successfully and remain there indefinitely, with no approval milestone or royalties. This breaks the licence settlement in formulas §55.5. [Out-licence transfer](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/pharma/licensing.py#L180-L222) · [Rival pipeline](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/pharma/pipeline.py#L446-L483) · [Milestone and royalties](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/pharma/licensing.py#L310-L363)

Out-license a Phase III programme and force a successful readout. Advance through the ordinary filing and review horizon. No rival filing appears. Have the rival file through the existing approval path once eligible. A seeded end-to-end test should reach approval, post the final milestone once, and reconcile subsequent royalties in both companies’ ledgers.

### 9. Unrelated activity changes vehicle incident and bought-launch draws

M38 shares one generator across a line’s regions and skips draws for regions without exposure. M40 keys a bought launch with `len(flown)`, which counts launches by earlier constellations. Both let unrelated activity change an otherwise identical entity’s draw, contrary to ADR-0013’s order-independence rule and the stable-identity requirement for streams 63 and 68. [Vehicle incident draws](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/vehicles/autonomy.py#L93-L109) · [Bought-launch key](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/space/constellation.py#L235-L244) · [ADR-0013](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/docs/adr/0013-rng-stream-per-use-and-entity-keys.md#L9-L17)

With the same seed and turn, add exposure only to a region earlier in iteration order and inspect the unchanged region’s draw. Separately, insert an earlier constellation that buys a flight and inspect the unchanged constellation’s first bought-launch key. Key the first by product and region, and the second by constellation and its own flight ordinal. Add seeded isolation tests that compare the unchanged entity’s draw in each pair.

### 10. The money guard misses binary-float arithmetic that posts wrong cents

The guard detects money primarily by the substring `cents`. It misses monetary values carried in aliases such as `revenue`, `sales`, and `cost`. Even `round(cents * s)` can pass when the rate comes from a loop target whose type the scanner does not propagate. A generic rival with `50,000,030` cents of monthly revenue and the shipped 55% COGS rate posts `27,500,017` cents. Exact half-even arithmetic posts `27,500,016`. Each entry balances arithmetically while recording the wrong amount. This breaks ADR-0003 and affects formulas §55.4–§55.5. [Rival cost posting](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/pharma/rivals.py#L199-L227) · [Other monetary aliases](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/pharma/licensing.py#L349-L370) · [Guard rules](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tests/money_guard.py#L144-L203)

Use the exact money helpers for the postings and trace money aliases and typed mapping values in the guard. Add a posting test for the concrete half-cent case and scanner fixtures for monetary assignments, tuple unpacking, and mapping iteration. The tests should fail independently when either the posting or the guard regresses.

## P3 findings

### 11. Space history enables a service after its opening month’s sales have run

The space history pin runs in phase 9, after phase 5 books sales. When the source data opens a line during the campaign, its previous month’s `None` price is still in force during the opening month’s sales. For example, Starlink’s paid beta opens in October 2020 in `space.yaml`, but the October market runs before its price is set. This breaks the dated openings in formulas §56.3–§56.4. [Starlink service date](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/data/space.yaml#L244-L258) · [Price gate](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/space/history.py#L67-L91) · [History phase](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/space/phase.py#L106-L115)

Run September, October, and November 2020 with the historical incumbents and inspect dated Starlink sales entries. Apply dated openings before the sales phase. Test the three months through the full turn, including zero sales before the opening.

### 12. Some derived caches key on object IDs without keeping the objects alive

`arrived()` keys on `id(data)` and stores a tuple of era definitions and arrivals. It does not keep `GameData` alive. The saturation caches have the same pattern with `data` and `balance`. If the caller retains the state, drops the input object, and its address is reused for different rules, the cache can return the old computation. This breaks M45’s cache equivalence requirement and ADR-0002’s input contract. [Era cache](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/research/eras.py#L47-L56) · [Saturation caches](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/markets/saturation.py#L123-L160)

Hold one state, populate the cache, replace the external input, and simulate a reused identity in the unit test. Compare the result with a fresh recomputation. Retain the external inputs with the cached value and validate their identity, as the payroll cache does. Test both repeated calls with the same inputs and distinct rule objects sharing the simulated cache key. [Payroll cache pattern](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/hiring/phases.py#L306-L315)

### 13. Fixed-price delivery can settle a different total from the accepted price

Each month independently rounds `value_cents / term`. A fully delivered 24-month contract for `12,000,007` cents books `12,000,000` cents. Other remainders can overpay. This breaks the fixed-price settlement in formulas §57.2 and the exact-money requirement in ADR-0003, although each monthly entry balances. [Fixed-price computation](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/government/delivery.py#L152-L181)

Run a fixed-price contract through every month with no lapse and all options exercised. Allocate cents by installment index or the difference between successive rounded cumulative entitlements. Test remainder cases on both sides of the rounding boundary and assert the exact lifetime amount in both the contract record and the ledger.

### 14. The pre-2040 guard can accept a change shared by both campaign settings

M43 regenerated `m37_pre_2040_hashes.json` from current standard-mode runs with M37’s fields removed. Both current modes are then compared to that recording. This still checks parity between the settings, but after a refresh it cannot detect an M37 rule that moved earlier in both modes. That leaves a gap in the separate pre-M37 comparison required by formulas §52.5 target 1. [Fixture refresh](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/CHANGELOG.md#L14) · [Regression test](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tests/balance/test_m37_balance.py#L23-L27)

Move one dynasty-only rule into 2039 in a test mutation and regenerate the fixture. A change shared by both settings becomes part of the reference. Keep the mode-parity check and add a same-code differential replay with the M37 rules disabled in the reference arm, so approved changes from other milestones can run on both sides. Test the guard by moving one rule across the January 2040 boundary and asserting that the replay identifies the first differing month.

## Other checks

- The M43a calibration patch directly changes AI models, cloud hosting, developer tools, and servers. Server CPU demand follows the affected categories as documented. I found no additional direct pre-2026 recalibration in that patch. [M43a brief](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/docs/tasks/M43a-market-sizes-and-saturation.md#L55-L59)
- The IPO gate applies `economy_scale.money` once with exact arithmetic. The checked inputs give `2,046,090,000` cents of game ARR. `steady_regions` calls the split before hiring and disables `steady`’s marketing pass. [IPO gate](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/sim/markets_public/ipo.py#L62-L90) · [Marketing call order](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/balance/strategies_v2.py#L271-L294)
- The Makefile wires both 2039 saves to the 400 ms runner-adjusted median and preserves the raw 1,000 ms guard. The 2069 median uses the runner ratio and the recorded exception. Workflow limits are 50 minutes for `check`, 180 for nightly, and 360 for weekly. These are configuration checks. [Timing recipes](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/Makefile#L45-L73) · [Check](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/.github/workflows/check.yml#L23-L29) · [Nightly](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/.github/workflows/nightly.yml#L39-L44) · [Weekly](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/.github/workflows/weekly.yml#L27-L34)
- The turn path keeps state, ledger, snapshot, and turn counter writes inside one SQLite transaction. Letter rendering uses the existing post-commit text service. The inspected pharma projection uses observations and public estimates for readouts and valuation, and the letter prompt uses the conglomerate ledger read model. These source checks leave crash injection and full endpoint and prompt comparisons unverified. [Turn transaction](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/db/repository.py#L900-L927) · [Pharma projection](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/api/pharma_views.py#L169-L192) · [Letter rendering](https://github.com/Reece77/Tech_Executive_Tycoon/blob/80a380792db2a4a63b01cfe880f48b62614ebeec/backend/tst/db/events.py#L173-L219)

**Severity count — P1 0 · P2 10 · P3 4 · Total 14**
## Resolution (product manager, 2026-11-22)

No P1. All fourteen findings go to **M43r** (`docs/tasks/M43r-review-9-fixes.md`), in two lanes so the turn-order changes stay together.

| # | Severity | Finding | Lane |
| --- | --- | --- | --- |
| 1 | P2 | Mortality credits the heir with the deceased founder's salary | A |
| 2 | P2 | An inherited foundation returns under the deceased founder after a cold reload | A |
| 3 | P2 | The conglomerate view exposes hidden construction overruns | A |
| 4 | P2 | The conglomerate view and letter include gaps in ownership | A |
| 5 | P2 | Classified contracts lose their clearance requirement when the tender is pruned | B |
| 6 | P2 | Pharma sales use the previous month's ceiling adjustment | A |
| 7 | P2 | Customer flights launch while their vehicle is grounded | B |
| 8 | P2 | A successful out-licensed programme stalls before approval | B |
| 9 | P2 | Unrelated activity changes vehicle-incident and bought-launch draws | B |
| 10 | P2 | The money guard misses binary-float arithmetic under other names | B |
| 11 | P3 | Space history opens a service after its first month's sales | A |
| 12 | P3 | Derived caches key on object ids without keeping the objects alive | B |
| 13 | P3 | Fixed-price delivery settles a different total from the price | B |
| 14 | P3 | The pre-2040 guard can accept a change shared by both settings | A |

Lane A holds every change to the turn's phase order (findings 1, 6 and 11) so they don't conflict.
