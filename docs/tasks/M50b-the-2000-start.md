# M50b: The 2000 start (lane B)

**Goal:** the player can found the company in **January 2000**, just before the dot-com peak (NASDAQ's peak, 10 March 2000), and play through the bust, the 2000s and on. A 2008 or 2010 game is unchanged. (1995, Reece's third start year, follows as M50c.)

**Formulas:** §60 (extend it as §60.4–§60.7 for 2000) · **ADRs:** 0024 (start years; point 5: offered only when every system's data covers them) · **Precedent:** M50 (`docs/tasks/M50-the-2008-start.md`), which added 2008 · **Depends on:** `m57r-a-done`, `m57r-b-done` · **Lane:** B, alongside M60 (lane A) and M57 (lane C)

## Reece's decisions (2026-11-21, 2026-11-22)

- Start years in this order: **2008 first** (done), **then 2000**, then 1995.
- Defaults for everything else.

## Defaults for 2000 (product manager, 2026-11-28)

1. **History, not hindsight:** 2000's world has no smartphones (the iPhone is 2007, the App Store 2008), no public cloud (AWS's S3 and EC2 are 2006), no social networks of scale (Facebook 2004, YouTube 2005, Twitter 2006) and no electric-car industry (Tesla's Roadster is 2008). These categories open at their dates as eras, as M50's 2008 did for the App Store. The player can be early, by research, but can't skip the era's prerequisites.
2. **The bust is real:** the NASDAQ peak and fall (March 2000 to October 2002), September 2001, the 2001 recession, the 2003–2007 recovery and 2007's subprime start. Capital markets (§11.8 and §16) follow it: IPO windows close from mid-2000 to 2003, and valuations fall. A 2000 start begins with a hot market that turns.
3. **Rivals at their 2000 values:** among others, Microsoft (and *US v. Microsoft*, 2000–2001), Intel, IBM, Oracle, Cisco, Sun, Dell, HP and Compaq (merged May 2002), Nokia, Motorola, BlackBerry (RIM), Yahoo, AOL (with Time Warner, January 2001), eBay, Amazon, Apple (pre-iPod: the iPod is October 2001), Google (a private start-up, IPO August 2004), Nortel and Lucent. Each exits by its real date: Compaq into HP, Sun into Oracle in January 2010, Nortel's bankruptcy in January 2009, Lehman in September 2008. Entrants arrive at their founding dates. Telecom: the 3G auctions of 2000 (the UK's £22.5B, Germany's €50.8B).
4. **Chips and commodities:** process nodes 180 nm (2000), 130 nm (2001), 90 nm (2004), 65 nm (2006) and 45 nm (2007); commodity and power prices from the same sources as M50's, extended back.
5. **Currencies (ADR-0025):** the euro's first years (EUR/USD about 0.92 in 2000, 0.90 in 2001, a high near 1.58 in July 2008). The player translates from the start, as in 2008 and 2010.
6. **Founder:** the 2000 founder is ten years younger at the 2010 mark than a 2010 founder of the same age, so family and succession (§45) unfold ten years earlier. A 2000 dynasty game still ends in December 2069, or continues in sandbox (M52).

## Lane

- Its own session, in its **own clone or worktree**, on branch `m50b-start-2000` from `main`.
- **Owns:** every data series' 2000–2007 years (`backend/data/**` history sections), `START_YEARS` and `HISTORY_START_YEAR`, the 2000 eras and entrants, the start-year code, `docs/v6-research/start-2000-dossier.md` (new), formulas §60.4–§60.7, `tst/balance/m50b.py` (new).
- **Shared files** with M57 (`balance.yaml`, `incumbents.yaml`, `eras.yaml`): keep both sides on a merge. M60 owns performance internals: if a pre-2008 path is slow, report it to M60 rather than optimising it yourself.
- **Guard:** a 2008 game and a 2010 game are identical to `main` (state cache, golden snapshots, the M50 fixture).
- CLAUDE.md §9's decision rules apply.

## Sub-tasks (commit after each)

1. **Research dossier:** every series' 2000–2007 values with sources, tagged S/D/R/A as M53's and M54's dossiers were. This session can reach en.wikipedia.org (and FRED's public series where reachable); record what it couldn't check. Rivals' 2000 revenue, employees and cash; market sizes for every category open in 2000; the bust's index path; macro (rates, GDP, confidence); commodities, power, process nodes, currencies, regulation (US v. Microsoft, Sarbanes-Oxley July 2002, the EU's Microsoft case March 2004).
2. **Data and the loader:** extend every series back to January 2000. The loader rejects gaps, using M57r-A's continuity check. Categories that don't exist yet get open dates; `START_YEARS` gains 2000.
3. **The bust and capital markets:** the index path and IPO windows (§11.8, §16) from the data, with the 2000 start's opening valuations; venture funding by year (2000's peak, 2002's trough).
4. **Rivals, exits and entrants** from the dossier; M28's history fingerprint recorded for 2000–2009 on seeds 1–10.
5. **The 2000 start's scenario and onboarding:** a "Dot-com 2000" entry in the start screen, the guided first year (§42) with 2000's categories, and an M51 scenario ("Survive the bust": reach positive cash flow by the end of 2003 without going bankrupt), tuned with M51's method.
6. **Targets** (§60.4–§60.7, printed):
   - history holds (2000–2009 rivals and markets within their bands);
   - the bust bites (a passive script with an IPO-dependent plan fails on at least 6 of 10 seeds; a sensible one survives on at least 7);
   - a 2000 campaign runs to December 2029 on seeds 1–3 with no error, and its 2039-equivalent month within M60's budget once M60 has merged;
   - 2008 and 2010 games unchanged.
7. **Close-out:**
   - **Playwright:** start a 2000 game and advance into 2001;
   - a practice save `pt-2000`;
   - CHANGELOG, data dictionary, README index row;
   - merge with `Milestone-Tag: m50b-done` and confirm the tag.

## Acceptance criteria

- [ ] Every series covers 2000–2009 with a cited source; the loader rejects gaps.
- [ ] 2008 and 2010 games identical to `main`.
- [ ] §60's 2000 targets printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged with `Milestone-Tag: m50b-done`.

## Decisions made

(filled in by the session)

## Follow-ups

(filled in by the session)
