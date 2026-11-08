# M24: The founder's life (lane C)

**Goal:** the founder becomes a person with a life around the company. Overwork builds stress that can burn them out. Their choices build a public persona (visionary, ruthless, beloved, reckless) that changes how staff, investors, the press, regulators and rivals treat them. Money they take out of the company goes into a personal account and can fund a foundation for a cause. Lobbying buys influence over regulators at the risk of a scandal. A legacy score sums it up.

**Spec sections:** §5 (people), §16 (events) · **ADRs:** 0002, 0003, 0005, 0007, 0013 (stream `founder` 46) · **Formulas:** `docs/formulas.md` §32 (all), with §6, §25.5, §28.4, §29, §30.1 · **Backlog:** `docs/ideas-backlog.md` (v5: the founder's life, part 1) · **Depends on:** M15a (`m15a-done`) · **Lane:** C, a third lane alongside v3 (starts with M16)

## Lane

- **Lane C,** its own session and branch (`m24-founder`). It runs alongside M16 (or M15r if M15r runs first). **Merge order: M24 merges first** (smaller); M16 then merges `main`, calls `founder.credit` for group dividends, and regenerates golden snapshots.
- **M24 owns:** new `backend/tst/sim/founder/` (stress, personal account, foundation, persona, influence, legacy); `data/events/founder.yaml`; the top bar's stress meter; the founder profile's Personal, Foundation and Persona tabs; a Government affairs panel (influence by region, lobbying spend, exposure); the legacy score on the Game over screen and Hall of Fame.
- **M24 must not edit:** `backend/tst/sim/finance/` beyond calling the existing secondary-sale and dividend code to credit the founder; M16's group, cap-table and consolidation code; `tst/balance/` strategies (M24 adds one script arm, `burnout_test`, in a new file).
- **Shared files:** `balance.yaml` (add only `stress.*`, `personal.*`, `foundation.*`, `persona.*`, `influence.*`), `docs/formulas.md` (notes in §32 only), `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **Hooks for later milestones:** `founder.credit(...)` (M16's dividends), `influence.of(state, company_id, region)` (M22's export licences).

## Out of scope

Personal investing and stock trading, family and heirs, succession (v5 part 2). Rival CEOs' own personas beyond reusing the persona text (follow-up). Elections and policy outcomes.

## Sub-tasks (commit after each)

1. **Data and formula tests:** the new keys with comments; event templates (burnout, scandal, foundation milestones); stream `founder` in ADR-0013; the §32.1 example as a unit test.
2. **Stress and burnout** (§32.1): monthly stress from energy use, recovery, Holiday, burnout's energy cut and backfire effect, the critical event, the top-bar meter. **Test:** the §32.1 arithmetic; energy use ≤ 0.6 never burns out (property test).
3. **Personal account** (§32.2): the separate book and its accounts, credits from secondaries, dividends, exits and salary. **Property tests:** the personal book balances; company ledgers never touch 9xxx accounts.
4. **Foundation** (§32.3): creation, gifts, yearly grants, cause effects.
5. **Persona** (§32.4): the four traits, their sources and drift, their effects, the profile tab, and the persona in press, staff and rival texts (LLM from engine facts, or templates).
6. **Influence and scandals** (§32.5): lobbying spend per region, influence, the antitrust effect, hidden risk, scandals as critical events. **Seeded test** of scandal timing; **hidden-value test:** risk never in the API (exposure band only).
7. **Legacy score** (§32.6) on the Game over screen and Hall of Fame, across a serial founder's companies.
8. **API, CLI, e2e and balance:**
   - **CLI:** `tst founder` (stress, persona, account), `tst foundation --create --cause`, `tst give --cents`, `tst lobby --region --monthly`.
   - **Playwright:** (a) spend all energy for four months and see burnout's event and the energy cut; (b) sell secondary shares, create a foundation and see its first grant's effects; (c) lobby in a region and see influence and exposure; a scripted scandal arrives as a critical event; (d) the legacy score on the Game over screen.
   - §32.7 targets printed and recorded; tune only M24's keys. No new xfails; report and stop on any guard that fails against `main` and that M24's keys can't fix.
   - Close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] The §32.1 example passes as a test; the personal book balances and never mixes with company books (property tests).
- [ ] The scandal risk never reaches the API or an LLM prompt (hidden-value test).
- [ ] §32.7 targets 2–5 met (printed, values recorded); target 1 holds.
- [ ] `make check` green; `make e2e` passes; merged first in its pair through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m24-done`.

## Manual check (Reece, after merge)

Play two hard months back to back and watch stress; take a Holiday month. Sell some shares after your IPO, start a foundation, and read what the press says about your persona a year later. Lobby in North America and see whether a later antitrust review goes your way, and whether a scandal finds you.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
