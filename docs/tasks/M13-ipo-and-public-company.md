# M13: IPO, public company, and Chair and CEO (lane B)

**Goal:** stage 4. A grown company can go public through an IPO event chain (banks, filing, roadshow, pricing, listing day). Once public it lives by quarterly earnings it guides: a share price from fundamentals and sentiment, analysts, buybacks, dividends and secondary offerings, and activists and takeover interest when the price lags. The founder can appoint a CEO and step up to Chair, letting the CEO run day-to-day operations while the Chair keeps capital and strategy.

**Spec sections:** §3 (stage 4), §10 (IPO, public stock, board dynamics) · **ADRs:** 0002, 0003, 0005, 0015, 0018, 0019 (§10–§12), 0020 (§7: listings per company) · **Formulas:** `docs/formulas.md` §25 (all), with §14, §20 and §24 · **Wireframes:** `docs/wireframes.md` (M13 screens), drawn with this brief's first sub-task if not yet present · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M12a (`m12a-done`)

## Lane

- **Lane B.** It runs at the same time as M12b (lane A, hardware and chips) in its own session and branch (`m13-ipo`).
- **Merge order: M13 merges first.** M12b then merges `main`, re-parents its migrations and regenerates golden snapshots.
- **M13 owns:**
  - new `backend/tst/sim/markets_public/` (listing, share price, analysts, earnings, activists and takeover interest);
  - new `backend/tst/sim/org/ceo.py`;
  - `backend/data/banks.yaml` and the IPO, earnings and activist event templates;
  - finance routes for public-company actions;
  - screens: an **IPO** flow in Fundraising, a **Stock** tab in Finance, and the CEO seat on the Executive team panel.
- **M13 must not edit:** facilities, goods, devices, chips or the assembly kind (M12b's), or research (M11's).
- **Shared files:**
  - `balance.yaml`: add only `ipo.*`, `public.*` and `ceo.*`;
  - `docs/formulas.md`: notes in §25 only;
  - `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **RNG:** new streams `ipo` (33) and `market_sentiment` (34), with 35 reserved for lane B. Add them to ADR-0013's main table at merge, using stable keys (company data key or id that can't shift; see the M12a amendment).

## Design for v3 (ADR-0020)

Listing, shares outstanding, share price, analysts and guidance belong to a `company_id`, so a v3 subsidiary can list on its own. Use `player_companies(state)` wherever "the player" is meant. The CEO's authority covers the company it's appointed to.

## Out of scope

Acquisitions (M14; M13 only raises takeover-bid events). Personal stock trading (v3). Rivals going public: incumbents are treated as already public, with no simulated share price. Debt changes (M10).

## Sub-tasks (commit after each)

1. **Data, wireframes and formula tests:**
   - `banks.yaml`, `ipo.*`, `public.*`, `ceo.*` keys; IPO, earnings, activist and takeover templates;
   - every §25.10 worked example as a unit test;
   - two wireframes in the design canvas style: the IPO flow and the Stock tab (or ask the product manager to draw them first).
2. **Eligibility and the IPO chain** (§25.1, §25.2):
   - the hire-banks action, the filing and roadshow events, the pricing critical event with book demand on stream `ipo`, the listing with new shares and the fee, dual-class shares, pulling the IPO;
   - stage 4, the board changes (§25.7), migration and data dictionary;
   - **tests:** each step, the cap table after listing, and a ledger property test.
3. **Share price and analysts** (§25.3): fundamental value, sentiment on stream `market_sentiment`, analysts' ratings and targets; history stored monthly. A seeded test, and a test that macro moves the multiple.
4. **Earnings and guidance** (§25.4): the guidance action, the quarterly report, sentiment jumps, board effects, activists and takeover-interest events. Tests for a beat, a miss, consecutive misses, the activist trigger and the takeover trigger.
5. **Capital actions** (§25.5): buyback, dividend, secondary, and the founder's stake. Ledger property tests.
6. **Chair and CEO** (§25.6): appointing a CEO, the CEO as super-delegate through `apply_action` with guardrails, decision quality, overrides at an energy cost, Chair energy, and the board replacing the CEO. **Property test:** the CEO never acts outside the guardrails or takes a Chair-only action.
7. **API, CLI and screens:**
   - the IPO flow, the Stock tab (price chart, market cap, analysts, guidance against actuals, the founder's stake), capital actions, the CEO seat and overrides;
   - glossary and driver breakdowns (share price drivers: fundamentals and sentiment as words, never the formula's hidden terms); History entries;
   - **CLI:** `tst ipo`, `tst guidance`, `tst buyback`, `tst appoint-ceo`;
   - the hidden-value test extended to the book-demand draw, future sentiment and the takeover threshold.
8. **Balance and e2e:**
   - the §25.9 targets printed and recorded; scripts gain an "IPO when eligible" step for steady and blitzscale;
   - **no new xfails:** any guard that fails versus `main` and M13's keys can't fix is reported with values;
   - **Playwright:**
     - (a) take a company public through the chain and see the Stock tab;
     - (b) miss guidance and see the price and board react;
     - (c) appoint a CEO, Holiday a year, and see the CEO's decisions;
   - close-out.

## Acceptance criteria

- [ ] Every §25.10 worked example passes as a test.
- [ ] The IPO chain runs end to end; the listing posts correctly and the cap table reconciles (property test).
- [ ] The share price follows fundamentals, sentiment and earnings; analysts publish ratings; activists and takeover interest trigger as specified.
- [ ] The CEO acts within guardrails and never takes Chair-only actions (property test); overrides cost energy.
- [ ] No API response shows the demand draw, future sentiment or hidden thresholds (planted-value test).
- [ ] §25.9 targets met (printed, values recorded); no new xfails.
- [ ] `make check` green; `make e2e` passes; merged first in the pair per CLAUDE.md §6 with the trailer `Milestone-Tag: m13-done`.

## Manual check (Reece, after merge)

Take a company public. Set guidance for a year and see how the market reacts to beats and misses. Appoint a CEO, step up to Chair, and Holiday a year: does the company run well without you, and do the decisions you kept feel like the important ones?

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
