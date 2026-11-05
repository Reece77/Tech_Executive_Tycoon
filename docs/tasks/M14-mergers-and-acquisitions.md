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

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
