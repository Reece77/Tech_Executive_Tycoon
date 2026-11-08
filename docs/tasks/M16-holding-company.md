# M16: Holding company and subsidiaries (v3)

**Goal:** the player runs a group. A holding company owns operating companies, each a real legal entity with its own books, cap table, board, CEO and mandate. Stakes are accounted as the size of the holding demands (consolidation, equity method, fair value). The player can sell stakes, buy out minorities, carve out and list a subsidiary, spin one off, build stakes in listed rivals and invest in startups. Transfer prices between group companies matter where minorities are involved, and a conglomerate discount makes spin-offs a real choice.

**Spec sections:** §1, §2 (v3 fantasy), §10 · **ADRs:** 0002, 0003, 0004, 0013 (stream `group` 45), 0015, 0020 · **Formulas:** `docs/formulas.md` §31 (all), with §25, §27, §28 · **Design:** `docs/v3-design/M16-holding-company.md` · **Review:** `docs/reviews/codex-review-4.md` findings 2 and 3 · **Depends on:** M15a (`m15a-done`); merges after M24 and M15r

## Lane

- Its own session and branch (`m16-holding`). It runs while M24 and M15r finish. **Merge order:** M24, then M15r, then M16 (M16 regenerates golden snapshots on the combined code).
- **M16 owns:** `finance/consolidation.py`, `state.group_companies` and `owner_of` (findings 2 and 3), new `backend/tst/sim/group/` (holding company, cap tables and boards for subsidiaries, mandates, capital actions, transfer prices, the discount, stakes and venture investments), accounts 1820, 1830, 3500, 4910, 4920, 4930, the Group screen and company switcher.
- **M16 must not edit:** `backend/tst/sim/founder/` beyond calling `founder.credit` (M24); the files M15r owns until it merges.
- **CLAUDE.md §9's decision rules apply.**

## Design for the rest of v3 (ADR-0020)

Facilities are owned by a subsidiary, so a mining or foundry business can later be carved out or sold. A subsidiary can be registered in a region (M22's entities per bloc). Transfer prices carry M22's taxes and tariffs later.

## Out of scope

Rivals forming groups, selling stakes or spinning off (after M23). Regional tax (M22). The founder investing personally (v5).

## Sub-tasks (commit after each)

1. **Group membership and consolidation by period** (§31.1; Codex review 4 findings 2 and 3): ownership history (`owned_from`, `owned_to` by owner), ultimate owners, `group_companies` at any depth and by period, disposals, eliminations at every level, antitrust by ultimate owner. **Tests:** Codex's two reproductions (a failed brand leaves earlier statements unchanged and balanced; a nested chain counts under its root), and the sell-a-parent-with-brands case from review 4.
2. **Data and formula tests:** `group.*` keys with comments; accounts; stream `group` in ADR-0013; the §31.8 examples as unit tests.
3. **The holding company** (§31.2): the gate, forming it (listing, cap table and Chair move to the new parent), the group office, the Group screen and switcher.
4. **Stake accounting** (§31.3): consolidation with NCI, the equity method, fair value. **Property tests:** consolidated cash equals controlled companies' cash; NCI equals outsiders' share of net assets; every period balances.
5. **Subsidiaries as companies** (§31.4): cap tables, boards, CEOs, mandates (and the brand directive mapping), pitches to the group, December reviews, dividends with minorities.
6. **Capital actions** (§31.5): selling stakes, buyouts, carve-out IPOs through M13's chain, spin-offs (the founder's shares to M24's book), stakes in listed rivals with disclosures and the 30% rule, corporate venture investments.
7. **Transfer prices** (§31.6) and **the conglomerate discount** (§31.7).
8. **API, CLI, e2e and balance:**
   - **CLI:** `tst group`, `tst form-holding`, `tst mandate --company --kind`, `tst sell-stake --company --pct`, `tst carve-out --company --pct`, `tst spin-off --company`, `tst stake --company --pct`, `tst venture --startup --cents`, `tst transfer-price --flow --kind`.
   - **Playwright:** (a) form a holding company on an eligible fixture and see the Group screen; (b) sell 30% of a subsidiary and see NCI in the consolidated statements; (c) spin off a subsidiary and see it become a listed rival; (d) an unfair transfer price raises a minority complaint.
   - §31.9 targets printed and recorded; tune only `group.*`.
   - Merge steps: merge `main` after M24 and M15r, re-parent migrations, regenerate goldens once (reasons in CHANGELOG), re-run every guard, CI `check` and `e2e` green.
   - Close-out: CHANGELOG, data dictionary, README index row, a Resolution note in `docs/reviews/codex-review-4.md` for findings 2 and 3.

## Acceptance criteria

- [ ] Codex review 4 findings 2 and 3 fixed, with their reproductions as regression tests.
- [ ] The §31.8 examples pass; consolidation property tests pass at three levels of ownership.
- [ ] A game that never forms a holding company plays exactly as before.
- [ ] §31.9 targets 3–5 met (printed, values recorded).
- [ ] `make check` green; `make e2e` passes; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m16-done`.

## Manual check (Reece, after merge)

On a listed company with two kept brands, form a holding company, give each subsidiary a mandate, sell 25% of one and carve out another. A year later: does the Group screen tell the story, and is the conglomerate discount a reason to spin something off?

## Decisions made

Engineering decisions (CLAUDE.md §9), by sub-task:

1. **Membership and consolidation.** Ownership history lives in `group_ownership`: `from_turn` is the closing (the company's lines up to it are opening balances), `to_turn` is inclusive (a disposal posts then); `company_parent` stays the current direct owner. The owner's 1810 investment at any turn is `book − stake × (the company's equity change since)`, since sweeps, funding and dividends move both together. A company that enters with its owner (a grandchild) brings its post-closing profit as goodwill (acquisition accounting at the group level); under common control (forming the holding company) that entry difference is equity. A disposal writes off the investment and the goodwill it paid; consolidated, the company's net assets go out and the difference goes to `4930`. 4910, 4920 and 4930 sit in a new "other gains" block below the operating result and inside the net result, so the operating result (and every game without a group) is unchanged. Upgraded saves get an open holding per kept brand from its latest brand closing (book from the parent's "Acquisition of <name>" 1810 line); a brand that had already failed is disposed of at the next month end. A hand-built state with only `parent_id` is held from its latest closing (or turn 0) and its disposal posts nothing (no known investment).
2. **Balance keys.** `group.*` as §31's numbers; `group.supply_cost` (0.80, an in-group supplier's cost as a share of the market price it replaces) is new: the saving that makes vertical integration pay. Stream `group` (45) has one call site (`tst.sim.group.draws`), keyed by the company's stable key and a tag.
3. **The holding company.** A new company (`is_player` true, stage 5, `rival_key` (5, n)); `state.player` resolves to the operating company, the one the player runs, and `player_companies` returns the operating company and the holding. Subsidiaries are run by their CEOs, not through `player_companies`. The holding takes the market state (`public_company`), guidance, board seats and every cap-table holder but the operating company's option pool and grants (31.4: a subsidiary keeps its option pool); the IPO chain's `listing` record stays the operating company's history. Formation postings: the holding's 1810 at the operating company's book against 3000 (one-for-one swap); the brands pass to it with their 1810 and goodwill as a distribution. The fees post on the operating company (the holding has no cash yet). The group office posts $250k a month on the holding; the operating company pays up the holding's shortfall and the holding funds the operating company's negative cash (mirror sweeps). The gate's revenue test reads the group's run rate (12 × this month's projected revenue), as stages 2–3 read ARR. The listed holding trades on the group's revenue, operating result and cash, and its value is the sum of the parts less the discount (31.7). Its events and inbox items go to the player's inbox; activist and takeover answers resolve to the listed entity. The M13 CEO stays with the operating company (31.2: "the operating company keeps its CEO"). The holding's share-price chart starts at formation. The Group screen is a Finance tab (the nav has ten hotkeyed items); the company switcher scopes Statements, Cap table and Board (`?company=`).
4. **Stakes.** A stake change rebases the holding (`rebases`: turn, stake, book, equity). NCI at each turn is the sum over members of (1 − the root's effective stake) × the member's contributed net assets (its entry goodwill aside: that is the group's); its share of the turn's profit posts to `4990` (consolidated only, shown below the net result as attributable to NCI, with the owners' part); the rest of NCI's movement, and what the outsiders' side of a dividend or a stake sale leaves, go to equity. Associates move monthly by their share of the company's operating result (the group's measure of profit for rivals); stakes under 20% are marked each December at the market cap, or at the displayed value range's midpoint for a private company (never the hidden value, 31.10).
5. **Subsidiaries.** A mandate maps to the directive the brand decides under and sets the months of costs it keeps before cash goes up (`group.mandate.*_keep_months`); "grow" pays up at most `group.mandate.grow_payout` of last month's operating profit and keeps its stock of cash. Without a mandate M14's rules hold, so existing brands are unchanged. With minorities, cash goes up only as pro-rata dividends and the owner stops funding shortfalls. Boards are derived (3 parent nominees, 2 independents, a seat per 15% held by minorities), not `board_seat` rows (whose removal vote would end the player's game). The December review scores growth, margin or payout against the mandate's target; a replacement ends the CEO's employment (`fired`) and the next leader takes over (rival CEOs are their company's top leader). **Pitches to the group** use M13b's quarterly cadence and approve/decline but a group-level record (`group_pitch`): a subsidiary CEO's request for capital, judged against the mandate and funded by its owner when approved; M13b's pitch records belong to the player's own executives.
6. **Capital actions.** Prices use public numbers only (market cap, or the displayed range's midpoint), less a standing complaint's 10%. A stake sale or a carve-out is an equity transaction on the owner's books (control is kept, so no gain or loss); the buyer is an `investors.yaml` firm drawn on stream `group`. Stakes are sold only in subsidiaries run by their own CEOs (not the operating company the player runs). A subsidiary's cap table opens at its first outside sale (10,000,000 shares). **The carve-out does not run M13's IPO chain**: it lists the share at once at its public value and the subsidiary trades like a listed rival (V_f × S, M14's model, which gives it a market price each month); M13's analysts, guidance and earnings for a second listed entity are a follow-up. A spin-off is from the holding company only (it needs shareholders to give the shares to) and posts as a distribution (equity); the founder's pro-rata part is a `group_personal_stake` (M24's book holds cash only, and M16 does not edit `founder/`). Market buying stops at 30% (a full offer from there, 31.5), so 49.9% applies to stakes reached otherwise. A venture stake is priced at the round's post-money value (the startup's public value plus the money) and its information rights reveal the startup's key people through the rival-diligence knowledge action.
7. **Transfer prices.** Flows are compute (the buyer's 6300) or chips (5000): each month the buyer's spend is supplied in-group (its outside purchase reversed), the seller's cost is `group.supply_cost` of it, and the transfer price posts to `5900` / `4300`, removed in consolidated statements. The complaint is the critical event `minority_complaint` (trigger `group`, effect `group_step`): moving to market settles it at the next month end. Its legal costs fall on the minority-held company of the flow. Segments for the discount are the distinct product categories the group sells in; the intra-group share is the year's transfer-priced supply over the group's revenue.
8. **Targets.** `tst/balance/m16.py` builds each seed's group from M13's listed company and two small revenue-earning rivals kept as brands at their public value: U in a category the company does not sell in, and I supplying the company's compute at cost. T4's revenue measure is revenue after three years under grow over revenue under return cash, less 1.

The holding company's API answers default to the listed entity (the holding once formed) for the cap table, the board and the statements, and to the operating company for the summary.

## Results (31.9, `tools/m16_targets.py`, 10 seeds)

| Target | Band | Value |
| --- | --- | --- |
| T1 nothing moves for a single company | goldens unchanged by sub-tasks 1–2 | golden snapshots unchanged through sub-task 7 (no group in the golden runs); consolidation tests below |
| T2 consolidation is right | property tests; 31.8's examples; a three-level group by hand | `tests/property/test_m16_consolidation.py` (cash, NCI, every turn balances, three levels), `tests/unit/test_m16_formulas.py`, `test_m16_stakes.py::test_31_8_nci_through_consolidation`, `test_m16_group_membership.py::test_a_nested_group_consolidates_each_company_once_and_balances` |
| T3 spin off the unrelated subsidiary | founder's value up on 40–80% | **8 of 10** (met) |
| T3 spin off the integrated one | lowers it on most | **3 of 10 (missed)** |
| T4 grow vs return cash, revenue after 3 years | +20% to +60% | +83%, +67%, +60%, +72%, +47%, +40%, +39%, +39%, +33%, +46%: **7 of 10 in band** (seeds 1, 2, 4 above) |
| T4 cash returned, return cash / grow | 2–4x | 1.9x, 2.2x, 2.1x, 2.1x, 2.3x, 2.3x, 2.3x, 2.3x, 2.4x, 2.3x: **9 of 10 in band** (seed 1 at 1.9x) |
| T5 a complaint within 6 months | every seed | **10 of 10** (month 6 on every seed) |

Tuned (`group.*` only): `group.mandate.grow_payout` 0.5 and `grow_keep_months` 6 set the cash ratio (1.0 gave 1.2x, 0.4 gave 2.5–3.1x with the larger brands of a first fixture); `supply_cost`, `discount.synergy` and `discount.per_segment` were tried at 0.3 / 0.5 / 0.02 without moving T3's integrated half (1 of 10) and are left at 0.80 and §31.7's 0.15 and 0.03. A marketing multiplier per mandate had no effect (the brands' products carry no marketing budget) and was removed.

## Follow-ups

Reece's ruling (2026-11-08): M16 merges with T3's integrated half and T4's partial bands recorded as known misses.

- **T3's integrated half misses** (see Results): spinning off a closely integrated supplier lowers the founder's value on only a few seeds. The lost in-group saving is small next to what a spin-off gains (no discount on that part, and a listing at V_f × S), and `group.*` alone does not move it (supply cost 0.3 and synergy 0.5 left it at 1 of 10). A product-manager ruling is needed: a stronger synergy mechanism (shared research, a dis-synergy cost on separation), or a different measure.
- **T4's revenue band** is met on most seeds; the rest grow faster than +60%. The gap comes from the grow/harvest brand styles the spec's directive mapping fixes (the payout and keep months move only the cash), so it is not tunable inside `group.*`.
- A carve-out through M13's full IPO chain (banks, roadshow, its own analysts, guidance and earnings) for a second listed entity.
- Rivals as groups (after M23), regional tax and tariffs on transfer prices (M22), wafers and minerals as flows (v3).
- The founder's personal stakes valued in M24's legacy and Personal tab (M16 does not edit `founder/`).
- Subsidiary CEOs' pitches as full M13b pitches (kinds, cases, follow-through records).
