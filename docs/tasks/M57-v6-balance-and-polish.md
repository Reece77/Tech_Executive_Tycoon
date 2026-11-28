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

## Follow-ups

(filled in by the session)
