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

1. **Stream name.** ADR-0013's row named stream 46 `founder`, but `founder` (id 7) is already the founder build's stream. Stream 46 is `founder_life` (key `(company_id,)`); the ADR row and §32.5 say so.
2. **The founder's secondary sales.** §25.5's secondary offering issues new shares and raises cash for the company; nothing sold the founder's own shares. M24 adds `sell_founder_shares`: the founder sells their own shares into the public float at §25.5's secondary terms (P × 0.95, a 3% fee, at most 10% of the shares a sale, energy `public.capital.secondary_energy`); the company's books do not move and the net reaches 9100. It lives in `tst/sim/founder/personal.py`; nothing in `finance/` changed.
3. **The personal book** is its own table (`personal_entry`) and its own chart (`personal_accounts` in `accounts.yaml`, 9100–9400). `LedgerEntry` refuses a 9xxx line and the loader refuses a company account coded 9xxx, so the books cannot mix. Income: secondaries, the founder's share of dividends (where M13 pays them), exit proceeds kept (`found_again`'s kept cents; all proceeds on Retire) and salary after `personal.tax_rate` (founders start on 0 salary, so usually nothing).
4. **Holiday.** `Decisions.holiday` marks a month played on Holiday (logged with the turn); replay feeds each turn's logged decisions back in. §32.1's terms add up: a Holiday month is also a month at or below 0.6 (−8 − 25). M7b's "a 12-month Holiday equals 12 Continues" now holds for everything but the founder's stress record, and the test says so.
5. **Burnout's answers.** "Take a month off" is this month: the founder's energy goes to 0 at once and the month counts as away. "Delegate more" has no engine effect; the event card links to the Executive team panel (on Org). "Push on": stress +5 and Reckless +4. Scripts take the first choice, a month off.
6. **"A bold answer's backfire chance doubles."** §29.1's backfire is not a chance (it happens when results contradict the claim), so a claim made while burnt out costs `stress.backfire_mult` (2) backfires' credibility when it backfires.
7. **Scandals.** The hit (credibility −15, brand −6 on every product, the region's influence to 0, a fine of 0.5% of the trailing 12 months' revenue to 6900, Ruthless +10, Reckless +5) lands when it breaks, at the month end; the critical event comes the next month. There is no head of government affairs in the game, so the second choice is **drop the lobbying firm** (the region's lobbying stops). Fighting it brings a second story (the hit again, no fine) if a draw made when it broke says so; that draw is hidden like the risk. A scandal does not reset the risk.
8. **The foundation** grants each December (the first December after a gift). Education's +0.03 scales with the year's grants up to $10M (`foundation.hiring_full_dollars`; 32.7 target 5) and applies while the company's HQ is in the founder's home region at creation; climate adds 2 brand-target points to products with a consumer segment; health adds 1 morale-target point (a new `founder` morale term, shown as "The founder"); local makes searches' candidate batches × 1.05 (rounded half up) while the HQ is that city.
9. **Persona sources** are read each month from records stamped with the month (eras caused, bold answers, launches in a category the company had not launched in, a top-10 place in January's lists, a month's firings of 10%+, offers accepted through poach searches, promises kept and broken, covenant breaches, raises to at least `persona.raise_share` (25%) of staff), plus two actions (a hostile tender, and a failed one). Beloved's "+1 brand" for a bold answer is +1% on the brand target for 3 months, in the press's units.
10. **Persona in texts**: `{persona}` (the strongest trait in words once above 20, else "little known to the public") in the launch and layoffs press events, the founder's persona in every event's LLM context, and rival CEOs' feud replies name it.
11. **Not wired: Visionary's investor heat and Reckless's lenders' rates.** Both live in `backend/tst/sim/finance/` (round heat, loan pricing), which M24 may not edit beyond crediting the founder. They are follow-ups; the profile's trait text leaves them out.
12. **Legacy** uses the best stored company score (§30.1, every December and at a game's end) over the founder's ventures and current company, and the traits as they stand.
13. **Tuned (M24's keys only):** `foundation.beloved_k` 2 → 3 (at 2, $10M a year raised Beloved 4, under target 5's 5–10) and `influence.risk_rate` 0.002 → 0.0005 (target 4: a scandal on 8 of 10 seeds at 0.002, 5 at 0.0005; $500k a month then reads "medium" exposure).
14. **§32.7 target 3: the product manager's ruling (2026-11-07), option (c).** As first built, blitzscale's scripted founder did nothing §32.4 counts as Ruthless or Reckless, so every trait sat at 20 at year 10 (0 of 10). The ruling added three Reckless sources, each with a `persona.*` key and a unit test: a month burning cash with runway under 6 months (+2, at most +12 a calendar year), a down round (+8 in the ruling), and, each December, headcount up more than 100% over the year (+5; the first year counts from the founding headcount, else blitzscale's 1 → 16 in its first year never counted). It also changed the measure: a top trait counts only when it leads the next by at least 5 (`m24.T3_LEAD`), so ties count for neither half.
15. **`persona.sources.down_round` tuned 8 → 70.** Blitzscale burns with little runway only in its first two years and its down rounds close in months 87–99 (8 of 10 seeds; seed 5's is in month 36). With the 2-a-month drift a source at month t shows at month 119 only as `min(100, 20 + S) − 2 × (119 − t)`, so six seeds need S ≥ 59; 70 gives 8 of 10 with margin. The ruling allowed tuning source sizes; the drift and the other keys are unchanged. A down round now takes the founder to Reckless 90, whose credibility effect (drift toward 45) runs for about 2.5 years after it. The guard suite decides whether that moves anything.

16. **Migration** `0037_founder` follows M15a's `0036_m15a` (merged before M24); schema version 37.

## Follow-ups

- `persona.sources.down_round` 70 is nine times the ruling's +8 because the year-10 snapshot sits behind a 2-a-month drift; a product-manager look at the drift (or a snapshot that averages the last year) would let the source return toward +8.
- Visionary's investor heat (+0.05 in rounds) and Reckless's lenders' rates (+1 point): one-line hooks in `finance/fundraising.round_heat` and the loan offer's rate, for a milestone allowed in `finance/` (M16 or after).
- M16: call `founder.personal.credit(state, person_id, cents, "dividend")` for group dividends, and regenerate goldens after the merge.
- M22: export licences and tariffs read `founder.influence.of(state, company_id, region)`.
- Rival CEOs' own personas (beyond naming the player's in their replies).
