# M57: v6 balance and polish (closes v6)

**Goal:** close v6. Every known miss is closed or re-owned by v7 with a reading, v6's new strategies are viable without one dominating, review 10's fixes are tuned in, and v6.1.0 ships.

**Formulas:** §30.7, §51, §54, §60–§66 · **Inputs:** `backend/tst/balance/known_misses.py` (20 rows, all owned by M57), `docs/reviews/review-10-consolidated.md` (rulings 6 and any Resolution row marked "M57"), every v6 brief's "Follow-ups", playtest 6 (`docs/playtests/` or the Playtest Log 6 page) when Reece has played it · **Depends on:** `m57r-a-done`, `m57r-b-done` · **Lane:** C, alongside M60 (lane A) and M50b (lane B); **merges last** and re-runs on the combined code

## Lane

- Its own session, in its **own clone or worktree**, on branch `m57-balance` from `main`.
- **Owns:** `backend/data/balance.yaml` keys named below and in each target's row, `tst/balance/**`, `known_misses.py`, `docs/balance-targets.md`, the conglomerate and strategy scripts, the v6 status section of `docs/roadmap.md`, and the polish items in sub-task 5.
- **Must not edit** M60's performance code or M50b's pre-2008 data; merge `main` often. M60 must leave results identical, and M50b must leave 2008 and 2010 games identical, so neither moves your readings; re-run every reading after each of them merges.
- CLAUDE.md §9's decision rules apply. Rule 1 covers every key listed here.

## Sub-tasks (commit after each)

1. **Readings on `main` after M57r:** run the nightly and weekly suites on the branch (rule 7) and record every target's reading against its row: `known_misses.py`'s 20 rows, M47–M55's targets, M50's and M53's new nightly tests, and the V-series. Some rows will have moved with M57r-A's RNG keys and rounding.
2. **Close the balance misses:**
   - V3.ai and V3.ai.survival: the AI-first scripts must survive; AI models' D0 ×0.19 is the lead;
   - V5.cells and V5.cats;
   - I1;
   - V4, V4.T1.1, V4.T1.2, V4.T2 and V4.T4;
   - M13b.T1;
   - M22.T2.variant;
   - M54.T5, where ruling 13 left it: either let forwards run to 24 months by a recorded decision, or show the band is wrong for 12-month hedges and ask;
   - M51.T2's three rules.

   Each is either met, or re-owned to `v7` with its reading and a one-line reason, never with a looser bound and no reason.
3. **M9.spread.africa** (review 10, ruling 6): add a fixed-broadband rival in Africa from the M53 dossier's operators (Liquid Intelligent Technologies or MTN's fixed business), or retire the cell with a recorded reason.
4. **v6 strategies:** add the telecom operator, the bank-owning group and the media studio to the strategy scripts. **Target:** each viable over 30 years (positive median company score growth on seeds 1–20), and no v6 strategy beats the field median by more than V2's dominance cap. Print alongside the v5 strategies.
5. **Polish:** the v6 briefs' follow-ups that are UI or wording only: screens, glossary, Explain, inbox text. Each takes under half a day. List what you took and what you left for v7. Also fold in playtest 6 notes if Reece has filled them in.
6. **Performance misses:** leave `M37.2069_month` and `M52.2100_month` to M60. If M60 has merged, re-read them; if it hasn't, keep their rows.
7. **Close-out:**
   - **v6 status** in `docs/roadmap.md`, as v4's and v5's were;
   - `known_misses.py` ends with only rows owned by `v7` (or M60's two, if M60 is still running);
   - CHANGELOG;
   - merge with `Milestone-Tag: m57-done` and confirm the tag;
   - add a player-facing `## v6.1.0` section to the CHANGELOG (bullets: telecom, financial services and currencies, media and entertainment, the editor and sandbox, scenarios, the 2000 start if M50b has merged) through a docs pull request;
   - dispatch `release.yml` with version `6.1.0` from `main`, confirm the release, and report.

## Acceptance criteria

- [ ] Every known miss is met, or owned by `v7` with a reading and a reason.
- [ ] The three v6 strategies are viable, and none dominates.
- [ ] Every earlier guard holds on the combined code (or is explained under rules 1–4).
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged with `Milestone-Tag: m57-done`; v6.1.0 published from `main`.

## Decisions made

(filled in by the session)

### Sub-task 4 scripts

The three v6 strategies are `tst/balance/strategies_v6.py` (`V6`); each grows out of `steady_regions`, acts only through `Game.act` and reads only what a player sees (announced auctions and reserves, build quotes, the bank's CET1 ratio and requirement and its deposits, the leads on offer as their shown ranges and fees). Their numbers are script constants there, not balance keys.

- **telecom_operator:** from `telecom.start` (January 2026), stage 3 and cash to cover it, one bid at a time in each announced low- or mid-band auction in the home region for an area and band it does not hold: as many blocks as cash covers twice, up to the auction's cap, at a limit of **4x the reserve**. The brief's "about the reserve" lost every contested auction tried (seeded rivals hold out to well above it; 2x and 3x both lost on seed 1), and the winner pays only as far as rivals push the clock, so a sensible entrant bids high and pays the clearing price. With a licence: a mobile line at **0.9x** the reference price on a team of **20** devops engineers; towers of the newest commercial generation on Ericsson radios in orders of **1,000** sites, one a year while cash covers one twice, to **75%** of a national grid; a newer generation's radios on all sites when one opens; once the mobile line is live, a fixed-broadband line (0.9x, a team of 20) and fibre in orders of **500,000** homes passed, one a year, to **5,000,000**; crews for every network order. Seeded auctions start three to six years after 2026, so the network is built from about 2030.
- **bank_group:** from 2014 (`finserv.unlock_year`), stage 3 and **$20M** of cash twice over, a banking line at the reference price on a team of **8**, its deposits held by a partner bank in the home region. It applies for its own charter after **24 months** on the partner, **not before `finserv.start` (2026)**, once cash covers the fee, the opening capital and **25% of the partner's deposits**; while it applies it puts in capital of **10%** of those deposits (M54's sensible bank opens at 9%). Settings: the deposit beta at the middle of `bank.beta_range` (**0.5**), loans **40%** and securities **50%** of deposits at a **2-year** duration (a conservative book: securities carry no risk weight and short ones cannot start a run). CET1 is kept between **1.1x** and **1.5x** its requirement: topped up to **1.25x** from cash above **12 months** of the company's costs, and capital above 1.5x brought back to the group. The "minimum capital" reading of the brief bankrupted seed 1 twice: chartering in 2018 with $0.5B of deposits, the bank grew to $16B before its charter came, every month's net interest stayed inside the under-capitalised bank (no dividends below the requirement), while the banking line's account costs stayed with the group and the partner's interest share stopped (cash fell from $258M to below zero within ten months).
- **media_studio:** from `media.start` (January 2026), stage 3 and **$20M** of cash twice over, a green light every **6 months** while fewer than **4** titles are in development: the next of a series, a film and a premium PC and console game, at the kind's typical budget (**1.0x**, the brief's mid budget), licensed out, on a studio unit of **6**; led by a free signed lead, or else the open lead with the best shown creative plus vision (the centres of the shown ranges) whose up-front share cash covers twice, signed for **3** years.

**Targets** (`tst/balance/v6.py`, `tools/v6_targets.py`, weekly `tests/balance/test_v6_balance.py` as `make weekly-v6-strategies`): each v6 strategy and every founder-played strategy of v5's field (`v5.FIELD`, 16) is played January 2010 to December 2039 on seeds 1-20, and each run's company score (30.1) read from its December 2010 (year 1) and December 2039 (year 30) snapshots; a run that fails before December 2039 scores 0 at year 30. **V6.T1 (viable):** the median of year 30's score less year 1's, in points (a difference, since year 1's score can be small), is positive. **V6.T2 (not dominant):** the strategy's median year-30 score is at most **1.4x** (`V2_BAND[1]`) the field's median, the median of the 19 field strategies' (v5's 16 and the 3 v6) own medians, so each strategy counts once.

## Follow-ups

(filled in by the session)
