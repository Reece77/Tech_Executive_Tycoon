# M14: Mergers and acquisitions

**Goal:** buying companies is a real strategic lever. Any company can be bought, from a struggling startup to a listed incumbent, for cash or (once listed) stock, by friendly offer or hostile tender. Due diligence narrows what you know. Regulators block deals that make a market too concentrated. After each deal you choose: keep it as a brand you steer with a directive, or integrate it for savings at the cost of culture clash and departures. Rivals buy startups too, and a bid for your own company can now end the game with an exit.

**Spec sections:** §2 (v2 fantasy), §10 (instruments) · **ADRs:** 0002, 0003, 0004, 0013 (streams `mna` 37, `integration` 38, `rival_mna` 39), 0015, 0019 (§16), 0020 · **Formulas:** `docs/formulas.md` §28 (all), with §15, §20.3, §25, §27 · **Depends on:** M13b (`m13b-done`) · **Lane:** A, alongside M14b

## Lane

- **Lane A.** It runs at the same time as M14b (lane B, people and press) in its own session and branch (`m14-mna`).
- **Merge order: M14b merges first.** Before merging M14: merge `main` (with M14b), re-parent M14's unmerged migrations, add M14b's press trigger for an acquisition announcement (§29.1) if M14b left a hook for it, regenerate golden snapshots once with both milestones' reasons in CHANGELOG, and re-run every guard on the combined code. If an M14b target moves, report it rather than tune M14b's keys.
- **M14 owns:** new `backend/tst/sim/mna/`; rivals' startup purchases; consolidation in finance; `listed_from` in `incumbents.yaml` and `entrants.yaml`; account 1800; `data/events/deals.yaml`; the Rival screen's value and deal controls; Finance → Deals and subsidiaries; Org's acquired units and directives; the exit ending.
- **M14 must not edit:** `backend/tst/sim/press/`, the rival CEO and feud code, `hiring/` recruitment changes, `data/events/press.yaml`, the Recruitment screen or the Overview's credibility panel (M14b's).
- **Shared files:** `balance.yaml` (add only `mna.*`, `antitrust.*`, `integration.*`; both lanes append to `events.trigger`), `docs/formulas.md` (notes in §28 only), `RivalScreen.tsx` (M14 owns it; M14b adds one panel component), `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **RNG:** `mna` 37, `integration` 38, `rival_mna` 39; lane B has 40–42.

## Design for v3 (ADR-0020)

- A brand subsidiary is a company with `parent_id`: its own ledger, pools, people and decisions. M16 adds cap tables, boards and minority stakes to the same model; do not add them now.
- Every function takes a `company_id`; consolidation iterates `player_companies(state)` extended with subsidiaries (one helper, `group_companies(state, parent_id)`).
- Rivals and the player use the same deal code (§28.6).

## Out of scope

Minority stakes, subsidiaries' own boards and cap tables, spin-offs and selling a division (M16). Goodwill impairment (follow-up). Earn-outs. Rivals bidding for each other's listed companies (rivals buy startups only).

## Sub-tasks (commit after each)

1. **Data and formula tests:** `mna.*`, `antitrust.*`, `integration.*` keys in `balance.yaml` with comments; `listed_from` for incumbents and entrants following history; account 1800 goodwill; the three streams in ADR-0013's main table (keys: stable rival keys); every §28.10 worked example as a unit test.
2. **Valuation** (§28.1): `V_f` for every company, listed rivals' market cap and sentiment, private value ranges with the seeded offset. **Test:** a company that never buys plays exactly as before (golden snapshots unchanged by this sub-task; valuation is read-only).
3. **Diligence and offers** (§28.2–28.3): diligence and hidden problems, private and listed offers, counters, hostile tenders, financing (cash, stock, a loan first), closing with goodwill.
   - **Property tests:** the ledger balances through closing (cash, stock and mixed consideration); the cap table sums to 100% after a stock deal.
   - **Differential test:** two targets with the same displayed range but different true values give the same API responses before diligence (no oracle in errors or ordering, as M12r finding 1).
4. **Antitrust** (§28.4): combined share by market, review, block probability, remedies with divestiture. Deterministic block test; seeded review test.
5. **After closing** (§28.5): the brand subsidiary (consolidation, cash sweep, directive, moving key people) and integration (products, key people, pool staff to individuals with the cap, severance, culture clash, flight, churn, technology). Tests for each, and a turn-time check: integrating the largest incumbent keeps `test_product_perf`'s budget.
6. **Being acquired and rivals' deals** (§28.6): accepting a bid ends the game with the exit ending; rivals buy startups.
7. **Pitches** (§28.7): the acquisition kind for the CEO and CPO; never auto-approved.
8. **API, CLI and screens:**
   - **Rival screen:** value (market cap or range), Diligence and Make an offer buttons, deal status.
   - **Deals panel** (Finance → Deals): open offers, reviews, closings, integration progress.
   - **Finance:** subsidiaries' columns and the consolidated statements; goodwill on the balance sheet.
   - **Org:** acquired units, flagged for 12 months; a directive control on each subsidiary.
   - **Exit ending** on the Game over screen.
   - **CLI:** `tst targets`, `tst diligence --company`, `tst offer --company --price --cash-share`, `tst directive --company --mode`.
   - **Hidden values:** extend the hidden-value test to §28.8's list.
9. **Balance and e2e:**
   - §28.9 targets printed and recorded; add the "acquirer" arm to the balance scripts; tune only `mna.*`, `antitrust.*` and `integration.*`.
   - **Playwright:** (a) diligence then a friendly offer for a startup, then integrate it and see its people join; (b) buy a startup and keep it as a brand, set a directive and see the consolidated P&L; (c) a scripted deal over 50% combined share is blocked and the remedy offered; (d) accept a takeover bid and see the exit ending.
   - **No new xfails;** any guard that fails against `main` and that M14's keys can't fix is reported with values, and you stop before merging.
   - Close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every §28.10 worked example passes as a test.
- [ ] A company that never buys plays exactly as before.
- [ ] Deals close with a balanced ledger and a correct cap table (property tests); no hidden value reaches the API or a prompt (differential and hidden-value tests).
- [ ] Antitrust blocks over 50% without a remedy; brand and integrate both work as specified.
- [ ] §28.9 targets 2–7 met (printed, values recorded); target 1 holds.
- [ ] `test_product_perf` stays within budget.
- [ ] `make check` green; `make e2e` passes; merged after M14b with migrations re-parented, golden snapshots regenerated on the combined code and both milestones' guards passing; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m14-done`.

## Manual check (Reece, after merge)

On `pt-ipo` after listing, buy a struggling startup in your category and integrate it, then buy a second one and keep it as a brand with the "grow" directive. A year later: who left, what did integration save, and does the brand pull its weight? Then try a deal that crosses 50% of a market.

## Status (2026-11-05): built; stopped before merging

Sub-tasks 1-9 are built and tested; the four Playwright flows pass. **Target 4 misses and M14's keys cannot fix it**, so per the instructions this branch is not merged (values in `docs/balance-targets.md`, M14):

| Target | Value | Band |
| --- | --- | --- |
| 2 private deals / listed premium | 1.38 x V_f / 35% | 1.0-1.6 / 25-50% |
| 3 key people lost: integrated / brand | 25% / 7% | 10-30% / <= 10% |
| **4 staff cost cut by integration** | **87% (scripted deals) / 51% (the acquirer's startups)** | **15-35%** |
| 5 acquirer / steady + regions ARR, year 10 | 1.06 | 1.0-1.4 |
| 6 deals at 40% blocked after review, after 2020 | 40% of seeds | 15-50% |
| 7 incumbents' startup purchases a decade | 3 (median) | 1-4 |

- **Why target 4 misses.** 28.5 keeps, per product, only the pool staff it needs: builders to the CTO's maintenance line and sellers for its customers. An incumbent's pools are sized for its revenue (thousands of people at Zoho or Apple), and a product's maintenance line needs a handful of builders, so integration lets 80-95% of the staff go. Startups have smaller pools and mostly key people, and still save about half.
- **Why the keys can't fix it.** The only lever on how many people stay is `integration.max_per_product`, which caps the kept staff and can only raise the saving; severance doesn't change it, and fewer departures would leave startups saving more than 35%. Options:
  - Define the kept staff as the product's share of the target's pools (for example its revenue share) instead of its minimum need.
  - Measure target 4 on the whole cost base, hosting and marketing included.
  - Re-band target 4.
- **Lane steps not yet run.** M14b has not merged (no `m14b-done` tag yet), so the merge of `main`, the migration's re-parenting, the press trigger and the golden regeneration are still to do.

## Decisions made

- **Fees** (diligence, failed tenders) post to 6900 general and administrative; 28.2's "6100 professional fees" names an account the chart does not have (6100 is rent).
- **Accounts.** 1800 goodwill, and 1810 investment in subsidiaries for a kept brand's book equity (consolidation replaces it with the brand's net assets; cash sweeps reduce it).
- **Hidden problems** are fixed per target from the master seed (stream `mna`, turn 0), equivalent to "drawn when first looked at" without depending on what the player opens.
- **Mode** (brand or integrate) is chosen with the offer and can change until closing; final at closing; integrate by default. A deal agreed in a month closes at that month's end.
- **Counters** are whole dollars (rounded up), and once made they are the bar: a lower offer ends talks even if it clears the hidden reservation.
- **Displayed value ranges** are rounded outward to two significant figures, so the display is no oracle (the differential API test relies on it).
- **The remedy** divests the target's overlapping product, not the acquirer's.
- **Integration need** for pool staff: builders to the maintenance line at the pool's skill, sellers to replace sales-led churn, one marketer per product; key people spread over the new units.
- **Culture distance** comes from the companies' average personality traits (`integration.distance_span` 4 points = distance 1). `integration.clash` is 0.1, a new key for 28.5's clash.
- **Flight, clash and sweeps** start the month after closing; flight is tracked for the player's acquisitions only.
- **The exit:** talks queue a `takeover_offer` event (data/events/deals.yaml) for the next month; accepting sells to the largest rival by revenue at the bid's premium; the game outcome is `exit`. `tst offer` keeps `--candidate` for job offers and takes `--company --price` for bids.
- **Pitches:** two new keys, `mna.pitch_synergy` (0.25) and `mna.pitch_bid_premium` (0.30), for the pitch's central case and its bid.
- **Rivals' purchases** need the combined share below the review line, close in the same month and merge the startup's pools into the buyer's.
- **Storage:** M&A records keep their fields as JSON (migration 0033); kept brands' parents are in `company_parent`.
- **Tuning (28.9):** `integration.flight_brand` 0.007, `integration.flight_base` 0.01, `mna.rival_rate` 0.008.

## Follow-ups

- Target 4 (above): Reece's decision on the kept-staff rule or the band.
- Goodwill impairment (out of scope).
- The acquirer's own overlapping product as a remedy.
- Rivals' executives pitching acquisitions; rivals bidding for the player outside the takeover event.
- A Deals entry in the top bar when a review or a closing is due.
