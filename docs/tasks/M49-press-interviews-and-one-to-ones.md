# M49: Press conferences, interviews and one-to-ones (v6, lane A)

**Goal:** the last of v6's conversations. Press moments become live interviews with journalists, and crises become press conferences where candour matters. The player can hold Football Manager-style one-to-ones with key people about morale, ambitions and rival offers, and promises are kept or broken. All of it is on M47's engine, and all of it can be skipped.

**Formulas:** `docs/formulas.md` §61 (all), with §2, §13, §18.8, §29, §32, §40, §48, §58 · **ADRs:** 0005, 0013 (stream `talks` 72), 0023 · **Depends on:** M48 (`m48-done`) · **Lane:** A, alongside M53 (lane B) and M51 (lane C)

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m49-talks` from `main`.
- **Must not edit** M53's or M51's's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M49 owns:** the interview, crisis and one-to-one conversation kinds (`tst/sim/talks/`), their prompts, screens and `talks.*` keys, and `tst/balance/m49.py`.
- **M49 reuses** M47 and M48's conversation service, and generalises it only in small, named commits.
- **Merges first** of this round.
- §61.3 target 1 (skip is today's game) is the guard.

## Sub-tasks (commit after each)

1. **Data and models:** stream `talks`, records, `talks.*` keys, migration and data dictionary.
2. **Interviews and crisis conferences** (§61.1), mapped onto §29's tones, promises and caps.
3. **One-to-ones** (§61.2): topics, moves, tracked promises, effects scaled by personality, delegated talks.
4. **Prompts and leaks:** an allowlist only.
   - **Hidden-value test**, including adversarial player text.
   - **Tests** use MockLLMAdapter only.
5. **Screens:**
   - a press room for interviews and conferences;
   - a one-to-one panel from every person's profile and the People screen (people flagged unhappy or approached);
   - promises tracked on the person's profile;
   - skip and template mode.
6. **API, e2e, balance and close-out:**
   - **Playwright:** (a) a launch interview with a bold claim, (b) a recall press conference, (c) a one-to-one that keeps a poached engineer, (d) a broken promotion promise;
   - a practice save `pt-talks`: a stage-3 company in 2019 with two people approached by rivals and a recall pending;
   - **§61.3 targets** printed, tuning only `talks.*` (rule 1);
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] With every talk skipped, the game matches `main` before M49 (state-cache check).
- [ ] No hidden value reaches the API or a prompt (hidden-value test, adversarial text included); no test calls the Anthropic API.
- [ ] §61.3 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m49-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
