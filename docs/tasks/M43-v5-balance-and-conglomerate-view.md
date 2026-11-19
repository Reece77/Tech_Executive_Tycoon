# M43: v5 balance and the conglomerate view (v5, lane L; closes v5)

**Goal:** close v5 on a believable, balanced game across every industry, and give the player one view of the whole conglomerate. This milestone re-tunes the earlier targets that M43a's corrected economy moved, closes or bounds every known miss, adds v5's own strategies over 30 and 60 years, and builds the **conglomerate view** Reece asked for. The `m43-done` tag closes v5.

**Formulas:** §43 (v3 targets), §51 (v4), §54 (markets), and each v5 section's targets (§45, §49, §50, §52, §53, §55, §56, §57) · **Depends on:** M42, M40, M44 · **Lane:** L

## Reece's decision (2026-11-15)

- **The conglomerate view** in M43.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m43-balance` from `main`.
- Start now with **measurement and the conglomerate view.** **Don't tune or merge until `m42-done`, `m40-done` and `m44-done` all exist**; then merge `main` and re-run everything on the combined code.
- **M43 owns:**
  - `tst/balance/` (new `v5.py` and strategies);
  - every `known_misses.py` entry (owner M43 after sub-task 1);
  - the balance keys of the v5 milestones;
  - the conglomerate view (screen, API and read model).
- **CLAUDE.md §9's decision rules apply.** Long runs go to GitHub (rule 7). **Re-banding an earlier target is still a stop-and-ask:** bring each one with its numbers.

## Sub-tasks (commit after each)

1. **Known misses:** move the four entries still owned by the finished M28 (`V3.ai`, `V5.cells`, `V5.cats`, `I1`) to owner M43, with a note.
2. **The conglomerate view:**
   - one screen across every industry the group is in: revenue, gross margin, operating profit, capital employed and return on capital by industry and by company in the group, ten-year trends, and where capital went;
   - **a capital-allocation panel**: each industry's displayed return, growth and risk, the player's planned allocation for next year, and the proposals waiting;
   - **a yearly letter to shareholders**, written in the founder's voice by the LLM within §16's budget from engine facts only (template fallback), each January, kept in History;
   - read-only, no energy;
   - hidden values never shown (displayed figures only).
3. **The IPO thresholds:** check whether M13's listing requirements are fixed dollar amounts. If so, scale them with `economy_scale.money` as M34's thresholds were (§48.1). Re-measure M13 T2.
4. **v5 strategies** in `tst/balance/`, each behaving as a sensible player would (rule 2's test):
   - **`ev_integrator`:** cars on own cells, lithium and chips;
   - **`life_sciences`:** devices into medical devices and pharma with AI discovery;
   - **`space_and_defence`:** chips into satellites, broadband and government;
   - **`robotics_first`:** industrial robots into humanoids and robotaxis;
   - **`dynasty`:** any of the above with a family to 2069;
   - **`cloud_first`:** M35b's follow-up, to measure power's effect directly.
5. **Runs on the combined code:**
   - 30-year runs (seeds 1–10, weekly 1–30) for every strategy since v1;
   - 60-year dynasty runs (seeds 1–10) for the v5 strategies;
   - dispatched on GitHub.
6. **Targets** (printed):
   - **T1, viable, not dominant:** each v5 strategy's median year-30 ARR is 0.9–1.4× its natural comparison (named in the brief's Decisions made before measuring).
   - **T2, no strategy always wins:** no strategy is top on more than 4 of 10 seeds among all strategies.
   - **T3, every system's targets hold** on the combined code: §45.8, §49.6, §50.6, §52.5, §53.4, §55.6, §56.4, §57.6, and §54.4's economy targets.
   - **T4, the known misses:** each closed, or reported with its reading, bound and cause. They are:
     - I1, V3.ai, V3.margin, V5.cells, V5.cats and V5's startup coverage;
     - V2.wins;
     - V4.T1.1, V4.T1.2 and V4.T4;
     - M13.T2.blitzscale, M13b.T1 and M22.T2.variant;
     - M28 target 2 (accepted at 12%).
   - **T5, compliance isn't free:** M34's `compliant_platform` pays at least 10% of `platform_owner`'s fines (it paid none), or M43 reports why zero is right.
   - **T6, the economy is believable:** in every year to 2069, technology stays under 15% of world GDP, and the pre-2026 AI excess in Africa and Asia (M43a's follow-up) is fixed or bounded.
7. **Tune** only the keys this lane owns (rule 1), recording before and after values. Bring any re-banding to the PM.
8. **Close-out:**
   - CHANGELOG;
   - a v5 section in the roadmap's status;
   - the README index row;
   - trigger the weekly on `main` after merging and report it.

## Acceptance criteria

- [ ] The conglomerate view and the yearly letter work on a 2039 save with at least four industries (e2e), and show no hidden values (test).
- [ ] T1–T6 printed and met, or carried with a recorded decision; T4 reported in full.
- [ ] Every earlier guard on the combined code is unchanged, or explained under rules 1–4.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m43-done`. **This tag closes v5.**

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
