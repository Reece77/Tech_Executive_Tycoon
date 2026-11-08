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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
