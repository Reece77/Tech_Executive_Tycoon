# M36r: Codex review 7 fixes, and a money-exactness guard

**Goal:** fix the five findings of Codex review 7 (no P1), each with the regression test the finding asks for, written first and seen failing. End the recurring float-money defect with an audit and a guard.

**Review:** `docs/reviews/codex-review-7.md` · **Formulas:** §31, §40.2, §40.7, §40.12, §44.1, §44.4, §45.6 · **ADRs:** 0003, 0020, 0021 · **Depends on:** M36 (`m36-done`), M30 (`m30-done`) · **Lane:** a fix lane beside M32, M33 and M34

## Lane

- Its own session and branch (`m36r-review7`) from `main`. Merges whenever ready, **before M32** (which merges last).
- **M36r owns** the files the findings name: `tst/sim/automation/run.py`, `scope.py` and `limits.py`; `tst/sim/contracts/termination.py`; `tst/sim/platforms/fees.py`; `tst/sim/finance/consolidation.py`; `tst/sim/family/estate.py`; and, for sub-task 2's audit, any money formula elsewhere in `tst/sim/` (small, separate commits per module, named in the PR).
- **Coordinate:** M34 may touch `platforms/` for duty hooks (fee-rule rows and forced settings). Keep `fees.py` changes to the money arithmetic and the group-pair classification, and merge `main` often. M32 and M33 own `power/` and `equipment/`. If the audit finds a float in their new code before they merge, leave a note in their PRs instead of editing.
- **Golden snapshots** may move by a cent where rounding was wrong. If so, regenerate with the reason in CHANGELOG, and show which values changed.
- **CLAUDE.md §9's decision rules apply.**

## Sub-tasks (commit after each; regression test first, seen failing)

1. **Never-actions stay the founder's** (finding 1). When an approved proposal of kind `set_grey_route` or `terminate_contract` is carried out, the actor is always the founder, inside a subsidiary too. Record the required actor on the proposal and enforce it centrally. Keep the runner's direct refusal.
   - **Tests:** end-to-end approval inside a subsidiary for both kinds:
     - the proposal reaches the player;
     - approving acts as the founder and changes the subsidiary's record and books once;
     - declining changes nothing;
     - a cold reload keeps the result;
     - the decision log never names a delegate for either kind.
2. **Exact money everywhere** (findings 2 and 3, and the pattern):
   - Automation commitments come from the same integer-cent quote that creates the deal, with rates applied by `money.times` and fractions rounded half-even once.
   - Platform fees use exact fractions for `paid_share`, user shares and fee rates, aggregated exactly and rounded once.
   - **Audit:** list every place in `tst/sim/` where a money amount is multiplied or divided by a float (a table in Decisions made: module, line, fixed or proven exact) and fix each.
   - **Guard:** a test that scans `tst/sim/` for money-typed arithmetic with float literals or float-typed rates outside `money.py`'s helpers. An AST check is preferred to a grep. It fails CI on a new occurrence, with an explicit allow-list comment for any proven-exact case.
   - **Tests:** Codex's two boundary regressions (commitment equal to the quote's obligation, and cost equal to the limit always making a proposal; the 1,750 × 0.4 × 0.7 × 0.15 fee case through `fees_due` and `fee_entries`). Add rational-reference property tests for commodity contracts, offtakes and platform fees that compute the expected cents independently.
3. **Group OS licences eliminate** (finding 4): own-OS licence fees between group companies post intercompany sales and purchases, as app-store fees do.
   - **Tests:** a property or integration test for subsidiary, parent and sister-company licences: every entity balances, cash moves between the right entities, the consolidated platform-fee lines net correctly, and a reload is identical.
4. **The estate pays what it owes** (finding 5): settlement realises every taxable asset in the quote in a defined order (personal cash, then family office, public holdings, angel stakes at their exit or secondary value, then company shares), or carries a real estate-tax payable that reduces what passes to the heir. Record only actual payments, and make the displayed cumulative tax equal the postings.
   - **Tests:** table-driven or property cases where the estate is mostly the family office, public holdings or angel stakes. Check against independent sums: tax paid equals the quote; gross estate equals tax plus net inheritance; no value disappears; and a cold reload agrees.
   - Remove the existing property's acceptance of `paid = min(tax, cash + share proceeds)`. It encoded the gap; say so in Decisions made.
5. **Close-out:** a Resolution line per finding in `codex-review-7.md` (fixed, with the test's name), CHANGELOG, and the README index row.

## Acceptance criteria

- [ ] Each of the five findings has a regression test that fails on `m30-done` and passes on this branch.
- [ ] No delegate is ever the actor of a grey route or a contract termination, approved or not (property test over random proposals and subsidiaries).
- [ ] The float-money guard runs in CI and passes, and the audit table is complete.
- [ ] Every entity's books balance and consolidation eliminates every intra-group platform payment (property tests).
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m36r-done`.

## Decisions made

1. **The required actor lives on the proposal.** `AutoRun.propose` adds `actor: "founder"` to an `auto` proposal for every founder-only kind (`NEVER_ACTIONS` and `FOUNDER_ACTIONS`); `scope.proposal_actor` returns the founder for that param, for the player's company, and for a founder-only kind on an older proposal without the param. JSON params: no migration. The M27b test that turned a founder proposal into a `create_plan` one now drops the param too (a real `create_plan` proposal never carries it).
2. **Commitments read the deal's own quote.** `limits.chain_commitment` calls `contract_quote` / `offtake_quote`; an invalid quote (a refused supplier, a term out of range) commits 0, and the action is then refused when applied, as before. The quotes' year value is `round(offtake.exact_value(...))`; `value_cents` stays for display and physical ratios.
3. **Fees round once per (seller product, owner) pair** (`fees.pair_fees`); `fees_due` keeps per-key display amounts. The M31 property `test_fee_postings_balance` (and the group test) now compares owners' earnings with `pair_fees` instead of the per-key sum: the same check (owners earn what sellers pay), against the amounts the books post.
4. **Group OS licences use the app-store classification** (`fees.intercompany`: both in the group and not the same company).
5. **The estate realises assets; no payable.** Order: cash, family office, public holdings (by company), angel stakes (by id, whole, at `stake_value_cents`; new status `sold`), company shares. The quote values each asset at its realisation price and the tax is at most the taxable estate, so the whole tax is always paid; only actual payments are recorded. The quote no longer counts shares bought in the listed company twice (they are in the head's cap-table shares). The M36 property's `paid = min(tax, cash + proceeds)` encoded finding 5's gap: it is now `paid = tax`.
6. **What "exact" means in the audit.** An amount (posted, quoted, stored, committed, or compared with cash as an amount) is computed from exact rationals (`money.exact` reads a float as the decimal it was written as) and rounded half-even once. A float **unit rate** (cents a unit, a wafer, a CU-month), a **ratio** or score between amounts, an **estimate** only ranked or compared, and **display** text are not amounts: they are tagged `# money-exact: <why>`, and the amount a rate makes is rounded once where it is posted. Converting the rate functions themselves to rationals would touch every price path and its performance; that is a follow-up, not this lane.
7. **The guard** (`tests/money_guard.py`, run by `tests/unit/test_money_guard.py`): an AST scan, no new dependency. Money = a name containing `cents`; float = a float literal, `float()`, a `math` function, `/` outside exact arithmetic, or a field, parameter or function declared `float` in `tst/sim/`. Name collisions can give false positives, answered with `# money-exact: exact` after checking by hand (two cases). The scanner has its own tests (a snippet with known hits, the allow comment).
8. **Lines in other lanes' files in flight are deferred, not edited** (seven: M32's `mining/phase.py` sustaining capex, `refining/quote.py` unit estimate and `fabs/plants.py` power rate; M33's `fabs/actions.py` upgrade capex): editing them would conflict with M32's and M33's open edits. They are listed by code in the guard's `DEFERRED` (a fixed one must leave the list) and handed over in the PR.
9. **Golden snapshots**: see CHANGELOG (GOLDEN_RESULT).

### The float-money audit

Every site the guard's rule finds in `tst/sim/` on `main` before M36r (`62551892`), with line numbers there. "fixed": the line now computes in exact rationals (a few lines the formatter re-wrapped after tagging also read "fixed"; the tag is on the new line). 189 sites: 97 fixed, 85 tagged (37 rates, 39 ratios, 4 estimates, 3 display, 2 exact), 7 deferred.

| Module | Line | Outcome | Code |
| --- | --- | --- | --- |
| `automation/chain.py` | 710 | tagged: display | `npv = (p.npv_mid_cents or 0) / 100` |
| `automation/chain.py` | 850 | tagged: rate | `fc.slot_price_cents(state, fab, b, data)` |
| `automation/digest.py` | 178 | tagged: ratio | `share = d.commitment_cents / max(o.limit_cents, 1)` |
| `automation/limits.py` | 30 | fixed | `return round(market_mid_cents(mid, bp) / MONTHS_PER_YEAR)` |
| `automation/limits.py` | 142 | fixed | `return round(value_cents(volume * years, price, good, data) * share)` |
| `chips/chips.py` | 99 | tagged: rate | `return fm.node_price_cents(state, node, balance, data) * mult` |
| `chips/chips.py` | 101 | tagged: rate | `return ch.types[chip_type].wafer_cents * index * mult * fm.price_factor(state, balance,...` |
| `chips/chips.py` | 124 | tagged: rate | `price = sum(s.volume * s.unit_cents for s in lots) / volume` |
| `chips/chips.py` | 145 | tagged: rate | `price = sum(c.units * c.price_cents for c in contracts) / wafers` |
| `chips/chips.py` | 181 | tagged: rate | `cost = sum(s.starts * s.cost_per_start_cents for s in shares)` |
| `chips/chips.py` | 220 | tagged: rate | `return share * balance.chips.packaging_cents + (1 - share) * contract` |
| `chips/formulas.py` | 16 | tagged: rate | `return wafer_cents / (per_wafer * yield_rate) + packaging` |
| `commodities/costs.py` | 78 | tagged: rate | `return own * base_cents, []` |
| `commodities/costs.py` | 83 | tagged: rate | `lines.append(CostLine(g, w, idx, base_cents * lead * mix.share * w * idx))` |
| `commodities/costs.py` | 84 | tagged: rate | `return own * base_cents * (1 - mix.share), lines` |
| `commodities/costs.py` | 93 | tagged: ratio | `out[g] = base_cents * mix.share * w / (usd_mean * CENTS)` |
| `commodities/offtake.py` | 224 | fixed | `value_cents(unused, deal.signing_price, deal.good, data)` |
| `commodities/power.py` | 23 | tagged: rate | `return base_cents * power_index` |
| `contracts/termination.py` | 187 | fixed | `value = Fraction(c.units * c.price_millicents, MILLICENTS_PER_CENT)` |
| `events/describe.py` | 235 | tagged: display | `cents = effect.value * loan.balance_cents * share / BP` |
| `events/triggers.py` | 95 | tagged: ratio | `s = below_strength(e.salary_cents / mid, t["underpaid"]) if mid else None` |
| `exploration/pipeline.py` | 316 | fixed | `base = db.hole_base_cents + db.hole_per_m_cents * block.depth_m` |
| `exploration/pipeline.py` | 326 | fixed | `round((db.hole_base_cents + db.hole_per_m_cents * lo) * index),` |
| `exploration/pipeline.py` | 327 | fixed | `round((db.hole_base_cents + db.hole_per_m_cents * hi) * index),` |
| `exploration/pipeline.py` | 337 | fixed | `cost = round(eb.survey.cost_cents * _region_cost(data, project.region))` |
| `fabs/actions.py` | 308 | deferred to M33 (file in flight) | `capex = round(q.capex_cents * fb.upgrade.capex_share)` |
| `fabs/formulas.py` | 14 | fixed | `return round(starts * MONTHS * capital_cents * scale * cost_mult)` |
| `fabs/formulas.py` | 78 | tagged: rate | `return wafer_cents * (index_now / index_ref) * (1 - decay) ** steps * factor` |
| `fabs/formulas.py` | 93 | tagged: rate | `return wafer_cost_cents / good + packaging_cents if good > 0 else float("inf")` |
| `fabs/foundry.py` | 71 | tagged: rate | `return fm.node_price_cents(state, fab.node, balance, data) * balance.fab.slot.discount` |
| `fabs/foundry.py` | 96 | tagged: rate | `ceiling = slot_price_cents(state, fab, balance, data) * fb.max_price` |
| `fabs/market.py` | 243 | tagged: rate | `return node_price_cents(state, node, balance, data) * balance.fab.slot.discount` |
| `fabs/market.py` | 307 | tagged: rate | `return nodes_file(data).euv.tool_cents * goods.index_now(state, EUV_GOOD, data) / ref` |
| `fabs/plants.py` | 308 | deferred to M32 (a rate) (file in flight) | `return mwh * balance.refining.power_cents_per_mwh * power.index(state, facility.region,...` |
| `fabs/plants.py` | 379 | fixed | `materials = round(run * materials_cents(state, fab, balance, data))` |
| `fabs/plants.py` | 380 | fixed | `power_ = round(run * _power_cents(state, fab, facility, balance, data))` |
| `facilities/compute.py` | 62 | tagged: rate | `return spec.spot_cents * index` |
| `facilities/compute.py` | 116 | fixed | `s.customers * category.market(s.segment).hosting_cents / spot for s in segments` |
| `facilities/compute.py` | 229 | tagged: ratio | `return spot_unit_cents(state, good, balance, data) / spot_unit_cents(` |
| `facilities/formulas.py` | 71 | tagged: ratio | `return hosting_base_cents / spot_cents` |
| `finance/formulas.py` | 83 | fixed | `traction = round(arr_cents * arr_multiple(g6, climate, fb))` |
| `finance/formulas.py` | 92 | tagged: ratio | `return sb.optimism * base_cents / cap_cents` |
| `finance/formulas.py` | 121 | fixed | `return round(base_cents * bias * math.exp(sd * z))` |
| `finance/formulas.py` | 132 | fixed | `hi = min(check_max_cents, round(max_of_pre * pre_money_cents))` |
| `founder/angel.py` | 318 | tagged: ratio | `f = (cents - ab.min_cheque_cents) / (ab.seed_full_cents - ab.min_cheque_cents)` |
| `founder/angel.py` | 372 | fixed | `extra = round(cents * ab.skill_runway * max(0.0, mean_true_skill(founder, data) - SKILL...` |
| `founder/angel.py` | 460 | fixed | `market_salary_cents(role.key, level, balance, data) * balance.rivals.startup.salary_mult` |
| `founder/effects.py` | 104 | tagged: ratio | `return fb.hiring * min(1.0, f.last_grant_cents / CENTS_A_DOLLAR / fb.hiring_full_dollars)` |
| `founder/foundation.py` | 100 | tagged: ratio | `dollars = grant_cents / CENTS_A_DOLLAR` |
| `founder/foundation.py` | 113 | fixed | `cents = round(personal.endowment_cents(state, pid) * balance.foundation.payout)` |
| `founder/influence.py` | 97 | tagged: ratio | `return ib.rate * math.sqrt(spend_cents / CENTS_A_DOLLAR / ib.unit_dollars)` |
| `founder/legacy.py` | 43 | tagged: ratio | `giving = GIVING_POINTS * math.log10(1 + grants_cents / unit)` |
| `founder/personal.py` | 149 | fixed | `price = round(public.price_cents * (1 - cb.secondary_discount))` |
| `founder/shares.py` | 379 | fixed | `due = round(t.gain_cents * (1 + pb.fine_mult))` |
| `founder/wealth.py` | 160 | tagged: ratio | `return pb.legacy_points * math.log10(1 + max(0, net_worth_cents) / unit)` |
| `geo/marketing.py` | 32 | tagged: ratio | `revenue[home] = sum(s.customers * (s.price_cents or 0) for s in state.segments_of(produ...` |
| `geo/marketing.py` | 35 | tagged: ratio | `revenue[rs.region] += rs.customers * (rs.price_cents or 0)` |
| `geopolitics/supply.py` | 227 | tagged: rate | `total += line.cents * x.share * x.premium` |
| `geopolitics/tariffs.py` | 145 | tagged: rate | `contract_cents = row.chip_cents - sold_own * balance.chips.packaging_cents` |
| `geopolitics/tariffs.py` | 157 | tagged: rate | `out[country] = out.get(country, 0.0) + contract_cents * weight` |
| `group/capital.py` | 581 | tagged: exact | `total = bp + (round(Fraction(old.stake_bp) * pre / (pre + action.cents)) if old else 0)` |
| `group/transfer.py` | 253 | fixed | `acc[0] += lot.taken * lot.unit_cents` |
| `group/transfer.py` | 254 | fixed | `acc[1] += lot.taken * lot.market_cents` |
| `hardware/formulas.py` | 15 | tagged: rate | `return base_cents * index` |
| `hardware/formulas.py` | 55 | tagged: rate | `return (fixed_cents + variable_cents * used + depreciation) / good` |
| `hardware/models.py` | 46 | tagged: rate | `return self.price_millicents / MILLICENTS_PER_CENT` |
| `hardware/production.py` | 364 | fixed | `bom = round(units * unit_bom_cents(state, product, balance, data))` |
| `hardware/production.py` | 373 | fixed | `+ bought * chips.bought_price_cents(data, balance, chip_type)` |
| `hardware/production.py` | 385 | fixed | `variable = run * balance.facility.kinds[balance.hardware.plant_kind].variable_cents` |
| `hiring/formulas.py` | 102 | tagged: exact | `return monthly_salary_cents(annual_salary_cents) * payroll.severance_months` |
| `hiring/formulas.py` | 115 | tagged: ratio | `raw = morale.pay_slope * (salary_cents / market_mid - 1)` |
| `hiring/phases.py` | 171 | tagged: ratio | `ratio = offer.salary_cents / expectation` |
| `hiring/phases.py` | 341 | fixed | `benefits[None] += round(pool.headcount * benefits_cents(pay, balance.payroll))` |
| `hiring/phases.py` | 342 | fixed | `office[None] += round(pool.headcount * balance.payroll.office_cost_per_head_cents)` |
| `hiring/rules.py` | 91 | tagged: ratio | `ratio = salary_cents / expectation if expectation else 0.0` |
| `markets_public/capital.py` | 36 | fixed | `return round(public.price_cents * (1 + balance.public.capital.buyback_premium))` |
| `markets_public/capital.py` | 100 | fixed | `price = round(public.price_cents * (1 - cb.secondary_discount))` |
| `markets_public/formulas.py` | 37 | fixed | `return round(arr_cents * m)` |
| `markets_public/formulas.py` | 41 | fixed | `return round(value_cents / shares) if shares > 0 else 0` |
| `markets_public/formulas.py` | 53 | fixed | `return round(value_cents * quality * ambition * (1 - dual_discount) / shares_after)` |
| `markets_public/formulas.py` | 76 | fixed | `return round(gross_cents * fee)` |
| `markets_public/formulas.py` | 86 | fixed | `return max(1, round(value_cents * sentiment / shares)) if shares > 0 else 0` |
| `markets_public/formulas.py` | 93 | tagged: ratio | `return min(ab.max, ab.min + int(math.log2(cap_cents / ab.base_cap_cents)))` |
| `markets_public/formulas.py` | 98 | tagged: ratio | `ratio = target_cents / price_cents if price_cents > 0 else 1.0` |
| `markets_public/formulas.py` | 108 | tagged: ratio | `return actual_cents / guided_cents - 1 if guided_cents > 0 else 0.0` |
| `markets_public/formulas.py` | 130 | fixed | `return round(op_cents * BP / revenue_cents) if revenue_cents > 0 else 0` |
| `markets_public/ipo.py` | 200 | fixed | `fee = round(pf.fee_cents(expected, bank.fee) * ib.pull_fee_share)` |
| `markets_public/ipo.py` | 333 | tagged: ratio | `ambition = listing.price_cents / (fair * discount) if fair > 0 else 1.0` |
| `markets_public/ipo.py` | 335 | fixed | `close = max(1, round(listing.price_cents * (1 + r)))` |
| `markets_public/public.py` | 263 | fixed | `expected = round(w * g.revenue_cents + (1 - w) * g.consensus_revenue_cents)` |
| `mining/actions.py` | 553 | fixed | `first = q.estimate_cents / max(1.0, span.lo)` |
| `mining/actions.py` | 761 | fixed | `cost = round(mine.capacity_t / 1000 * cb.restart_cents_per_kt)  # tunable-exempt: t to kt` |
| `mining/formulas.py` | 16 | fixed | `return round(estimate_design_cents * float((capacity / design) ** scale))` |
| `mining/formulas.py` | 73 | fixed | `return round(basis_cents * min(1.0, ore_mined / ore_estimate))` |
| `mining/formulas.py` | 77 | fixed | `return round(revenue_cents * rate)` |
| `mining/formulas.py` | 106 | fixed | `return round(product_t * per_t_cents)` |
| `mining/models.py` | 108 | fixed | `return round(self.estimate_cents * (1 + self.hidden_overrun))` |
| `mining/phase.py` | 123 | tagged: display | `pct = round(100 * (mine.hidden_total_cents / mine.estimate_cents - 1))` |
| `mining/phase.py` | 135 | fixed | `pay = round(mine.estimate_cents / (mine.ready_turn - mine.ordered_turn))` |
| `mining/phase.py` | 288 | fixed | `else min(left, math.ceil(mine.aro_cents / balance.mining.reclamation_months))` |
| `mining/phase.py` | 355 | deferred to M32 (file in flight) | `sustaining = mb.sustaining_share * mine.capex_paid_cents / CENTS / 12 if running else 0.0` |
| `mining/phase.py` | 493 | fixed | `depletion = min(mine.book_cents, round(mine.book_cents * min(1.0, ore_mt / est_left)))` |
| `mining/phase.py` | 713 | deferred to M32 (file in flight) | `sustaining = mb.sustaining_share * mine.capex_cents / CENTS` |
| `mining/risk.py` | 573 | fixed | `price = round(xp.sale_price_cents(state, p, balance, data) * rb.buy_share)` |
| `mna/formulas.py` | 24 | fixed | `half = abs(value_cents) * half_share` |
| `mna/formulas.py` | 73 | tagged: ratio | `return monthly_costs_cents > 0 and cash_cents < mb.distress_months * monthly_costs_cents` |
| `mna/formulas.py` | 108 | tagged: ratio | `return price_cents / market_cap_cents - 1 if market_cap_cents > 0 else math.inf` |
| `mna/formulas.py` | 119 | fixed | `return round(price_cents * tb.fee_bp / 10_000)  # tunable-exempt: basis points` |
| `mna/integration.py` | 392 | fixed | `paid += round(e.salary_cents / 12 * ib.severance_months)  # tunable-exempt: months a year` |
| `mna/rivals.py` | 40 | tagged: ratio | `if cash <= mb.rival_cash_months * deals.monthly_costs_cents(state, buyer.id, balance, d...` |
| `modes/rankings.py` | 57 | fixed | `e.salary_cents / mid for e in staff if (mid := market_mid_for(state, e, balance, data))...` |
| `org/authority.py` | 236 | fixed | `price = min(ceiling, round(seg.price_cents * (1 + step)))` |
| `org/authority.py` | 340 | fixed | `amount = max(b.debt.min_cents, round(terms.max_cents * b.exec_authority.loan_share))` |
| `org/pitches.py` | 187 | fixed | `total += sum(s.customers * (s.price_cents or 0) for s in state.segments_of(product_id))` |
| `org/pitches.py` | 191 | fixed | `total += sum(s.customers * (s.price_cents or 0) for s in rows)` |
| `org/pitches.py` | 209 | fixed | `return round(market_mid_cents(mid, bp) / MONTHS_PER_YEAR)` |
| `org/pitches.py` | 286 | tagged: estimate | `revenue = customers * m.reference_price_cents` |
| `org/pitches.py` | 350 | fixed | `s.customers * data.category(p.category).market(s.segment).hosting_cents` |
| `org/pitches.py` | 538 | fixed | `b.payroll.office_cost_per_head_cents * b.office.lease_discount * city.rent_index` |
| `org/pitches.py` | 579 | tagged: rate | `fee = sum(c.units * c.price_cents for c in contracts) / units` |
| `org/pitches.py` | 629 | fixed | `push = max(pb.campaign_min_cents, round(p.marketing_budget_cents * pb.campaign_share))` |
| `platforms/fees.py` | 222 | fixed | `uplift = round(store_revenue_cents(state, product, balance, data) * drag / (1 - drag))` |
| `platforms/formulas.py` | 122 | fixed | `return round(revenue_cents * paid_share * users * fee)` |
| `platforms/phase.py` | 251 | tagged: ratio | `licence = pf.clamp((pb.android_licence_cents + 1) / (p.licence_cents + 1), lo, hi)` |
| `platforms/rivals.py` | 119 | tagged: ratio | `key=lambda p: index(p.id) * (pb.android_licence_cents + 1) / ((p.licence_cents or 0) + 1),` |
| `platforms/rivals.py` | 121 | tagged: ratio | `score = index(best.id) * (pb.android_licence_cents + 1) / ((best.licence_cents or 0) + 1)` |
| `products/formulas.py` | 166 | tagged: ratio | `return budget_cents / pb.budget_mk_unit_cents + pb.marketer_mk * mu` |
| `products/formulas.py` | 184 | tagged: ratio | `return clamp_score(PRICE_SCORE_AT_REFERENCE * reference_cents / price_cents)` |
| `products/phases.py` | 711 | fixed | `amount = round(sold * (seg.price_cents or 0))` |
| `products/phases.py` | 713 | fixed | `amount = round(seg.customers * (seg.price_cents or 0) * paid)` |
| `products/phases.py` | 720 | fixed | `booked += round(sold * (rseg.price_cents or 0))` |
| `products/phases.py` | 722 | fixed | `booked += round(rseg.customers * (rseg.price_cents or 0) * paid)` |
| `products/phases.py` | 726 | fixed | `flows.get((product.id, seg.segment), Flow()).units` |
| `products/phases.py` | 815 | fixed | `total += sum(round(s.customers * s.price_cents) for s in rows if s.price_cents is not N...` |
| `refining/actions.py` | 160 | fixed | `true_capex = round(q.capex_cents * (1 + overrun_share(state, facility_id, balance)))` |
| `refining/formulas.py` | 48 | tagged: rate | `return mwh * cents_per_mwh * index` |
| `refining/formulas.py` | 64 | tagged: rate | `input_price_cents * input_units` |
| `refining/formulas.py` | 75 | tagged: ratio | `return (price_cents - unit_cost) / price_cents if price_cents > 0 else 0.0` |
| `refining/formulas.py` | 102 | tagged: rate | `return value * source_cents * per_source` |
| `refining/formulas.py` | 104 | tagged: rate | `return source_cents * per_source / value` |
| `refining/formulas.py` | 105 | tagged: rate | `return base_cents * ((1 - value) + value * source_index)` |
| `refining/mines.py` | 91 | tagged: rate | `month = replace(month, unit_cost_cents=month.cost_cents / month.output)` |
| `refining/models.py` | 58 | tagged: rate | `return self.output * self.market_cents` |
| `refining/models.py` | 64 | tagged: ratio | `return (value - self.cost_cents) / value if value > 0 else None` |
| `refining/plants.py` | 247 | fixed | `charge = round((deliverable - take) * deal.price_cents * rb.deal.take_or_pay)` |
| `refining/plants.py` | 253 | tagged: rate | `cents += take * deal.price_cents` |
| `refining/plants.py` | 353 | fixed | `power = round(output * rf.power_cents(r.mwh_per_unit, rb.power_cents_per_mwh, p_index))` |
| `refining/plants.py` | 354 | fixed | `other = round(output * r.other_cents)` |
| `refining/plants.py` | 510 | tagged: rate | `revenue += take * deal.price_cents` |
| `refining/plants.py` | 638 | fixed | `amount = round(taken * lot.unit_cents)` |
| `refining/plants.py` | 679 | fixed | `at_market = round(taken * lot.market_cents)` |
| `refining/plants.py` | 690 | fixed | `turn, lot.seller_id, lot.buyer_id, "Own-group wafers", round(taken * lot.unit_cents)` |
| `refining/plants.py` | 698 | fixed | `at_market = round(taken * lot.market_cents)` |
| `refining/plants.py` | 713 | fixed | `round(taken * lot.unit_cents),` |
| `refining/plants.py` | 717 | tagged: rate | `spot[lot.facility_id] = spot.get(lot.facility_id, 0.0) + rest * lot.market_cents` |
| `refining/quote.py` | 58 | deferred to M32 (a rate) (file in flight) | `rg.price_cents(state, r.input_good, balance, data) * per_in if r.input_good else 0.0` |
| `refining/quote.py` | 63 | deferred to M32 (a rate) (file in flight) | `fixed = size * r.fixed_cents / out_year if out_year else 0.0` |
| `refining/quote.py` | 64 | deferred to M32 (a rate) (file in flight) | `dep = q.capex_cents / (kind.life_months / MONTHS) / out_year if out_year else 0.0` |
| `research/eras.py` | 146 | fixed | `sum(s.customers * (s.price_cents or 0) for s in state.segments_of(product_id))` |
| `research/eras.py` | 147 | fixed | `+ sum(s.customers * (s.price_cents or 0) for s in state.regional_segments_of(product_id))` |
| `research/licensing.py` | 128 | fixed | `total += sum(round(s.customers * (s.price_cents or 0)) for s in state.segments_of(p.id))` |
| `research/licensing.py` | 130 | fixed | `round(s.customers * (s.price_cents or 0)) for s in state.regional_segments_of(p.id)` |
| `research/projects.py` | 52 | tagged: ratio | `return 1.0 if self.needed_cents <= 0 else min(1.0, self.budget_cents / self.needed_cents)` |
| `rivals/decisions.py` | 499 | fixed | `state, replace(seg, price_cents=max(1, round((seg.price_cents or 0) * factor)))` |
| `rivals/decisions.py` | 511 | fixed | `budget = round(product.marketing_budget_cents * (1 + rv.brand_push_marketing))` |
| `rivals/decisions.py` | 534 | fixed | `budget = round(p.marketing_budget_cents * (1 - rv.cut_costs_marketing))` |
| `rivals/decisions.py` | 727 | fixed | `product.marketing_budget_cents / (1 + rv.brand_push_marketing)` |
| `rivals/formulas.py` | 68 | fixed | `0.0, revenue_cents * (1 - margin_bp / BP_DENOMINATOR) - hosting_cents - marketing_cents` |
| `rivals/poaching.py` | 65 | tagged: ratio | `return float(grant.unvested * price) / employment.salary_cents` |
| `rivals/poaching.py` | 85 | tagged: ratio | `approach.offer_cents / employment.salary_cents,` |
| `rivals/poaching.py` | 214 | fixed | `ask = round(e.salary_cents * pb.ask_mult)` |
| `rivals/setup.py` | 53 | fixed | `total += seg.customers * (seg.price_cents or 0) * rate` |
| `rivals/setup.py` | 56 | fixed | `total += rseg.customers * (rseg.price_cents or 0) * rate` |
| `rivals/setup.py` | 64 | tagged: estimate | `revenue = sum(s.customers * (s.price_cents or 0) for s in state.segments_of(product.id))` |
| `rivals/setup.py` | 66 | fixed | `r.customers * (r.price_cents or 0) for r in state.regional_segments_of(product.id)` |
| `rivals/setup.py` | 156 | fixed | `salary = round(market_salary_cents(role.key, level, balance, data) * salary_mult)` |
| `rivals/setup.py` | 196 | fixed | `return round(monthly_revenue_cents(state, company_id, data) * spec.cash_months)` |
| `rivals/setup.py` | 234 | fixed | `s.customers * (s.price_cents or 0) * sale_rate(cat, s.segment)` |
| `rivals/setup.py` | 246 | tagged: estimate | `hosting += seg.customers * hosting_cents(category, seg.segment, ai) * rate` |
| `rivals/setup.py` | 267 | tagged: ratio | `heads = pool_budget * mix[function] / loaded_cost_cents(function, balance, data)` |
| `score.py` | 89 | tagged: ratio | `return float((now / then.revenue_cents) ** (1 / years) - 1)` |
| `score.py` | 119 | tagged: ratio | `by[product.company_id] = by.get(product.company_id, 0.0) + s.customers * (` |
| `score.py` | 124 | tagged: ratio | `by[product.company_id] = by.get(product.company_id, 0.0) + r.customers * (` |
| `world/bids.py` | 51 | tagged: estimate | `return value_cents * (1 + tilt + bb.view_sd * z)` |
| `world/bids.py` | 76 | fixed | `per_share = round(public.price_cents * (1 + wb.bids.premium))` |
| `world/groups.py` | 253 | tagged: ratio | `buffer = gb.cash_months * costs_cents(state, buyer.id, balance, data)` |
| `world/groups.py` | 268 | fixed | `price = round(value_cents(state, target.id, balances, balance, data) * (1 + gb.premium))` |
| `world/operate.py` | 216 | fixed | `round(f.capex_cents / (wb.life_years * MONTHS)),` |
| `world/query.py` | 70 | tagged: rate | `return index * balance.world.foundry_wafer_cents / CENTS` |

## Follow-ups

- **M32 and M33:** the seven deferred lines (the guard's `DEFERRED`): make them exact when your edits land, then remove them from the list. New code in `power/` and `equipment/` meets the guard when you merge `main`.
- **Rates as rationals:** the tagged unit-rate functions (wafer, BOM, power, refining unit costs, `value_cents`) could return exact rationals or millicents, removing most `rate` tags; it touches every price path and needs a turn-time check (M35's performance lane).
- **Turn time:** the exact revenue booking in `products/phases.py` adds `Fraction` work per segment a month; the CI timing job is the check (rule 6).
