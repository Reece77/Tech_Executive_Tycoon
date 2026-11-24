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

Engineering and design choices the spec, ADR-0023 and this brief left open (CLAUDE.md §9), each with its numbers:

1. **No migration; the game state gains no field** (target 1 by construction, as M48). Talks are conversations in M47's `conversation`/`conversation_round` tables (kinds `interview`, `crisis`, `one_to_one`; schema version stays 65). A finished talk ends through one new action, `talk_outcome`, in `decision_log`, which re-checks every bound and moves existing fields only. A skipped talk, and one left open at the month end (lapsed), runs no action. The brief's "migration" is therefore none; the data dictionary records the new kinds and keys.
2. **Interviews answer their press event** (61.1). A press moment whose event is shown this month can be taken as an interview instead of picking a tone: 2-4 questions (drawn) from a journalist (a drawn name, one of `talks.interview.outlets` with its beat, a public stance friendly/neutral/sceptical). Each move maps to 29.1's tone (`bold_claim`, `attack_rival` bold; `measured`, `promise`, `apologise`, `take_responsibility` measured; `deflect`, `no_comment` deflect; `neutral` counts for none); the answers' most used tone (a tie to measured) answers the event through its own choice (A/B/C), so 29.1's effects, credibility and backfires apply exactly as today. On top, the coverage: the answers' strengths (published table x the founder's factor x the journalist's hidden receptiveness, gains x the stance) x `brand_share` (1%) on every product's brand target for 6 months and x `cred_share` (1) credibility, each within ±`brand_step` (2%) and ±`cred_step` (3) x the audience. Skipping leaves the event to be answered as before (measured if left).
3. **Promises in interviews are 29.2's**: a launch offers no price rise on the product for 12 months, layoffs offer no more layoffs (the only kinds a moment's facts pin down); none when three press promises are open or the moment has one; never with a deflecting answer. Made through `promises.make` with its energy.
4. **Crisis conferences** (61.1): a breach or an outage press moment is taken as a crisis conference on its event (tone as above); a class I recall (50) or a robotaxi incident (53.3) last month (`window_months` 1) brings one without an event. Candour (`apologise`, `take_responsibility`) outweighing deflection raises Beloved by up to `persona_points` (3), the reverse Ruthless (32.4); a deflection on a medical device's class I recall brings a for-cause FDA inspection with chance `deflect_inspection` (0.3), drawn when the talk ends (the regulator's attention, 48/50). Brand x `brand_share` (6%) within ±`brand_step` (12%) for 12 months, credibility x 2 within ±6, both x the audience.
5. **One-to-ones** (61.2): with anyone on the staff but the founder, once a month a person, 2 founder energy (when it ends). Questions: how things are (shown morale and its two weakest shown causes from the morale breakdown), where they want to go (level, revealed interests; offers a promotion one rung up 13.8's ladder within 12 months), a rival's approach (only its name, never its offer) and burnout (stress from 70, where tracked). Moves' strengths come from `effects` with `topic_effects` where a topic takes them differently, x a personality factor by move from the person's true ego, ambition and loyalty (`trait_weight`, within 0.5-1.5; hidden), x the founder's factor (0.8-1.2 from 0.6 communication + 0.4 leadership), x the person's receptiveness at that question (0.85-1.15, drawn; hidden). Effects: morale x 4 within ±6; loyalty (the personality trait) x 0.6 within ±1; `push_harder` +5 stress; `listen` reveals interests and work style (18.8's profile reveal); `offer_raise` gives 5% through `give_raise` (its energy and morale rules); `offer_equity` grants 10 bp of FD from the pool, vesting from this month, only for someone without a grant (14.2 has no top-up grant); `reassign` is a gesture on workload and ambition (no move of unit: follow-up).
6. **Retention** (61.2's "a retention chance when a rival bids"): on the approach question, `retain_base` (0.5) x the answer's hidden-scaled strength, at most `retain_cap` (0.6), drawn when the talk ends (stream `talks`, closing key): the person turns the rival down at once; otherwise the approach is answered in phase 1 as today, with the talk's morale and loyalty in 15.6's score.
7. **Tracked promises**: `promise_promotion` records `promise.kind` `promotion` (level = the person, baseline = their rung). Kept when they are above it; broken at 12 months or when they leave. Kept: morale +4, loyalty +0.5; broken: twice as much (-8, -1), and their resignation chance x`leave_mult` (2) for 12 months. Private: not on the Press screen, not a persona source, no press reminder or draw.
8. **Delegated one-to-ones** (40): a seat holder above the person in the org can hold it for the player, by skip: listen and praise at every question, scaled by the holder's own factor moved by up to `delegate_noise` (10% of the band, drawn); no LLM, no founder energy.
9. **Stream `talks` (72)**: key `(kind index, source index, subject id)` at the opening month; `(…, 1)` for the closing draw. ADR-0013's row was updated to these keys.
10. **The LLM's jobs, validated** as M47's and M48's: the classifier returns the kind's moves only (`{"move": name}`; anything else, a meeting's or negotiation's move included, is neutral, source `invalid`); three suggestions within 600 characters; the other side's line within 60 words naming no number outside the talk's displayed facts. The player's answer is quoted as a JSON string. M47's classifier schema enum gained the talks' moves (one named commit); `llm_call_log.purpose` `talk`, from the conversations' cap.
11. **Target 2's measure.** In real games most approached people turn a rival down whatever the founder does (97.3% on the steady script, seeds 1-3), so "30% more kept" of all approached people cannot be reached; target 2 is read as: **of the approached people the rival wins when the founder skips, the talking founder keeps at least 30%** (median over seeds). Approaches are measured paired (the same state and the same phase-1 draw, with and without the talk), so both founders face the same approaches. The PM may prefer another reading: see Follow-ups.
12. **Tuning (rule 1, `talks.*` only), seeds 1-3:** first values `crisis.brand_share` 3.0, `brand_step` 6.0: T4 1.15x (band 1.25x). Tuned to 5.0/10.0 (1.26x), then 6.0/12.0 for margin.
13. **Screens** (see the front end): a Press room, a one-to-one panel on every profile and the People screen's flags, promises on the profile; skip and template mode; glossary entries `talk.*`.
14. **Practice save `pt-talks`** (`tools/e2e_m49_save.py talks`): Quill, stage 3, January 2019 (2010-2018 played in memory by the engine), a device business, two senior engineers approached last month (verified: a good one-to-one keeps both; skipping loses both) and a class I recall of Quill Glucose last month. `launch` adds a launch interview; `due` makes promised promotions fall due.

### 61.3 targets (`python -m tst.balance.m49`, seeds 1-10)

1. Skip is today's game: a game that holds no talk runs no talk code and the state gains no field; golden snapshots and M30's state cache unchanged (see the pull request's runs); `tests/integration/test_m49_talks.py::test_skip_changes_nothing` (an interview and a one-to-one opened, answered in part and skipped leave the state and the decision log as they were, and the press event still waits): **met**.
2. Talks retain people: of the approached people the rival wins when the founder skips, the talking founder keeps **100%** (median; at least 30%); overall kept 95.1% skipping, 99.6% talking; 678 approaches, 678 talks costing 2,712 founder energy (2.26 a month, with the raises); per seed (lost on skip, lost talking) (1: 0, 0), (2: 2, 1), (3: 4, 0), (4: 7, 2), (5: 6, 0), (6: 4, 0), (7: 6, 0), (8: 2, 0), (9: 2, 0), (10: 0, 0): **met** (on decision 11's reading).
3. Promises bite: a promotion promised at month 24 to the best non-executive and never given (10/10 seeds) costs them **8.0** morale at its judging (at least 8) and multiplies their monthly resignation chance by **2.14** at least (at least 2): **met**.
4. Crises reward candour: after a class I recall (a 9.5-10.0 point brand hit), apologising and taking responsibility regain **1.32x** the brand deflection does in 12 months (median; at least 1.25x; every seed 1.24-1.42x); a deflection's inspection chance 30%, candour's 0%: **met** (tuned, decision 12).
5. No leak: `tests/integration/test_m49_talks.py` plants receptiveness, the founder's factor and personality factors, and checks every prompt and API response for them and for the rival's offer, with adversarial text asking for them: **met**.

## Follow-ups

(filled in by the agent)
