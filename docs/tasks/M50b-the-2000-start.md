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

1. **Start years and the floor (60.4).** `START_YEARS = (2000, 2008, 2010)`, `HISTORY_START_YEAR = 2000` (turn -120). Rather than per-world reads, a history read is floored at the latest start year at or before it (`calendar.history_floor_year`/`history_floor_turn`, used by `from_2010`, `world_start_turn`, `world_year_of`, the goods' yearly change, mining's capacity path, vehicles' ramp start): a read from January 2008 sees nothing dated before 2008, so a 2008 game reads exactly what it read on `main`; a 2000 game's series step once at January 2008 (as M50's 2008 game steps at 2010). Year-end readers (telecom and media, `end_year_at`: January 2008 reads 2007.08) floor at their own first read (`END_YEAR_2008_READ = 2007.04`); found by the identity fixture, which differed from month 0 until then.
2. **The guard (60.7 target 4).** `tests/fixtures/m50b_identity_hashes.json`, recorded on `main` (d6655977's parent, before any M50b change): M30's digest of a 2008 and a 2010 game, full_integrator and research_heavy, seeds 1-2, 120 months each (research_heavy seed 2 from 2010 ends at month 31, as on `main`). Nightly test `tests/balance/test_m50b_identity.py` (a 12-month form runs in `check`).
3. **Demand before 2008.** A category with no `growth_by_year` read its 2010 growth back for every negative month (M50); before January 2008 it now divides the 2008 world's first month by each earlier month's `early_growth`, so the 2008 world is unchanged.
4. **History eras (60.5)** in eras.yaml's new `history_eras`, apart from `eras` (no era index, stream key, baseline, boost or estimate of a 2008 or 2010 game moves): social networks (2004-02, social), public cloud (2006-03, cloud hosting), video streaming (2007-01), smartphones (2007-06, devices; operating systems sell through devices), electric cars and music streaming (held to 2008-01: Tesla's Roadster production March 2008 and Spotify October 2008 are after the 2008 world's first month, which has both markets). A category one opens takes no launch (the player's, a rival startup's founding) until it arrives: on its month, or earlier by research (21.4's threshold, `eras.causer`). Prerequisites: a history era waits for those listed before it in its domain, and no other era arrives while a history era is still to come (the first runs had Mobile-first in September 2003 and Open banking in 2004 by research). An incumbent product in an opened category must launch no earlier than its era (loader check). Arrivals go to `state.era_arrivals` (no new state field, so no digest moves) with a new inbox template `history_era_arrived`.
5. **The bust (60.5).** The venture climate carries it (macro_history monthly from 2000: 1.8, the climate bounds' top, through May 2001; a 0.76-0.99 trough in 2002-2003; 1.05 by January 2008; uncapped derivation in the file). New `macro_history.ipo_closed` (July 2000 to December 2003, the brief's default; every window must end before 2008): `ipo.eligibility_problem` refuses banks then. No NASDAQ index series was added: the game's market index is built from listed companies' caps (37.4), not data.
6. **Rivals (60.6).** New `IncumbentCompany.history_only` (only in a world begun before 2008, appended at the file's end so every 2008/2010 id holds), `exit` and `exit_into` (customers move to the buyer's live product in the same category, by segment and region, then `fail_rival`; a market-news move "merged into ..."/"closed"). Added: Compaq (into HPE, 2002-05), Sun (into Oracle, 2010-01; Oracle sells no servers, so its customers return to the market), Cisco, Motorola, AOL, Yahoo, eBay, Google (listed 2004-08). Not added: Nortel, Lucent and Cisco's/Motorola's network gear (network_equipment vendors need telecom.yaml rows: a follow-up); Lehman (banks are M54's system; not in the 2008 world either); RIM (no devices before the smartphones era). HPE's 2000 `early_scale` is HP's own servers (0.15), Compaq being its own record. Entrants: 17 founded 2000-2007 (Fortinet 2000-10 to Zuora 2007-10) on their real months; MySpace, Reddit and Tumblr are consumer apps (social is scheduled-only); Palantir left out (a government prime by name).
7. **Prelaunch runway.** New `rivals.prelaunch_after_months` (12): an incumbent with nothing on sale at the start opens with key-people costs for max(36, months to its first launch + 12) months (Oracle's only line launches 45 months after January 2000 and it failed in 2004 with 36). A 2008 world's longest wait is 24 months, so its cash is unchanged.
8. **Finance rows before 2008.** `insured_limit` and `interchange_bp` gain 2000-01 rows (US $100,000, EU EUR 20,000, Japan JPY 10M; US interchange 1.7%), read only before January 2008, so a 2008 game keeps `main`'s (including its zero US limit to September 2008).
9. **Survive the bust (60.6)** uses the existing `solvent_margin` goal (solvent with a positive trailing operating margin at December 2003) for "positive cash flow without going bankrupt". Tuned with M51's method (cash $9M, $6M, $3M, $2.4M, then $3M with 60 SMB and 3 mid-market customers): the IPO-dependent passive plan (no venture round, lists when a bank will) fails 8/10; the sensible plan (`m50b.bust_sensible`: raise, launch, cut one person a month to a core of 8 when runway is under 12 months) survives and wins 10/10 at every setting tried, above M51's 3-8 band: the brief's own target (survives on >= 7) is met, and making the goal fail on survivors would need a harder goal than the brief's. Recorded here, `sensible_wins: 10`.
10. **The guided first year (42.2)**: in a world with history eras still to come, the launch step names the markets not yet open and their months. Nothing else in onboarding reads a year.
11. **Not changed:** the sandbox (still 2008-2025) and the editor's blank starts (2008, 2010); M51's scenario scripts (`tst/balance/m51.py`, M57's lane: the bust's scripts live in `m50b.py`).

## Follow-ups

(filled in by the session)
