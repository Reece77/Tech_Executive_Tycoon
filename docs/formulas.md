# Formula Reference

This is the authoritative source for game math. Task briefs summarize these formulas; when a brief and this file differ, this file wins. Every number below is a default that lives in `backend/data/balance.yaml` under the key shown in §12, never as a literal in code (ADR-0008).

Status: §1–§10 are final for M1. §11 is a draft for M3 and will be confirmed in the M3 brief.

## 0. Conventions

| Item | Rule |
| --- | --- |
| Attribute scale | Float in [1.0, 20.0], clamped on every write with `clamp_attr()`; displayed as an integer |
| Ability scale | Current ability (CA) and potential ability (PA) in [10, 200] |
| Morale, stress | Float in [0, 100] |
| Money | Integer cents (ADR-0003); rounding is round-half-to-even |
| Probabilities | Basis points (bp), 10,000 bp = 100%; a roll succeeds when `rng.integers(0, 10000) < p_bp` |
| Time | Monthly turns; age in years = `(turn − birth_turn) // 12` |
| Randomness | Each formula names its RNG stream and key (ADR-0013). Worked examples show values **before noise** |
| Iteration order | People are processed in ascending `id` order inside every phase |

## 1. Current ability (CA)

Each role in `roles.yaml` lists primary skills (weight 3) and secondary skills (weight 1). Skills outside the role do not count.

```latex
CA = 10 \times \frac{3\sum_{p \in primary} s_p + \sum_{q \in secondary} s_q}{3\,n_{primary} + n_{secondary}}
```

The founder has no hiring role; the founder is scored against every role, and the founder's CA is the highest result. That role is the founder's "best fit", recomputed each month and used for growth (§3). Ties go to the role listed first in `roles.yaml`. Every other person has a role: candidates take the role of the search that found them.

**Worked example.** A software engineer (primaries: software engineering, infrastructure; secondaries: data, security, communication, product) with skills 14, 11 and 9, 8, 12, 10:
numerator = 3 × (14 + 11) + (9 + 8 + 12 + 10) = 75 + 39 = 114; denominator = 3 × 2 + 4 = 10; CA = 10 × 114 / 10 = **114**.

## 2. Person generation (stream `people_gen`, key `search_id`; the founder uses stream `founder`)

Inputs: role, level, region, turn.

1. **Target CA:** `Normal(level_ca.mean, level_ca.sd)`, clipped to [30, 190].

   | Level | Mean | SD | Age range |
   | --- | --- | --- | --- |
   | junior | 70 | 12 | 21–28 |
   | mid | 95 | 12 | 25–35 |
   | senior | 120 | 12 | 29–45 |
   | staff | 140 | 10 | 32–50 |
   | principal | 155 | 10 | 35–58 |
   | exec | 150 | 15 | 38–62 |

2. **Skills:** primaries `target/10 + Normal(0, 1.5)`; secondaries `target/10 − 3 + Normal(0, 2)`; all others `Uniform(1, 8)`. Clamp each. Then scale the primaries by one common factor so the derived CA is within ±2 of the target (re-clamp after scaling).
3. **Age:** uniform integer within the level's range; `birth_turn = turn − 12 × age − Uniform{0..11}`.
4. **Potential:** `PA = min(200, CA + max(0, Normal(gap_mean(age), 15)))`.

   | Age | gap_mean |
   | --- | --- |
   | under 25 | 45 |
   | 25–29 | 30 |
   | 30–34 | 18 |
   | 35–44 | 8 |
   | 45+ | 2 |

5. **Personality and hidden 1–20 traits:** each `Normal(10.5, 3.5)`, clamped.
6. **Interests:** count uniform in {2, 3, 4}; tags drawn without replacement using the role's interest weights. **Work style:** one draw using the role's work-style weights. The interest list (13 tags in `interests.yaml`) extends the 9 examples in spec §5.1.
7. **Behavior tags:** for each tag in `tags.yaml`, chance = `base_bp × multiplier` where the multiplier applies if the tag's attribute condition holds (for example `mentor`: base 400 bp, ×3 if sociability ≥ 13 and temperament ≥ 13). Process tags in file order; skip a tag that an already-assigned tag excludes; stop after 2 tags. Conditions use personality traits, not skills, because a new hire's non-role skills are drawn from 1–8 and would rarely meet a skill threshold. With the `tags.yaml` defaults, about 25% of generated people carry at least one tag.
8. **Salary expectation (2010 USD):**

   ```latex
   E = band_{mid}(role, level) \times \left(1 + \frac{CA - level\_ca.mean}{100}\right) \times region\_multiplier
   ```

   where `region_multiplier` is the region's `salary_multiplier_bp` ÷ 10,000 from `regions.yaml`, rounded to the nearest $500, then converted to cents.

**Worked example.** A senior software engineer (band mid $115,000) generated with CA 126 in North America (multiplier 1.0): E = 115,000 × (1 + 6/100) = $121,900 → **$122,000**.

## 3. Monthly skill growth and aging (phase 8, stream `growth`, key `person_id`)

Applies to every person with an active or notice employment, including the founder. For each primary and secondary skill of the person's current role (the founder's best-fit role):

```latex
\Delta s = r \cdot a(age) \cdot \frac{\max(0,\,PA - CA)}{PA} \cdot \frac{professionalism}{10} \;-\; d(age) \;+\; Normal(0,\,0.05)
```

Skills outside the role change only by `−d(age)` plus noise. Clamp every skill, then recompute CA. `PA` never changes.

| Age | a(age) growth factor | d(age) monthly decline |
| --- | --- | --- |
| under 25 | 1.3 | 0 |
| 25–29 | 1.0 | 0 |
| 30–34 | 0.7 | 0 |
| 35–44 | 0.4 | 0 |
| 45–49 | 0.1 | 0 |
| 50–54 | 0.1 | 0.005 |
| 55+ | 0 | 0.015 |

Default r = 0.12. Mentoring and project difficulty multipliers arrive in M2 and M3; until then they are 1.

**Worked examples (before noise):**

| Person | CA → PA | Professionalism | Δ per month | Δ per year |
| --- | --- | --- | --- | --- |
| Age 24 | 106 → 160 | 14 | +0.0737 | +0.88 |
| Age 38 | 120 → 128 | 10 | +0.0030 | +0.04 |
| Age 58 | 130 → 132 | 12 | −0.0150 | −0.18 |

One noise value is drawn per skill, in `skills.yaml` order, for every skill (role skills and others).

**Retirement (from M1b, stream `retire`, key `person_id`):** from age 60, monthly chance `retire_bp_per_year_over_60 × (age − 59) / 12`; default 600 bp, so a 62-year-old retires with 150 bp (1.5%) chance per month. The founder never retires in M1.

## 4. Revealed ranges (ADR-0007, stream `reveal`, key `(observer_company_id, person_id)`)

Each `(observer company, person, attribute)` stores a half-width `hw` and a center offset `o ~ Uniform(−0.5, 0.5)`, drawn once when the record is created. The attributes with records are the 25 skills, the 9 personality traits, and PA. Offsets are drawn in that order (skills in `skills.yaml` order, then personality, then PA).

```latex
min = \lfloor clamp(t - hw\,(1 + o)) \rfloor \qquad max = \lceil clamp(t + hw\,(1 - o)) \rceil
```

where `t` is the true value and `clamp` limits to [1, 20] for skills and personality, or [10, 200] for PA. If `hw < 0.5`, then `min = max = round(t)`. The true value is always inside the range.

**Narrowing** after a knowledge action:

```latex
hw \leftarrow hw \times (1 - strength \times scout\_factor), \qquad scout\_factor = 0.5 + \frac{judgment\_of\_talent}{40}
```

| Action | Strength | Applies to | Founder energy |
| --- | --- | --- | --- |
| job_post_screen | 0.20 | skills, PA | 0 (automatic) |
| network_intro | 0.30 | all (skills, personality, PA) | 0 (automatic) |
| interview | 0.35 | all | 6 |
| reference_check | 0.30 | personality, PA | 3 |
| scouting_month | 0.25 | all | — (M2, delegated) |
| employed_month | 0.08 | all | 0 (automatic, each month) |

Initial `hw`: skills 5.0, personality 7.0, PA 40.0 (on the 10–200 scale). The scout is the actor; for `employed_month` it is the highest true `judgment_of_talent` among the company's active employees, including the founder.

**Interests and work style** are not ranges: they are hidden until the first interview or network intro, then shown exactly.

**Worked example.** True skill 14, offset +0.2, scout judgment 12 (scout_factor 0.8):

| Step | hw | Displayed |
| --- | --- | --- |
| Stranger | 5.00 | 8–18 |
| After job-post screen | 4.20 | 8–18 |
| After interview | 3.02 | 10–17 |
| After 6 months employed | 2.03 | 11–16 |

**Potential phrase.** PA is never shown as a number. The profile shows the phrase for each bucket the displayed PA range touches, joined with "to" (for example "good to excellent"):

| PA | Phrase |
| --- | --- |
| under 70 | limited |
| 70–99 | decent |
| 100–129 | good |
| 130–159 | excellent |
| 160+ | outstanding |

## 5. Founder build

- Every skill starts at 5. The player distributes 70 points; no skill may exceed 18 after background bonuses. Each background in `backgrounds.yaml` carries a default allocation, used when the player (or the CLI) does not supply one.
- Background bonuses (`backgrounds.yaml`): engineer +3 software engineering, +2 infrastructure; salesperson +3 sales, +2 negotiation; academic +3 ML research, +2 data; ex-big-tech +2 software engineering, +2 product, +1 leadership; geologist +3 geology, +2 mining engineering (available in v3).
- Personality: one of four presets (visionary, operator, hustler, scientist) or `Normal(10.5, 3.5)` per trait.
- Hidden traits and PA are generated as in §2 (stream `founder`), using age 28 unless the player sets age (22–60).
- The founding company knows the founder exactly (`hw = 0` for skills and personality; interests and work style shown). PA keeps its normal initial `hw` and is shown only as a phrase.
- The founder has an employment row (role `founder`, level `exec`, salary 0, equity 0) so headcount counts them. In M1 the founder is excluded from payroll, morale, resignation, retirement, and firing; board removal arrives in M4.

## 6. Founder energy

100 points per month, stored on the founder's `person_state.energy`. Actions spend it at once (ADR-0014); `advance_turn` resets it after phase 12. Unused energy does not carry over.

| Action | Cost |
| --- | --- |
| Interview | 6 |
| Reference check | 3 |
| Open a job post | 4 |
| Engage a recruiter | 4 |
| Network search | 10 |
| Make an offer | 0 |

## 7. Hiring (stream `hiring`)

**Searches.** A network search and a recruiter search each produce one batch, then close. A job post stays open and produces a new batch every month until the player closes it. Each search is for one role.

**Candidate pools** (generated in phase 12 for the next turn, stream `people_gen`, key `search_id`):

| Channel | Cost | Candidates | Level mix (junior/mid/senior/staff) | Starting knowledge |
| --- | --- | --- | --- | --- |
| Network | free (energy 10) | 2–4, +1 if founder sociability ≥ 15 | 30/40/25/5 | network_intro applied |
| Job post | $500 per month open | 6–10 | 45/40/13/2 | job_post_screen applied |
| Recruiter | 20% of first-year salary, charged on hire | 4–6 | 10/35/40/15 | job_post_screen applied twice |

Candidates stay for 3 turns unless hired or withdrawn. Each candidate's salary expectation is shown exactly from the start.

**Offer acceptance** (resolved in phase 1 of the next turn, stream `hiring`, key `offer_id`; one offer per candidate at a time):

```latex
score = 4.0\,(R - 1) + w_{eq}\cdot B \cdot 0.002 \cdot m_{stage} + 0.5\,F + A_{stage} - \frac{10 - risk\_appetite}{10}
```

```latex
p = \frac{1}{1 + e^{-3\,(score - 0)}}
```

- `R` = offered salary ÷ expectation; `B` = equity in basis points; `F` = number of the candidate's interests that match the company mission.
- `w_eq` = 1.0, or 1.5 if ambition > 15.

| Stage | A_stage (appeal) | m_stage (equity value multiplier) |
| --- | --- | --- |
| 0 Solo founder | −0.5 | 1.0 |
| 1 Garage | 0.0 | 0.8 |
| 2 Venture-backed | +0.5 | 0.5 |
| 3 Scale-up | +1.0 | 0.3 |

- If `R < 0.85`, the candidate always declines.
- An accepted offer moves the company from stage 0 to stage 1 ("first hire", spec §3) in phase 10.
- New hires start with morale 65.

**Acceptance hint** shown in the offer dialog: the same score computed from what the player knows (R and equity exactly, F from revealed interests only, the midpoints of displayed ranges for risk appetite and ambition). Score ≥ +0.3 → "likely"; −0.3 to +0.3 → "uncertain"; below −0.3 → "unlikely". The true probability is never shown.

**Worked example.** Stage 0 company, 50 bp equity, one matching interest, risk appetite 10, ambition 10:

| Offer | Score | Acceptance |
| --- | --- | --- |
| 0.95 × expectation | −0.10 | 42.6% |
| 1.00 × expectation | +0.10 | 57.4% |
| 1.10 × expectation | +0.50 | 81.8% |

The gap between 1.10× and 0.95× is 39 percentage points, which satisfies the M1b acceptance criterion (≥ 30).

## 8. Payroll and costs (phase 6)

| Item | Formula | Account |
| --- | --- | --- |
| Salary | `round(salary_cents / 12)` per active employment | 6000_salaries |
| Benefits | `pct_of(monthly_salary, 2000 bp)` | 6010_benefits |
| Office | $600 per active employee | 6100_rent |
| Base overhead | $2,000 in M0, reduced to $500 from M1b | 6900_general_admin |
| Severance | 1 month of salary, on firing | 6000_salaries |
| Recruiter fee | 2,000 bp of annual salary, on hire | 6200_recruiting |
| Job post | $500 per month open | 6200_recruiting |

All are credited to 1000_cash.

**Worked example.** A senior engineer at $115,000: salary 958,333 cents + benefits 191,667 cents + office 60,000 cents = **$12,100.00 per month**.

## 8a. Starting cash (game start)

```latex
starting\_cash = scenario.starting\_cash\_cents \times \frac{difficulty.starting\_cash\_mult\_bp}{10000}
```

rounded half-to-even to whole cents and posted as one ledger entry on turn 0 (debit 1000_cash, credit 3000_common_equity for founder money, or 3100_preferred_equity for the funded spinout). Values are 2010 US dollars.

| Scenario id | Starting cash | Available | Rationale |
| --- | --- | --- | --- |
| `garage_bootstrap` | $50,000 | v1 | Founder savings; about 25 months of M0 overhead, but only a few months once two hires are on payroll |
| `ex_big_tech_founders` | $400,000 | v1 | Savings plus angel money from former colleagues |
| `funded_spinout` | $1,500,000 | v1 | A seed round already closed; equity structure arrives with M4 |
| `mineral_first_prospector` | $5,000,000 | v3 | Exploration capital; not selectable until v3 |

| Difficulty | Multiplier (bp) |
| --- | --- |
| easy | 15000 |
| standard | 10000 |
| hard | 6000 |
| ironman | 10000 (difficulty comes from no reloads) |

## 9. Morale (phase 8, stream `morale`, key `person_id`)

```latex
target = 50 + P + F + W_{runway} + W_{load}
```

| Term | Formula |
| --- | --- |
| P (pay) | `clamp(60 × (salary / market_mid − 1), −20, +15)`, where market_mid = band mid for the role and level × region multiplier |
| F (fit) | `+5 × matching mission interests`, `−5` if work style mismatches the role's primary work style |
| W_runway | `−10` if runway < 6 months; `−20` if < 3 months. Runway here = current cash ÷ (opening cash − current cash) at phase 8; no penalty when cash has not fallen this month |
| W_load | 0 in M1 (placeholder; project workload drives it from M3) |

Monthly update, clamped to [0, 100]:

```latex
morale \leftarrow morale + 0.3\,(target - morale) + Normal\!\left(0,\; 2 \cdot \frac{21 - temperament}{20}\right)
```

**Firing side effect:** all remaining employees −3 morale, or −6 if the fired person had a revealed or hidden `culture_carrier` tag.

**Worked example.** Paid $85,000 against a $90,000 market mid, one matching interest, healthy runway: P = 60 × (0.944 − 1) = −3.33; target = 50 − 3.33 + 5 = 51.67. Starting at 65, morale after 6 months is **53.2** (before noise).

## 10. Resignations and tag reveals (phase 8)

**Resignation chance per month** (stream `resign`, key `person_id`), capped at 2,000 bp:

```latex
p_{bp} = 50 \times \left(1 + \frac{\max(0,\,40 - morale)}{20}\right) \times \frac{21 - loyalty}{10} \times (2 \text{ if job\_hopper})
```

| Case | Monthly chance |
| --- | --- |
| Morale 70, loyalty 12 | 45 bp (0.45%) |
| Morale 25, loyalty 6 | 131 bp (1.3%) |
| Morale 25, loyalty 6, job hopper | 263 bp (2.6%) |

A resignation sets employment status to `notice` with `end_turn = turn + 1`. A notice employment is still paid that month; in phase 1 of `end_turn` it becomes `ended` (`end_reason` = `resigned`). Firing ends it at once (`end_reason` = `fired`); retirement works like a resignation (`end_reason` = `retired`).

**Tag reveal:** each hidden tag of an employee reveals with 500 bp per month (stream `tags`, key `person_id`). An interview or reference check also rolls each still-hidden tag once at 1,500 bp (stream `actions`, key `action_seq`). Reveals are recorded per observer company (ADR-0007). A reveal writes an inbox item.

## 11. Market formulas (draft for M3)

These are proposals to be confirmed in the M3 brief.

**Appeal** of product i in segment s, each score on 0–100:

```latex
appeal_{i,s} = \sum_k w_{s,k} \cdot score_{i,k}, \qquad k \in \{quality, price, brand, features, reach\}
```

with `price_score = clamp(50 × reference_price / price, 0, 100)` and segment weights summing to 1 (for example SMB: quality 0.25, price 0.35, brand 0.15, features 0.15, reach 0.10; enterprise: quality 0.30, price 0.10, brand 0.25, features 0.25, reach 0.10).

**Market share target and smoothing** (γ = 3):

```latex
share^{*}_i = \frac{appeal_i^{\gamma}}{\sum_j appeal_j^{\gamma}}, \qquad share_{i,t} = share_{i,t-1} + (1 - c_s)\,(share^{*}_i - share_{i,t-1})
```

where `c_s` is the segment's switching cost (consumer 0.5, SMB 0.7, enterprise 0.9).

**Monthly churn:**

```latex
churn_{i,s} = base\_churn_s \times \left(1 + \frac{\max(0,\; best\_rival\_appeal - appeal_i)}{50}\right) \times (1.5 \text{ if quality} < 40)
```

with base churn: consumer 6%, SMB 3%, mid-market 1.5%, enterprise 0.8%.

## 12. Balance keys

| Key | Default | Unit | Section |
| --- | --- | --- | --- |
| `people.level_ca.<level>.mean` / `.sd` | see §2 | CA points | §2 |
| `people.level_age.<level>` | see §2 | years [min, max] | §2 |
| `people.ca_clip` | [30, 190] | CA points | §2 |
| `people.skill_noise_sd.primary` / `.secondary` | 1.5 / 2.0 | attribute points | §2 |
| `people.secondary_offset` | 3.0 | attribute points | §2 |
| `people.other_skill_range` | [1, 8] | attribute points | §2 |
| `people.ca_tolerance` | 2 | CA points | §2 |
| `people.pa_gap_mean.<age_band>` / `people.pa_gap_sd` | see §2 / 15 | CA points | §2 |
| `people.personality_mean` / `_sd` | 10.5 / 3.5 | attribute points | §2 |
| `people.interest_count` | [2, 4] | count [min, max] | §2 |
| `people.max_tags` | 2 | count | §2 |
| `people.region_weights` | north_america 55, europe 15, east_asia 8, south_southeast_asia 10, latin_america 6, africa 3, oceania 3 | relative weight | §2 |
| `payroll.salary_round_to_cents` | 50000 | cents | §2 |
| `growth.rate` | 0.12 | attribute points per month | §3 |
| `growth.age_factor.<band>` | see §3 | multiplier | §3 |
| `growth.decline.<band>` | see §3 | attribute points per month | §3 |
| `growth.noise_sd` | 0.05 | attribute points | §3 |
| `people.retire_bp_per_year_over_60` | 600 | bp | §3 |
| `reveal.initial_hw.skill` / `.personality` / `.pa` | 5.0 / 7.0 / 40.0 | attribute or CA points | §4 |
| `reveal.strength.<action>` | see §4 | fraction | §4 |
| `reveal.scout_base` / `reveal.scout_divisor` | 0.5 / 40 | — | §4 |
| `reveal.pa_phrase_bounds` | [70, 100, 130, 160] | CA points | §4 |
| `founder.skill_base` / `.skill_points` / `.skill_cap` | 5 / 70 / 18 | attribute points | §5 |
| `founder.default_age` | 28 | years | §5 |
| `founder.energy_per_month` | 100 | energy | §6 |
| `founder.energy_cost.<action>` | see §6 | energy | §6 |
| `founder.age_range` | [22, 60] | years | §5 |
| `founder.default_region` | north_america | `regions.yaml` key | §5 |
| `hiring.hint_bands` | [−0.3, 0.3] | score | §7 |
| `hiring.channel.<channel>.size` / `.level_mix` | see §7 | count / percent | §7 |
| `hiring.job_post_cost_cents` | 50000 | cents per month | §7 |
| `hiring.recruiter_fee_bp` | 2000 | bp of annual salary | §7 |
| `hiring.candidate_shelf_turns` | 3 | turns | §7 |
| `hiring.offer.w_salary` / `.w_equity` / `.w_fit` / `.w_risk` | 4.0 / 1.0 / 0.5 / 1.0 | score per unit | §7 |
| `hiring.offer.ambition_equity_boost` | 1.5 (if ambition > 15) | multiplier | §7 |
| `hiring.offer.equity_value_per_bp` | 0.002 | score per bp | §7 |
| `hiring.offer.stage_appeal.<stage>` / `.stage_equity_mult.<stage>` | see §7 | score / multiplier | §7 |
| `hiring.offer.k` / `.threshold` | 3.0 / 0.0 | — | §7 |
| `hiring.lowball_ratio` | 0.85 | ratio | §7 |
| `morale.new_hire` | 65 | morale points | §7 |
| `payroll.benefits_bp` | 2000 | bp of salary | §8 |
| `payroll.office_cost_per_head_cents` | 60000 | cents per month | §8 |
| `company.base_monthly_cost_cents` | 200000 (M0), 50000 (M1b) | cents per month | §8 |
| `scenario.<id>.starting_cash_cents` | see §8a | cents | §8a |
| `difficulty.<level>.starting_cash_mult_bp` | see §8a | bp | §8a |
| `payroll.severance_months` | 1 | months | §8 |
| `morale.pay_slope` / `.pay_min` / `.pay_max` | 60 / −20 / 15 | morale points | §9 |
| `morale.fit_per_interest` / `.work_style_mismatch` | 5 / −5 | morale points | §9 |
| `morale.runway_warn_months` / `.runway_crit_months` | 6 / 3 | months | §9 |
| `morale.runway_warn` / `.runway_crit` | −10 / −20 | morale points | §9 |
| `morale.workload_term` | 0 | morale points | §9 |
| `morale.rate` | 0.3 | fraction per month | §9 |
| `morale.noise_scale` | 2.0 | morale points | §9 |
| `morale.fire_penalty` / `.fire_penalty_culture_carrier` | −3 / −6 | morale points | §9 |
| `resign.base_bp` / `.cap_bp` | 50 / 2000 | bp per month | §10 |
| `resign.morale_floor` / `.morale_divisor` | 40 / 20 | morale points | §10 |
| `resign.job_hopper_mult` | 2.0 | multiplier | §10 |
| `tags.reveal_bp_per_month` / `.reveal_bp_on_check` | 500 / 1500 | bp | §10 |
| `events.light_tone_chance_bp` | 1000 | bp | ADR-0011 |
