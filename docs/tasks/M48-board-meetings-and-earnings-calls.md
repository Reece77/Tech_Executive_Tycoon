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

Engineering and design choices the spec, ADR-0023 and this brief left open (CLAUDE.md §9), each with its numbers:

1. **Credibility is 29.3's.** §59.2 calls it "new", but the company already has a 0-100 credibility (`state.credibility`, M14b) that tracks promises, is shown on the Overview and already weights guidance in §25.4's consensus. A second 0-100 "credibility" would show the player two numbers with one name, so M48 extends the existing one: guidance given on a call becomes a promise kept (+`credibility.guidance_kept`, 4) or broken (-`guidance_broken`, 10), a deflection on a real problem costs `call.deflect_cred` (3), an investor day moves it by up to 10, and it scales the calls' and investor days' gains (whole from `credibility.full_at` 50, halved at or below `half_at` 30, linear between). No company field was added.
2. **§25.4's jumps are not rescaled by credibility.** 59.2 says credibility scales "§25.4's jumps", but every game has a credibility that press moves monthly, so rescaling the report's jump would change a game that skips every meeting (target 1, the guard). Credibility already weights the player's guidance in the consensus (29.3); M48 leaves the jump as it is.
3. **The game state gains no field** (target 1 by construction). Meetings are conversations in M47's `conversation`/`conversation_round` tables (kinds `board`, `call`, `investor_day`; no migration, schema version 65). A finished meeting ends through one new action, `meeting_outcome`, in `decision_log`, which re-checks every bound and moves existing fields only: seats' confidence, `PublicCompany.sentiment`, analysts' `target_cents`, credibility, guidance (by the player) and promises. A skipped meeting, and one left open at the month end (lapsed), runs no action. Golden snapshots and M30's state cache are unchanged (a game without meetings runs no meeting code).
4. **Commitments are §29's promises** with two new kinds, `commitment` (a board commitment to the plan figure: next quarter's revenue at least the consensus once listed, else last quarter's revenue at the six-month trend) and `guidance` (guidance reaffirmed, raised or lowered on a call, or a figure promised), stored in `domain` (metric) and `level` (cents or bp), judged in phase 12 of the quarter's last month on the displayed quarter (the last three months' revenue, or their operating margin). Kept, a commitment lifts every voting director by `board.commitment_kept`; broken, it costs `commitment_broken_mult` (2) x that. They do not count against the press's three open promises and bring no press reminder (and no press draw, so a game's press stream is untouched).
5. **When.** A board meeting is held in the month after a meeting month (14.6's summary: January, April, July, October) by a company with voting directors; a call in the quarter's first month after a report, once listed and covered; an investor day once listed, at most every `investor_day.every_months` (12). One meeting of a kind a month; it runs within the month (lapses at Continue). Extraordinary meetings (a removal vote, an activist's demands) are a follow-up: today's chains for those stay as they are.
6. **Agendas** (59.1): results against plan (a problem when the board's growth term is negative or last quarter missed), next quarter's plan (with the figure), cash and runway (a problem under six months), and a director's concern when one is under `board.concern_below` (50), last quarter missed or an activist holds a stake (asked by the lowest-confidence director). A call: the guidance question first (a problem after a miss), then each covering analyst by their public focus (growth, margin, risk), up to `call.questions` (4). An investor day: the plan's economics, execution and growth, from three investors of `investor_day.firms`.
7. **Hidden priorities** (stream `meetings` 71, key (kind index, meeting turn)): a director's weights over growth, margin, risk and governance come from their personality (ambition, professionalism, 21 - risk appetite, integrity; `priority_traits`), each moved by up to `priority_noise` (30%) by the meeting's draw; an analyst weighs its public focus double; investors weigh all alike. Askers are drawn, never chosen by the priorities, so who asks reveals nothing hidden. A speaker feels an answer x (1 + `priority_weight` x (4w - 1)) x their receptiveness (0.85-1.15, drawn). Analysts' names and focus are theirs for the listing (key (call index, 0, analyst index) at the listing month). ADR-0013's row was updated to these keys (no per-item tie-breaks were needed).
8. **Moves and strength.** An answer's checked moves sum their fixed strengths (`effects`, or `problem_effects` on a real problem; within -1..1); a move the item does not bear out is neutral (`explain` needs a listed fact, `commit`/`promise` a figure, `reaffirm`/`raise`/`lower` the guidance question, one guidance move an answer). Push-back on a topic the asker weighs under a quarter takes `board.push_back_unloved`. The founder's factor (0.8-1.2 from 0.5 communication + 0.5 leadership, true values) multiplies a gain and multiplies a loss by (2 - factor); a beloved founder's gains x1.10, a ruthless founder's push-back loses /1.10; and **every answer gains `skill.impression` x (factor - 1)** (key added: the founder's manner, without which the 4-point clamp made a poor communicator's sensible answers as good as a strong one's). Board: the asker moves by strength x `item_points`, the other directors by `spill` x that, each clamped to ±`board.step` (4) a meeting. Call: sentiment by strength x `item_share`, clamped to ±3%; the asker's target by strength x `target_share`, clamped to ±5%. Investor day: the plan's economics ((last year's return on capital, the industry's if the group has it, - `hurdle` 10%) / `span` 10%, within ±1) x `economics_share` and x `economics_cred`, plus the answers; clamped to ±8% and ±10.
9. **Votes** (59.1): after the meeting each voting director backs next quarter's plan when their confidence after it plus `vote_priority` x (4 w_growth - 1) is at least `vote_at` (50). Votes are shown with the effects; they bind nothing yet (follow-up: binding votes on §40.2's one-off proposals).
10. **Raise and lower** move this quarter's revenue guidance by `call.guidance_step` (3%) from the guidance already set this month, or the consensus; the call's outcome sets it through §25.4's own rules (`guidance_problem`), by the player, keeping the margin.
11. **Energy:** a meeting costs the founder `energy` (board 2, call 2, investor day 4) when it ends; skipping costs nothing. Opening one checks the founder has it.
12. **The LLM's jobs, validated** as M47's: the classifier returns the kind's moves only (anything else, a negotiation's move included, is neutral, source `invalid`); three suggested answers within `max_message_chars`; the speaker's line (the engine's reaction, from the published strengths only, and the next question) within `max_reply_words` naming no number outside the meeting's displayed facts and figures. The player's answer is quoted as a JSON string; an investor day's plan is chosen from lists (kind, industry), never typed, so no other player text reaches a prompt.
13. **M47 generalised in small, named commits:** the cap, mode, adapter, untrusted-text cleaning, one call within the cap, its log and spend, and the busy-save wait moved to `tst/conversations/common.py` (M47's busy-wait test now patches it there); negotiations list and read only negotiation rows; the classifier schema's move enum includes the meetings' moves. Meetings spend from the conversations' cap (`llm_call_log.purpose` `meeting`).
14. **Screens:** Finance > Meetings (this month's meetings with Attend, the investor-day planner, the meeting room, past meetings, commitments), credibility as a tile on Finance > Board and Finance > Stock (with a link to this month's meetings) and in the meeting room; `tst meet` headless in template mode.
15. **Tuning (rule 1, `meetings.*` only), seeds 1-3 then 1-10.** First values (board effects explain 0.6 / commit 0.7 / concede 0.2, problem explain 0.4 / commit 0.5 / concede 0.6; `call.item_share` 0.012; `commitment_kept` 3; no impression): good +6.5 points / +5.7%, poor +6.3 points (should be lower), T3 at exactly 50% (the full-credibility call was clamped; the measure now takes one answer, below the clamp, against credibility 50). Tuned: `skill.impression` 12 (new), board effects explain 0.3 / commit 0.4 / concede 0.1, problem explain 0.2 / commit 0.3 / concede 0.4, `call.item_share` 0.002, `board.commitment_kept` 1.5, and (with the impression) `investor_day.item_share` 0.015 -> 0.008, `item_cred` 2 -> 1.
16. **Practice save `pt-boardroom`** (`tools/e2e_m48_save.py boardroom`): M13's Kestrel listed, played by the engine to January 2024, last quarter's guidance 25% above the consensus (a miss), sentiment 0.04 under the activist's bar with four of its six months counted and no activist in the last 24 months, so one arrives in two months unless the price recovers; a stage-4 team with a CTO.

### 59.4 targets (`python -m tst.balance.m48`, seeds 1-10, 60 months from M13's listed company on the steady script)

1. Skip is today's game: a game that holds no meeting runs no meeting code and the state gains no field; golden snapshots and M30's state cache unchanged (see the pull request's runs); `tests/integration/test_m48_meetings.py::test_skip_changes_nothing` (a meeting answered and then skipped leaves the state and the decision log as they were): **met**.
2. Good communicator (score 16): board confidence **+6.6** points (band 3-10), sentiment **+5.0%** (band 2-6%) against skipping: **met**. Poor communicator (score 6): **1.5** points lower (band 0-8), sentiment -0.8%: **met** (re-run on the code merged with M46; before it, +6.7, +5.0%, 1.5 lower, -1.2%).
3. After three broken guidance promises within 24 months (10/10 seeds; credibility 27 on each), the next call's gains are **50%** of the same call's at credibility 50 (at most 50%): **met**.
4. No leak: `tests/integration/test_m48_meetings.py` plants priorities, receptiveness and the founder's factor and checks every prompt and API response, with adversarial text asking for them: **met**.

## Follow-ups

- Extraordinary board meetings: a removal vote, an activist's demands and a large one-off proposal (§40.2) as meetings, with votes that bind (today those stay as events and proposals).
- Investor days with more plan kinds and a plan's own figures (a capital plan's amount, a restructuring's savings) tracked as commitments.
- A director's history across meetings (their questions, answers and confidence) on the board-member card.
- `pt-boardroom` takes about 2.5 minutes to build through the database; building it in memory as M47's `pt-negotiate` does would cut the fixtures test's time.
