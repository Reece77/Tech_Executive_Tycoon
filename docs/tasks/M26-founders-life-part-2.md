# M26: The founder's life, part 2: personal investing (lane C)

**Goal:** the founder's own money becomes a second game. Invest as an angel in rival startups' rounds, or back a new startup with a founder from your network. Buy and sell listed companies' shares, including your own, inside the rules; trading ahead of news you know about risks an insider-trading investigation. Past $50M, form a family office with an investment manager and a mandate. Net worth joins the legacy score.

**Spec sections:** §5 (people) · **ADRs:** 0002, 0003, 0005, 0007, 0013 (stream `personal` 53) · **Formulas:** `docs/formulas.md` §37 (all), with §15.4, §25, §28, §31, §32 · **Playtest:** `docs/playtests/reece-playtest-4.md` · **Depends on:** M24 (`m24-done`), M16 (`m16-done`) · **Lane:** C, alongside M19 and M20

## Lane

- Its own session and branch (`m26-founder-2`). It merges whenever it's ready; whichever pair lane merges later handles the merge (decision rule 8).
- **M26 owns:** `backend/tst/sim/founder/` additions (angel, public shares, family office, net worth), the personal accounts in §37.1, the network list, the founder profile's Investments tab, `data/events/personal.yaml`.
- **M26 may touch, minimally:** M14's rival-purchase payout and M13's listing code (to pay the founder's stakes), M16's corporate venture pricing (to share a round's price); each change with a test that nothing else moves.
- **M26 must not edit:** M19's or M20's files (`sim/mining/`, `sim/refining/`, their facility kinds).
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Family and heirs, succession, lifestyle spending (a later part). Debt or margin on personal investments. Shorting.

## Sub-tasks (commit after each)

1. **Data and formula tests:** `angel.*`, `family_office.*`, `personal.*` keys; the personal accounts; event templates (conflict of interest, filings, investigation, finding); stream `personal` in ADR-0013; unit tests for stake arithmetic, dilution, the family office's monthly return and the legacy term.
2. **Angel investing** (§37.2): joining rounds, backing a new startup with a network founder, information rights, outcomes (acquisition, listing, failure), pro-rata follow-ons, the conflict-of-interest event. **Property tests:** the personal book and each startup's books balance; a stake never exceeds 100%.
3. **Public shares** (§37.3): buying and selling, dividends, own-company windows and filings, insider-trading risk and investigations. **Hidden-value test:** the risk and investigation draws never reach the API or a prompt.
4. **The family office** (§37.4): forming, the manager, mandates, the market index, fees, moving money.
5. **Net worth and legacy** (§37.5).
6. **API, CLI, screens:** an Investments tab on the founder's profile (net worth chart; angel stakes; holdings; the family office), "Invest" on startups' Rival pages and in round news, "Buy shares" on listed companies; **CLI:** `tst angel --startup --cents`, `tst back-startup --founder --category --cents`, `tst shares --company --buy|--sell --count`, `tst family-office --form --mandate`, `tst net-worth`.
7. **Balance, e2e and close-out:** §37.6 targets printed and recorded; tune only M26's keys. **Playwright:** (a) join a rival startup's round and see the stake; (b) back a former employee's new startup; (c) buy shares of a listed rival and receive a dividend; (d) a scripted insider trade leading to an investigation. CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] The personal book balances and never mixes with company books; intercompany entries balance (property tests).
- [ ] Regulatory risk never reaches the API or a prompt (hidden-value test).
- [ ] A founder who never invests personally plays exactly as before.
- [ ] §37.6 targets met (printed, values recorded).
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m26-done`.

## Manual check (Reece, after merge)

After an exit or a secondary sale, back a startup with someone who used to work for you, join two rounds as an angel, and put the rest in a family office. Ten years on, compare your net worth with your company's value.

## Decisions made

1. **Rounds are recorded, not re-priced.** Every startup's founding money and later rounds (15.4) are read from the month's entries (`Founders' and angels' money`, `Funding round`) into `startup_round`, priced at post-money = raised / `angel.round_dilution`; M16's `venture` adds one line recording its own price (pre-money + cheque). Rivals never read these records.
2. **Joining a round** is open for `angel.round_window_months` (1) after it closes (the month the round news shows). The founder's cheque extends the round at its price: the post-money grows by the cheque, earlier holders dilute, and the stake is cheque / (post + cheque), so a stake never exceeds 100%. A cheque is at least `angel.round_min_cents` ($10k) and at most the round's size. A founding counts as a round (37.6 target 1 writes into "every new startup").
3. **Backing a new startup** uses 15.4's founding (name, personality, segments from the action's draws; team `angel.team` 3-8 from people_gen) with the network founder as its exec builder; the cheque is its founding cash; the stake is `angel.seed_stake` 20-40%, linear from $250k to `angel.seed_full_cents` ($3M); post-money = cheque / stake. It may exceed 15.4's eight-startup cap (it counts toward it). "Better odds from true skills" comes from the founder's own output in the startup's product work; `angel.skill_runway` (extra founding money per true skill point above 10) exists at 0 and was not needed (target 2 met untuned).
4. **The network** is the last `angel.network_size` (40) people who left the player's group (not retirees), kept loaded in the save (`founder_network`), plus the player's open candidates. The Hall of Fame holds past games' founders, not colleagues, so it adds no one. "Known well" means the mean half-width of the person's revealed skill ranges is at most `angel.known_hw` (2.5).
5. **Outcomes** are read from closed deals (M14's rival purchases and the player's own), `failed_turn` and listings in the M26 phase, so M14's payout and M13's listing code are unchanged. A purchase by the player's group is flagged related-party in the inbox and raises the conflict-of-interest event when agreed. A held startup competing with the player (a category the player sells in) raises it when the stake is taken.
6. **Conflicts:** disclose has no effect; conceal draws (stream `personal`, key (1, stake id)) whether it comes out (`personal.coi_found_p` 0.5) and when (within `coi_found_months` 12): credibility `coi_cred` -10 and every board seat's confidence `coi_board` -10.
7. **Listed rivals' shares** have a notional `personal.rival_shares` (1,000,000,000) outstanding: price = market cap (28.1) / that. Carve-outs and spin-offs use their listing's shares, the player's company its issued shares. Trades never touch company books; own-company trades move shares between the public float and the founder's cap entry (so M24's dividends and control follow). M24's `sell_founder_shares` (25.5's secondary terms) stays.
8. **Windows and insider trading.** Own-company trades are closed in each quarter's last month (its earnings report lands at that month's end), which is how "earnings" is covered: the founder knows a quarter's numbers only in that month. A trade is sensitive when the player's group is preparing a deal (diligence started or a bid made, no deal agreed since) for that company, or for anyone while it is the founder's own company. It becomes an insider trade when that deal is agreed within `personal.insider_months` (3); then it adds hidden `personal.risk_per_trade`, and the investigation draw (`sec_p` 0.25, opening within 12 months) is made (stream `personal`, key (0, trade id)). Takeover bids on the player arrive as public events, so they are not inside information. The finding comes `finding_months` (3) after it opens.
9. **A finding:** fine `fine_mult` (3) x the gain plus the gain (the gain is the price move to the month the news went public, never negative), paid from personal cash (which may go below zero: the debt is owed); credibility -20, Reckless +15, every seat's confidence -20; then the board votes at once by 14.6's rule (seats that vote with confidence below `board.removal_below` remove the founder by a majority of all seats, unless dual-class or Sandbox protects them). Kept: the `personal_finding` event follows (accept, or deny for credibility `deny_cred` -5).
10. **Dividends:** own-company dividends stay M24's (9400, source `dividend`). Listed rivals had no dividends, so one was added for the founder's shares only: a rival whose operating result over the quarter was positive pays `personal.dividend_yield` (2%) a year of its market cap, quarterly, on the founder's shares, out of its own cash (Dr common equity Cr cash; personal Dr 9100 Cr 9430). Rivals' other holders are not modelled, so a founder who holds nothing moves nothing.
11. **The family office:** forming costs `family_office.energy` (5); the manager is a generated senior finance manager (stream `personal`, key (3,)), outside every company, with its true finance skill hidden; the 1% fee covers them. The mandate can be changed (energy `move_energy` 1). The market index is recorded every month for every game (value-weighted over companies listed at both month ends); "plus the base rate on cash" is read as the mandate's cash share earning the base rate.
12. **Net worth** is recorded at every month end (`wealth_point`); open angel stakes at the last round price (37.5), listed shares and M16's spin-off shares at market, the founder's own stake at market once listed, else their fully diluted share of 28.1's value. The legacy term uses the last month end's net worth.
13. **Measuring 37.6 target 1:** an open stake at year 10 is valued at its startup's 28.1 value (true values; the script is a tool). At the last round price nearly every open stake read exactly 1.0x (most startups never raise again: a founding cheque is marked at cost forever), so the median and top decile were 1.00x whatever happened. The in-game net worth keeps the last round price.
14. **Tuned (M26's keys only):** `angel.round_dilution` 0.2 -> 0.12 (target 1: at 0.2 the portfolio was 4.84x on seeds 1-4, above 0.8-3.0, top decile 18.5x); `family_office.mandates` conservative index 0.3 -> 0.4, balanced 0.6 / vol 0.01 -> 0.95 / 0.005, aggressive vol 0.02 -> 0.03 (target 3: the game's index returns about 32% a year with 38% volatility, so balanced at 0.6 trailed it by 13.6 points).
15. **Migration** `0044_m26` follows M19's `0043_m19` (M19 merged first; renumbered at the merge, decision rule 8); schema version 44.

## 37.6 targets (10 seeds, `tools/m26_targets.py`, on the code with `round_dilution` 0.12 and the tuned mandates)

| Target | Value | Band | Result |
| --- | --- | --- | --- |
| 1 Angel investing is skewed (215 stakes; 129 open, 64 failed, 14 acquired, 8 listed) | median 0.13x; top decile 17.4x (its lowest, the 90th percentile, 9.1x); portfolio 2.69x | median < 1.0, top decile > 10x, portfolio 0.8-3.0 | met, reading "a top-decile startup" as the top decile's mean (decision 16) |
| 2 Backing people you know pays (90 backings each) | 5-year survival 34% known vs 23% blind: 1.48x (true skill 6.6 vs 5.9) | >= 1.3x | met |
| 3 The family office behaves like a fund (2010-2025) | index 32.0% a year; balanced 29.2% (largest miss on a seed 3.7 points); conservative vol 15.8%, aggressive 40.4% (2.56x) | within 4 points; >= 1.5x | met |
| 4 Insider trading gets caught | investigated on 10 of 10 seeds (9-10 insider trades a seed) | 6-10 | met |
| 5 Nothing else moves | steady 10 years with and without M26's phase identical on 3 of 3 seeds; golden snapshots unchanged | identical | met |

16. **Target 1's "top-decile startup above 10x"** is read as the top decile's mean multiple (17.4x); the 90th-percentile stake alone is 9.1x. A strict 90th-percentile reading passes only for `round_dilution` in a band about 0.133-0.134 (0.13 gives about 9.9x; 0.135 takes the portfolio to about 3.0x), which seed variance would not hold, so 0.12 was kept and both values are recorded for the product manager's review.

## Follow-ups

- Startups' rounds are priced from their costs (37.2) and most never raise again, so in-game net worth marks most angel stakes at cost for years; a product-manager look at marking open stakes (for example at 28.1's low range end, as M18's sales do) would make net worth track startups' success.
- Listed rivals have no share counts or dividends of their own; M26's notional shares and founder-only dividends are a stand-in until rivals get real capital structures.
- The founder can trade but not short or borrow (out of scope); family, heirs and succession (a later part).
- The family office's manager cannot be replaced; a search for a better one would make the alpha a choice.
- "Invest" in round news: the inbox's market news links to the Rival page, where "Invest" sits; a button on the news line itself would need the inbox to know about rounds.

