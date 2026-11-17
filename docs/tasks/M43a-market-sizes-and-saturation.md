# M43a: Market sizes and saturation (v5, lane G; the first part of M43)

**Goal:** the game's economy stays believable for 60 years. Every market gets a ceiling tied to the size of the economy that buys from it, so growth fades instead of compounding forever. Each category's 2025 size is recalibrated against published figures. M37's runaway (an AI market hundreds of times world GDP by 2039, and money values near the integer limit by 2069) is closed.

**Formulas:** `docs/formulas.md` §54 (all), with §8, §21.4, §26.4, §37, §52 · **ADRs:** 0002, 0003 · **Research:** `docs/v5-research/market-sizes-dossier.md` · **Depends on:** M37 (`m37-done`) · **Lane:** G, alongside M39 (finishing) and the next v5 lanes

## The product manager's decision (2026-11-17)

M37 found the AI-models market at about $1.2–1.6T a year in 2025 (real-dollar equivalent) and $1,600–2,600T by 2039. This affects Reece's standard 30-year campaign, not only dynasty mode, so it is fixed now rather than in M43's final balance pass. History before 2026 **may change** where calibration needs it (§54.3), with every change listed.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m43a-markets` from `main`.
- **Merges after M39**: merge `main` after `m39-done`, then re-run everything on the combined code.
- **M43a owns:**
  - market growth and saturation (`tst/sim/markets/` demand growth; the era-boost application in `tst/sim/eras/` where it multiplies growth);
  - `categories.yaml`'s `growth_by_year` and starting sizes;
  - `markets.*` in `balance.yaml`;
  - the post-2025 GDP path in `macro_history.yaml` (seeded, from M37's continuation rules);
  - `tst/balance/m43a.py` (new);
  - `known_misses.py`'s `M37.money` entry (to close it).
- **M43a must not edit** any later lane's new code (M40, M42, M45 when they start). Merge `main` often.
- **CLAUDE.md §9's decision rules apply,** with §54.3's exception: history before 2026 may change, listed. Changing M8 target 4's band, or any earlier target's band, is still a stop-and-ask.

## Sub-tasks (commit after each)

1. **Research:** a 2025 published size (and 2010 and 2020 where available) for every category, with definition and source, from the dossier. Report the game's current 2025 sizes at real-dollar equivalent beside them, as a table in Decisions made.
2. **Ceilings and saturation** (§54.1):
   - `markets.ceiling_share.<category>` with sources;
   - the GDP path;
   - growth as `g × (1 − A / C)`;
   - era ceiling lifts;
   - long-run growth decaying to GDP plus a premium.
   - **Unit tests** of the formula. **Property test:** no market passes its ceiling.
3. **Calibration** (§54.2): recalibrate categories outside 0.5–2× their published 2025 size, keeping 2010 starts and curve shapes where possible. List every pre-2026 series that changes, with before and after values. Re-measure M8 target 4 and report it.
4. **Re-run everything** on the combined code: §54.4's targets, and every earlier guard (V1–V6, M8, M13b, M21–M23b, M28, M31–M35b, M36–M41).
   - Re-record M28's history fingerprint, M30's state cache and golden snapshots, with reasons.
   - Tune only `markets.*` and category growth (rule 1).
   - Apply rules 2–4 to anything that moves.
5. **Close-out:**
   - close `M37.money`, or report its reading;
   - CHANGELOG, data dictionary;
   - an economy note in `docs/economy-scale-audit.md` (what changed, and whether the audit's option C is still needed);
   - README index row.

## Acceptance criteria

- [ ] Every category has a sourced 2025 size and a ceiling; no market passes its ceiling in any year to 2069 (property test and target 1).
- [ ] §54.4 targets 1–6 printed and met, or carried with a recorded decision; `M37.money` closed.
- [ ] Every pre-2026 change is listed with before and after values; every earlier guard re-run, and the results reported under rules 1–4.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m43a-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
