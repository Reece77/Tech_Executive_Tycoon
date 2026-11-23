# M46: v6 balance pass one (v6, lane A)

**Goal:** settle what v5 handed on, before v6's new systems build on it. Close or tighten every known miss owned by the finished M43. Answer the two design questions v5 raised: why holding IPO cash beats putting it to work, and why listed companies' critical events bunch together. Then make the nightly run in six shards.

**Formulas:** §14, §23, §25, §30, §43, §51, §54 · **Depends on:** M43r (`m43rb-done`), M47 (`m47-done`) · **Lane:** A, alongside M48 (lane B) and M50 (lane C)

## Carried here

- **Known misses owned by the finished M43** (`known_misses.py`): V3.ai, V3.margin, V5.cells, V5.cats, I1, V4.T1.1, V4.T1.2, V4.T4, M13b.T1, M22.T2.variant. Also those M43 handed to "v6's first balance pass": V4 (at most 1.47×), V4.T2 (at most 5 of 10), M10b.T1.spacing (at most 5 of 10 seeds).
- **M43's design question:** a hiring-to-plan rule for a listed steady founder lowered its own ARR (about $368M down to $299M). Holding IPO cash beats deploying it.
- **M43's follow-up:** listed companies' `follow_up` critical events don't respect the director's 6-month critical spacing.
- **M43's follow-up:** the nightly in six shards.
- **Not here:** M37's 2069 month (v6's performance pass).

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m46-balance` from `main`.
- **M46 owns** `tst/balance/`, `known_misses.py`, the balance keys of the systems behind each miss, the events director's spacing for `follow_up` events, and the nightly workflow's sharding.
- It merges **first** of this round's three lanes (it moves the most balance). M48 and M50 merge `main` after it.
- **CLAUDE.md §9's decision rules apply.** Re-banding an earlier target is a stop-and-ask: bring each one with its numbers. Long runs go to GitHub (rule 7).

## Sub-tasks (commit after each)

1. **Deploying listed capital:** find why a steady founder can't put IPO cash to work at a positive return. Look at hiring's marginal value when products share one team, the cost of a hire against what it adds within 3–5 years, and whether new products, regions or acquisitions pay. Report the finding with numbers. Then make **one** change to the game (a rule or keys in the owning system's lane) so that a sensible founder can deploy listed capital at a positive return. Record why. **Target:** a listed steady founder who hires to plan, with work for every hire, ends 10 years at least 5% above one who leaves the cash idle (median, 10 seeds).
2. **Critical-event spacing:** listed companies' `follow_up` critical events respect the director's 6-month spacing (deferred, not dropped). Close `M10b.T1.spacing`.
3. **The known misses:** for each entry above, trace the cause on the current code, then close it, tighten its bound, or report it with numbers. Tune only the owning system's keys (rule 1). Fix balance scripts that lack sensible behaviour (rule 2). Move every entry still owned by "M43" to its new owner, with a note.
4. **The nightly in six shards:** rebalance with the durations file, and keep job names stable for any required checks.
5. **Close-out:** re-run everything (30-year runs on seeds 1–30, dynasty runs on 1–10); CHANGELOG; the README index row.

## Acceptance criteria

- [ ] The listed-capital target is met, with the cause and the change recorded.
- [ ] `M10b.T1.spacing` closed.
- [ ] Every listed known miss closed, tightened or reported with numbers; none left owned by a finished milestone.
- [ ] The nightly runs in six shards within its time limit.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m46-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
