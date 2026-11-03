# M13: IPO, public company, and Chair and CEO (lane B)

**Goal:** stage 4. A grown company can go public through an IPO event chain (banks, filing, roadshow, pricing, listing day). Once public it lives by quarterly earnings it guides: a share price from fundamentals and sentiment, analysts, buybacks, dividends and secondary offerings, and activists and takeover interest when the price lags. The founder can appoint a CEO and step up to Chair, letting the CEO run day-to-day operations while the Chair keeps capital and strategy.

**Spec sections:** §3 (stage 4), §10 (IPO, public stock, board dynamics) · **ADRs:** 0002, 0003, 0005, 0015, 0018, 0019 (§10–§12), 0020 (§7: listings per company) · **Formulas:** `docs/formulas.md` §25 (all), with §14, §20 and §24 · **Wireframes:** `docs/wireframes.md` (M13 screens) and `docs/wireframes/source/IPO.dc.html`, `Stock.dc.html` · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M12a (`m12a-done`)

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

- [x] Every §25.10 worked example passes as a test.
- [x] The IPO chain runs end to end; the listing posts correctly and the cap table reconciles (property test).
- [x] The share price follows fundamentals, sentiment and earnings; analysts publish ratings; activists and takeover interest trigger as specified.
- [x] The CEO acts within guardrails and never takes Chair-only actions (property test); overrides cost energy.
- [x] No API response shows the demand draw, future sentiment or hidden thresholds (planted-value test).
- [x] §25.9 targets met (printed, values recorded); no new xfails.
- [x] `make check` green; `make e2e` passes; merged first in the pair per CLAUDE.md §6 with the trailer `Milestone-Tag: m13-done`.

## Manual check (Reece, after merge)

Take a company public. Set guidance for a year and see how the market reacts to beats and misses. Appoint a CEO, step up to Chair, and Holiday a year: does the company run well without you, and do the decisions you kept feel like the important ones?

## Decisions made

Engineering and design details the spec and ADRs left open, decided while building (each is also in formulas.md §25.11 where it touches a formula):

1. **The chain is `public` events with engine choices.** Ten templates in `data/events/public.yaml` (S-1, three roadshow events, two pricing variants, earnings miss, activist, takeover bid, the board's CEO vote), queued by id under one new scheduled trigger `public`. Each choice carries a new valueless effect `public_step` whose stat names the engine step. The LLM may write a public event's words; its choices are always the template's (the M10 lender events keep template words too).
2. **Pricing has two templates** because templates allow three choices (16.3): with book demand ≥ 1.3, "price at the suggestion / raise 10% / pull"; otherwise "price at the suggestion / cut 15% / pull". The IPO card lists all four with the unavailable one marked.
3. **Timing.** S-1 month 1 (+1 if the metric is restated), ambition and share-sold month 2, share class month 3, pricing month 4; the company lists in phase 7 of the month the price is set. Pulling costs 30% of the fee on the suggested raise, −10 confidence, and the banks return after `ipo.retry_months` (12).
4. **First day:** `a` is the final price over the fair price (before the dual-class discount), so a raise or a cut moves the first day as ambition does. The likely first day on the card uses the middle of the demand word's band, never the draw.
5. **Shares:** IPO and secondary shares are common, held by "Public shareholders"; prices use fully diluted shares; dividends are paid on issued shares at the next month end, one declaration a month, and debit common equity (there is no retained-earnings account). Buybacks come from the public float, at most 10% of shares at a time; secondaries at most 20%.
6. **Analysts:** 3, plus one per doubling of market cap above $1B, at most 8, named from eight research houses; ratings follow target / price monthly.
7. **Earnings:** a beat is `s ≥ 0`, a miss `s < −2%`; consensus = last quarter × a quarter of the trailing year's growth, with the trailing year's margin; guidance within ±50% of consensus (a guard against typos); quarters start in January, April, July and October, and the first full quarter after listing is the first guided. A miss also queues the major `earnings_miss` event.
8. **Activists and takeover bids** wait 24 months between triggers. Activist choices: a board seat (an investor seat with a generated director), a buyback of 10% of cash, or a proxy fight costing 1% of cash; these run at the next phase 7, because they need that month's cash or a draw. Takeover: reject, rights plan, or open talks (sentiment × 1.175). No sale happens before M14.
9. **The public board:** two independents at listing (none if the board is full); each year one investor seat becomes independent (the fund sells; the director stays); patience from the analysts' consensus (buy +5, sell −5); dual-class shares stop the board removing the founder.
10. **Chair and CEO:** a CEO needs stage 4 and an employee at senior level or above (the exec seats' rule; hire one through an exec-level search). The CEO covers each scope (the five seats and "products": launching ready products) that no seat holder with authority covers, under that seat's guardrails, with `ceo.price_band_pct` around the player's last prices. It can only take operating actions (plans, moves, prices, marketing, launches). Debt repayment, rounds, the IPO, guidance, capital actions and appointments stay with the Chair; the CFO rule still proposes rounds and loans to the Chair. An override applies the decision's reverse at exactly 6 energy and moves the CEO's price anchor to the Chair's price; launches cannot be overridden. Dismissing a CEO costs 10 energy, changing scopes 2. The Chair's 40 energy applies from the next month. The board's vote comes as the critical `ceo_vote` event after 3 months below 30 average confidence.
11. **Stage 4 in hiring:** offers treat a public company as stage 3 (`hiring.offer.stage_appeal` and `stage_equity_mult` stop at 3, and this lane may not add `hiring.*` keys).
12. **The player's operating history is kept for 12 months** (was 6), for 25.1's four quarters; no migration (it is JSON in `finance_history`).
13. **Persistence:** migration `0030_public_company` (six tables); the live state keeps 36 months of share prices and 12 months of CEO decisions, while the database keeps every row and the Stock chart reads all of them.
14. **Balance scripts:** steady and blitzscale hire Morgan Stanley as soon as eligible and take each event's first choice.
15. **Tuning (`public.*` and `ipo.*` only):** `public.multiple` growth 25 → 18 and margin 15 → 5 (target 4: P/S was 20× in 2012–2019 because scripted IPOs list at +30–40% margins); `ipo.min_growth` 0.40 → 0.20 (target 2: blitzscale reached $80M ARR loss-making and growing 20–25% a year, so it never listed). The 25.10 worked example is tested with 25.3's own coefficients.

## Follow-ups

- **Preferred shares convert to common at the IPO** (they stay preferred on the cap table now); M14 or M15.
- **Accepting a takeover bid** (selling the company, an exit ending) needs M14's acquisitions; M13's bid can only be rejected, fought with a rights plan or answered with talks.
- **API: name the event behind each pricing option.** `PriceOptionOut` has no event choice key and `IpoOut` no event id; the front end matches the open `public` event's choices by order. An `event_id` and `event_choice` would make that explicit.
- **`CeoOut` could carry the scope-change energy** (the front end reads `exec_authority.change_energy` from the org meta).
- **Hiring's stage tables stop at 3** (`hiring.offer.stage_appeal`, `stage_equity_mult`): a public company's appeal and liquid equity could earn their own stage-4 values (lane rules kept this lane off `hiring.*`).
- **Exec-level search for a CEO from outside:** the seat appoints an employee at senior level or above; an outside CEO is hired first through the existing exec-level search.
- **The S-1, roadshow and pricing are fixed choices;** a richer S-1 (cost, delay and brand) and roadshow events that move the book could come with M15's balance pass.
- **25.9 targets with the CEO:** target 5 compares a CEO with the steady script on the e2e scale-up; M15 could add a CEO arm to the v2 strategies.
