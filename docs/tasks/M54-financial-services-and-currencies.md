# M54: Financial services and currencies (v6, lane A)

**Goal:** the player's fintech can grow into a bank, a payments network or an insurer, each regulated, rate-sensitive and capable of failing. Every company with foreign sales lives with currency moves, and can hedge them.

**Formulas:** `docs/formulas.md` §64 (all), with §11.8, §16, §17, §18.6, §20, §40, §44, §48, §54 · **ADRs:** 0002, 0003, 0013 (streams `finserv` 74 and `fx` 75), 0020, **0025** (currencies) · **Research:** `docs/v6-research/finance-dossier.md` · **Depends on:** `m53-done` (on `main`) · **Lane:** A, alongside M55 (lane B) and M52 (lane C)

## Reece's decisions (2026-11-21, 2026-11-22)

- **Financial services at scale** in v6: banking, payments and insurance, with regulators, capital rules and stress tests.
- **Currencies and hedging** go into the first milestone that needs them: this one.
- Defaults for everything else.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m54-finance` from `main`.
- **Must not edit** M55's or M52's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M54 owns:**
  - new `backend/tst/sim/finserv/` (banks, deposits, loans, capital, stress tests, runs, payments networks, insurers);
  - new `backend/tst/sim/fx/` (rate indexes, translation, hedges);
  - `finance_services.yaml` and `fx_history.yaml` (new);
  - the bank, payments and insurance categories (new keys after `network_equipment`), and the bank and insurance regulator kinds' data;
  - the Bank, Payments, Insurance and Currency screens;
  - `tst/balance/m54.py` (new).
- **Shared files** (keep both sides on a merge): `categories.yaml`, `incumbents.yaml` (append; ids follow merge order, as M53's decision 8), `balance.yaml`, `regulation.yaml`, `accounts.yaml`, glossary, inbox templates, formulas §64, the data dictionary, ADR-0013, CHANGELOG.
- **No fixed merge order** with M55 and M52: the first ready merges first; the others then merge `main`, re-parent their migrations on the new head, and re-run every guard.
- §64.6 target 1 (history holds, and a company with no bank, network, insurer or foreign sales plays exactly as before) is the guard.

## Out of scope

Investment banking and trading desks; asset management; health insurance; crypto and stablecoins (a follow-up); central bank digital currencies; multi-currency cash accounts (ADR-0025, point 1).

## Sub-tasks (commit after each)

1. **Research and data:** `finance_services.yaml` and `fx_history.yaml` from the dossier, every value tagged S/D/R/A with its source; `finserv.*` and `fx.*` keys; streams `finserv` and `fx`; migration and data dictionary.
2. **Currencies first** (§64.4, ADR-0025): rate indexes, translation of regional prices and local costs, the FX gain and loss accounts, forwards. **Property tests:** books balance through translation and hedge settlement; a North-America-only company's state is identical to `main`'s (state hash, seeds 1–3, 240 months).
3. **Banking** (§64.1): charters and partner banks, deposits with a chosen beta, loans and losses through the cycle, securities and their market value, capital, stress tests, runs and failure. **Property test:** a bank's balance sheet balances every month; CET1 is computed exactly (integers or exact decimals).
4. **Payments** (§64.2): networks, issuers and acquirers; interchange caps by date; real-time rails; fraud.
5. **Insurance** (§64.3): lines, combined ratio, catastrophe years, float income, solvency.
6. **Rivals and regulation** (§64.5): the banks, networks, payments companies and insurers, pinned to history before 2026 as M53's operators were; bank and insurance regulators; a bank inside a tech group under review. **Hidden-value test:** no stress-test shock, run draw or catastrophe draw reaches the API or a prompt before it happens.
7. **Screens:**
   - **Bank** (balance sheet, net interest margin, deposit beta, capital ratio against the line, stress test results, uninsured share and run risk shown as a band);
   - **Payments** (volume by region, take rate, acceptance, fraud);
   - **Insurance** (premiums by line, combined ratio, float, solvency);
   - **Currency** (exposure by region, hedges and their settlement dates, a what-if of a 10% dollar move);
   - M29 unlocks; glossary entries (net interest margin, deposit beta, CET1, risk-weighted assets, interchange, combined ratio, float, forward, translation); Explain on a bank's profit and on an FX loss;
   - the CFO delegate (§40) can run the hedging programme within its limit.
8. **API, e2e, balance and close-out:**
   - **Playwright:** (a) charter a bank from a fintech and take deposits, (b) a rate rise squeezes a high-beta bank's margin on the Bank screen, (c) hedge 80% of Europe's revenue and see the settlement;
   - a practice save `pt-bank`: a fintech group in 2019 with cash for a charter;
   - **§64.6 targets** printed, tuning only `finserv.*` and `fx.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `finance_services.yaml` and `fx_history.yaml` cite a source for every value; history to 2025 follows them.
- [ ] A company with no bank, network, insurer or foreign sales plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] Money stays integer cents through translation, interest and hedges (the float-money guard covers `finserv/` and `fx/`).
- [ ] No run, stress or catastrophe draw reaches the API or a prompt before it happens (hidden-value test).
- [ ] §64.6 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m54-done`.

## Decisions made

1. **Workspace, branch and order (2026-11-26).** This session's own clone, on branch `claude/m54-finance-i4evfk` (the cloud session's assigned branch, standing for the brief's `m54-finance`: cloud sessions push only to their own branch). Docs PR #108 (`docs-v6-round4`) was green, up to date and docs-only, so this session merged it with a merge commit before starting (rule 9). No M55 or M52 file was edited; shared files (categories, incumbents, balance, regulation, accounts, glossary, inbox templates, the data dictionary, CHANGELOG) keep both sides.
2. **Research.** Unlike M40's and M53's sessions, this one could reach FRED's CSV service, so `fx_history.yaml` is S throughout (H.10 exchange rates and the OECD's interbank rates, monthly 2008-2025, 11 currencies and 12 policy rates), and the US banks' net interest margin (to Q3 2020), all-loan and per-kind charge-off rates and deposits and loans (H.8) are S. The dossier's yearly exchange-rate table is confirmed within 1%; its NIM and charge-off figures are corrected in `finance_services.yaml`'s header. Network volumes, interchange, premiums, combined ratios, catastrophe losses, rivals' sizes and regulators stay R (recalled from the named filings and reports) or A. 2008-2009 entries follow M50's convention (a series starting in 2010 lists 2008 at its 2010 value, A).
3. **Regions and baskets.** ADR-0025 names five regions' currencies; the game has seven: Africa reads the rand and Oceania the Australian dollar (A: each region's largest floating currency). Baskets are weighted by 2020 GDP (D/A): Europe EUR 0.80, GBP 0.16, CHF 0.04; East Asia CNY 0.69, JPY 0.24, KRW 0.07; Latin America BRL 0.60, MXN 0.40 (as the ADR says, although telecom's region parts put Mexico in North America). A region's index is the basket's weighted dollar value against January 2010, built exactly at load (`Fraction`, 6 decimals, an integer x 10^6); its policy rate the same weights' average.
4. **Markets, as M53's.** Three categories in a new family `finance` (banking: `bank_consumer`, `bank_business`, its own fee index; payments: `pay_merchants`, `pay_networks`; insurance: `ins_property`, `ins_life`), growth 0, their addressable markets set each month from the data (accounts, card volume less the rails', premiums by line) at `finserv.scale` 0.085, grown from 2026 by seeded yearly rates. 25 incumbents appended (ids after M53's): 10 banks (Silicon Valley Bank's line closes in March 2023), the four card networks (lines in `pay_networks` in their regions), four acquirers (First Data stands for Fiserv's acquiring: Fiserv is already a fintech incumbent; PayPal and Stripe stay fintech) and 7 insurers, pinned to their data's shares before 2026 and held (no decisions, never failed, not ranked), as M53's operators. Rivals' books follow the data too: banks earn their accounts' deposits x the year's US margin, insurers pay the line's claims ratio, acquirers pay interchange, network fees and fraud.
5. **A bank's books** are a sub-book in integer cents: reserves (1060, apart from the company's cash, so depositors' money never pays the company's bills), loans by kind (1310), securities lots at amortised cost (1320) and deposits by segment (2310); CET1 = reserves + loans + securities - deposits exactly. The parent's capital moves cash into reserves; each December a bank above its line pays half its year's profit (at most its excess) back. Deposits move 10% a month toward accounts x the region's balance an account x the rate pull; loans fill the gap to their target from reserves above 5% of deposits, only above the capital line. Mortgages are fixed-rate (a balance-weighted book yield); other loans float (A). Charge-offs follow FRED's yearly rates to 2025 (they are the cycle), then the 2015-2019 mean x the confidence factor. A charter's opening capital is paid in at application; a partner programme in the region ends at the charter, and the new bank's deposits build from zero. A failed bank's books leave the company through 4930 and its accounts go with it.
6. **Target 1's currency guard (accepted, PM ruling 2026-11-26).** The brief's "a North-America-only company's state is identical to main's for 240 months" cannot hold from 2026: ADR-0025 point 4 translates rivals' regional lines from January 2026 and the indexes walk, so the world, and through competition the company itself, moves by design (seed 3's North American company differs from October 2026). The guard (`tst/balance/m54.py`, `tests/balance/test_m54_balance.py`, nightly, seeds 1-3, 240 months) compares the full state to December 2025 and, to December 2029, the company's currency footprint (marks, currency months, forwards, programmes, FX balances and translation entries), which stays empty; history's guard is M28's fingerprint (decision 21).
7. **Translation.** A regional price is marked at the month it was set; revenue books at price x index now / index then (half-even), while customers weigh the local price as set (appeal is unchanged). A home segment translates only when the home region is not North America. Local costs: staff working from an office abroad (salary and benefits, from their hire or last raise) and leases abroad (from their opening). Remote staff, rivals' pools (paid at North American rates), facilities' running costs, power (ADR-0025 point 7), drugs' sales and contract revenue are not translated (a follow-up).
8. **Payments.** Merchants each carry $300K of card volume a year (A); acquiring lines (every company with books) pay the region's dated interchange and the 25 bp network fee on it, and fraud of 6.5 bp less up to half for a security team at 20 (the line's builders' `security`). A network's acceptance moves 8% a month toward its share ** 0.5; its line's card-programme appeal is x clamp((acceptance / 0.3) ** 1.2, 0.2, 3). Rails take their share of both segments' volume. A bank's cards earn interchange on card balances x 0.4 a month of volume.
9. **The targets' harnesses.** Targets 2, 3 and 5 run the engine's own bank and currency phases on a new game's state moved to the target's years, the player's lines at fixed customers and the macro layer stepping monthly (a sensible player's bank: default settings, capital 9% of its first year's deposits). Target 4 plays the full game (do-nothing to December 2025, then five years).
10. **Forwards book at settlement (accepted, PM ruling 2026-11-26).** Booking a forward's fair value through profit each month (no hedge accounting) put next year's hedge moves into this year's profit, so hedging raised the spread of yearly profit on most seeds. ADR-0025 point 5 posts "at settlement the gain or loss"; fair value is now recomputed monthly and shown on the Currency screen, and only settlements book (4940/4945, below the operating result: `NON_OPERATING`). The hedge asset and liability accounts first proposed (1340, 2340) are not used and were removed.
11. **Target 4's network** is maintained: its line holds fixed scores (quality 82, brand 80, features 78; a sensible player keeps it developed), so the measure reads the network effect, not a do-nothing team's decay.
12. **A layered rolling programme.** One 12-month forward a month only lags the rate a year, which leaves yearly totals' spread unchanged. The programme buys, each month, one forward for each of the next 12 months on a twelfth of the share (each month is covered by forwards bought over the year before it; R: large groups layer their hedges). Settled forwards are kept 24 months.
13. **Target 5 is carried, untuned (PM ruling 2026-11-26: a known miss `M54.T5`, owned by M57, known while the median cut is at least 5%).** With forwards of at most 12 months (ADR-0025) and a persistent currency walk, a layered 80% hedge lowers the spread of yearly operating profit after currency results by a median of about 7% (readings below), not 15%: yearly totals already average a year of rates, and a hedge cannot outlast a lasting move. Probes of every `fx.*` dial (reversion 0.02-0.15, drift on and off, rate co-movement 0.6-1.0, larger and rarer jumps, lower sigma) moved the median between 5% and 15% only at an unrealistic four-month half-life, so nothing was tuned; meeting it needs hedges beyond a year or hedge accounting (follow-ups). "Operating profit" here includes the forwards' results (they are below the operating result in the statements).
14. **Insurers.** Premiums are the line's revenue; claims = premiums x (combined ratio - expense share) x (reference / price) x (1 - 8% x the team's finance and data skill), reserved and paid over the line's lag (9 months property, 180 life); an amount equal to the claims incurred moves from cash into 1330 and pays them, so own funds are the capital paid in plus investment income at the policy rate less 0.5 points; underwriting results fall on the company's cash. Solvency asks a year's premiums x 20% (25% in Europe from 2016) + reserves x 5-6%. Catastrophes after 2025 are drawn monthly by region (a year's chance 25% spread by the region's share) and add a year's points to that month's property claims there.
15. **Regulators.** `regulation.yaml` gains `finance_regulators` (kinds `bank` and `insurance`, strictness A with dated changes); strictness at or above 1.15 adds six months to a charter. A player group whose last month's revenue is more than half outside banking and that owns a chartered bank is reviewed each January: the bank's dividends to the group are blocked for the year. The data's dated actions (Wells Fargo's asset cap, Ant's halted listing, SVB's failure) are news only for a company already in finance, so a company without finance hears nothing.
16. **The CFO delegate** runs the hedging programme through a new guardrail, `hedge_pct` (0 by default, so every existing delegate acts exactly as before), capped at `fx.cfo_limit_share`, once 5% of revenue is foreign; it never replaces a programme the player set.
17. **Unlocks** 36 (`finserv`: the Bank, Payments and Insurance screens, from a finance line, a bank, network or insurer, or a stage-3 fintech from 2014) and 37 (`currency`: from 5% foreign revenue or any hedge). M55 runs in parallel and may take 36; whichever merges second renumbers.
18. **Hidden values.** A bank's run risk is shown as a band (low, elevated, high), never its chance; a stress test's shock is drawn when it runs and only its result stored; catastrophes are stored once they happen; the index walk holds no future month. The API test checks the schemas' field names and the served JSON, and that the event and LLM code never read the finance draws.
19. **API names.** OpenAPI component names are global, so M54's schemas avoid existing ones (`OwnBankOut`, `BankLoanOut`, `BankStressOut`, `BankRunOut`, `InsuranceLicenceOut`, `FinRegionOptionOut`), and a forward's value is `fair_value_cents` (`value_cents` is a forbidden key since M53).
20. **A 2008 game's finance markets** are 2010's (M50's convention for series that start in 2010); the 2008-2009 crisis in banking is a follow-up.
21. **History holds.** M28's fingerprint gains a `finance` series for the 25 companies' events and books; its six earlier series equal `main`'s fixture on seeds 1-10 (recorded 2026-11-26), so the finance markets change nothing to 2025 for a company without finance.
22. **M22's known miss `M22.T2.variant` (PM ruling 2026-11-26).** Nightly shard 6 read 10.6%-21.0% against the known miss's line of 21% (M46: 20.8%). Measured on seeds 1-10, clean `main` against this branch: every seed's loss with a variant rises by the same 0.16-0.17 points (seed 6, the known outlier: 20.82% -> 21.03%), from the script's accelerator selling in East Asia from October 2022 at 2022-2023's weaker yen, renminbi and won. Ruled: the line 0.21 -> 0.215 in `tst/balance/known_misses.py` (owner M57) with the reason "M54 currencies: East Asia's 2022-23 exchange rates lift every seed by 0.16-0.17 points", and `tests/unit/test_known_misses.py` (0.215 known, 0.22 a fail).
23. **M51's EV maker (PM ruling 2026-11-26).** Nightly shard 2: 63.4 target 1's sensible script wins The EV maker on 0 of 10 seeds (band 3-8; `main` 6). Seeds 1-4 on clean `main` sold 63,836, 65,266, 62,108 and 59,566 cars a year by the deadline (wins on 1 and 2); this branch 55,848, 57,250, 60,841 and 53,686 (none); this branch with `fx` removed exactly `main`'s figures, so the finance markets play no part and translation is the whole cause. The scenario's car sells abroad from 2016 (`regions_step`), and the real, the rupee, the euro and the renminbi weakened against their 2016 levels, so its dollar revenue and cash are lower, it hires and contracts less and sells 4-14% fewer cars. Rules 1-4 do not resolve it: no `fx.*` key acts before 2026, the script lacks no sensible behaviour (local repricing is a choice, not an obvious omission), it does not happen on `main`. Ruled: ADR-0025 stands (translation from the start). Rule 2's first step: the sensible script held one $35,000 price in every region, which no sensible exporter does; `ev_sensible` (`tst/balance/m51.py`) now reprices each foreign region each January back to the region's $35,000 reference at that month's rate (at most +/-10% a year) and runs a 50% rolling hedge 12 months ahead (the founder's programme: the scenario has no CFO). Readings, seeds 1-10: the sensible script wins 6 (1, 2, 5, 7, 8, 10; 59,557-65,281 cars a year by August 2023), the passive script none, as on `main` (6 and 0), so step 2 (re-tuning the goal) was not needed: the goal stays 68,500 cars by August 2023.

## Readings

Seeds 1-10, `uv run --project backend python tools/m54_targets.py` (2026-11-26):

| Target | Band | Reading | Met |
| --- | --- | --- | --- |
| 1 history holds | earlier guards unchanged | M28's six earlier series equal `main`'s fixture on seeds 1-10; the `finance` series recorded; the currency guard (decision 6) | yes |
| 2 NIM 2015-2025 | 2.5%-4.0% | 2.91% on every seed (the history's rates; seeds draw only runs and stress tests) | yes |
| 2 profit rises with the rate (beta 0.3) | correlation > 0 | 0.92 (yearly profit a dollar of deposits against the year's policy rate) | yes |
| 3 runs, over 50% uninsured | >= 3 of 10 | 4 (78% uninsured, long securities bought 2019-2021) | yes |
| 3 runs, under 20% uninsured | none | 0 | yes |
| 4 network keeps 10% for 5 years | >= 7 of 10 | 10 (15.9%-18.1% after 5 years) | yes |
| 5 80% hedge cuts yearly profit's spread | >= 15% (median) | 6.9% (0.0%-12.9%) | known miss `M54.T5` (M57; decision 13) |

Nothing tuned (rule 1): targets 2-4 met at the first keys; no `fx.*` setting within reason meets target 5.

## Follow-ups

- Re-check the R and A rows (network volumes and regional splits, interchange outside the US and EU, premiums by region, combined ratios, rivals' sizes, regulators' months) against the networks' filings, Swiss Re, the FDIC and the regulators when those hosts are reachable (decision 2).
- Hedges beyond 12 months, or cash-flow hedge accounting (fair value through equity), so a rolling programme can meet target 5 (decision 13).
- Translate remote staff by their home city, facilities' running costs, drugs' sales and contract revenue (decision 7).
- Loan vintages (fixed-rate consumer and business loans), deposit products by rate, branches as facilities (decision 5).
- The 2008-2009 crisis for banks and insurers in a 2008 game (decision 20).
- Acquired banks and insurers' balance sheets (an acquired rival keeps its data books, as M53's operators).
- Buy-now-pay-later, wallets and stablecoins (out of scope; the brief's crypto follow-up).
