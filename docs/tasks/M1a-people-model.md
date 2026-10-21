# M1a: People model, generator, founder, and reveal

**Goal:** every person in the game is a seeded, fully specified individual with skills, personality, interests, hidden traits, and per-observer revealed ranges; the founder is created at game start; people age and grow each month.

**Spec sections:** §5.1, §5.2, §5.3 · **ADRs:** 0002, 0006, 0007, 0008, 0011 · **Depends on:** M0

## Context

The people system is the game's core pillar. This brief builds the model and its monthly evolution, headless and fully tested. Hiring, payroll, morale, and screens follow in M1b. The formulas below are **provisional**: implement them exactly, keep every number in `balance.yaml`, and copy this section into `docs/formulas.md` as the first sub-task so tuning has one home.

## Out of scope

Hiring flow, offers, payroll, morale, resignations, UI (all M1b). Departments and managers (M2). Rivals' people (M5). Events (M6). Do not add relationships beyond the table and a neutral default.

## Attribute catalog

All attributes are floats in [1.0, 20.0] internally, displayed as integers.

| Group | Keys |
| --- | --- |
| Technical | `software_engineering`, `ml_research`, `data`, `infrastructure`, `hardware_design`, `chip_design`, `manufacturing`, `geology`, `mining_engineering`, `security` |
| Business | `product`, `design`, `sales`, `marketing`, `finance`, `legal`, `operations`, `procurement`, `recruiting` |
| Leadership | `leadership`, `mentoring`, `strategy`, `negotiation`, `communication`, `judgment_of_talent` |
| Personality | `ambition`, `loyalty`, `professionalism`, `temperament`, `adaptability`, `risk_appetite`, `ego`, `integrity`, `sociability` |
| Hidden (1–20) | `consistency`, `burnout_risk`, `big_moments`, `poachability` |
| Hidden ability | `current_ability` (derived, 10–200), `potential_ability` (stored, 10–200) |

**Interests:** 2–4 tags from `interests.yaml`: `ai`, `hardware`, `crypto`, `climate`, `security`, `gaming`, `mining`, `policy`, `design`, `fintech`, `consumer`, `enterprise`, `open_source`. **Work style:** one of `builder`, `operator`, `researcher`, `seller`.

**Behavior tags (hidden until revealed):** `mentor`, `quiet_genius`, `credit_taker`, `politician`, `maverick`, `perfectionist`, `job_hopper`, `culture_carrier`, `toxic_high_performer`. In M1a they are assigned at generation and stored with `revealed_turn = null`.

## Provisional formulas

1. **Current ability:** `CA = 10 × weighted mean of the role's primary and secondary skill values`, with weight 3 for each primary skill and 1 for each secondary skill as listed in `roles.yaml`. Skills outside the role do not count. People without a role (the founder, pooled candidates) use the role that gives them the highest CA.
2. **Generation by level:** level target CA ~ Normal(mean, sd) from `balance.people.level_ca` (starting values: junior 70±12, mid 95±12, senior 120±12, staff 140±10, principal 155±10, exec 150±15), clipped to [30, 190].
   - Primary skills: `target_CA/10 + Normal(0, 1.5)`; secondary: `target_CA/10 − 3 + Normal(0, 2)`; all others: `Uniform(1, 8)`. Clamp, then rescale primaries so derived CA is within ±2 of the target.
   - Age by level from `balance.people.level_age` ranges (junior 21–28, mid 25–35, senior 29–45, staff 32–50, principal 35–58, exec 38–62); `birth_turn = turn − age×12 − Uniform{0..11}`.
   - Potential: `PA = CA + gap`, `gap ~ Normal(gap_mean(age), 15)` clipped to ≥ 0, `PA ≤ 200`; `gap_mean` from balance (age < 25: 45, 25–29: 30, 30–34: 18, 35–44: 8, 45+: 2).
   - Personality: each `Normal(10.5, 3.5)` clipped. Hidden 1–20 traits the same.
   - Interests: 2–4, sampled with role-based weights from `roles.yaml`. Work style weighted by role.
   - Tags: for each tag, probability from `tags.yaml` conditioned on attributes (for example `mentor`: base 4%, ×3 if `mentoring ≥ 15` and `sociability ≥ 12`). Max 2 tags per person.
   - Names from `names.yaml` by region. Region weights from `balance.people.region_weights`.
   - Salary expectation (2010 USD, cents): `band(role, level).mid × (1 + (CA − level_mean)/100) × region_multiplier`, rounded to $500.
3. **Monthly growth** (phase 8), for each primary and secondary skill of the person's current role:
   `Δ = rate × age_factor(age) × max(0, PA − CA)/PA × professionalism/10 + Normal(0, 0.05)`
   with `rate = 0.12`, `age_factor`: < 25: 1.3, 25–29: 1.0, 30–34: 0.7, 35–44: 0.4, 45–54: 0.1, 55+: −0.15. Skills not used by the role decay by `0.01/month` after age 35. Clamp after every update; recompute CA.
4. **Reveal (ADR-0007):** each `(observer_company, person, attribute)` has a half-width `hw` and a fixed center offset `o ~ Uniform(−0.5, 0.5)` drawn once from stream `"people_gen"` and stored.
   - Displayed range: `min = floor(clamp(true − hw × (1 + o)))`, `max = ceil(clamp(true + hw × (1 − o)))`; if `hw < 0.5`, `min = max = round(true)`. The true value is always inside.
   - Initial `hw` for a stranger: `balance.reveal.initial_hw` (skills 5.0, personality 7.0).
   - Narrowing: `hw ← hw × (1 − strength × scout_factor)`, `scout_factor = 0.5 + judgment_of_talent/40`.
   - Action strengths (`balance.reveal.strength`): `job_post_screen` 0.20 (skills), `network_intro` 0.30 (all), `interview` 0.35 (skills and personality), `reference_check` 0.30 (personality), `scouting_month` 0.25 (all), `employed_month` 0.08 (all, scout = the company's best `judgment_of_talent`, or the founder).
   - Hidden 1–20 traits and PA are never given ranges. M1b surfaces PA only as a qualitative phrase from a revealed bucket.
5. **Founder:** chosen background from `backgrounds.yaml` (`engineer`, `salesperson`, `academic`, `ex_big_tech`; `geologist` exists but is flagged `available_in: v3`). Every skill starts at 5; the player distributes `balance.founder.skill_points = 70` with a cap of 18 per skill; the background adds fixed bonuses (for example engineer: +3 software_engineering, +2 infrastructure). Personality is chosen from 4 presets or randomized. The founding company knows its founder exactly (`hw = 0`). PA is generated as for others and hidden.
6. **Aging and retirement:** age is derived from `birth_turn`. From age 60, monthly retirement chance `balance.people.retire_bp_per_year_over_60 × (age − 59) / 12` basis points (applies in M1b once people are employed).

## Sub-tasks (commit after each)

1. **Formula reference:** create `docs/formulas.md` from the section above, with a table of every balance key used.
2. **Seed data:** `skills.yaml`, `personality.yaml`, `interests.yaml`, `tags.yaml`, `backgrounds.yaml`, `names.yaml` (7 regions: North America, Europe, East Asia, South Asia, Latin America, Africa, Oceania; at least 60 first names and 60 surnames each, culturally plausible, no real public figures), `roles.yaml` for v1 roles (software engineer, data scientist, devops engineer, security engineer, product manager, designer, sales representative, account executive, marketer, finance manager, recruiter, operations manager) with skill weights, interest weights, work-style weights, and 2010 US salary bands (approximate; for example software engineer junior $65k, mid $90k, senior $115k, staff $140k, principal $165k). Pydantic models and load tests.
3. **Sim models:** `tst/sim/people/` with `Person`, `Skills`, `Personality`, `HiddenTraits`, `RevealState`, `clamp_attr`, `current_ability`. All frozen.
4. **Generator:** `generate_person(rng, data, balance, turn, role, level, region) -> Person` and `generate_pool(...)`. Seeded tests; distribution tests over 5,000 generated people (mean CA per level within ±3 of target; all attributes in range; PA ≥ CA).
5. **Founder builder:** `build_founder(spec: FounderSpec, rng, data, balance, turn) -> Person` with validation errors for overspent or over-cap points. `tst new-game` gains `--founder-background` and `--founder-preset` with sensible defaults; the API `POST /api/saves` accepts a `founder` object.
6. **Reveal engine:** `apply_knowledge_action(reveal, action, scout_judgment, balance) -> RevealState` and `displayed_range(true, reveal) -> (min, max)`. Hypothesis: the true value is always within the displayed range; repeated actions never widen a range.
7. **Monthly people phase:** implement growth and aging inside turn phase 8 for all `employed` people (only the founder in M1a). Uses stream `"people_gen"` for noise.
8. **Persistence:** migration adding `person`, `person_skill`, `person_personality`, `person_interest`, `person_hidden`, `person_tag`, `person_reveal`, `person_state` (energy, stress, morale placeholders), `employment` (company, role, level, salary_cents, equity_bp, start_turn, end_turn, status), `relationship` (empty table). Mappers, repository functions, data-dictionary update.
9. **Golden update:** golden seeds now include the founder's CA each turn; regenerate with a CHANGELOG note.

## Acceptance criteria

- [ ] `docs/formulas.md` exists and every number in it maps to a `balance.yaml` key.
- [ ] Generating 5,000 people per level gives mean CA within ±3 of the configured target, with all attributes in [1, 20] and PA ≥ CA (test).
- [ ] The same seed generates byte-identical people (test).
- [ ] Revealed ranges always contain the true value, and never widen (Hypothesis).
- [ ] A new game creates a founder from a background and point allocation; overspending is rejected with a clear error.
- [ ] Over 120 turns, a 24-year-old founder's CA rises and a 58-year-old founder's CA is flat or declining (seeded test).
- [ ] `tst/sim` purity test still passes; `make check` green; golden snapshots updated with a CHANGELOG entry.

## Manual check (Reece)

1. `uv run tst new-game --seed 7 --name m1a --founder-background engineer`
2. `uv run tst inspect --save m1a --person founder` prints the founder's skills, personality, interests (true values are fine in this debug CLI, which is never exposed to the UI).
3. `uv run tst advance --save m1a --turns 60`, inspect again, and confirm skills grew sensibly.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
