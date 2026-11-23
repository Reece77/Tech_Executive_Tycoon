# M48: Board meetings, earnings calls and investor days (v6, lane B)

**Goal:** the player attends the meetings that decide a company's fate. At quarterly board meetings, directors ask about results and plans, and answers move their confidence and votes. On earnings calls, analysts probe the numbers, and answers move sentiment and a new credibility score. Investor days present big strategy changes. All of it is built on M47's conversation engine, and every meeting can be skipped for today's outcome.

**Formulas:** `docs/formulas.md` §59 (all), with §14.6, §25.3–§25.4, §29, §58 · **ADRs:** 0005, 0013 (stream `meetings` 71), 0023 · **Depends on:** M47 (`m47-done`) · **Lane:** B, alongside M46 (lane A) and M50 (lane C)

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m48-meetings` from `main`.
- **Merges after M46.** Then merge `main` and re-run every guard.
- **M48 owns:** new conversation kinds and their engine rules (`tst/sim/meetings/`), their prompts, the meeting screens, credibility (a new company field), `meetings.*` keys, and `tst/balance/m48.py`.
- **M48 reuses** M47's conversation service, classifier, budget and template mode. It changes M47's code only to generalise it, in small, named commits.
- **M48 must not edit** M46's or M50's files.
- **CLAUDE.md §9's decision rules apply.** §59.4 target 1 (skip is today's game) is the guard.

## Sub-tasks (commit after each)

1. **Data and models:** stream `meetings`; meeting, agenda-item and credibility records; `meetings.*` keys; migration and data dictionary.
2. **Board meetings** (§59.1): agendas from facts, directors' questions, moves and bounded effects, commitments tracked as promises, votes.
3. **Earnings calls** (§59.2): analysts' questions from public numbers and guidance, moves, bounded sentiment and target effects, credibility.
4. **Investor days** (§59.3).
5. **Prompts and leaks:** allowlisted context only (ADR-0023).
   - **Hidden-value test:** planted priorities and draws never reach any prompt or reply, including with adversarial player text.
   - **Tests** use MockLLMAdapter only.
6. **Screens:**
   - a meeting room for board meetings and calls (agenda, the speaker's profile, the conversation, three suggested replies, live effects shown afterwards);
   - the credibility score on the company and market screens;
   - an investor-day planner;
   - skip and template mode;
   - glossary entries (guidance, credibility, consensus).
7. **API, e2e, balance and close-out:**
   - **Playwright:** (a) a board meeting where a commitment is made and later kept, (b) an earnings call after a miss, (c) an investor day for a new industry, (d) skip;
   - a practice save `pt-boardroom`: a listed company in 2024 that missed guidance last quarter, with an activist circling;
   - **§59.4 targets** printed, tuning only `meetings.*` (rule 1);
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] With every meeting skipped, the game matches `main` before M48 (state-cache check).
- [ ] No hidden value reaches the API or a prompt (hidden-value test, adversarial text included); no test calls the Anthropic API.
- [ ] §59.4 targets 2–4 printed and met, or carried with a recorded decision.
- [ ] `make check`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m48-done`.

## Manual check (Reece, after merge)

Load `pt-boardroom`. Take the board meeting and the next earnings call, and see whether you can keep the activist away.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
