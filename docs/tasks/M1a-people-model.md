# M1a: People model, generator, founder, and reveal

**Goal:** every person in the game is a seeded, fully specified individual with skills, personality, interests, hidden traits, and per-observer revealed ranges; the founder is created at game start; people age and grow each month.

**Spec sections:** §5.1, §5.2, §5.3 · **ADRs:** 0002, 0006, 0007, 0008, 0011, 0012, 0013 · **Depends on:** M0

## Context

The people system is the game's core pillar. This brief builds the model and its monthly evolution, headless and fully tested. Hiring, payroll, morale, and screens follow in M1b. The formulas below summarize `docs/formulas.md` §1–§5, which is authoritative: implement them exactly as written there, with worked examples as test cases, and keep every number in `balance.yaml`.

**Seed data is already drafted.** `backend/data/` contains `skills.yaml`, `personality.yaml`, `interests.yaml`, `regions.yaml`, `roles.yaml`, `tags.yaml`, and `backgrounds.yaml`, written by the product side and checked against `docs/formulas.md`. Do not change their values; write Pydantic schemas that fit them, load them in `tst/loader.py`, and raise any value you think is wrong as a question. Only `names.yaml` remains for you to write.

Two engine changes come with this milestone. `advance_turn` gains its sixth argument, `data: GameData`, after `balance` (ADR-0012). `RngFactory.stream` gains entity keys, and every random draw uses its own stream name (ADR-0013); without this, growth and later tag and resignation rolls would reuse the same random numbers.

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

## Formulas (summary of `docs/formulas.md`)

1. **Current ability:** `CA = 10 × weighted mean of the role's primary and secondary skill values`, with weight 3 for each primary skill and 1 for each secondary skill as listed in `roles.yaml`. Skills outside the role do not count. Candidates always have a role (the role of their search). The founder has no hiring role and uses their best-fit role, recomputed monthly (`docs/formulas.md` §1).
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
   `Δ = rate × a(age) × max(0, PA − CA)/PA × professionalism/10 × max(0, 1 + Normal(0, growth.noise_rel_sd)) − d(age)`, with `noise_rel_sd = 0.25`
   with `rate = 0.12`; growth factor `a(age)`: < 25: 1.3, 25–29: 1.0, 30–34: 0.7, 35–44: 0.4, 45–54: 0.1, 55+: 0; monthly decline `d(age)`: 0 below 50, 0.005 at 50–54, 0.015 at 55+. Skills outside the role change only by `−d(age)`, with no noise. Clamp after every update; recompute CA.
4. **Reveal (ADR-0007):** each `(observer_company, person, attribute)` for the 25 skills, 9 personality traits, and PA has a half-width `hw` and a fixed center offset `o ~ Uniform(−0.5, 0.5)`, drawn once from stream `reveal` keyed by `(observer_company_id, person_id)` and stored.
   - Displayed range: `min = floor(clamp(true − hw × (1 + o)))`, `max = ceil(clamp(true + hw × (1 − o)))`; if `hw < 0.5`, `min = max = round(true)`. The true value is always inside.
   - Initial `hw` for a stranger: `balance.reveal.initial_hw` (skills 5.0, personality 7.0).
   - Narrowing: `hw ← hw × (1 − strength × scout_factor)`, `scout_factor = 0.5 + judgment_of_talent/40`.
   - Action strengths and which attributes each narrows: `docs/formulas.md` §4 table.
   - The four hidden 1–20 traits have no reveal record. PA has one, but is only ever shown as a phrase (M1b). CA is never shown.
5. **Founder:** chosen background from `backgrounds.yaml` (`engineer`, `salesperson`, `academic`, `ex_big_tech`; `geologist` exists but is flagged `available_in: v3`). Every skill starts at 5; the player distributes `balance.founder.skill_points = 70` with a cap of 18 per skill; the background adds fixed bonuses and carries a default allocation used when none is given. Personality is one of 4 presets (visionary, operator, hustler, scientist, defined in `backgrounds.yaml`) or randomized. Age 22–60, default 28. The founding company knows its founder's skills and personality exactly (`hw = 0`); PA is generated as for others and shown only as a phrase. The founder gets an employment row (role `founder`, level `exec`, salary 0) and is excluded from payroll, morale, resignation, retirement, and firing in M1 (`docs/formulas.md` §5).
6. **Aging and retirement:** age is derived from `birth_turn`. From age 60, monthly retirement chance `balance.people.retire_bp_per_year_over_60 × (age − 59) / 12` basis points (applies in M1b once people are employed).

## Sub-tasks (commit after each)

0. **Hard-coded number check (ADR-0008):** before any M1a logic, add the deferred test that fails on numeric literals in `tst/sim` other than 0, 1, −1, 2, 12, and 100 outside `rng.py` and `calendar.py`, with a `# tunable-exempt: <reason>` escape. M1a adds dozens of tunables, so this check must exist first.
1. **Formula tests first:** turn every worked example in `docs/formulas.md` §1–§5 into a unit test (noise disabled), and add each §12 balance key used by M1a to `balance.yaml`.
2. **Seed data:** write schemas in `tst/sim/data_models.py` for the seven drafted files and load them in `tst/loader.py` (add them to `DATA_FILES` so they are hashed). Cross-checks at load: every skill, trait, interest, and work-style key a file mentions exists; each background's default allocation spends exactly `founder.skill_points` within the cap; tag exclusions are mutual. Write `names.yaml` keyed by the 7 region keys in `regions.yaml`: at least 60 first names and 60 surnames each, culturally plausible, no real public figures. Load tests for each file, including a broken fixture per file.
3. **Sim models and RNG:** `tst/sim/people/` with `Person`, `Skills`, `Personality`, `HiddenTraits`, `RevealState`, `Employment`, `clamp_attr`, `current_ability`. All frozen. `GameState` gains `people` and `employments` (tuples sorted by id) and `reveals`. Extend `RngFactory.stream(turn, name, *key)` and `STREAM_IDS` per ADR-0013, with a test that no stream name is used at two call sites; M0 golden snapshots must not move from this change alone.
4. **Generator:** `generate_person(gen, data, balance, turn, role, level, region) -> Person`, where `gen` is a `numpy.random.Generator` the caller obtains from the right stream (ADR-0013), and `generate_pool(...)`. Seeded tests; distribution tests over 5,000 generated people (mean CA per level within ±3 of target; all attributes in range; PA ≥ CA).
5. **Founder builder:** `build_founder(spec: FounderSpec, rng, data, balance, turn) -> Person` with validation errors for overspent or over-cap points. `tst new-game` gains `--founder-background` and `--founder-preset` with sensible defaults; the API `POST /api/saves` accepts a `founder` object.
6. **Reveal engine:** `apply_knowledge_action(reveal, action, scout_judgment, balance) -> RevealState` and `displayed_range(true, reveal) -> (min, max)`. Hypothesis: the true value is always within the displayed range; repeated actions never widen a range.
7. **Monthly people phase:** implement growth and aging inside turn phase 8 for everyone with an `active` or `notice` employment (only the founder in M1a). Noise uses stream `growth` keyed by person id. Snapshot `headcount` counts `active` and `notice` employments, so it is 1 from turn 0.
8. **Persistence:** migration adding `person`, `person_skill`, `person_personality`, `person_interest`, `person_hidden`, `person_tag` (true tags), `person_tag_reveal` (person, observer company, tag, revealed_turn), `person_reveal`, `person_state` (energy, stress, morale), `employment` (company, role, level, salary_cents, equity_bp, start_turn, end_turn, status `active`/`notice`/`ended`, end_reason `resigned`/`fired`/`retired`/null), `relationship` (empty table). Mappers, repository functions, data-dictionary update.
9. **Golden update:** the golden test also records the founder's CA each turn in its own fixture output (not in `turn_snapshot`, which the API returns; CA must never reach the API). Regenerate with a CHANGELOG note.

## Acceptance criteria

- [ ] Every worked example in `docs/formulas.md` §1–§5 passes as a unit test, and every M1a key from §12 exists in `balance.yaml`.
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

Settled with Reece during the build:

- **`person_reveal` stores `hw` and `center_offset`**; displayed min/max are derived on read, so ranges follow skill growth. ADR-0007 is amended to match. The "never widen" property asserts that `hw` never increases, and that for a fixed true value the displayed width never grows.
- **Founder gaps:** interests and work style are drawn with the best-fit role's weights (computed after the allocation is applied), and tags are rolled per §2. The founding company sees them from turn 0. Region comes from `founder.default_region`, and the name from that region's pool, unless supplied. `FounderSpec` may override interests and work style. All of this is recorded in `docs/formulas.md` §5, with the new key in §12.
- **Sub-task 1** landed as pure functions in `tst/sim/people/formulas.py` (numbers from `Balance`, no randomness), with one test per worked example.

Engineering decisions made by the agent:

- **New balance key `people.interest_count: [2, 4]`** (added to §12). §2.6's "2–4 interests" otherwise needed a literal the sub-task 0 check forbids.
- **Scale definitions** (attribute 1–20, ability 10–200, the CA weights 3/1, the professionalism and salary divisors) live in `tst/sim/scale.py`, marked `# tunable-exempt`. The same comment exempts the reveal offset bounds (±0.5), the hw < 0.5 exact-display threshold, the basis-point denominator, and name/company column widths.
- **Generator signatures:** `generate_person(...)` takes a keyword-only `person_id`. `generate_pool(gen, data, balance, turn, role, levels, *, first_person_id)` draws each person's region by `people.region_weights`. Channel sizes and level mixes are M1b.
- **Primary rescaling** happens only when the drawn CA misses the target by more than `people.ca_tolerance`. The common factor is then solved exactly on the clamped, piecewise-linear primary sum. A target outside what clamped primaries can reach gets the nearest reachable CA.
- **Draw order is fixed and documented** in `generator.py` and `founder.py`. Tag rolls draw one number per tag even after the cap or an exclusion, so the draw count never varies. The interest count is capped at the number of interests with non-zero weight.
- **Founder allocation** must spend exactly `founder.skill_points`; underspending is rejected as well as overspending.
- **`apply_knowledge_action`** takes keyword `turn` (for `last_updated_turn`) and `skill_keys` (to group attributes), beyond the brief's four arguments. Interviews and network intros also reveal interests and work style.
- **"Range contains the true value":** once `hw < 0.5` the range collapses to `round(true)`, so the property checks the rounded value there and the exact value otherwise.
- **Extra table `person_profile_reveal`** (observer, person, `revealed_turn`) records when a company learned interests and work style (§4). `person_hidden` stores `potential_ability` as one more row. Attribute tables carry `position` so file order round-trips. `person_state` and `relationship` are created empty.
- **Golden snapshots** were regenerated in sub-task 8 (headcount becomes 1 once the founder is persisted) so every commit stays green. Sub-task 9 adds the founder-CA fixtures.

## Follow-ups

- The API hidden-field test still matches substrings (`potential`, `hidden`). ADR-0007 now asks for exact names, so it will block `potential_phrase` in M1b; align it then.
- Growth noise is now multiplicative on the growth term (`growth.noise_rel_sd` 0.25, settled with Reece after review), so it never turns growth into loss and non-role skills no longer drift. Worth confirming the feel in the balance pass.
- Cash can go negative with no insolvency handling (M0 behaviour; loss conditions come later).
- `people.retire_bp_per_year_over_60` and `reveal.pa_phrase_bounds` are loaded but unused until M1b.
