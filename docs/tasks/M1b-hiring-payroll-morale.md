# M1b: Hiring, payroll, morale, and people screens

**Goal:** the player can find candidates, learn about them, make offers, build a team of 10, pay them every month, and watch morale and resignations respond, all from the browser.

**Spec sections:** §5.2, §5.4, §13 · **ADRs:** 0003, 0005 (inbox only, no LLM), 0007, 0008, 0009, 0011 · **Depends on:** M1a

## Context

M1a built people. This brief makes them hireable and alive. The rules below summarize `docs/formulas.md` §6–§10, which is authoritative; keep every number in `balance.yaml`. Everything the player does here must also be callable by a delegate (ADR-0011), so put each action in `tst/sim/actions/` as a pure function that takes an `actor` person; the UI passes the founder for now.

## Out of scope

Departments, managers, span of control, relationships beyond storage (M2). Products, revenue (M3). Cap table math (M4; store `equity_bp` only). Poaching and acqui-hires (M5). LLM or template events (M6). Interest-driven assignments beyond the company mission (M3).

## Rules and formulas (summary of `docs/formulas.md`)

1. **Company mission:** at game start the player picks 2 interest tags as the company mission (for example `ai`, `enterprise`). Stored on `company`. Used for interest fit until products exist.
2. **Founder energy:** 100 points per month, reset in phase 1. Costs from `balance.founder.energy_cost`: interview 6, reference check 3, network intro search 10, job post 4. Actions fail with `InsufficientEnergyError` when out of energy. (Delegation to a recruiter arrives in M2; leave the `actor` parameter ready.)
3. **Candidate pools** (generated in phase 12 for next turn, stream `"hiring"`), per role the player has opened as a search:
   - `network`: free, 2–4 candidates, initial `hw` reduced by `network_intro` strength, size scaled by founder `sociability`.
   - `job_post`: costs `balance.hiring.job_post_cost_cents` ($500 in 2010), 6–10 candidates, level mix skewed junior and mid.
   - `recruiter`: fee `balance.hiring.recruiter_fee_bp` (2,000 bp of first-year salary) charged on hire, 4–6 candidates, level mix skewed senior.
   - Candidates stay in the pool for `balance.hiring.candidate_shelf_turns` (3) unless hired elsewhere (M5) or withdrawn.
4. **Offers** (resolved in phase 1 of the next turn, stream `"hiring"`):
   - `salary_ratio = offer_salary / expectation`; `equity_value = equity_bp × balance.hiring.equity_value_per_bp × stage_multiplier`.
   - `score = w_salary × (salary_ratio − 1) + w_equity × equity_value + w_fit × interest_overlap(candidate, mission) + w_stage × stage_appeal − w_risk × (10 − risk_appetite)/10`, weights from balance.
   - `p_accept = 1 / (1 + exp(−k × (score − threshold)))`; ambition above 15 raises `w_equity`.
   - Below `balance.hiring.lowball_ratio` (0.85) the candidate always declines and the reveal improves slightly (they tell you what they want: expectation shown exactly).
   - Accepted: create `employment` starting this turn, `reveal` continues via `employed_month`, recruiter fee posted if applicable. Declined: candidate leaves the pool. Both write an inbox item.
5. **Payroll** (phase 6): for each active employment, `salary_cents / 12` to `6000_salaries` and `benefits_bp` (2,000 bp in 2010) to `6010_benefits`, credited to `1000_cash`. Replace M0's placeholder overhead with `office_cost_per_head_cents` (2010: $600/month) to `6100_rent` plus a reduced `base_monthly_cost_cents`. Ledger balances; runway updates.
6. **Morale** (0–100, phase 8, stream `"morale"`): `target = 50 + pay_term + fit_term + runway_term + workload_term`.
   - `pay_term = clamp(60 × (salary / market_mid − 1), −20, +15)`
   - `fit_term = 5 × interest_overlap(person, mission) − 5 × (work_style mismatch with role)`
   - `runway_term = −10` if runway < 6 months, `−20` if < 3
   - `workload_term = 0` in M1 (a named placeholder in code and `balance.yaml`; project workload drives it from M3)
   - `morale ← morale + 0.3 × (target − morale) + Normal(0, 2 × (21 − temperament)/20)`; clamp to [0, 100]. New hires start at 65.
7. **Resignations** (phase 8): monthly probability `base_bp × (1 + max(0, 40 − morale)/20) × (21 − loyalty)/10`, plus `job_hopper` × 2. A resignation sets `employment.status = notice` with `end_turn = turn + 1`, writes an inbox item, and frees the role. Retirement per M1a rule 6.
8. **Firing:** immediate; severance `balance.payroll.severance_months` (1) of salary posted; morale of all others −3 (−6 if the fired person has `culture_carrier`).
9. **Tag reveal:** each month employed, each hidden tag reveals with probability `balance.tags.reveal_bp_per_month` (500 bp), boosted by interviews and reference checks. Revealed tags write an inbox item ("You have noticed that Priya is a natural mentor").
10. **Potential phrase:** profile shows PA as one of five phrases (limited, decent, good, excellent, outstanding) from a revealed PA range bucket narrowed by the same reveal engine (`hw` initial 40 on the 10–200 scale). Never a number.

## Sub-tasks (commit after each)

1. **Formula tests and data:** turn every worked example in `docs/formulas.md` §6–§10 into a unit test (noise disabled); add the M1b keys from §12 to `balance.yaml`; mission picker data.
2. **Actions:** `tst/sim/actions/hiring.py` (`open_search`, `interview`, `reference_check`, `make_offer`, `withdraw_offer`, `fire`) as pure functions returning new state + ledger entries + log. Each validates energy, cash, and target ids. Decisions now carry a list of these actions; phase 1 applies them in submission order.
3. **Turn phases:** candidate pool generation (phase 12), offer resolution (phase 1), payroll (phase 6), morale, resignation, tag reveal, retirement (phase 8). Update `test_turn_order.py` only if order changes (it should not).
4. **Inbox:** `inbox_item` table (turn, company, kind, title, body, link_kind, link_id, read). Log items from the sim become inbox items for the player company. Template wording in `backend/data/inbox_templates.yaml`; light-tone variants allowed per ADR-0011.
5. **Persistence and migration** for searches, candidate pools, offers, inbox, mission; data dictionary updated.
6. **API:**
   - `GET /people` (roster with displayed ranges), `GET /people/{id}` (profile: ranges, interests, revealed tags, potential phrase, employment, 12-turn morale history)
   - `GET /recruitment/searches`, `POST /recruitment/searches`, `GET /recruitment/candidates?search_id=`
   - `POST /recruitment/candidates/{id}/interview`, `/reference-check`, `/offer`, `DELETE /recruitment/offers/{id}`
   - `POST /people/{id}/fire`
   - `GET /inbox`, `POST /inbox/{id}/read`
   - `GET /founder/energy`
   - Integration test scanning every response model for forbidden hidden fields (ADR-0007).
7. **Front end** (regenerate the client first):
   - **People:** TanStack Table roster (name, role, level, age, salary, morale, form placeholder, top 3 skills as ranges); column chooser with two saved views ("Overview", "Skills"); click name → profile.
   - **Person profile:** header (name, age, role, salary, tenure, morale bar); attribute grid in three columns (Technical, Business, Leadership) using `AttributeRange`, colored by midpoint (1–5 grey, 6–10 neutral, 11–15 good, 16–20 excellent); personality grid; interests and work style chips; revealed tags; potential phrase; morale sparkline; Fire button with confirm.
   - **Recruitment:** open a search (role, channel, cost shown), candidates table with ranges and expectation, actions (interview, reference check, offer) with energy cost shown, offer modal (salary, equity bp, acceptance hint: "likely", "uncertain", "unlikely" from the displayed score band, not the true probability).
   - **Inbox:** list with unread badges, kind icons, links to the person or candidate. Inbox becomes the default home screen.
   - **Top bar:** founder energy meter.
   - Playwright: open a job-post search, advance, interview a candidate, offer at expectation, advance, see the new hire in People and a payroll drop in cash.

## Acceptance criteria

- [ ] From a fresh game the player can hire 10 people through the UI within 6 turns using the three channels.
- [ ] Payroll and benefits post monthly; the ledger balances; runway on Overview reflects payroll.
- [ ] Offer acceptance responds to salary: over 1,000 seeded offers, acceptance at 1.10× expectation exceeds acceptance at 0.95× by at least 30 percentage points (test).
- [ ] Underpaid, misfit employees lose morale and resign more often than well-paid, well-fit ones over 60 turns (seeded comparative test).
- [ ] Interviews and reference checks visibly narrow ranges; ranges never exclude the true value (property test carried over).
- [ ] No API response contains hidden fields (integration test).
- [ ] Inbox shows offer outcomes, resignations, and tag reveals with working links.
- [ ] `make check` green; golden snapshots regenerated with a CHANGELOG note; Playwright flow passes.

## Manual check (Reece)

1. New game, mission `ai` + `enterprise`, engineer founder.
2. Hire a team of 10 over a few months mixing channels; deliberately underpay two people.
3. Advance 24 turns. Expect: cash falls by payroll, the underpaid pair's morale trends down, at least some tags revealed in the inbox.
4. Fire someone and check severance in cash and the morale dip on the roster.
5. Note anything that feels off for the balance pass and the M2 brief.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
