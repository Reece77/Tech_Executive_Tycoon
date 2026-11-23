# M50: The 2008 start (v6, lane C)

**Goal:** the game can begin in January 2008, two years before the current start. The financial crisis hits the first year, and the App Store, Android and the cloud arrive on their dates. Airbnb, Uber, WhatsApp and Square are founded on their real dates. A 2010 game stays exactly as it is.

**Formulas:** `docs/formulas.md` §60 (all), with §20, §54 · **ADRs:** **0024 (new: start years before 2010)**, 0002, 0013 · **Research:** `docs/v6-research/start-2008-dossier.md` · **Depends on:** M43r (`m43rb-done`) · **Lane:** C, alongside M46 and M48

## Reece's decision (2026-11-22)

- **Start years: 2008 first,** then 2000, then 1995.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m50-start-2008` from `main`.
- **Merges after M46 and M48.** Then merge `main` and re-run every guard.
- **M50 owns:** `tst/sim/calendar.py` and the RNG factory for negative turns; the 2008–2009 entries in every data file; the new-game start-year choice; the start-turn field; `tst/balance/m50.py`; and a sentence in CLAUDE.md §7 about negative turns.
- **M50 must not edit** M46's balance keys or M48's meetings code.
- **CLAUDE.md §9's decision rules apply.** §60.3 target 1 (a 2010 game is byte-identical to `main` before M50) is the guard everything answers to.

## Sub-tasks (commit after each)

1. **ADR-0024 and the calendar:**
   - negative turns, the save's start turn, RNG streams for negative turns;
   - every place that assumes turn 0 is the start (audit: list them in Decisions made, then fix each);
   - the migration, the data dictionary, CLAUDE.md §7's sentence.
   - **Test:** a 2010 game is byte-identical (golden snapshots and the M30 state cache).
2. **Research and data:** 2008–2009 for every series, from the dossier, with every value cited, at the game's scale. The loader rejects gaps.
3. **The crisis and the platforms** (§60.2): macro, venture climate, rates and credit; app stores, Android and the cloud on their dates; rivals at 2008 values and new ones on their founding dates; eras, nodes, commodities and power.
4. **The new game:** a start-year choice (2008 or 2010) on the new-game screen, CLI (`--start-year`) and sandbox; scenarios keep their own years.
5. **API, e2e, balance and close-out:**
   - **Playwright:** start in 2008, play through Q4 2008, and see the venture climate freeze;
   - a practice save `pt-2008`: a garage start in January 2008;
   - **§60.3 targets** printed, tuning only the 2008–2009 data's calibration;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] A 2010 game is byte-identical to `main` before M50 (golden snapshots, every state cache and every guard).
- [ ] Every data series covers 2008–2009 with a cited source; the loader rejects gaps.
- [ ] §60.3 targets 2–4 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m50-done`.

## Manual check (Reece, after merge)

Start a new game in January 2008. Try to raise a seed round in late 2008, and see whether you survive to 2010.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
