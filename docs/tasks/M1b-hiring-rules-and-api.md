# M1b: Hiring, payroll, and morale (rules and API)

**Goal:** the player company can search for candidates, learn about them, make offers, hire, pay, and fire, and its people's morale moves and they resign, all through the API and the command line, fully tested. Screens come in M1c.

**Spec sections:** §5.2, §5.4 · **ADRs:** 0003, 0004, 0005 (inbox only, no LLM), 0007, 0008, 0009, 0011, 0013, 0014 · **Formulas:** `docs/formulas.md` §6–§10 · **Depends on:** M1a (`m1a-done`)

## Context

M1a built people. This brief makes them hireable and alive. `docs/formulas.md` §6–§10 is authoritative for every number and rule below; keep every number in `balance.yaml`. Player actions apply at once in their own transaction and offers resolve at Continue (ADR-0014). Every action is a pure function taking an `actor` person; the API and CLI pass the founder for now, and M2 delegates will call the same functions.

M1a's decisions carry forward: `person_profile_reveal` records when interests and work style became known; `generate_pool(gen, data, balance, turn, role, levels, *, first_person_id)` generates candidates; draw order is fixed per generator.

## Out of scope

Screens and the new-game setup flow (M1c). Departments, managers, delegation (M2). Products and revenue (M3). Cap table, financing, and insolvency (M4; store `equity_bp` only). Poaching and acqui-hires (M5). LLM or template events (M6).

## Rules and formulas (summary of `docs/formulas.md`)

1. **Company mission:** 2 interest keys stored on `company`; chosen at new game (CLI and API). Existing saves migrate with an empty mission.
2. **Founder energy:** 100 per month on the founder's `person_state.energy`, spent at once by actions, reset after phase 12 (ADR-0014). Costs: interview 6, reference check 3, network search 10, job post 4, recruiter 4, offer 0. `InsufficientEnergyError` when short.
3. **Searches and candidate pools:** one role per search. Network and recruiter searches produce one batch, then close; a job post produces a batch each month until closed and costs $500 per month while open (phase 6). Batches are generated in phase 12 from stream `people_gen` keyed by search id, with sizes and level mixes in `balance.hiring.channel`. Candidates stay 3 turns.
4. **Offers:** one open offer per candidate; made at once, resolved in phase 1 of the next turn (stream `hiring`, key offer id, in offer-id order). Score and acceptance per §7; below 85% of the ask the candidate always declines. Accepted: employment starts that turn, recruiter fee posted if applicable, company moves from stage 0 to 1 on its first hire (phase 10). Declined: the candidate leaves.
5. **Payroll** (phase 6) per §8: salary and benefits per staff employment, $600 office per head (the founder counts), $500 base overhead, job-post fees.
6. **Morale** (phase 8, stream `morale`) per §9; new hires start at 65.
7. **Resignations and retirement** (phase 8, streams `resign` and `retire`) per §10 and §3; notice employments are paid that month and end in phase 1 of `end_turn`.
8. **Firing:** immediate action; severance posted; others lose 3 morale (6 if the fired person is a culture carrier).
9. **Tag reveals:** monthly for employees (stream `tags`), and one roll per hidden tag on an interview or reference check (stream `actions`); stored per observer.
10. **Founder** is excluded from payroll, morale, resignation, retirement, and firing.

## New rules from the M1b sweep

These close gaps found by checking this brief against M1a's code. Add each number to `balance.yaml` and the §12 table in `docs/formulas.md`.

1. **Live state only.** `GameState` holds staff (active and notice employments) and live candidates. When a candidate expires, declines, or is withdrawn, they leave the state; the database keeps their rows with a status (`candidate_status`: `open`, `hired`, `declined`, `expired`, `withdrawn`). This keeps every turn fast over a 360-turn campaign.
2. **Stored id counters.** Because people leave the state, the next id cannot be "highest id + 1". `GameState` gains `next_ids` (person, search, offer, employment), persisted in `save_meta`, and every new entity takes and advances its counter.
3. **Option pool.** Equity on offers is limited: at most `hiring.max_offer_equity_bp` (200) per offer, and the total held by staff plus pending offers may not exceed `hiring.option_pool_bp` (1,000, a 10% pool). Founder ownership is outside the pool (M4). Without this, equity is free in M1 and every offer could include 50% of the company.
4. **Negative cash.** M1 has no insolvency (M4). Cash may go below zero. Opening a job post requires cash of at least its first month's fee (`InsufficientCashError`); offers and payroll are never blocked. The month cash first goes negative, and every month it stays negative, the inbox gets a "You are out of cash" item. Morale's runway term treats zero or negative cash as the 3-month (critical) case.
5. **Overview data.** The snapshot gains `payroll_cents` (salaries plus benefits this month) and `avg_morale` (employees, excluding the founder; null when there are none). The overview API returns them.
6. **Previews for M1c, so no game math runs in the browser:**
   - `POST …/recruitment/candidates/{id}/offer-preview` with salary and equity returns the hint band (`likely`, `uncertain`, `unlikely`, from §7 using only known values), the 85% floor, the ratio to the ask, and any rule the offer would break (option pool, per-offer cap). No energy, no randomness, nothing saved.
   - `POST /api/meta/founder-preview` with a founder build returns the resulting skill values, points remaining, and validation errors. Current ability is never returned.
7. **New-game metadata for M1c:** `GET /api/meta/new-game` returns selectable scenarios, difficulties, backgrounds (label, description, bonuses, default allocation, availability), personality presets, skills (key, label, group), interests, and founder rules (base, points, cap, age range, default region).
8. **Inspect fix:** `tst inspect --person` shows the founder's employment level (`exec`), not "n/a".

## Sub-tasks (commit after each)

1. **Formula tests and data:** every worked example in `docs/formulas.md` §6–§10 as a unit test (noise off); M1b balance keys including the new ones above; `backend/data/inbox_templates.yaml`.
2. **State and persistence:** mission, searches, candidates with status, offers, `next_ids`, founder energy; Alembic migration; mappers; data dictionary. Existing saves migrate (empty mission, counters set from current maximum ids).
3. **Actions (ADR-0014):** `tst/sim/actions/hiring.py` with `open_search`, `close_search`, `interview`, `reference_check`, `make_offer`, `withdraw_offer`, `fire`, dispatched by `apply_action(...) -> ActionResult`; `decision_log.seq`; a replay test (start state + logged actions + turns reproduce the save exactly).
4. **Turn phases:** phase 1 (offers, ending notices), 6 (payroll, job-post fees), 8 (morale, resignation, retirement, tag reveals, `employed_month` narrowing), 10 (stage 0→1), 12 (candidate batches, expiry), energy reset. `test_turn_order.py` unchanged.
5. **Inbox:** `inbox_item` table; `LogItem` gains `template`, `params`, `link_kind` (`person`, `candidate`, `search`, none), `link_id`; persistence renders title and body from `inbox_templates.yaml` for the player company. Light-tone variants allowed (ADR-0011).
6. **API** (save-scoped under `/api/saves/{save_id}`, ADR-0009): people roster and profile (ranges, interests if known, noticed tags, potential phrase, employment, 12-turn morale history); searches (list, open, close); candidates; interview, reference check, offer, offer preview, withdraw; fire; inbox (list, mark read); founder energy; extended overview; the two meta endpoints above; new-game accepts the mission. Align the hidden-field test with ADR-0007's exact names (`current_ability`, `potential_ability`, `master_seed`, `true_*`, `hidden_*`).
7. **CLI** so hiring is playable without screens: `tst search open|close|list`, `tst candidates`, `tst interview`, `tst references`, `tst offer` (with `--preview`), `tst fire`, `tst inbox`, `tst people`. Same action functions as the API.
8. **Golden snapshots** regenerated with a CHANGELOG note; the golden run now uses the `ex_big_tech_founders` scenario and a scripted hiring plan so payroll, morale, and resignations are exercised.

## Acceptance criteria

- [ ] A scripted test hires 10 people within 6 turns from a fresh `ex_big_tech_founders` game, using all three channels.
- [ ] Payroll, benefits, office, overhead, job-post fees, recruiter fees, and severance post correctly; every entry balances; runway reflects payroll.
- [ ] Over 1,000 seeded offers, acceptance at 1.10× the ask exceeds acceptance at 0.95× by at least 30 percentage points.
- [ ] Underpaid, misfit employees lose morale and resign more often than well-paid, well-fit ones over 60 turns (seeded comparative test).
- [ ] The option pool and per-offer cap are enforced, and the offer preview reports them.
- [ ] Replaying a save's actions and turns reproduces it exactly.
- [ ] No API response contains a hidden field (exact-name test).
- [ ] 120 turns with 10 staff and an open job post average under 1 second per turn (ADR-0006 budget); the test prints the timing.
- [ ] `make check` green; golden snapshots regenerated with a CHANGELOG note.

## Manual check (Reece, command line)

1. `uv run tst new-game --seed 11 --name m1b --scenario ex_big_tech_founders --company-name "Test Co" --mission ai,enterprise`
2. `uv run tst search open --save m1b --role software_engineer --channel job_post`, then `uv run tst advance --save m1b --turns 1`.
3. `uv run tst candidates --save m1b`, interview two, `uv run tst offer --save m1b --candidate <id> --salary <ask> --equity-bp 50 --preview`, then send it and advance one turn.
4. `uv run tst inbox --save m1b` shows the outcome; `uv run tst people --save m1b` shows the hire; cash fell by payroll.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
