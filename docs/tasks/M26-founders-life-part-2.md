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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
