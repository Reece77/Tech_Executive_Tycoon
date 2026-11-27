# Formula Reference

This is the authoritative source for game math. Task briefs summarize these formulas; when a brief and this file differ, this file wins. Every number below is a default that lives in `backend/data/balance.yaml` under the key shown in §12, never as a literal in code (ADR-0008).

Status: §1–§10 are final for M1. §13 (organization) is final for M2 and adds terms to §3, §6, §7 and §9, each marked "M2". §11 (products and markets) is final for M3 and adds rows to §6, each marked "M3". §16 (events, storylines and relationships) is final for M6 and adds a morale term to §9 and changes §13.6. §15 (rivals) is final for M5. §14 (finance) is final for M4 and changes §7 (equity in options), §8 and §10 (retention), each marked "M4".

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
\Delta s = r \cdot a(age) \cdot \frac{\max(0,\,PA - CA)}{PA} \cdot \frac{professionalism}{10} \cdot \max\big(0,\; 1 + Normal(0,\,\sigma)\big) \;-\; d(age)
```

with σ = `growth.noise_rel_sd` (0.25). The noise is multiplicative, so it scales the growth term and never turns growth into loss. Skills outside the role change only by `−d(age)`, with no noise. Clamp every skill, then recompute CA. `PA` never changes.

| Age | a(age) growth factor | d(age) monthly decline |
| --- | --- | --- |
| under 25 | 1.3 | 0 |
| 25–29 | 1.0 | 0 |
| 30–34 | 0.7 | 0 |
| 35–44 | 0.4 | 0 |
| 45–49 | 0.1 | 0 |
| 50–54 | 0.1 | 0.005 |
| 55+ | 0 | 0.015 |

Default r = 0.12. **M2:** the growth term is also multiplied by the mentoring multiplier `M_growth` from §13.5 (1 for the founder). Project difficulty arrives in M3; until then it is 1.

**Worked examples (before noise):**

| Person | CA → PA | Professionalism | Δ per month | Δ per year |
| --- | --- | --- | --- | --- |
| Age 24 | 106 → 160 | 14 | +0.0737 | +0.88 |
| Age 38 | 120 → 128 | 10 | +0.0030 | +0.04 |
| Age 58 | 130 → 132 | 12 | −0.0150 | −0.18 |

One noise value is drawn per role skill (primary and secondary), in `skills.yaml` order; skills outside the role draw nothing.

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

Initial `hw`: skills 5.0, personality 7.0, PA 40.0 (on the 10–200 scale). **M2b:** a stranger's PA `hw` is raised (tuned in the range 60–120 to the §13.10 target), because potential must be genuinely unknown for a good scout to matter; the founder's own PA keeps `reveal.founder_pa_hw` = 40. The scout is the actor; for `employed_month` it is the highest true `judgment_of_talent` among the company's active employees, including the founder.

**Potential narrows more steeply with judgment (M2b).** For PA only, the scout factor is

```latex
scout\_factor_{PA} = clamp\left(\frac{judgment\_of\_talent}{20},\; 0.1,\; 1.0\right)
```

and each action's PA strength is `reveal.pa_strength.<action>`. This is what makes a good scout worth having: current skills show themselves quickly; potential does not. `reveal.initial_hw.pa`, `reveal.pa_scout_divisor` and `reveal.pa_strength.*` are tuned to the §13.10 target. **Tuned in M2b:** stranger PA `hw` 67, `pa_scout_divisor` 16 (a judgment-6 scout learns potential at 0.375 of the full rate, judgment 16 and above at 1.0, against 0.65 and 0.9 for skills), and PA strengths job-post screen 0.05, interview 0.10, scouting month 0.60, network intro 0.30, reference check 0.30, employed month 0.08. **M4c (Reece's playtest: interviews felt pointless for potential):** interview PA strength rises to 0.20, and `reveal.initial_hw.pa` is re-tuned within 60–120 (smallest value that holds) so the §13.10 +3 PA target still passes; every interview and reference check now shows what it taught (§4 feedback in the M4c brief).

**PA worked example (M4c values: stranger `hw` 66, interview PA strength 0.20).** True PA 140, offset +0.2, scout judgment 12 (PA scout factor 0.75):

| Step | hw | Displayed | Phrase |
| --- | --- | --- | --- |
| Stranger | 66.00 | 60–193 | limited to outstanding |
| After job-post screen | 63.52 | 63–191 | limited to outstanding |
| After interview | 54.00 | 75–184 | decent to outstanding |
| After 6 months employed | 37.25 | 95–170 | decent to outstanding |

(M2b values, for comparison: 67.00, 64.49, 59.65 after the interview (68–188, still "limited to outstanding"), 41.15.) **M4c result:** `reveal.initial_hw.pa` = **66**, the smallest value in 60–120 that holds the §13.10 target (judgment 16 over judgment 6: +3.05 PA over 400 seeds; 65 gives +2.74). For a typical mid-level candidate (true PA 113, centred) seen by a judgment-10 founder, a job post plus one interview now shows 57–169 ("limited to outstanding"; M2b: 52–174): one interview takes 12% off the PA range instead of 6%, but the phrase usually needs a reference check or a second look to move.

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
- The founding company knows the founder exactly (`hw = 0` for skills and personality; interests and work style shown). PA starts at `reveal.founder_pa_hw` (40) and is shown only as a phrase.
- **Interests and work style** are drawn as in §2 using the weights of the founder's best-fit role, computed after the skill allocation is applied. The player may supply them instead (2–4 valid interests; one work style).
- **Behavior tags** are rolled as in §2 step 7. The founding company knows them from turn 0 (`person_tag_reveal` rows with `revealed_turn = 0`), and sees the founder's interests and work style from turn 0.
- **Region and name:** region is `founder.default_region` (north_america) unless chosen; the name is drawn from that region's `names.yaml` pool unless the player supplies both first and last name.
- **Draw order** in stream `founder` (no key): birth month, personality (only if random), hidden traits, PA gap, interests, work style, tags, first name, last name. A value the player supplied skips its draw.
- The founder has an employment row (role `founder`, level `exec`, salary 0, equity 0) so headcount counts them. In M1 the founder is excluded from payroll, morale, resignation, retirement, and firing; board removal arrives in M4.

## 6. Founder energy

**M4c (Reece's playtest: energy never limited him).** The monthly budget falls from 100 to **60**, and hiring actions cost more: interview 8, reference check 4, job post 5, recruiter 5 (network stays 10, scouting 20). A typical hiring month (one job post, four interviews, two reference checks) now takes 45 of 60, leaving little for org, product and fundraising actions, so delegating hiring pays off. Delegates keep 100 (their whole month is the work). The table below shows the M1–M4 values; `balance.yaml` holds the current ones.

100 points per month, stored on the founder's `person_state.energy`. Actions spend it at once (ADR-0014); `advance_turn` resets it after phase 12. Unused energy does not carry over.

| Action | Cost |
| --- | --- |
| Interview | 6 |
| Reference check | 3 |
| Open a job post | 4 |
| Engage a recruiter | 4 |
| Network search | 10 |
| Make an offer | 0 |
| **M2:** Create or dissolve a unit | 2 |
| **M2:** Move a team to another parent | 2 |
| **M2:** Set a unit leader | 2 |
| **M2:** Move a person between units | 1 |
| **M2:** Set a unit policy | 1 |
| **M2:** Give a raise | 2 |
| **M2:** Promote | 3 |
| **M2:** Create or change a hiring plan | 2 |
| **M3:** Scout a search (§11.12) | 20 |
| **M3:** Create a product | 4 |
| **M3:** Assign or unassign a unit to a product | 2 |
| **M3:** Set a price or a marketing budget | 1 |
| **M3:** Add a segment | 2 |
| **M3:** Launch or sunset a product | 3 |
| **M4:** Raise on a SAFE | 10 |
| **M4:** Start a priced round | 15 |
| **M4:** Accept a term sheet or a bridge | 5 |

Delegates (§13.10) have their own energy and never spend the founder's.

## 7. Hiring (stream `hiring`)

**Searches.** A network search and a recruiter search each produce one batch, then close. A job post stays open and produces a new batch every month until the player closes it. Each search is for one role.

**Candidate pools** (generated in phase 12 for the next turn, stream `people_gen`, key `search_id`):

| Channel | Cost | Candidates | Level mix (junior/mid/senior/staff) | Starting knowledge |
| --- | --- | --- | --- | --- |
| Network | free (energy 10) | 2–4, +1 if founder sociability ≥ 15 | 30/40/25/5 | network_intro applied |
| Job post | $500 per month open | 6–10 | 45/40/13/2 | job_post_screen applied |
| Recruiter | 20% of first-year salary, charged on hire | 4–6 | 10/35/40/15 | job_post_screen applied twice |

Candidates stay for 3 turns unless hired or withdrawn. Each candidate's salary expectation is shown exactly from the start. **M2 fix:** a candidate with a pending offer does not expire until that offer resolves in phase 1, even if their last month has passed.

**Offer acceptance** (resolved in phase 1 of the next turn, stream `hiring`, key `offer_id`; one offer per candidate at a time):

```latex
score = 4.0\,(R - 1) + w_{eq}\cdot B \cdot 0.002 \cdot m_{stage} + 0.5\,F + A_{stage} - \frac{10 - risk\_appetite}{10} + pitch
```

```latex
p = \frac{1}{1 + e^{-3\,(score - 0)}}
```

- `R` = offered salary ÷ expectation; `B` = equity in basis points; `F` = number of the candidate's interests that match the company mission.
- `w_eq` = 1.0, or 1.5 if ambition > 15 (`hiring.offer.ambition_boost_above`).
- **M2:** `pitch = 0.3 × (recruiting − 10) / 10`, using the true `recruiting` skill of whoever made the offer (the founder or a delegate). A recruiting-15 delegate adds +0.15; the engineer founder's default 7 gives −0.09. The worked example below assumes a recruiting-10 actor (pitch 0), so its numbers are unchanged.

| Stage | A_stage (appeal) | m_stage (equity value multiplier) |
| --- | --- | --- |
| 0 Solo founder | −0.5 | 1.0 |
| 1 Garage | 0.0 | 0.8 |
| 2 Venture-backed | +0.5 | 0.5 |
| 3 Scale-up | +1.0 | 0.3 |

- **M2a: an offer requires an interview** (ADR-0016). The offering company must have interviewed the candidate (the founder or one of its delegates); a network intro or reference check does not count. Otherwise the action fails with `InterviewRequired`.
- If `R < 0.85`, the candidate always declines.
- **Option pool:** an offer may carry at most 200 bp of equity, and equity held by staff plus pending offers may not exceed 1,000 bp (a 10% pool). **M4:** equity is granted as options from the pool's unallocated shares (§14.2); the limit becomes the unallocated pool. The founder's ownership is outside the pool and arrives with the cap table in M4.
- An accepted offer moves the company from stage 0 to stage 1 ("first hire", spec §3) in phase 10.
- **Withdrawing an offer** removes only the pending offer. The candidate stays open and can receive a new offer the same turn: nothing is decided until Continue. **Closing a job post** stops new batches; its existing candidates stay until they expire. The candidate status `withdrawn` is reserved for M2 (a candidate or a delegate pulling out) and is unused in M1.
- **Company mission:** two interests from `interests.yaml`, chosen at new game. If none are given, the mission is the founder's first two interests, ordered as in `interests.yaml`. When given, they must be exactly two distinct valid interests. Saves created before M1b keep an empty mission.
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
| Tools and travel (M4c) | `costs.tools_per_head_cents` = $1,500 per active employee, the founder excepted, remote staff included | 6900_general_admin |
| Base overhead | $2,000 in M0, reduced to $500 from M1b | 6900_general_admin |
| Severance | 1 month of salary, on firing | 6000_salaries |
| Recruiter fee | 2,000 bp of annual salary, on hire | 6200_recruiting |
| Job post | $500 per month open | 6200_recruiting |

All are credited to 1000_cash.

**Negative cash (M1–M3):** there is no insolvency until M4, which adds insolvency, bridges and bankruptcy (§14.7). Cash may fall below zero; payroll and offers are never blocked, but opening a job post requires cash of at least its first month's fee. The inbox warns the first month cash is negative and every month it stays negative. For morale's runway term, zero or negative cash counts as under 3 months.

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
target = 50 + P + F + W_{runway} + W_{load} + W_{mgr} + W_{team} + W_{remote}
```

| Term | Formula |
| --- | --- |
| P (pay) | `clamp(60 × (salary / market_mid − 1), −20, +15)`, where market_mid = band mid for the role and level × region multiplier |
| F (fit) | `+5 × matching mission interests`, `−5` if work style mismatches the role's primary work style |
| W_runway | `−10` if runway < 6 months; `−20` if < 3 months. Runway here = current cash ÷ (opening cash − current cash) at phase 8; no penalty when cash has not fallen this month |
| W_load | 0 in M1 (placeholder; project workload drives it from M3) |
| W_mgr (M2) | Manager quality term, §13.4 |
| W_team (M2) | Teammates' behavior tags, §13.6 |
| W_remote (M2) | Work-location policy, §13.9 |
| W_rel (M6) | Relationships with unit-mates, §16.7 (from M6 it absorbs the credit-taker and toxic-high-performer parts of W_team) |

Monthly update, clamped to [0, 100]:

```latex
morale \leftarrow morale + 0.3\,(target - morale) + Normal\!\left(0,\; 2 \cdot \frac{21 - temperament}{20}\right)
```

**Firing side effect:** all remaining employees −3 morale, or −6 if the fired person had a revealed or hidden `culture_carrier` tag. Because the larger hit gives the tag away, firing a culture carrier also reveals that tag to the company, with an inbox item.

**Worked example.** Paid $85,000 against a $90,000 market mid, one matching interest, healthy runway, M2 terms zero: P = 60 × (0.944 − 1) = −3.33; target = 50 − 3.33 + 5 = 51.67. Starting at 65, morale after 6 months is **53.2** (before noise).

**M10d balance pass:** the target base is now 56 (`morale.target_base`), so the median employee of the steady and blitzscale strategies sits at 58–68; the worked example keeps 50, and its test uses it.

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

**M7a balance pass:** the base is now 80 bp (`resign.base_bp`), so about 10–25% of staff leave a year (docs/balance-targets.md T6); the formula and the table above keep the original 50 bp, and their tests use it.

**M10d balance pass:** the morale floor is now 50 (`resign.morale_floor`), about ten points below the median employee after §9's new target base; the formula and the table keep 40, and their tests use it.

**M4:** the chance is then multiplied by the retention factor for unvested options, `max(0.5, 1 − 0.5 u)` (§14.2), before the cap.

A resignation sets employment status to `notice` with `end_turn = turn + 1`. A notice employment is still paid that month; in phase 1 of `end_turn` it becomes `ended` (`end_reason` = `resigned`). Firing ends it at once (`end_reason` = `fired`); retirement works like a resignation (`end_reason` = `retired`).

**Tag reveal:** each hidden tag of an employee reveals with 500 bp per month (stream `tags`, key `person_id`). An interview or reference check also rolls each still-hidden tag once at 1,500 bp (stream `actions`, key `action_seq`). Reveals are recorded per observer company (ADR-0007). A reveal writes an inbox item.

## 11. Products and markets (M3)

**M4c balance pass:** the per-head tools-and-travel line (§8) alone met every target, so `market.awareness_scale` (0.5) and `products.seller_rate.*` (mid-market 2, enterprise 0.3) are unchanged; the M3a earn-and-burn ARR at turn 36 is about $2.55M (band $500k–$4M).

Final for M3. Products are built by org units (§13), sold into segments of a category's market, and compete on appeal against every other product in that market. Until rivals get AI in M5, the other products belong to **incumbents**: real 2010 companies whose products hold fixed scores (ADR-0017). Regions are not modelled in M3: each category has one global market per segment.

### 11.1 Categories and segments (data: `categories.yaml`)

Four v1 categories. Each sells to some of four segments. Per category and segment: addressable customers `D₀` in January 2010, reference monthly price `p_ref`, and hosting cost per customer per month `h`.

| Category | Segment | D₀ (customers) | p_ref / month | h / month |
| --- | --- | --- | --- | --- |
| B2B SaaS (`b2b_saas`) | SMB | 400,000 | $50 | $4 |
| | Mid-market | 40,000 | $800 | $50 |
| | Enterprise | 4,000 | $8,000 | $400 |
| Developer tools (`dev_tools`) | SMB | 200,000 | $30 | $6 |
| | Mid-market | 20,000 | $500 | $80 |
| | Enterprise | 3,000 | $5,000 | $700 |
| Consumer apps (`consumer_apps`) | Consumer | 50,000,000 | $0.40 (revenue per user) | $0.04 |
| Cybersecurity (`cybersecurity`) | SMB | 300,000 | $40 | $3 |
| | Mid-market | 30,000 | $1,000 | $60 |
| | Enterprise | 5,000 | $12,000 | $600 |

| Category | Annual market growth `g` | Features expected at turn 0 `F₀` | Expected features added per month `ΔF` | Scope `σ` | Brand constant `K` |
| --- | --- | --- | --- | --- | --- |
| B2B SaaS | 20% | 60 | 4.0 | 6 | 60 |
| Developer tools | 25% | 50 | 4.0 | 5 | 50 |
| Consumer apps | 30% | 40 | 5.0 | 4 | 300 |
| Cybersecurity | 15% | 70 | 3.5 | 7 | 70 |

| Segment | Appeal weights quality / price / brand / features | Outside option `a₀` | Base churn per month | Adoption of the unserved per month | How new customers are reached |
| --- | --- | --- | --- | --- | --- |
| Consumer | 0.30 / 0.20 / 0.30 / 0.20 | 45 | 6% | 3.0% | Self-serve: awareness |
| SMB | 0.25 / 0.35 / 0.15 / 0.25 | 45 | 3% | 1.5% | Self-serve: awareness |
| Mid-market | 0.30 / 0.25 / 0.20 / 0.25 | 45 | 1.5% | 1.0% | Sales capacity |
| Enterprise | 0.35 / 0.10 / 0.25 / 0.30 | 45 | 0.8% | 0.5% | Sales capacity |

Addressable customers grow every month in phase 9: `D ← D × (1 + g)^(1/12)`.

### 11.2 Products and lifecycle

- **Create** (immediate action, energy 4): name, category, and one or more of the category's segments. The product starts `in_development` with quality 10, features 0, brand 0, no customers. A price must be set for each segment before launch (immediate action, energy 1 per change; any positive amount in cents).
- **Launch** (energy 3): allowed when quality ≥ 25 and feature score ≥ 30 (§11.4). From the next phase 5 the product can win customers.
- **Add a segment** (energy 2) at any time; customers start at 0 there.
- **Sunset** (energy 3): no new customers; existing customers churn at 3× the normal rate; when none remain the product is retired. A sunset cannot be undone. **M3b:** a product still in development can be **cancelled** instead (energy 3): it retires at once and its units are freed.
- **Lifecycle labels** shown in the UI: In development, Live, Sunset. "Growth" and "maturity" are display labels the API derives from the 6-month customer trend (rising more than 5% a month: growth; otherwise mature); they change no rule.
- A company may have any number of products.

### 11.3 Who works on a product

- **Assignment** (immediate action, energy 2 to assign or unassign): an org unit, including the company root, is assigned to at most one product. A product may have several units. Everyone whose unit is the assigned unit works on that product; members of child units do not (they follow their own unit's assignment). The founder works on whatever the root is assigned to.
- **Function by role** (`roles.yaml` gains `product_function`): software engineer, data scientist, DevOps engineer, security engineer, product manager and designer are **builders**; sales representative and account executive are **sellers**; marketer is a **marketer**; finance, recruiter and operations roles contribute nothing to products. The founder counts as a builder.
- **Morale factor**: `m = 0.7 + 0.6 × morale / 100` (morale 50 gives 1.0). The founder has no morale and uses `m = 1`.

**Builder output.** Each category weights skills into a development skill (`categories.yaml`, weights sum to 1):

| Category | Development skill weights |
| --- | --- |
| B2B SaaS | software engineering 0.35, product 0.20, design 0.15, infrastructure 0.15, data 0.10, security 0.05 |
| Developer tools | software engineering 0.40, infrastructure 0.25, product 0.15, data 0.10, security 0.10 |
| Consumer apps | software engineering 0.30, design 0.25, product 0.25, marketing 0.10, data 0.10 |
| Cybersecurity | security 0.40, software engineering 0.25, infrastructure 0.20, data 0.10, product 0.05 |

```latex
d_i = \sum_k w_k \cdot skill_{i,k}, \qquad o_i = \frac{d_i}{10} \cdot m_i \cdot t_i, \qquad o = coord(n) \cdot \varepsilon \cdot \sum_i o_i
```

- `t_i` is the tag multiplier (§11.10, 1 for most people).
- `coord(n) = max(0.6, 1 − 0.02 × max(0, n − 5))`, where `n` is the number of builders on the product across all its units: a coordination cost for large teams.
- `ε = max(0, 1 + N(0, sd))` is monthly development noise (stream `product_dev`, key `product_id`), with `sd = 0.15 + 0.10` per maverick builder, capped at 0.40.

**Seller capacity** (mid-market and enterprise only), with `sell_i = (2·sales + negotiation + communication) / 4`:

```latex
cap_{p,s} = r_s \cdot \sum_{sellers} \frac{sell_i}{10} \cdot m_i
```

with `r_s` = 2 new customers a month for mid-market and 0.3 for enterprise. One seller works for all of the product's sales-capacity segments at once: each segment gets the full capacity (a simplification; splitting effort waits for v2).

**Marketer contribution**, with `mkt_i = (2·marketing + communication + design) / 4`: `μ = Σ (mkt_i / 10) × m_i`.

### 11.4 Quality and features (phase 3)

Phase 3 (named "R&D progress" in ADR-0006) now runs product development; the technology tree joins it in v2.

```latex
\bar d = \frac{\sum_i o_i\, d_i}{\sum_i o_i}, \qquad Q_{cap} = 5\,\bar d
```

```latex
Q \leftarrow Q + 0.15 \cdot \min\left(1, \frac{o}{\sigma}\right) \cdot (Q_{cap} - Q) \quad \text{when } Q < Q_{cap}
```

- If `Q ≥ Q_cap` (a weaker team took over), `Q ← max(Q_cap, 0.99 Q)`.
- If `o < 0.25 σ` (no or a token team), quality falls 0.5 points a month instead of climbing: unmaintained software rots. With no builders at all the product only rots.
- Quality is kept in [0, 100]. A perfectionist builder raises `Q_cap` (§11.10).

**Features.** Accumulated feature points `F` grow by `o` each month. The market expects `F_exp(t) = F₀ + ΔF × t` (t = turn). The feature score is

```latex
feature = clamp\left(100 \cdot \frac{F}{F_{exp}(t)},\; 0,\; 100\right)
```

so a product must keep developing or its feature score slides as the market moves on. Over a long run a team's feature score settles near `100 × o / ΔF`: a B2B SaaS team needs about 4 output a month (roughly four average builders) to stay at full marks.

### 11.5 Brand and marketing (phase 9)

Each product has a monthly marketing budget (immediate action, energy 1 to change; cents; posted to `6400_marketing` in phase 6).

```latex
mk = \frac{budget_{\$}}{1000} + 5\,\mu, \qquad B^{*} = 100 \cdot \frac{mk}{mk + K}, \qquad brand \leftarrow brand + 0.10\,(B^{*} - brand)
```

Brand is per product and kept in [0, 100]. With no marketing, brand drifts toward 0.

**Marketers direct a large budget (M46).** Budget points above `marketer_lift_from_mk` (200, a $200,000 monthly budget) are multiplied by `1 + min(0.3, 0.03 μ)`:

```latex
mk = b + 5\,\mu + \max(0,\; b - 200) \cdot \min(0.3,\; 0.03\,\mu), \qquad b = \frac{budget_{\$}}{1000}
```

A startup's budget sits below the threshold, so nothing changes there; at a listed company's budget (thousands of points) the fixed `5 μ` was negligible, and a marketing team had no work. One average marketer (μ ≈ 1) now adds 3% to the budget above the threshold, and ten reach the cap. Why (M46 sub-task 1): a listed steady founder could not put IPO cash to work, because builders saturate (the feature score stops at 100 and Q_cap follows the team's average skill, not its size) and sellers only serve the small sales-led segments.

### 11.6 Appeal (phase 5)

For product `i` in segment `s`, all scores on 0–100:

```latex
price\_score = clamp\left(50 \cdot \frac{p_{ref}}{price},\; 0,\; 100\right)
```

```latex
appeal_{i,s} = w_q\, Q + w_p\, price\_score + w_b\, brand + w_f\, feature
```

A product at the reference price scores 50 for price; at half the reference price, 100.

### 11.7 Customers (phase 5, stream `market`, key `(category_index, segment_index)`)

For each category and segment, with `C_j` the customers of every live or sunset product `j` (player's and incumbents'):

1. **Churn.** Each product loses `C_j × churn_j`, where

```latex
churn_j = base_s \cdot \left(1 + \frac{\max(0,\; best_s - appeal_j)}{50}\right) \cdot (1.5 \text{ if } Q_j < 40) \cdot (3 \text{ if sunset})
```

and `best_s` is the highest appeal of any live product in the segment.

2. **In play.** `P = min(churned + U, (Σ_j C_j × churn_j + adoption_s × U) × η)` (the cap keeps a segment within its demand), where `U = max(0, D − Σ_j C_j)` is unserved demand and `η = max(0, 1 + N(0, 0.05))` is monthly demand noise.

3. **Choice.** Among live products and the outside option:

```latex
share^{*}_i = \frac{appeal_i^{3}}{a_0^{3} + \sum_{j\ \text{live}} appeal_j^{3}}
```

4. **New customers.** Self-serve segments: `new_i = P × share*_i × awareness_i`, with `awareness_i = 0.5 × max(brand_i, 5) / 100` (half of customers who would choose a product never hear of one with modest brand). Sales segments: `new_i = min(P × share*_i, cap_{i,s})`. Incumbents use awareness 1 and no capacity limit. In-play customers not won return to the unserved pool.

5. `C_i ← C_i − churned + new_i`. Customers are stored as floats (not money) and shown rounded.

### 11.8 Revenue and costs

- **Revenue** (phase 5): for each player product and segment, `round(C × price)` cents, debit `1000_cash`, credit `4000_revenue_subscriptions`. Consumer apps book revenue per user the same way.
- **Hosting** (phase 6): `round(C × h)` cents to `6300_compute`.
- **Marketing** (phase 6): each product's budget to `6400_marketing`. Budgets are paid even with negative cash until M4.
- **MRR** = this month's revenue; **ARR** = 12 × MRR, summed over the company's products. Both go into `turn_snapshot`.
- Incumbents have no ledger until M5.

### 11.9 Incumbents (data: `incumbents.yaml`, ADR-0017)

Companies with `is_player = false`, no people and no AI. Each product has fixed quality, brand and price per segment. Its feature score stays fixed: its `F` grows with `F_exp`. Initial customers are a share of `D₀`.

| Company | Product (category) | Q / features / brand | Price and starting share of D₀ by segment |
| --- | --- | --- | --- |
| Salesforce | Sales Cloud (B2B SaaS) | 70 / 80 / 80 | SMB $65, 10% · mid $900, 21.5% · ent $9,000, 36.5% |
| Oracle | CRM On Demand (B2B SaaS) | 60 / 75 / 70 | mid $800, 16% · ent $8,000, 23.5% |
| Zoho | Zoho CRM (B2B SaaS) | 55 / 60 / 40 | SMB $25, 15% · mid $400, 17.5% |
| Atlassian | JIRA (developer tools) | 70 / 75 / 60 | SMB $25, 20% · mid $450, 18% · ent $4,500, 23.5% |
| Microsoft | Team Foundation Server (developer tools) | 65 / 80 / 85 | mid $600, 20% · ent $6,000, 31.5% |
| GitHub | GitHub (developer tools) | 75 / 60 / 50 | SMB $25, 15% · mid $300, 22% |
| Facebook | Facebook (consumer apps) | 65 / 80 / 95 | consumer $0.35, 24.5% |
| Zynga | FarmVille (consumer apps) | 55 / 60 / 70 | consumer $0.50, 8% |
| Evernote | Evernote (consumer apps) | 70 / 55 / 40 | consumer $0.20, 12.5% |
| Symantec | Norton (cybersecurity) | 60 / 80 / 85 | SMB $35, 17.5% · mid $900, 24.5% · ent $11,000, 28.5% |
| McAfee | McAfee Total Protection (cybersecurity) | 55 / 75 / 80 | SMB $30, 17.5% · mid $850, 20% · ent $10,000, 22.5% |
| Check Point | Check Point (cybersecurity) | 70 / 70 / 60 | mid $1,100, 15.5% · ent $13,000, 19% |

Starting shares within a segment sum to at most 90%; the rest is unserved. **M3a tuning:** the shares above are the fixed-score steady state (each segment's total kept, split in proportion to share* / churn, rounded to 0.5%), so with no player product no incumbent's share of served customers drifts more than about a point in 24 turns. Real names, approximate 2010 values, personal use (CLAUDE.md §7).

### 11.10 Behavior tags on products

Using true tags, for builders on a product:

| Tag | Effect |
| --- | --- |
| `quiet_genius` | `t_i = 1.25` |
| `toxic_high_performer` | `t_i = 1.20` (the §13.6 morale drain on teammates still applies) |
| `perfectionist` | `t_i = 0.85`, and their `d_i` counts as `d_i + 3` (capped at 20) in `Q_cap` |
| `maverick` | `t_i = 1.10`, and +0.10 development noise sd (§11.3) |
| `politician` | none in M3 (conflict events in M6) |

### 11.11 Stages from revenue (phase 10)

Stage 2 is entered at ARR ≥ $1M (or a closed seed round, M4); stage 3 at ARR ≥ $20M (or Series B, M4). Stages only rise. Stage 3 unlocks nothing new until v2.

### 11.12 Founder scouting (immediate action)

The founder may **scout a search** (energy 20): apply `scouting_month` (§4) once to every open candidate of that search, with the founder as the scout. It is the same action delegates use (§13.10).

### 11.13 What the API may show

Quality, feature score, brand, price, appeal, customers, share of the segment's customers, MRR and churn rate for every product in a market (incumbents' scores are public). For the player's own products also: assigned units, builders, sellers and marketers by name, and a development-pace label (fast if `min(1, o/σ) ≥ 0.75`, steady if ≥ 0.4, else slow). Never `Q_cap`, `d_i`, `o_i`, `cap` or per-person contributions, which would reveal true skills. A sales-capacity limit is shown only as "Sales capacity limited new customers in <segment>" when it bound.

### 11.14 Worked examples (noise off)

**Design check (not a test).** A spreadsheet model of the M3a earn-and-burn script (founder plus three builders at d ≈ 11, one account executive and one marketer, $10,000 a month marketing, SMB at $40 and mid-market at $700 against the §11.9 incumbents) gives first revenue around turn 5, break-even (about $60,000 a month of costs) around turn 17, and an ARR of about $2.6M at turn 36; without the marketing budget, about $1.4M. These values set the band in the M3a brief.

**Team output and quality.** A B2B SaaS product built by the root: the founder (d = 12.0) and two engineers (d = 10.5, morale 58; d = 9.0, morale 54).

| Step | Value |
| --- | --- |
| Morale factors | 1.0 (founder), 1.048, 1.024 |
| `o_i` | 1.200, 1.100, 0.922 |
| `o` (n = 3, coord 1) | 3.222 |
| `d̄`, `Q_cap` | 10.63, 53.2 |
| Created in January 2010; phase 3 first runs in turn 0 | |
| Quality after turns 0, 5, 11 (from 10) | 13.5, 27.1, 37.4 |
| Feature points after turns 5 / 8 / 11 | 19.3 / 29.0 / 38.7 |
| Feature score after turn 8 (`F_exp(8)` = 92) | 31.5: launch allowed from turn 9 (quality 32.9 ≥ 25, features ≥ 30) |

**Appeal and share (SMB, B2B SaaS).** The player's product at quality 40, price $40, brand 10, features 40, against Salesforce (70, $65, 80, 80) and Zoho (55, $25, 40, 60):

| Product | Price score | Appeal | share* |
| --- | --- | --- | --- |
| Player | 62.5 | 43.38 | 10.71% |
| Salesforce | 38.5 | 62.96 | 32.77% |
| Zoho | 100 | 69.75 | 44.55% |
| No purchase (`a₀` = 45) | — | 45 | 11.96% |

With D = 400,000, Salesforce holding 15% and Zoho 10%: churn 3.41% (Salesforce) and 3.00% (Zoho); in play = 2,044 + 1,200 + 4,500 = **7,744**. At brand 10 (awareness 0.5 × 0.10 = 0.05) the player wins **41.5** new customers. Its own churn is 3% × (1 + 26.37/50) = **4.58%** a month.

**Brand.** $10,000 a month plus one marketer (mkt 12, morale 50): `mk = 10 + 5 × 1.2 = 16`, `B* = 21.05`; from 0, brand is **15.1** after 12 months.

**Sales capacity.** One account executive with sell 12 and morale 60 closes up to **2.54** mid-market customers a month.

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
| `growth.noise_rel_sd` | 0.25 | fraction of the growth term | §3 |
| `people.retire_bp_per_year_over_60` | 600 | bp | §3 |
| `people.retire_from_age` | 60 | years | §3 |
| `reveal.initial_hw.skill` / `.personality` / `.pa` | 5.0 / 7.0 / 66.0 (40.0 before M2b, 67.0 in M2b–M4b) | attribute or CA points | §4 |
| `reveal.strength.<action>` | see §4 | fraction | §4 |
| `reveal.scout_base` / `reveal.scout_divisor` | 0.5 / 40 | — | §4 |
| `reveal.pa_phrase_bounds` | [70, 100, 130, 160] | CA points | §4 |
| `reveal.pa_scout_divisor` / `reveal.pa_strength.<action>` | 16 / see §4 (tuned; interview 0.20 from M4c) | attribute points / fraction | §4, tuned in M2b |
| `reveal.pa_scout_clamp` | [0.1, 1.0] | multiplier [min, max] | §4 (M2b) |
| `reveal.founder_pa_hw` | 40 | CA points | §4, §5 (M2b) |
| `founder.skill_base` / `.skill_points` / `.skill_cap` | 5 / 70 / 18 | attribute points | §5 |
| `founder.default_age` | 28 | years | §5 |
| `founder.energy_per_month` | 60 (100 before M4c) | energy | §6 |
| `founder.energy_cost.<action>` | see §6 (M4c: interview 8, reference check 4, job post 5, recruiter 5) | energy | §6 |
| `founder.age_range` | [22, 60] | years | §5 |
| `founder.default_region` | north_america | `regions.yaml` key | §5 |
| `hiring.hint_bands` | [−0.3, 0.3] | score | §7 |
| `hiring.channel.<channel>.size` / `.level_mix` | see §7 | count / percent | §7 |
| `hiring.channel.<channel>.sociability_bonus` / `.sociability_threshold` | network 1 / 15, others 0 / 0 | count / attribute points | §7 |
| `hiring.channel.<channel>.knowledge` | network [network_intro], job post [job_post_screen], recruiter [job_post_screen ×2] | knowledge actions | §7 |
| `hiring.job_post_cost_cents` | 50000 | cents per month | §7 |
| `hiring.recruiter_fee_bp` | 2000 | bp of annual salary | §7 |
| `hiring.candidate_shelf_turns` | 3 | turns | §7 |
| `hiring.offer.w_salary` / `.w_equity` / `.w_fit` / `.w_risk` | 4.0 / 1.0 / 0.5 / 1.0 | score per unit | §7 |
| `hiring.offer.ambition_equity_boost` / `.ambition_boost_above` | 1.5 / 15 | multiplier / attribute points | §7 |
| `hiring.offer.equity_value_per_bp` | 0.002 | score per bp | §7 |
| `hiring.offer.stage_appeal.<stage>` / `.stage_equity_mult.<stage>` | see §7 | score / multiplier | §7 |
| `hiring.offer.k` / `.threshold` | 3.0 / 0.0 | — | §7 |
| `hiring.lowball_ratio` | 0.85 | ratio | §7 |
| `hiring.max_offer_equity_bp` | 200 | bp | §7 (the pool limit is the unallocated option pool, §14.2; `hiring.option_pool_bp` retired in M4b) |
| `morale.new_hire` | 65 | morale points | §7 |
| `payroll.benefits_bp` | 2000 | bp of salary | §8 |
| `payroll.office_cost_per_head_cents` | 60000 | cents per month | §8 |
| `company.base_monthly_cost_cents` | 200000 (M0), 50000 (M1b) | cents per month | §8 |
| `costs.tools_per_head_cents` | 150000 (M4c; 0 before) | cents per month per employee, founder excepted | §8 |
| `scenario.<id>.starting_cash_cents` | see §8a | cents | §8a |
| `difficulty.<level>.starting_cash_mult_bp` | see §8a | bp | §8a |
| `payroll.severance_months` | 1 | months | §8 |
| `morale.target_base` | 50 (56 from M10d) | morale points | §9 |
| `morale.pay_slope` / `.pay_min` / `.pay_max` | 60 / −20 / 15 | morale points | §9 |
| `morale.fit_per_interest` / `.work_style_mismatch` | 5 / −5 | morale points | §9 |
| `morale.runway_warn_months` / `.runway_crit_months` | 6 / 3 | months | §9 |
| `morale.runway_warn` / `.runway_crit` | −10 / −20 | morale points | §9 |
| `morale.workload_term` | 0 | morale points | §9 |
| `morale.rate` | 0.3 | fraction per month | §9 |
| `morale.noise_scale` | 2.0 | morale points | §9 |
| `morale.fire_penalty` / `.fire_penalty_culture_carrier` | −3 / −6 | morale points | §9 |
| `resign.base_bp` / `.cap_bp` | 50 / 2000 | bp per month | §10 |
| `resign.morale_floor` / `.morale_divisor` | 40 (50 from M10d) / 20 | morale points | §10 |
| `resign.loyalty_divisor` | 10 | attribute points | §10 |
| `resign.job_hopper_mult` | 2.0 | multiplier | §10 |
| `tags.reveal_bp_per_month` / `.reveal_bp_on_check` | 500 / 1500 | bp | §10 |
| `events.light_tone_chance_bp` | 1000 | bp | ADR-0011 |
| `org.department_unlock_headcount` | 10 | people | §13 |
| `org.span_base` / `org.span_per_leadership` | 5 / 4 | reports / attribute points | §13 |
| `org.manager_morale_slope` / `org.manager_morale_cap` | 0.8 / 8 | morale per quality point / morale points | §13 |
| `org.mentoring_neutral` / `.mentoring_divisor` / `.mentor_tag_bonus` | 5 / 20 / 3 | attribute points | §13 |
| `org.growth_mult_min` / `.growth_mult_max` | 0.75 / 1.5 | multiplier | §13 |
| `org.tag_morale.<tag>` / `.tag_morale_cap.<tag>` | culture_carrier +2/+2, credit_taker −2/−4, toxic_high_performer −3/−6 | morale points | §13 |
| `org.reorg.move` / `.new_leader_members` / `.replaced_leader` / `.dissolve_members` | −2 / −1 / −5 / −2 | morale points | §13 |
| `org.raise_morale` / `.raise_threshold_bp` / `.raise_cooldown_turns` / `.pay_cut_morale` | 3 / 500 / 12 / −10 | morale points / bp / turns | §13 |
| `org.promote_morale` | 5 | morale points | §13 |
| `org.remote.sociable_at` / `.sociable_morale` / `.solitary_at` / `.solitary_morale` | 14 / −3 / 7 / +2 | attribute points / morale points | §13 |
| `founder.energy_cost.<org action>` | see §6 | energy | §6 |
| `hiring.pitch_per_recruiting` / `.pitch_neutral` | 0.3 / 10 | score per 10 points / attribute points | §7 |
| `delegates.energy_per_month` / `.scout_cost` / `.max_ratio_bp` | 100 / 20 / 12000 | energy / energy / bp | §13 |

| `products.start_quality` / `.launch_min_quality` / `.launch_min_feature` | 10 / 25 / 30 | quality or feature points | §11.2, §11.4 |
| `products.morale_factor_base` / `.morale_factor_slope` | 0.7 / 0.6 | multiplier | §11.3 |
| `products.coord_free_builders` / `.coord_per_builder` / `.coord_floor` | 5 / 0.02 / 0.6 | builders / fraction / multiplier | §11.3 |
| `products.dev_noise_sd` / `.maverick_noise_sd` / `.dev_noise_sd_cap` | 0.15 / 0.10 / 0.40 | multiplier sd | §11.3 |
| `products.seller_rate.<segment>` | mid-market 2, enterprise 0.3 | customers per month per 10 sell | §11.3 |
| `products.marketer_mk` / `.budget_mk_unit_cents` | 5 / 100000 | mk points / cents per mk point | §11.5 |
| `products.marketer_lift` / `.marketer_lift_cap` / `.marketer_lift_from_mk` | 0.03 / 0.3 / 200 (M46) | fraction per unit of μ / fraction / mk points | §11.5 |
| `products.qcap_per_skill` / `.quality_rate` / `.overcap_decay` / `.rot_threshold` / `.rot_per_month` | 5 / 0.15 / 0.01 / 0.25 / 0.5 | quality points / fraction / fraction / fraction of σ / quality points | §11.4 |
| `products.brand_rate` | 0.10 | fraction per month | §11.5 |
| `products.tag.<tag>.output` / `.perfectionist_qcap_bonus` | see §11.10 / 3 | multiplier / attribute points | §11.10 |
| `products.pace_bands` | [0.4, 0.75] | fraction of σ | §11.13 |
| `market.gamma` / `.awareness_floor` / `.awareness_scale` / `.demand_noise_sd` | 3 / 5 / 0.5 / 0.05 | exponent / brand points / fraction / multiplier sd | §11.7 |
| `market.gap_divisor` / `.low_quality_at` / `.low_quality_churn_mult` / `.sunset_churn_mult` | 50 / 40 / 1.5 / 3 | appeal points / quality / multiplier / multiplier | §11.7 |
| `stages.arr_cents.<stage>` | 2: 100000000, 3: 2000000000 | cents | §11.11 |
| Category, segment and incumbent values | see §11.1, §11.9 | — | data: `categories.yaml`, `incumbents.yaml` |

| `finance.initial_fd_shares` / `.pool_target_bp` | 10000000 / 1000 | shares / bp of post-money FD | §14.2, §14.5 |
| `finance.vesting_months` / `.cliff_months` | 48 / 12 | months | §14.2 |
| `finance.retention_slope` / `.retention_floor` | 0.5 / 0.5 | multiplier | §14.2 |
| `finance.multiple_base` / `.multiple_per_growth` / `.multiple_min` / `.multiple_max` | 4 / 4 / 3 / 20 (2.5 / 5.5 / 3 / 20 from M10d) | ARR multiple | §14.3 |
| `finance.floor_cents.<no_product\|live>` / `.floor_per_head_cents` / `.floor_head_cap` | 200000000 / 400000000 / 10000000 / 30 | cents / people | §14.3 |
| `finance.safe.min_cents` / `.max_cents` / `.optimism` / `.steepness` / `.fee_cents` | 2500000 / 200000000 / 1.2 / 6 / 200000 | cents / multiplier / slope / cents | §14.4 |
| `finance.safe.max_fraction` | 0.5 | fraction of the company | §14.4 (M4a: a SAFE is refused if outstanding SAFEs would claim this much, which keeps the §14.5 close defined) |
| `finance.round.typical_cents.<series>` | seed 100000000–300000000, a 300000000–1000000000, b 1000000000–3000000000 | cents | §14.5 guidance |
| `finance.round.open_turns` / `.valuation_noise_sd` / `.max_amount_of_pre` / `.max_response` | 3 / 0.15 / 0.5 / 0.95 | turns / log sd / fraction / probability | §14.5 |
| `finance.round.gate_arr_cents.<series>` | a: 100000000, b: 500000000 | cents | §14.5 |
| `finance.round.fee_min_cents` / `.fee_bp` | 1500000 / 50 | cents / bp | §14.5 |
| `board.start` / `.rate` / `.growth_weight` / `.expected_growth.<series>` | 70 / 0.2 / 20 / seed 2.0, a 1.5, b 1.0 | confidence / fraction / points / annual growth | §14.6 |
| `board.runway_terms` | ≥12: +10, 6–12: 0, 3–6: −15, <3: −30 | months / points | §14.6 |
| `board.no_product_penalty` / `.no_product_after_turns` / `.down_round_hit` | −20 / 12 / −15 | points / turns / points | §14.6 |
| `board.warning_below` / `.removal_below` / `.removal_months` | 40 / 25 / 3 | confidence / confidence / months | §14.6 |
| `finance.round.heat_max` / `.heat_seed_live` | 3 / 1.5 | multiplier | §14.5 (M4c) |
| `founder.energy_cost.name_nominee` | 2 | energy | §14.6 (M4c) |
| `board.history_months` / `.trend_points` | 6 / 2 | month ends / confidence points | §14.6 (M4b: each director's recent confidence for the Board tab, and how far the average must move to read as rising or slipping) |
| `bankruptcy.months` / `.bridge_burn_months` / `.bridge_cap_of_post` / `.bridge_min_confidence` / `.bridge_open_turns` | 3 / 3 / 0.8 / 40 / 2 | months / months / fraction / confidence / turns | §14.7 |
| Investor firms, scenario cap tables, funding climate | see §14.2, §14.3, §14.5 | — | data: `investors.yaml`, `scenarios.yaml`, `climate.yaml` |

| `rivals.act_threshold` / `.noise_sd` / `.cooldown_turns` / `.push_turns` / `.window_turns` | 0.5 / 0.1 / 6 / 6 / 6 | utility / utility / turns / turns / turns | §15.3 |
| `rivals.need.<action>` | see §15.3; tuned in M5: `poach_gain` 0.007 (was 0.05) | divisors | §15.3 |
| `rivals.weights.<personality>.<action>` / `.price_factor.<personality>` | see §15.3 | multiplier | §15.3 |
| `rivals.price_cut` / `.price_rise` / `.push_pool_growth` / `.brand_push_marketing` / `.cut_costs_pools` / `.cut_costs_marketing` | 0.90 / 1.05 / 0.10 / 0.50 / 0.15 / 0.30 | multiplier / fraction | §15.3 |
| `rivals.function_mix.<category>` / `.pool_morale` / `.pool_skill_other` / `.start_marketing_share` / `.key_people` | see §15.1 / 60 / 12 / 0.08 / 8 | fraction / morale / attribute / fraction / people | §15.1 |
| `rivals.free_agent_months` | 6 | months | §15.4 (M6 sub-task 0: a failed rival's people join the player's later searches for their role) |
| `rivals.startup.found_rate` / `.max_alive` / `.team` / `.cash_cents` / `.raise_months` / `.raise_chance` | 0.02 (tuned in M5; 0.01 before) / 8 / [3, 8] / [100000000, 300000000] / 18 / 0.6 | probability / companies / people / cents / months / probability | §15.4 |
| `rivals.poach.offer_mult` / `.top_fraction` / `.ask_mult` / `.leave_penalty` / `.key_builder_quality_hit` | 1.0 (tuned in M5; 1.25 before) / 0.30 / 1.3 / −0.5 / 2 | multiplier / fraction / multiplier / score / quality | §15.6 |
| `founder.energy_cost.poach_search` | 10 | energy | §15.6 |
| `rivals.poach.bands` / `rivals.money_bands_months` | [0.20, 0.50] / [12, 36] | probability / months | §15.5, §15.6 |
| Incumbent personalities, skills, margins and cash | see §15.1 | — | data: `incumbents.yaml` |

| `events.count_weights` / `.category_repeat_factor` / `.template_cooldown_turns` / `.person_cooldown_turns` / `.critical_gap_turns` | [0.08, 0.40, 0.38, 0.14] / 0.5 / 12 / 4 / 6 (tuned in M6.9; were [0.15, 0.50, 0.28, 0.07] / 0.5 / 24 / 6 / 6) | probabilities / multiplier / turns | §16.1 |
| `events.major_from` | 0.5 | trigger strength | §16.1 |
| `events.trigger.<trigger>` | see §16.2; tuned in M6.9: `underpaid.below` 0.95, `star_performer.top_fraction` 0.30, `team_clash.at_most` −25, `team_bond.at_least` 30, `board_unhappy.below` 50 (§16.1) | thresholds and strengths | §16.2 |
| `events.caps.<effect>.<severity>` | see §16.3; tuned in M6.9: `morale_delta` minor 3 | per effect | §16.3 |
| `events.max_storylines` / `.summary_words` / `.body_words` | 3 / 60 / 180 | count / words / words | §16.5, §16.6 |
| `relationships.start_base` / `.start_per_temperament` / `.start_clamp` / `.drift` | 15 / 1.5 / [−20, 15] / 0.10 | points / points per attribute point / points / fraction per month | §16.7 |
| `relationships.tag_push.<tag>` / `.politician_ambition_at` | credit_taker −3, toxic_high_performer −4, culture_carrier +2, politician −3 / 14 | points per month / attribute points | §16.7 |
| `relationships.morale_weight` / `.morale_cap` / `.label_bounds` | 0.1 / 5 / [−50, −20, 20, 60] | morale per point / morale points / points | §16.7 |
| `llm.monthly_budget_cents` / `.price_per_mtok_cents.<model>` / `.model_events` / `.model_story` | 1000 / settings / settings / settings | cents / cents / model id | ADR-0005, §16.5 (settings, not `balance.yaml`) |

## 13. Organization (M2)

The org is a tree of units under the company. Every effect below works through things M1 already has: morale (§9), growth (§3), offers (§7) and founder energy (§6). Productivity, coordination cost and decision latency arrive with products in M3.

### 13.1 Units and reporting lines

| Unit | Parent | Available |
| --- | --- | --- |
| Company (root, implicit) | — | Always; led by the founder |
| Department | Company | At 10 staff, or at stage 2 |
| Team | Company or a department | Always |

- Each unit has a name, an optional leader, and a work-location policy (§13.9). A unit without its own policy uses its parent's.
- Every staff member belongs to exactly one unit; `employment.unit_id` is null for the company root. A leader must be a member of the unit they lead, and leads at most one unit. The founder always belongs to the root.
- **Manager of a person:** the leader of their unit. If they lead that unit, or it has no leader, go up one level and repeat; the company root's leader is the founder. The founder has no manager.
- **Direct reports** of a manager are everyone whose manager they are.

**Why departments unlock at 10 staff:** spec §6 unlocks them at stage 2 (seed closed or $1M ARR), which no company can reach before M3 and M4. The headcount gate keeps the feature usable now and matches stage 2's typical size (10 to 75).

### 13.2 Span of control

```latex
L = 5 + \left\lfloor \frac{leadership}{4} \right\rfloor, \qquad S = \begin{cases} 1 & n \le L \\ L / n & n > L \end{cases}
```

`n` is the number of direct reports. A leadership-14 manager handles 8 comfortably (spec §6); at 12 reports, `S = 8 / 12 = 0.67`.

### 13.3 Manager quality

```latex
Q = \frac{2\,leadership + communication + mentoring}{4} \times S
```

### 13.4 Manager morale term

```latex
W_{mgr} = clamp\big(0.8\,(Q - 10),\; -8,\; +8\big)
```

Applies to every employee except the founder, using their manager's true attributes.

### 13.5 Mentoring multiplier on growth

```latex
M_{growth} = clamp\left(1 + \frac{mentoring \cdot S + bonus - 5}{20},\; 0.75,\; 1.5\right)
```

`mentoring` and `S` are the manager's. `bonus` is 3 if any other member of the person's unit has the `mentor` tag (true tags, noticed or not), else 0. A manager with mentoring 5 is neutral, because most people's non-role skills are drawn from 1 to 8.

### 13.6 Teammates' behavior tags

Each tag affects the other members of its holder's unit (not the holder), using true tags. Sums per tag are capped.

| Tag | Effect on each other member's morale target | Cap per tag |
| --- | --- | --- |
| `culture_carrier` | +2 | +2 |
| `credit_taker` | −2 (until M6) | −4 |
| `toxic_high_performer` | −3 (until M6) | −6 |

**M6 (§16.7):** the `credit_taker` and `toxic_high_performer` rows are removed; their effect now comes through relationships (tag pushes on unit-mate pairs, then W_rel). `culture_carrier` keeps its row and also pushes relationships.

`mentor` acts through §13.5. `politician`, `maverick`, `perfectionist` and `quiet_genius` take effect with products (M3). The API never explains a morale change by a tag the company has not noticed (§13.11).

### 13.7 Reorganizing (immediate actions, ADR-0014)

| Action | One-off morale change |
| --- | --- |
| Move a person to another unit | −2 for that person |
| Set or replace a unit's leader | −1 for each other member; −5 for a replaced leader who stays in the unit |
| Dissolve a unit | −2 for each member; members and child teams move to the parent |
| Create a unit | none |
| Move a team under a department or the company | none; its members and child units go with it |

### 13.8 Raises and promotions (immediate actions)

- **Raise:** the new salary applies from the next payroll. A raise of at least 5% gives +3 morale once, at most once per 12 turns per person. Any pay cut gives −10 once. Pay then moves morale through §9's pay term as usual.
- **Promote:** one level up (junior → mid → senior → staff → principal; exec is not reachable in M2). +5 morale once. The new level's market rate applies from then on, so a promotion without a raise lowers the pay term: promote and raise together.

### 13.9 Work-location policy

`office` (default) or `remote`, per unit. Remote members cost no office fee (§8). Remote morale term: −3 if sociability ≥ 14, +2 if sociability ≤ 7, else 0.

### 13.10 Delegated hiring

- **Hiring plan:** owned by a delegate (any staff member except the founder; usually a recruiter or the unit's leader), for one unit and role, with a target count, a channel (job post, recruiter, network, or any), a maximum salary ratio (at most 1.2× the ask), equity per offer, and a **focus**: `current` (default) or `potential` (M2b). Hires join the plan's unit.
- **Delegate energy:** 100 per month per delegate, stored on their `person_state.energy`, reset with the founder's. It is separate from the founder's.
- **Each turn, in phase 2** (deterministic; randomness only inside the actions it takes), for each plan in id order, while the delegate has energy:
  1. If the plan is short and has no open search for its role, open one (channel `any` means job post).
  2. Rank that role's open candidates by the **company's displayed** range midpoints of the role's skills (primary × 3, secondary × 1); ties by candidate id. **Focus `potential` (M2b):** consider only junior and mid candidates, and rank by the midpoint of the company's displayed PA range, ties by the role-skill score and then candidate id. Steps 3 and 5 use the same order.
  3. Interview the best uninterviewed candidates (6 energy each) while more than 20 energy would remain.
  4. With at least 20 energy left, scout: apply `scouting_month` (§4) once to every open candidate of the plan's searches.
  5. Offer to the best candidates the company has interviewed (the §7 interview rule) without a pending offer, at the ask × the plan's ratio, up to the number still needed, within the option pool.
- Delegate actions call the same `apply_action` with `actor` = the delegate, so energy, rules and the offer pitch (§7) apply. Their randomness uses stream `delegate`, key `(person_id, n)`, where `n` counts that delegate's actions this turn (ADR-0015).
- **Quality emerges:** better `judgment_of_talent` narrows ranges more (§4); better `recruiting` lands more offers. M2a found that judgment barely changes current-ability hires (gap about 0.1 CA), because every candidate in a batch is interviewed and current skills show quickly. Judgment's real job is **spotting potential**.
- **Potential target (M2b acceptance, revised after the first tuning run):** over 400 seeded runs of a `potential` plan for 2 software engineers, a judgment-16 recruiter's hires have a mean true PA at least **3 points** higher than a judgment-6 recruiter's on the same seeds. With a stranger's PA `hw` at 40 the named keys reached only +1.3, because a 40-point range is already accurate enough to rank candidates whose potential spreads over about 25 points. Tune `reveal.initial_hw.pa` (60–120, preferring the smallest value that meets the target) together with `reveal.pa_scout_divisor` and `reveal.pa_strength.*`. Record the final values and, for a judgment-10 founder, the typical potential phrase after a job-post screen plus one interview (for example "decent to excellent"), so the cost to the player's own reading is visible. The current-focus CA gap is printed but has no target.
- The API never shows a PA number: focus changes only the delegate's ranking, and the plan's inbox summary says "favouring potential".
- Each plan writes one inbox summary per turn when it acted ("Petra interviewed 4 software engineers and made 2 offers").
- **Closing searches:** when a plan fills or closes, its delegate closes any job post it opened for that plan, unless another open plan for the same role uses it. A filled plan's job posts close in phase 2 (a `close_search` action by the delegate); a closed plan's close with the `close_plan` action. A job post another open (active or paused) plan for the same role uses stays open and passes to that plan, lowest plan id first.

### 13.11 What the API may explain

A person's morale breakdown may show pay, fit (revealed interests only), runway, manager, remote policy, and teammate-tag effects for tags the company has noticed. Anything else is grouped as "other", so morale never reveals a hidden tag.

### 13.12 Worked examples

| Case | Values | Result |
| --- | --- | --- |
| Team lead, 6 reports | leadership 14, communication 12, mentoring 10 | L = 8, S = 1, Q = 12.5, W_mgr = **+2.0**, M_growth = **1.25** (1.40 with a mentor teammate) |
| Same lead, 12 reports | as above | S = 0.667, Q = 8.33, W_mgr = **−1.33** |
| Founder managing 12 directly | engineer default: leadership 11, communication 10, mentoring 5 | L = 7, S = 0.583, Q = 5.40, W_mgr = **−3.68**, M_growth = **0.90** |
| Same founder with 2 team leads | 2 direct reports | S = 1, Q = 9.25, W_mgr for the two leads = **−0.60** |
| Lead B, 5 reports | leadership 12, communication 11, mentoring 7 | L = 8, Q = 10.5, W_mgr = **+0.40**, M_growth = **1.10** |
| Offer pitch | recruiting 7 / 15 | **−0.09** / **+0.15** |

A flat company run by the founder loses about 4 morale per person once it passes 7 staff; two capable leads remove the penalty. Building the org is the M2 answer to M1's growing team.

## 14. Finance (M4)

M4 gives the company a cap table in shares, real statements, SAFEs and priced rounds (Seed, Series A, Series B) from investor firms, a board whose confidence can end the founder's run, and bankruptcy. Venture debt, bank loans, Series C onward, liquidation waterfalls, IPO and M&A are v2. ADR-0018 records the game-over states and the share model.

### 14.1 Statements (derived from the ledger)

Statements are views over `ledger_line`; they add no state.

- **Profit and loss** for a month, quarter or year: revenue (`4xxx`), cost of revenue (`6300_compute` hosting, shown under gross margin), operating expenses (`6000`–`6900` except `6300`), operating result, interest (`7000`, zero in v1), tax (`8000`, zero in v1), net result.
- **Balance sheet** at a month end: assets (`1xxx`), liabilities (`2xxx`, including `2600_safes`), paid-in equity (`3xxx`) and **accumulated result** (the sum of every past net result; there are no closing entries). Invariant, tested every turn: assets = liabilities + paid-in equity + accumulated result.
- **Cash flow** for a period: operating (net result; there are no accruals in v1), financing (SAFE money, priced rounds, fees on rounds are operating), and the change in cash, which must equal the cash account's movement.
- **Burn** = net cash used before financing: −(operating + investing cash flow) over the month when negative, else 0. Investor and loan money (SAFEs, rounds, bridges, debt) never counts, and the month includes cash moved by actions before Continue (a paid event). Decided 2026-10-31 (M8r, Codex review 1 finding 7); the snapshot, the Overview tile and its breakdown all use it; **runway** = cash ÷ this month's projected net burn (projected costs − this month's revenue), shown as "profitable" when the projection is positive.

### 14.2 Shares and the cap table

- At game start the company has **10,000,000 fully diluted shares** (FD). Holdings by scenario (data: `scenarios.yaml`):

| Scenario | Founder | Option pool | Others |
| --- | --- | --- | --- |
| `garage_bootstrap` | 9,000,000 | 1,000,000 | — |
| `ex_big_tech_founders` | 8,500,000 | 1,000,000 | 500,000 common, "Former colleagues" (the angel money in the starting cash) |
| `funded_spinout` | 7,000,000 | 1,000,000 | 2,000,000 Seed preferred at $0.75, led by a seed firm with one board seat (the $1.5M starting cash; post-money $7.5M) |

- The **option pool** has granted and unallocated shares. An offer still states equity in basis points of the current FD (§7); on hire it becomes a grant of `round(bp × FD / 10000)` options from the unallocated pool. The M1 rule "equity held by staff plus pending offers may not exceed 1,000 bp" becomes: pending offers plus grants may not exceed the unallocated pool. Saves from before M4 convert each employee's `equity_bp` to options at 1,000 shares per bp.
- **Vesting:** 48 months with a 12-month cliff, from the hire turn: vested = 0 before 12 months, then `floor(granted × min(48, months) / 48)`. When someone leaves, unvested options return to the unallocated pool; vested options stay with them (they remain on the cap table as former employees).
- **Share price** for display and retention: the price of the latest priced round, or $0 before any.
- **Retention:** unvested value `u = unvested × share price ÷ annual salary`; the monthly resignation chance (§10) is multiplied by `max(0.5, 1 − 0.5 u)`.
- Rounding: share counts are integers, rounded half-to-even; money stays integer cents.

### 14.3 Investors' view of value

Every investor starts from the same base value, then applies their own bias and noise (§14.5).

```latex
g_6 = \left(\frac{MRR_t}{MRR_{t-6}}\right)^{2} - 1 \qquad (g_6 = 3 \text{ if } MRR_{t-6} = 0 < MRR_t;\ g_6 = 0 \text{ if } MRR_t = 0)
```

```latex
multiple = clamp(2.5 + 5.5\,g_6,\; 3,\; 20) \times climate(year), \qquad V_{traction} = ARR \times multiple
```

```latex
V_{floor} = \begin{cases} \$2{,}000{,}000 & \text{no live product} \\ \$4{,}000{,}000 & \text{a live product} \end{cases} + \$100{,}000 \times \min(headcount, 30)
```

```latex
V_{base} = \max(V_{floor},\; V_{traction})
```

**Funding climate** by calendar year (data: `climate.yaml`; years after the table use 1.0 until the v2 macro layer):

| 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.90 | 1.00 | 1.00 | 1.10 | 1.20 | 1.25 | 1.00 | 1.10 | 1.20 | 1.20 | 1.30 | 1.60 | 0.90 | 0.75 | 0.90 | 1.00 |

### 14.4 SAFEs (immediate action; resolved in phase 7)

- **Raise on a SAFE** (energy 10): an amount ($25,000 to $2,000,000) and a **post-money valuation cap**. No discount in v1. At most one SAFE raise open at a time.
- In phase 7 of the next turn, angels and seed funds answer once, all or nothing (stream `finance`, key `(safe_id,)`):

```latex
p = \frac{1}{1 + e^{-6\,(1.2\,V_{base} / cap - 1)}}
```

  A cap at 1.2 × `V_base` gets 50%; a lower cap is likelier to fill.
- Money: debit `1000_cash`, credit `2600_safes`; a $2,000 legal fee to `6900_general_admin`. The SAFE holders own `amount / cap` of the company at the next priced round (post-money SAFE), before the new money.

### 14.5 Priced rounds

**Series and gates** (the round's name follows the company's last priced round):

| Series | Allowed when | Typical raise (shown as guidance) |
| --- | --- | --- |
| Seed | No priced round yet | $1M–$3M |
| Series A | After a seed (or the scenario's) and ARR ≥ $1M | $3M–$10M |
| Series B | After a Series A and ARR ≥ $5M | $10M–$30M |

**Starting a round** (energy 15): choose the series and a target amount. At most one round open at a time; it stays open for 3 turns.

**Term sheets** arrive in phase 7 of the next turn (stream `finance`, key `(round_id, firm_index)`). Each firm in `investors.yaml` that invests in that series answers with probability `response × climate × heat` (at most 0.95), where **heat (M4c)** rewards traction: `heat = clamp(ARR / gate, 1, 3)` for Series A and B (gate = that series' ARR gate) and, for a seed, 1.5 with a live product, else 1. A Series A candidate at $6M ARR (heat 3) hears from almost every eligible firm; one just over the $1M gate hears from two or three. Each answer quotes:

```latex
V_{pre} = V_{base} \times bias \times e^{N(0,\, 0.15)}, \qquad amount = clamp(target,\; check_{min},\; \min(check_{max},\; 0.5\,V_{pre}))
```

- Standard terms in v1: 1× non-participating liquidation preference (recorded; it matters only at exits, v2), pro rata rights (recorded), the lead takes **one board seat**, and an **option pool top-up** so the unallocated pool is 10% of the post-money FD.
- If no firm answers, the inbox says so and the round closes; the player may start again next turn.

**Accepting** a term sheet (energy 5, while the round is open) closes the round in phase 1 of the next turn; the others lapse. **Closing** (`E` = FD before the round, `f` = Σ SAFE amount / cap, `u` = unallocated pool, `V_post = V_pre + amount`):

```latex
k = \frac{0.10\, V_{post}}{V_{pre}\,(1 - f)}, \qquad X = \max\left(0,\; \frac{k E - u}{1 - k}\right)
```

```latex
C = \frac{f}{1 - f}\,(E + X), \qquad FD_{pre} = E + X + C, \qquad price = \frac{V_{pre}}{FD_{pre}}, \qquad N = \frac{amount}{price}
```

`X` new pool shares, `C` SAFE conversion shares, `N` new preferred shares (each rounded half-to-even). Ledger: debit cash, credit `3100_preferred_equity` (the new money); debit `2600_safes`, credit `3100_preferred_equity` (the converted SAFEs); legal fees `max($15,000, 0.5% of amount)` to `6900_general_admin`. A price below the previous round's is a **down round**.

**Investor firms** (data: `investors.yaml`; real names, personal use, CLAUDE.md §7):

| Firm | Series | Check size | Bias | Response | Patience |
| --- | --- | --- | --- | --- | --- |
| SV Angel | Seed | $250k–$1M | 1.05 | 0.6 | +5 |
| First Round Capital | Seed | $500k–$2M | 1.00 | 0.5 | +5 |
| Union Square Ventures | Seed, A | $1M–$5M | 0.95 | 0.4 | 0 |
| Founders Fund | Seed, A, B | $1M–$15M | 1.10 | 0.3 | +5 |
| Accel Partners | A, B | $3M–$20M | 1.00 | 0.4 | 0 |
| Benchmark | A | $4M–$12M | 1.05 | 0.3 | 0 |
| Sequoia Capital | A, B | $5M–$30M | 0.95 | 0.35 | −5 |
| Andreessen Horowitz | A, B | $5M–$30M | 1.15 | 0.35 | 0 |
| Kleiner Perkins | B | $10M–$30M | 0.90 | 0.4 | −5 |
| Greylock Partners | A, B | $5M–$25M | 1.00 | 0.35 | 0 |

`patience` shifts the board-confidence target of the firm's seat (§14.6). The funded-spinout scenario's seed is led by First Round Capital.

### 14.6 The board

- **Seats:** before any priced round there is no board. Directors other than the founder are generated people (stream `board`, id 17, key `(seat_id,)`; M4a); every new director starts at `board.start`. After the seed: 1 common seat (the founder) and 1 investor seat (the seed lead). After Series A: 2 common, 2 investor. After Series B: 2 common, 3 investor, 1 independent. The second common seat is the founder's nominee. **M4c:** the founder chooses the nominee from current employees when accepting the Series A term sheet (default: the most senior); if the nominee leaves, the seat is empty until the founder names another (energy 2), and an empty common seat still votes no. Investor directors and the independent are generated people (role `board_member`, not employees) so events can name them; the screens show them on a board-member card, not an employee profile.
- **Confidence** `B` (0–100, starts at 70 when the first board forms; each director has their own, shown as the average) moves each month in phase 10:

```latex
B \leftarrow B + 0.2\,(T - B), \qquad T = 50 + 20\cdot clamp\left(\frac{g_6}{g_{exp}} - 1,\; -1,\; 1\right) + R + patience
```

  with `g_exp` the expected annual MRR growth for the last round (Seed 2.0, Series A 1.5, Series B 1.0) and the runway term `R`: ≥ 12 months +10, 6–12 months 0, 3–6 months −15, under 3 months −30. Before the company has 6 months of revenue history the growth term is 0, or −20 if 12 months have passed since the last round without a live product. A down round lowers every director's `B` by 15 once.
- **Warnings:** each quarter-end (March, June, September, December) the inbox carries a board meeting summary; average `B` below 40 adds a formal warning.
- **Removal:** when an investor or independent director's `B` has been below 25 for 3 consecutive months they vote to remove the founder; common seats vote no. If the votes to remove are a majority of all seats, the founder is removed: **game over** (ADR-0018). A tie keeps the founder, so removal is possible only after Series B.

### 14.7 Bankruptcy and bridges (phase 7)

- Each month, after phase 6, if cash < 0 the company is **insolvent**: a critical inbox item names how much is needed. If the company has a board and the average `B` ≥ 40, existing investors offer a **bridge SAFE** once per insolvency: post-money cap = 0.8 × the last priced round's post-money valuation, accepted with an immediate action (energy 5) within 2 turns; it posts like §14.4 (fee included) in phase 7 of the turn it is accepted. **Amount (M4b fix):** computed when it is accepted, not when offered: `3 × this month's projected net burn + max(0, −cash)`, so a bridge taken in the last month of grace still clears the deficit and buys three months. The offer shows the amount it would be today.
- Cash below zero at the end of phase 7 for **3 consecutive months** is **bankruptcy: game over**. The M1 rule "opening a job post requires cash for its first month" stays; nothing else is blocked while insolvent.

### 14.8 Stages from funding

Stage 2 is entered once the company is at stage 1 and has closed a seed (the funded spinout's counts) or reached $1M ARR; stage 3 once it has closed a Series B or reached $20M ARR (§11.11).

### 14.9 What the API may show

Statements, the full cap table (holders, classes, shares, percentages, vesting per employee), rounds and their terms, term sheets with each firm's quoted valuation, board seats and directors, average and per-director confidence as a label and number, and the runway. Never `V_base`, a firm's bias or noise, or the SAFE acceptance probability; a SAFE dialog may show a hint band ("likely", "uncertain", "unlikely") from `1.2 V_base / cap` (≥ 1.15, 0.9–1.15, below 0.9).

### 14.10 Worked examples

**Dilution through a SAFE and three rounds** (garage start: founder 9,000,000, pool 1,000,000 with 400,000 granted):

| Event | Terms | X (pool top-up) | C (SAFE) | Price | New shares | FD after | Founder |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SAFE | $500,000 at a $5M post-money cap (`f` = 0.10) | — | — | — | — | 10,000,000 | 90.00% |
| Seed | $2M at $6M pre | 1,034,783 | 1,226,087 | $0.48936 | 4,086,957 | 16,347,827 | 55.05% |
| 800,000 more options granted | | | | | | | |
| Series A | $5M at $16M pre | 1,508,914 | — | $0.89602 | 5,580,232 | 23,436,973 | 38.40% |
| 1,000,000 more options granted | | | | | | | |
| Series B | $15M at $60M pre | 1,812,485 | — | $2.37629 | 6,312,364 | 31,561,822 | 28.52% |

After each round the unallocated pool is exactly 10.00% of FD; after the seed the SAFE holders own 7.50% and the seed investor 25.00%; after Series B the Series B investor owns 20.00%.

**Investors' base value.** ARR $1.81M with MRR growing 6.8% a month for 6 months: `MRR_t / MRR_{t−6}` = 1.4840, `g_6` = 1.2022, multiple = 9.112 (climate 1.0 in 2012), `V_traction` = **$16.49M**, above the floor. (M10d balance pass: the multiple was `4 + 4 g_6`, 8.809 and $15.94M here; growth now weighs more, so faster-growing strategies are worth more against steady, docs/balance-targets.md T2.)

**SAFE acceptance.** With `V_base` = $4.5M: a cap of $5.4M gives p = 50%; $4.5M gives 76.9%; $7M gives 20.2%.

**Board confidence.** From 70, with growth at half of expected (`g_6 / g_exp` = 0.5) and 4 months of runway: T = 50 − 10 − 15 = 25, and B is 36.8 after 6 months (warning). With under 3 months of runway: T = 10, B falls below 25 in month 7 (22.6); a removal vote follows in month 9 if it stays there.

**Retention.** 75,000 unvested options at $0.896 for someone paid $95,000: u = 0.707, so their resignation chance is multiplied by 0.646.

## 15. Rivals (M5)

M5 turns the 2010 incumbents into companies that act, and adds rival startups that are founded, grow and die. Rivals use the same market (§11), finance rules for cash and bankruptcy (§14.7) and people rules (§2–§10) as the player; only their decisions differ (ADR-0010, ADR-0015: rivals act in phase 2).

### 15.1 Incumbent companies (data: `incumbents.yaml`)

Each incumbent gains a **personality**, a **workforce pool** per function, **8 key people**, cash and a ledger.

| Company | Personality | Builder skill `d` | Target margin | Cash (months of revenue) |
| --- | --- | --- | --- | --- |
| Salesforce | premium | 14 | 15% | 24 |
| Oracle | fast_follower | 12 | 25% | 60 |
| Zoho | cost_leader | 11 | 15% | 18 |
| Atlassian | fast_follower | 14 | 20% | 24 |
| Microsoft | aggressive | 13 | 30% | 60 |
| GitHub | aggressive | 15 | 0% | 12 |
| Facebook | aggressive | 13 | 20% | 36 |
| Zynga | aggressive | 11 | 15% | 18 |
| Evernote | premium | 14 | 0% | 12 |
| Symantec | premium | 12 | 25% | 36 |
| McAfee | cost_leader | 11 | 20% | 24 |
| Check Point | premium | 14 | 30% | 48 |

- **Pools are sized from revenue**, so each incumbent starts near its target margin in the modelled market: monthly cost budget = revenue × (1 − margin) − hosting − marketing; headcount = budget ÷ the loaded cost per head (salary at the role's mid-level market rate, benefits, office, `costs.tools_per_head_cents`), split by the category's function mix: B2B SaaS and cybersecurity 45% builders, 40% sellers, 15% marketers; developer tools 70 / 15 / 15; consumer apps 75 / 0 / 25. Pool morale is 60; pool skill is the table's `d` for builders and 12 for sellers and marketers.
- **Marketing budget** at start: 8% of each product's revenue.
- **Key people:** 8 generated individuals per incumbent (senior to principal, in its pool roles, stream `people_gen`), included in the headcount. They grow, age, resign and retire like anyone, and they are the people the player can poach (§15.6). The rest of the staff stay as pools (ADR-0010).
- **Ledgers:** from M5 each rival posts revenue (phase 5), payroll, hosting and marketing (phase 6) like the player. A rival whose cash is below zero for 3 consecutive month ends goes bankrupt (§14.7); its products are retired and their customers return to the unserved pool.

### 15.2 How rival products change

Rival products keep the M3 held feature score and fixed quality except through the actions below; their brand changes only through actions. This keeps the M3 equilibrium (§11.9) stable until a rival chooses to move.

| Effect | Rule |
| --- | --- |
| Quality | moves toward `5 d` at 1 point a month while a quality push runs (§15.3), and back toward its starting value at 0.2 a month after a key builder leaves for the player |
| Feature score | +1 a month during a feature push; −0.5 a month for 6 months after a cost cut |
| Brand | +1 a month during a brand push; −0.5 a month for 6 months after a cost cut |
| Price | changed by price actions |

### 15.3 Decisions: one action a month (phase 2, stream `rivals`, key `(company_id,)`)

Each month each rival scores every action it could take and takes the best one if its utility is at least 0.5:

```latex
U(a) = need(a) \times w_{personality}(a) + N(0,\, 0.1)
```

| Action | `need` (each clamped to 0–1) | Effect |
| --- | --- | --- |
| `price_cut` (product, segment) | its share of the segment's served customers fell by `drop` over 6 months: `drop / 0.05` | price × 0.90 |
| `price_rise` | appeal leads the next best product by `lead`, share not falling: `(lead − 5) / 10` | price × 1.05 |
| `feature_push` | `(best feature in segment − own) / 15` | +1 feature a month for 6 months; builder pool +10% |
| `quality_push` | `(best quality in segment − own) / 15` | toward `5 d` for 6 months; builder pool +10% |
| `brand_push` | `(best brand in segment − own) / 30` | +1 brand a month for 6 months; marketing budget +50% for 6 months |
| `enter_segment` | a category segment it does not serve, with `unserved / D ≥ 0.4` and cash ≥ 12 months of costs: `(unserved / D − 0.4) / 0.4` | sells there at `p_ref × price_factor` |
| `cut_costs` | cash covers fewer than 12 months of costs: `(12 − months) / 6` | every pool −15%; marketing −30% |
| `poach` | the player gained `gain` share points over 6 months in a segment they share: `gain / 0.05`, and the player has an employee in the top 30% of its CA | approach one such employee, drawn by CA (§15.6; the best one until M10d) |

| Personality | price_cut | price_rise | feature | quality | brand | enter | cut_costs | poach | `price_factor` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| aggressive | 1.3 | 0.6 | 1.2 | 0.9 | 1.1 | 1.3 | 0.9 | 1.4 | 0.9 |
| fast_follower | 1.0 | 0.8 | 1.3 | 1.0 | 0.9 | 1.0 | 1.0 | 1.0 | 1.0 |
| premium | 0.6 | 1.2 | 1.0 | 1.3 | 1.2 | 0.8 | 1.0 | 0.9 | 1.3 |
| cost_leader | 1.4 | 0.5 | 0.9 | 0.8 | 0.8 | 1.1 | 1.2 | 0.8 | 0.7 |

- **Cooldown:** the same action on the same product and segment is not chosen again within 6 months; a push runs its 6 months before another of the same kind.
- Actions are written to `decision_log` with `source = "rival"` and replayed by recomputation (ADR-0015 §5).

### 15.4 Rival startups (phase 9, stream `rival_spawn`, key `(category_index,)`)

- Each month, each category founds a startup with probability `0.01 × climate × (1 + g)` (`g` = the category's annual growth), while fewer than 8 rival startups are alive.
- A startup: a generated name (`names.yaml` company pool), a founder and 3 to 8 individual employees (stream `people_gen`), $1M to $3M cash, one product in development in that category for one or two segments, and a random personality other than premium. It develops, launches and prices like the player's products (§11, using its individuals' output) and decides with §15.3.
- **Funding:** when its cash covers fewer than 6 months, it raises 18 months of costs with probability `0.6 × climate` once a quarter; otherwise it cuts costs. Bankruptcy follows §14.7. A dead startup's people become candidates in the player's next searches for their roles.

### 15.5 What the player sees

A monthly **Market news** inbox item lists every rival action and every startup founded, launched, funded or failed that month ("Zoho cut SMB prices 10%", "Northwind launched in Developer tools"). Prices, quality, features, brand and customers of every product stay public (§11.13). A rival's personality is shown as a label, its money as "deep pockets" (cash covers 36 months of costs or more), "comfortable" (12–36) or "tight" (under 12), and its stance toward the player as "responding" (it took an action in a segment the player sells to within the last 6 months), "watching" (it shares a segment with the player) or "not competing". Pools are shown as estimated headcount (rounded to the nearest 10 above 100). Key people are shown with the player's revealed ranges (they start as strangers).

### 15.6 Poaching

**Rivals approach the player's people.** A `poach` action picks one of the player's employees in the top 30% by true CA who has no approach pending (M10d, product manager 2026-11-02: drawn weighted by CA, a current seat holder's weight × `rivals.poach.seat_holder_weight` 0.4, since executives are better paid and harder to reach; stream `poach`, key `(new approach id, 1)`, so no other draw moves; before M10d it was always the highest CA, ties by id) and offers `1.25 ×` their role and level's market rate. The approach arrives as an inbox item; the player may counter with a raise (§13.8) before Continue. In phase 1 of the next turn the employee decides (stream `poach`, key `(approach_id,)`):

```latex
s = 4\,(R - 1) + \frac{55 - morale}{20} - \frac{loyalty - 10}{10} - 2u + leave\_penalty, \qquad p = \frac{1}{1 + e^{-2s}}
```

`R` = offer ÷ current salary (after any counter), `u` = unvested option value ÷ annual salary (§14.2). Accepting is a resignation with one month's notice; the person joins the rival as a key person. The screens show a band, never `p`, computed from what the player knows (true salary, offer and options; displayed midpoints for loyalty; morale exactly): below 20% "likely to stay", 20–50% "might go", above 50% "likely to go".

**The player poaches from rivals.** A new search channel, **Poach from a rival** (energy 10, one rival): candidates are 2 to 4 of that rival's key people, shown as strangers. The interview rule (§7) applies; asks are `1.3 ×` their current salary; the offer score (§7) gets `−0.5` for leaving an employer. A hire removes the person from the rival; if they were a builder, each of that rival's products in their category loses 2 quality over the next 6 months (§15.2).

### 15.7 Balance targets (M5 acceptance, printed)

1. **Living market:** with no player product, over 120 turns on 10 seeds, no incumbent's share of a segment's served customers falls below half or rises above double its starting share, and on average at least one rival startup per category launches a product.
2. **Rivals respond:** in the M3a earn-and-burn script, at least one incumbent cuts a price or starts a push in a segment the player sells to within 24 turns of launch, on at least 7 of 10 seeds.
3. **Still winnable:** the earn-and-burn script's ARR at turn 36 stays within $500,000 to $4M on at least 8 of 10 seeds.
4. **Poaching felt, not crushing:** in the fast-growth script, 1 to 4 approaches a year on average, and 10% to 40% of uncountered approaches accepted (20–60% before M10d; re-banded by the product manager on 2026-11-02: with the median employee at 58–68 morale, happier staff refuse more offers).
6. **Rivals carry the threat (M10d, product manager 2026-11-02):** the player loses 0.5 to 1.5 staff a year to rivals while the company has 30 or more people (median of 10 seeds, steady and blitzscale, 120 turns); executive retention stays at 8 of 10 or better.
5. **Speed:** 120 turns with 25 player staff, all incumbents and up to 8 startups under 1 second per turn on average.

Tune only `rivals.*` keys and the personality weights to meet them; record the values.

### 15.8 Worked examples

**A cost leader answers a price war.** Zoho's SMB share of served customers fell from 47% to 41% in 6 months (`drop` = 0.06): `need` = 1, `U` = 1 × 1.4 = 1.4 (noise off), so it cuts its SMB price from $25 to $22.50.

**A premium incumbent ignores a small threat.** Salesforce's SMB share fell 1 point: `need` = 0.2, `U` = 0.2 × 0.6 = 0.12, below 0.5: no action.

**Poaching Priya** (salary $118,000, morale 62, loyalty 12, 52,084 unvested options at $1.0295; `leave_penalty` −0.5 from M5, Reece's decision): Salesforce offers $143,750 (`R` = 1.218, `u` = 0.454): `s` = −1.086, **p = 10.2%**. If the player counters with a raise to $135,000 (`R` = 1.065, `u` = 0.397): `s` = −1.585, **p = 4.0%**. An underpaid, unhappy employee with no options (`R` = 1.218, morale 40, loyalty 8, `u` = 0): `s` = 1.323, **p = 93.4%**. (Before the leaving penalty: −0.586 and 23.7%, −1.085 and 10.2%, 1.823 and 97.5%.) **M10d balance pass:** `rivals.poach.leave_penalty` is now −0.3, so happier staff (median morale 58–68) still take some offers; the example keeps −0.5, and its test uses it.

## 16. Events, storylines and relationships (M6)

The engine decides when an event happens, about whom, how severe it is and what it may change; the LLM (or a template) decides only how it reads and which allowed effects each choice carries (ADR-0005). In v1 there are no weekly sub-turns: a critical event blocks Continue until the player decides (ADR-0006, amended).

### 16.1 When events happen (phase 12, stream `events`, key `(turn,)`)

- Each month the director draws how many events to queue for next month: 0 with 15%, 1 with 50%, 2 with 28%, 3 with 7% (mean 1.27).
- **Candidates** are templates (§16.4) whose trigger holds this month (§16.2). Weight = template weight × trigger strength (0–1) × 0.5 if its category was used last month × 0 if the same template ran in the last 24 months or any event named the same person in the last 6 months. Draw without replacement by weight.
- **Severity** comes from the template and the trigger's strength: minor below 0.5, major from 0.5, critical only for templates marked critical and at most one critical event in any 6 months.
- **Critical follow-ups wait (M46):** a queued follow-up or moment whose template is critical only (a listed company's IPO pricing, an activist's stake) takes the month's critical slot ahead of storyline steps, crises and drawn events; when the slot is taken (a critical event in the last 6 months), it stays queued and arrives in the first month the slot is free, deferred, never dropped. **While the player's IPO chain is under way** (banks hired, not yet priced) the slot is held for its pricing step: drawn critical events and crises wait, so the pricing (which the listing waits on) is deferred only when a critical event came in the months just before the banks were hired.
- Events for a company with no employees yet use only founder, market and finance templates. (M7a: the `founder` category holds the `early_days` templates: the founder's own first months, before anything is live; Reece asked for a varied early game for a solo founder, docs/balance-targets.md E3.)
- **Quiet-month fill (Reece, 2026-10-29, M6.9):** when the drawn count still has slots but every triggered candidate is spent or in cooldown, `quiet_month` templates fill the remaining slots, drawn the same way (weight × the `quiet_month` strength, same cooldowns), at **minor** severity only; never when `quiet_month` holds anyway.
- **M6.9 tuning** (to meet §16.10 at about 1.2 events a month): count weights [0.08, 0.40, 0.38, 0.14] (mean 1.58; was [0.15, 0.50, 0.28, 0.07]), template cooldown 12 months (was 24), person cooldown 4 (was 6); triggers `underpaid` below 0.95 (was 0.9), `star_performer` top 30% (was 10%), `team_clash` at −25 or below (was −50), `team_bond` at 30 or above (was 60), `board_unhappy` below 50 (was 40); minor `morale_delta` cap 3 (was 5). The values in §16.1–§16.3 below are the original design; `balance.yaml` holds the tuned ones. `low_morale` stays at 35 so the §16.11 director example holds.

### 16.2 Triggers (computed by the engine from state; true values allowed here, never passed on)

| Trigger | Holds when | Strength |
| --- | --- | --- |
| `low_morale` (person) | an employee's morale < 35 | (35 − morale) / 20 |
| `unhappy_unit` | a unit's average morale < 45 | (45 − avg) / 15 |
| `underpaid` (person) | salary < 0.9 × market rate | (0.9 − ratio) / 0.2 |
| `star_performer` (person) | an employee in the top 10% of CA with tenure ≥ 12 months | 0.4 |
| `team_clash` (pair) | two people in the same unit with relationship ≤ −50 | (−50 − rel) / 30 |
| `team_bond` (pair) | relationship ≥ 60 | 0.3 |
| `office_politics` (person) | a `politician` (true tag) in a unit of 4 or more | 0.6 |
| `tag_noticed` (person) | a tag was revealed this month | 0.5 |
| `anniversary` (person) | tenure reaches a whole number of years | 0.2 |
| `product_launched` | a product launched this month | 0.5 |
| `product_slipping` | a product is rotting (§11.4) | 0.6 |
| `price_war` | a rival cut a price in a segment the player sells to | 0.6 |
| `rival_move` | any rival action in the player's segments | 0.3 |
| `poached` | a rival hired one of the player's people this month | 0.8 |
| `customer_milestone` | first enterprise customer, or customers pass a power of ten | 0.4 |
| `runway_short` | runway < 6 months (strength 0.6) or < 3 months (1.0, critical allowed) | as stated |
| `funding_closed` | a round closed this month | 0.5 |
| `board_unhappy` | average board confidence < 40 | (40 − B) / 15 |
| `early_days` (M7a) | the player has no live product (names a product in development, if any) | 0.4 |
| `quiet_month` | none of the above | 0.2 |

### 16.3 Effects (the catalog; caps by severity)

Every choice carries 0 to 3 effects, every event 2 or 3 choices. Effects apply immediately when the player chooses (an immediate action, ADR-0014, energy 0); an unanswered minor or major event resolves to its first choice at Continue; a critical event must be answered first.

| Effect | Target | Minor / major / critical cap |
| --- | --- | --- |
| `morale_delta` | person, unit or company | ±5 / ±10 / ±20 |
| `relationship_delta` | pair | ±10 / ±20 / ±40 |
| `cash_delta` | company | cost up to 100 / 300 / 1,000 bp of max(cash, 3 × monthly revenue); gains up to half that |
| `brand_delta` | product | ±2 / ±5 / ±10 |
| `quality_delta` | product | ±1 / ±3 / ±6 |
| `customers_pct` | product and segment | ±1% / ±3% / ±8% of its customers |
| `growth_boost` | person and skill | +0.2 / +0.5 / +1.0 skill points, once |
| `reveal_tag` | person | reveals one of their hidden tags (the engine chooses which; nothing if none) |
| `energy_delta` | founder, next month | ±5 / ±10 / ±15 |
| `board_confidence` | every director | ±3 / ±6 / ±12 |
| `salary_change` | person | 0% to +5% / +10% / +15% (a raise demand) |
| `resign` | person | major and critical only, and only if the template allows it |
| `follow_up` | — | critical only: queue the template's named follow-up next month |

Targets must come from the event's eligible list (the trigger's people, unit, product or pair). The validator drops unknown effects, clamps values to the caps, and rejects a draft with no valid choice.

### 16.4 Templates (data: `events/*.yaml`)

About 60 templates: personnel 20, market 12, operations 10, finance 8, board and investors 6, rivals 4. (M7a adds 22: founder 14 for `early_days`, personnel 4, market 2, operations 2; 82 in all.) Each has: id, category, trigger, allowed severities, weight, eligible-target rules, title and body with placeholders (`{person}`, `{product}`, `{rival}`, `{amount}`), 2 or 3 choices with labels and fixed effects within the caps, an optional `storyline` step, and for critical ones a `follow_up`. Templates are the offline mode and the fallback, so every trigger must have at least one minor template and every critical trigger at least one critical template.

### 16.5 LLM requests (outside the sim, after the turn commits)

Phase 12 emits `EventRequest`s (ADR-0012). After the turn's transaction commits, the event service turns each request into a stored event: with the LLM adapter if the budget allows, else the template. Events are shown when the player opens the new month; they are persisted, so replay never calls the LLM.

- **Context** (allowlist only): company KPIs (cash, runway, MRR, headcount, stage), the eligible people with name, role, level, tenure, morale, displayed skill ranges as words ("strong at sales"), noticed tags and revealed interests; eligible products' public scores; involved rivals' public data; the last 10 event summaries; active storyline summaries; the template's situation facts (computed by the engine, for example "Priya's morale is 31; she is paid 0.86 of market"); the allowed effects with their caps and targets; the severity; and the tone (grounded realism, a light or satirical touch with 10% chance; ADR-0011).
- **Output:** the spec §12 JSON (title, body ≤ 180 words, 2–3 choices with labels and effects). One retry on rejection, then the template.
- **Models:** `llm.model_events` (small model) for events, headlines and minutes; `llm.model_story` (larger model) for storyline steps. Both are settings.
- **Budget:** ADR-0005 §6, $10 a calendar month by default.
- **Never in a prompt:** true attributes, potential, hidden tags, other companies' hidden values, or any number the API would not show the player. A test builds a prompt from a state with planted hidden values and asserts none appear.

### 16.6 Storylines

A template step may open or advance a storyline: `{key, step, next_after_turns, next_template}`. At most 3 storylines are active; each carries a short summary (≤ 60 words, written by the LLM or the template) passed to later requests. v1 ships 5 template storylines of 2 to 4 steps: a co-founder-style tension between the founder and a senior lead, a rival poaching war, a key customer that wants special treatment, a burnout arc for a star performer, and an investor who wants a say. A storyline ends at its last step or when its people leave.

### 16.7 Relationships (phase 8)

- Pairs are tracked between members of the same unit and between each manager and their reports. A new pair starts at `round(15 − 1.5 × |temperament_a − temperament_b|)`, clamped to [−20, 15], using true values (the number shown is a label, §16.9).
- Each month a relationship drifts 10% of the way back toward its starting value. Behaviour tags move it before the drift: a `credit_taker` −3 a month with each unit-mate, a `toxic_high_performer` −4, a `culture_carrier` +2, a `politician` −3 with each unit-mate whose ambition is 14 or more. Events add `relationship_delta`.
- **Morale term (adds to §9):** `W_rel = clamp(0.1 × mean relationship with unit-mates, −5, +5)`. It replaces the part of the §13.6 teammate-tag term that the tag drift now covers: from M6 the `credit_taker` and `toxic_high_performer` morale terms are removed (their effect comes through relationships); `culture_carrier`'s stays.
- Relationships are shown as labels: "close" (≥ 60), "good" (20–59), "neutral" (−19–19), "strained" (−49 to −20), "hostile" (≤ −50).

### 16.8 Other LLM text (read-only)

Monthly headlines (two or three lines added to Market news), quarterly board meeting minutes (a short paragraph in the board summary), and one exit-interview line when someone resigns. Each has a template fallback and counts toward the budget. "Ask my COO" waits for M7.

### 16.9 What the API may show

Events with their choices and, for each choice, its effects as words with a size ("small morale lift for Priya", "costs about $8,000"), never the caps or the trigger strengths. **Replaced in M10b by §23.2:** effects show as plain numbers ("Priya's morale +5", "costs $8,000", "+5% brand target for Pipeline for 12 months"); caps and trigger strengths stay hidden. Relationship labels, never numbers. Storyline titles and summaries. The LLM meter: spend this month against the budget, and the adapter in use.

### 16.10 Balance targets (M6 acceptance, printed, with `MockLLMAdapter` choosing the first choice)

Over 120 turns on 10 seeds of the M3a earn-and-burn script: 1.0 to 1.6 events a month on average; at most one critical event in any 6 months; events' combined cash effect within ±5% of cumulative revenue; events' combined effect on average employee morale within ±3 points; at least 40 distinct templates used across the 10 runs; and the M5 balance targets still hold.

### 16.11 Worked examples

**Director draw.** A month with `low_morale` for Priya (morale 31, strength 0.20), `price_war` (0.6) and `rival_move` (0.3), and the personnel category used last month: weights for a weight-1 template each are 0.20 × 0.5 = 0.10, 0.60 and 0.30.

**Validator clamp.** A major draft offers `morale_delta` +15 for Priya and `cash_delta` −$40,000 with cash $500,000 and monthly revenue $100,000: the morale effect is clamped to +10 and the cost to 300 bp of $500,000 = $15,000.

**Relationship start and drift.** Temperaments 14 and 6: start = 15 − 12 = 3 ("neutral"). With a credit-taker in the unit the pair loses 3 a month and then drifts 10% of the way back to 3: 0.3 after the first month, −2.13 after the second, settling at **−24** ("strained"), where the drift back exactly offsets the push.

## 17. Holiday, history and the COO (M7b)

None of this changes the simulation: Holiday runs ordinary turns, History reads what is already stored, and the COO only reads. Nothing here may show a hidden value (ADR-0007).

### 17.1 Holiday (auto-advance)

- **Starting.** The player chooses how many months (1 to `holiday.max_months`, 24; default `holiday.default_months`, 6) and a stop severity (minor, major or critical; default `holiday.default_stop`, major). Holiday cannot start while a critical event is open or the game is over.
- **Each month** is exactly one Continue: its own transaction (ADR-0004), its events written after the commit (ADR-0005), and the next month only after that. Open minor and major events below the stop severity resolve to their first choice at the next Continue, as they do now (§16.3). Delegates act in phase 2 as usual (ADR-0015); the founder takes no actions and their energy is unused.
- **It stops after the month in which** (checked in this order, the first one names the reason):
  1. the game is over (ADR-0018);
  2. an event at or above the stop severity was queued (a critical event always stops);
  3. runway fell below `holiday.stop_runway_months` (6) for the first time in this holiday, or is below 3 months;
  4. a term sheet, a SAFE offer or a bridge offer arrived;
  5. the chosen number of months has passed;
  6. the player pressed Stop (the month in progress finishes; nothing is rolled back).
- **Afterwards** one inbox item, kind `holiday_summary`, "While you were away": months played, start and end values of cash, ARR, headcount and average morale, the events resolved for the player with the choice taken, hires and departures, launches, rounds, and the stop reason.
- Determinism: a holiday of N months gives the same save as N presses of Continue with no actions in between.

### 17.2 History

- **Timeline.** One entry per thing that happened to the player's company, newest first, from stored rows only: events (title, the choice taken and by whom: player, or "default" when it resolved at Continue), the decision log (player and delegate actions, with the delegate's name), and inbox items of kinds hire, departure, launch, round, board, rival news and month-end. Search is a case-insensitive match on title, body and names; filters: year, category (people, products, finance, rivals, events), source (player, delegate, default), person, product.
- **Month lines.** Each month gets one summary line from `turn_snapshot`: "Mar 2012 · ARR $1.2M (+8%) · cash $640k · 14 staff (+1) · morale 62".
- **Charts.** Every `turn_snapshot` KPI over the whole game, plus each product's MRR and customers from its product months; ranges 1 year, 3 years, all.
- **Storylines.** Each storyline (active and ended) with its steps on a time line: month, step title, the choice taken.
- **Hall of fame** (computed from history when the screen opens; values only as the player could see them):

| Record | Definition |
| --- | --- |
| Peak ARR | highest `arr_cents` and its month |
| Peak headcount | highest `headcount` and its month |
| Biggest round | largest closed round by amount: stage, amount, lead firm, month |
| Firsts | first launch, first paying customer, first enterprise customer, first $1M ARR, first round closed, each with its month |
| Longest serving | top 5 people by tenure, current and former |
| Best hires | top 5 by the rise in shown rating (the midpoint of the displayed range) from hire to now, or to their last month |
| Notable departures | top 5 former staff by shown rating at departure, with the reason (resigned, poached by a named rival, fired, retired) |
| Best product | highest peak MRR, and highest quality score shown |
| Rivals outlasted | rival startups that went out of business while the player sold in one of their segments |

A person's **shown rating** (M7b decision) is the mean midpoint of the displayed ranges of their role's primary skills, as the player sees them; it is logged for every player employee at each month end (`person_rating_log`), so "from hire" is their first logged month.

### 17.3 Ask my COO

- **Who answers.** The highest-level active employee whose role is `operations_manager`; if none, the highest-level non-founder employee (ties: longest tenure); with no staff, "Founder's notebook" (the founder thinking aloud).
- **Briefing** (engine-computed, always available, no LLM): up to 5 issues, most urgent first, each a sentence and a link: runway under 12 months; an open critical or major event; a rotting product (§11.4); a person whose shown morale is under 40; a unit over its span limit; a role open more than 3 months; average board confidence under 50; a rival price cut in one of the player's segments this month. "Nothing urgent" when none apply.
- **Questions.** Free text up to `coo.max_question_chars` (300). Context: the briefing, the §16.5 allowlist context, and the last 12 months of the player's `turn_snapshot` KPIs. Answer up to `coo.max_answer_words` (200), plain prose, written as the named person; the prompt tells the model to use only the numbers given and to say when it doesn't know. Model `llm.model_story`; counts toward the monthly budget (ADR-0005 §6); logged in `llm_call_log`.
- **Offline, over budget or after an error:** the reply is "I can't think that through right now" plus the briefing.
- **Stored:** the last `coo.keep_answers` (20) questions and answers per save, read-only, never fed into events.
- **Never** changes state or costs energy. The hidden-value prompt test (§16.5) covers COO prompts too.
- **Keys** (M7b): `coo.max_issues` (5), `coo.runway_months` (12), `coo.morale_below` (40), `coo.role_open_months` (3) and `coo.board_below` (50) hold the briefing's thresholds above.

## 18. Divisions, executives and new markets (M8)

First v2 milestone (ADR-0019). Everything in §18.1–§18.5 takes effect only from **stage 3** (ARR ≥ $20M or a Series B, §11.11, §14.8), except the layer tax (§18.2), which can't apply before stage 3 because v1 trees are at most two levels deep. So v1's early game and its balance targets are unchanged. The new markets (§18.6) are open from January 2010.

### 18.1 Divisions

- **New unit type `division`** (stage 3): its parent is the company root. At most `org.max_divisions` (6). Departments and teams can be moved under a division with the existing move action (§13.7), and it costs the usual morale.
- **President:** the division's leader. They must be a member of the division at senior level or above, and can't hold an executive seat (§18.3). The president is the manager of everyone in the division who has no nearer leader (§13.1).
- **Products belong to a division** (`product.division_id`; null means corporate). Setting it is an immediate action (energy 1) and changes no rule except the reporting below and the cross-division factor in §18.2.
- **Division P&L** (reporting, derived from the ledger). Every ledger line gains a nullable `division_id`:
  - a product's revenue, hosting and marketing go to its division;
  - an employee's salary, benefits, office, tools and recruiting fee go to the division containing their unit;
  - everything else, including the founder, investor flows and event effects, is corporate.

  A division's statement is its revenue minus its direct costs, then a **shared-services allocation**: this month's corporate operating costs × `h_div / (h_corporate + Σ h_central divisions)`, so only divisions using central services (§18.4) take a share and corporate keeps its own. The allocation is a reporting line, not a ledger entry: no cash moves between divisions. Interest (lenders' fees included) and tax sit below operating profit (§14.1, §20.3): they are in no division's operating columns and in no allocation, so the statements' company operating profit equals the P&L's (M10r).

### 18.2 Coordination cost

- **Layer tax.** Depth counts from the root: root 0, division 1, department 2, team 3, a team under a team 4. Each person's builder output (§11.3) and seller capacity are multiplied by

```latex
\lambda = \max\big(0.85,\; 1 - \tau \cdot \max(0,\, depth - 2) \cdot k_{COO}\big)
```

  with `τ = org.layer_tax` (0.03) and `k_COO` from §18.3 (1 when the seat isn't in play).
- **Cross-division products.** If a product's assigned units sit in more than one division (counting corporate as one), its output is multiplied by `org.cross_division_factor` (0.90).

### 18.3 Executive seats (stage 3)

- **Seats:** COO, CFO, CTO, CPO, CMO and CRO. The founder remains CEO until M13.
- **Appoint** (immediate action, energy 5): any employee except the founder, at senior level or above, holding no other seat and not a president. They become **exec** level at a **new salary**, applied at once: by default the exec market rate for their role and region, never below their current pay; the player may set another, never lower than current pay (product manager, 2026-10-31, M8r). Appointment gives +5 morale once, and the §13.8 raise rules apply to the new salary (a raise of at least 5% gives its +3 once, alongside the +5). Without the raise, rivals' offers at the exec market rate took appointees within months once a poached holder left the seat (Codex review 1, finding 3).
- **Remove** (energy 5): −10 morale once. Their level stays exec.
- **Seat score** `s`, from true skills with these weights (data: `exec_seats` in `balance.yaml`):

| Seat | Skill weights |
| --- | --- |
| COO | operations 0.35, leadership 0.25, strategy 0.20, communication 0.20 |
| CFO | finance 0.45, strategy 0.20, negotiation 0.20, communication 0.15 |
| CTO | software engineering 0.25, infrastructure 0.15, ML research 0.10, leadership 0.25, strategy 0.25 |
| CPO | product 0.45, design 0.15, strategy 0.20, leadership 0.20 |
| CMO | marketing 0.45, communication 0.20, strategy 0.20, leadership 0.15 |
| CRO | sales 0.40, negotiation 0.25, leadership 0.20, communication 0.15 |

- **Effect strength:** `e = clamp((s − 10) / 8, −0.5, 1)`. A **vacant seat at stage 3 or later counts as `e = −0.5`**. Before stage 3, `e = 0` for every seat.

| Seat | Effect (company-wide) |
| --- | --- |
| CTO | builder output × (1 + 0.10 e) and `Q_cap` (§11.4) × (1 + 0.10 e) |
| CPO | feature points gained × (1 + 0.15 e) and base churn (§11.6) × (1 − 0.15 e) |
| CMO | marketing points `mk` (§11.5) × (1 + 0.20 e), brand target `B*` × (1 + 0.10 e) (at most 100) and awareness (§11.7) × (1 + 0.20 e) |
| CRO | seller capacity × (1 + 0.20 e), and `p_ref` in `price_score` (§11.6) × (1 + 0.10 e) in sales-led segments (pricing power) |
| CFO | investors' `V_base` (§14.3) × (1 + 0.08 e); each director's monthly confidence + 0.5 e |
| COO | `k_COO = 1 − 0.5 e`, applied to the layer tax (§18.2) and the support shortfall (§18.4) |

**Redesign (Reece, 2026-10-31).** The first version (output, features, marketing points and capacity only) barely moved ARR at a plateau: quality sits at `Q_cap`, features at 100 and brand near 91, so target 2 measured 0.995. Each seat's second effect reaches what limits a mature product. `e`, the vacancy rule and the API rules are unchanged.

- The coefficients are `exec_seats.seats.<seat>` keys in `balance.yaml`: `effect` for the first effect, then `qcap`, `churn`, `brand`, `awareness` and `pricing`.
- **Exec hiring:** from stage 3, searches may target exec level (job post, recruiter or network). Candidates are generated at exec level and ask the exec market rate.

### 18.4 Support staff and shared services (stage 3)

- **Support staff** are employees whose role's product function is `none` (finance manager, recruiter, operations manager), seat holders included.
- **Coverage** for a pool of `h` people with `n` support staff:

```latex
c = \min\left(1,\; \frac{n}{h / \rho}\right)
```

  with `ρ = org.support_ratio` (15).
- **Shortfall.** For everyone in a pool with `c < 1`, builder output, seller capacity and marketing points are multiplied by `1 − 0.15 (1 − c) k_COO`. A morale term `W_support = −6 (1 − c)` joins §9; it shows in the morale breakdown as "Admin and support".
- **Churn and delegates (2026-10-31).** The base churn of the pool's products (a product's pool is its division's if embedded, else central) is × `1 + 0.4 (1 − c) k_COO` (`org.support_churn`), and each delegate's monthly energy is × `c` of their pool, rounded down.
- **Shared services** per division: `central` (default) or `embedded` (immediate action, energy 2).
  - **Central pool:** corporate and every central division share one pool, which uses the central support staff.
  - **Embedded division:** its own pool, covered only by its own support staff. Its builder output and seller capacity get × `org.embedded_bonus` (1.05), for faster decisions.
  - Embedded divisions take no shared-services allocation (§18.1).
- **Before stage 3,** `c = 1` and there is no morale term.

### 18.5 Order of effects

In phase 3, builder output `o` (§11.3) = Σ person output × `λ` × support factor × embedded bonus × CTO, then × `coord(n)` × cross-division factor × `ε`; `Q_cap` × CTO. Features gain `o` × CPO. In phase 5, base churn × CPO × support churn, awareness × CMO, and `p_ref` × CRO in sales-led segments. Seller capacity (phase 5) = §11.3 capacity × the same `λ`, support and embedded factors × CRO. Marketing points (phase 9) × support factor × CMO, and `B*` × CMO (at most 100).

### 18.6 New markets (data: `categories.yaml`, appended)

**Fintech** (`fintech`): growth 25%, F₀ 60, ΔF 4.0, σ 6, K 80; launch also needs quality ≥ 30 (`launch_quality`, compliance). Development skill: software engineering 0.30, security 0.20, finance 0.20, legal 0.15, data 0.15.

| Segment | D₀ | p_ref / month | h / month |
| --- | --- | --- | --- |
| Consumer | 20,000,000 | $0.60 (revenue per user) | $0.05 |
| SMB | 300,000 | $60 | $5 |
| Mid-market | 25,000 | $1,200 | $80 |
| Enterprise | 2,500 | $15,000 | $900 |

**AI models and inference** (`ai_models`): F₀ 30, ΔF 6.0, σ 8, K 70. Development skill: ML research 0.40, software engineering 0.20, data 0.20, infrastructure 0.20.
- **Growth by year** (`growth_by_year`) instead of a constant `g`: 30% a year for 2010–2015, 60% for 2016–2019, 40% for 2020–2021, 150% in 2022, 200% in 2023, 120% in 2024, 60% for 2025–2029, then 25%.
- **Hosting** is `h × compute_index(year)` from `compute_index.yaml`: 1.0 in 2010, falling 15% a year to 2016, ×1.1 a year in 2017–2018, flat in 2019–2021, ×1.6 in 2023 and ×1.3 in 2024 (the GPU shortage), then falling 15% a year. Only AI uses the index in M8.

| Segment | D₀ | p_ref / month | h / month (× index) |
| --- | --- | --- | --- |
| Consumer | 200,000 | $0.50 | $0.20 |
| SMB | 20,000 | $100 | $40 |
| Mid-market | 2,000 | $2,000 | $600 |
| Enterprise | 300 | $25,000 | $6,000 |

**Incumbents** (appended to `incumbents.yaml`; starting shares by the M3a steady-state method, recorded in the brief):

| Company | Personality | Builder skill | Product (category: segments) | Quality / features / brand |
| --- | --- | --- | --- | --- |
| PayPal | fast_follower | 12 | PayPal (fintech: consumer, SMB) | 62 / 70 / 85 |
| Intuit | premium | 13 | QuickBooks Online (fintech: SMB, mid-market) | 68 / 75 / 75 |
| Fiserv | cost_leader | 11 | Fiserv Banking (fintech: mid-market, enterprise) | 58 / 72 / 60 |
| IBM | premium | 13 | Watson (AI: mid-market, enterprise) | 45 / 40 / 70 |
| Nuance | fast_follower | 12 | Dragon (AI: consumer, SMB) | 50 / 45 / 55 |

Their function mixes (builders / sellers / marketers): fintech 50 / 30 / 20, AI 75 / 10 / 15.

### 18.7 Scheduled entrants (data: `entrants.yaml`; phase 9, stream `entrants` id 20, key `(entrant_index,)`)

Named rival startups founded in their real month. Each is a §15.4 startup with a fixed name, personality, cash, staff count and product (category and segments). Its people are generated at senior level from the stream, so each entrant starts strong. Entrants don't count toward the cap of 8 startups and fund and fail by §15.4. Founding needs no draw, so every seed sees each entrant.

| Entrant | Founded | Personality | Cash | Staff | Product |
| --- | --- | --- | --- | --- | --- |
| Square | Mar 2010 | aggressive | $10M | 8 | fintech: SMB |
| Stripe | Sep 2011 | aggressive | $2M | 6 | fintech: SMB, mid-market |
| Plaid | May 2013 | fast_follower | $3M | 6 | fintech: mid-market, enterprise |
| OpenAI | Dec 2015 | aggressive | $50M | 12 | AI: consumer, SMB, enterprise |
| Anthropic | Jan 2021 | premium | $120M | 12 | AI: SMB, mid-market, enterprise |

### 18.8 What the API may show

- Division statements and allocations.
- Coverage as counts (support staff against need) and the shortfall's effect.
- The layer tax and cross-division factor in a product's output breakdown.
- **Seats:** the holder, and their fit as words from the company's displayed ranges ("strong fit for CTO"), with an **estimated** effect computed from the displayed midpoints and labelled as an estimate. Never `s` or `e` from true values.
- Vacant seats at stage 3 show their penalty.
- Entrants appear like any rival.

### 18.9 Balance targets (M8 acceptance, printed)

1. All v1 targets still pass: `make balance` T1–T3, E1–E3 and the M5/M6 guards.
2. **Seats matter.** From each seed's steady save at stage 3, play 36 more months with six seat holders of score ≥ 14 and again with all seats vacant. The median ARR at the end is at least 15% higher with the seats filled (10 seeds).
3. **Support matters.** From the same saves, coverage 1.0 against 0.5: the median ARR is at least 8% higher at full coverage.
4. **New markets earn.** The M3a earn-and-burn script in fintech reaches 50–150% of the B2B SaaS run's ARR at turn 36. AI's total addressable demand in January 2024 is 100–400 times January 2010's.
5. **The ceiling lifts.** blitzscale with its second product in fintech: median turn-120 ARR at least 1.2 times the standard blitzscale, over seeds where both runs still have their founder.

**Scripts (2026-10-31).** The strategies staff their second product (the M7a check compared a hire's start turn with the current turn; offers resolve a turn later) and, from stage 3, appoint the best senior-or-above employee by displayed fit to each vacant seat, or run an exec-level network search for the seat's role if nobody fits (`tst/balance/strategies.py`). Target 2's and 3's arms turn those appointments off and set the seats themselves.
6. Every entrant is founded in its month on every seed.

### 18.10 Worked examples

**Seat effect.** A CTO with `s = 14` has `e = 0.5`, so builder output × 1.05. The seat vacant at stage 3 gives × 0.95.

**Support shortfall.** 120 staff with 5 support staff: need 8, `c = 0.625`. Output × (1 − 0.15 × 0.375) = × 0.944, and morale −2.25. With a COO at `e = 0.5`, `k_COO = 0.75`, so output × 0.958.

**Layer tax.** A team under a department under a division is at depth 3: `λ = 1 − 0.03 × 1 = 0.97`. With the COO above, 0.9775.

**Redesigned seats (2026-10-31).** A holder at `s = 14` (`e = 0.5`): CTO `Q_cap` 50 → 52.5; CPO base churn 3% → 2.775%; CMO `B*` 80 → 84 (98 → 100, capped) and awareness × 1.10; CRO mid-market `p_ref` $800 → $840. Vacant at stage 3: CPO churn × 1.075, CRO `p_ref` × 0.95.

**Support churn and delegates.** 120 staff with 5 support staff (`c = 0.625`): the pool's churn × (1 + 0.4 × 0.375) = × 1.15; with the COO at `e = 0.5`, × 1.1125. A delegate's 100 energy becomes 62.

**Allocation.** Corporate 12 staff with $520,000 of operating costs this month; the Platform division (128, central) and the Fintech division (46, embedded). Platform's allocation = $520,000 × 128 / (12 + 128) = **$475,429**; Fintech's is $0; corporate keeps $44,571.

## 19. Cities, offices and regions (M9, lane A)

Reece's decisions (2026-10-31): about 15 named tech hubs; a product **launches per region**; v1's market is the home region, so other regions add demand on top and v1's early game is unchanged. Merge order: M10 merges first, then M9 (`docs/v2-roadmap.md` lane rules).

### 19.1 Cities (data: `cities.yaml`)

Each city has: key, name, region (`regions.yaml`), a salary multiplier (replacing the region's for people working there), a rent index (San Francisco = 1.0), and a talent bonus per skill group (added to the mean of generated candidates' role skills, in attribute points).

| City | Region | Salary × | Rent index | Talent bonus |
| --- | --- | --- | --- | --- |
| San Francisco | North America | 1.00 | 1.00 | technical +1.0, business +0.5 |
| Seattle | North America | 0.95 | 0.80 | technical +0.8 |
| New York | North America | 1.00 | 0.95 | business +1.0 |
| Austin | North America | 0.85 | 0.55 | — |
| Toronto | North America | 0.75 | 0.55 | technical +0.3 |
| London | Europe | 0.85 | 0.85 | business +0.8 |
| Berlin | Europe | 0.65 | 0.45 | technical +0.3 |
| Dublin | Europe | 0.75 | 0.55 | business +0.3 |
| Tel Aviv | Europe | 0.75 | 0.55 | technical +0.8 (security +1.5) |
| Bangalore | South and Southeast Asia | 0.30 | 0.15 | technical +0.3 |
| Singapore | South and Southeast Asia | 0.75 | 0.75 | business +0.3 |
| Shenzhen | East Asia | 0.40 | 0.30 | hardware design +1.5, manufacturing +1.5 |
| Tokyo | East Asia | 0.75 | 0.70 | hardware design +0.8 |
| São Paulo | Latin America | 0.40 | 0.30 | — |
| Sydney | Oceania | 0.85 | 0.70 | — |

- **HQ.** A new game picks an HQ city (default San Francisco). Existing saves get San Francisco by migration.
- **Market rates.** Everyone's market rate (§2) uses the salary multiplier of the city they work in: their office's city, or their home city when remote. A person generated in v1 gets the first city of their region as their home city (migration).
- **Pay level** `geo.pay_level` (0.876; Reece, 2026-11-01): every city's salary multiplier is x this for asks and for every company's market rates, so city ratios are unchanged. It is the calibration that makes a San Francisco-HQ company's average pay equal v1's regional mix (`people.region_weights` x the regions' multipliers = 0.876), where 45% of candidates came from cheaper regions.
- **Talent bonus.** Groups are `skills.yaml` groups. The values above are starting points for tuning.

### 19.2 Offices

- **Flexible HQ** (every company, as now): an office-policy employee working in the HQ city costs `$600 × rent index` a month (§8). That is unchanged for a San Francisco HQ.
- **Lease an office** (immediate action, energy 10): a city and a size of 25, 50, 100 or 250 seats.
  - **Rent:** `seats × $600 × rent index × office.lease_discount` (0.75) a month, full or not, to `6100_rent`.
  - **Fit-out:** 3 months' rent, once.
  - **Closing** (energy 10): 3 months' rent as a penalty. Everyone in it moves to flexible space in that city, or becomes remote if the city isn't the HQ.
- **Where people work.** An office-policy unit (§13.9) has a home office (`unit.office_id`; null means flexible space in the HQ city). Its members work there. If an office's members exceed its seats, everyone in it gets −4 morale ("Crowded office"), and new hires still join.
- Remote-policy members work from their home city.

### 19.3 Hiring by city

- A search has a city (default: the hiring unit's office city). Its candidates live in that city (85%) or are willing relocators from other cities (15%, drawn by city talent weight). Their role skills get the city's talent bonus.
- Searches for a remote unit may choose **anywhere**: every candidate's city is drawn by talent weight.
- Relocating a candidate to the search's city adds `hiring.relocation_cents` ($15,000) to the hire's cost (`6200_recruiting`).
- Randomness stays in `people_gen` (the city draw is part of generating the candidate).

### 19.4 Working across regions

A product whose builders work in more than one **region** loses output: × `max(0.85, 1 − 0.05 × (regions − 1))` (time zones). This multiplies with M8's coordination factors (§18.5).

### 19.5 Regional markets

- **Home region:** the HQ city's region. Its markets are exactly v1's (§11.1, §18.6), with the same `D₀`, prices and incumbents. Its RNG key stays `(category_index, segment_index)`, so v1 runs replay unchanged.
- **Other regions** add markets with `D₀ = home D₀ × region size` and `p_ref × region price index`. Their RNG key is `(category_index, segment_index, region_index)`.

| Region | Size (× North America's D₀) | Price index | Neighbour (for sales) |
| --- | --- | --- | --- |
| North America | 1.00 | 1.00 | Latin America |
| Europe | 0.80 (0.55 from M10d) | 0.90 | Africa |
| East Asia | 0.70 (0.45 from M10d) | 0.80 | South and Southeast Asia |
| South and Southeast Asia | 0.40 | 0.35 | East Asia |
| Latin America | 0.25 | 0.50 | North America |
| Africa | 0.06 | 0.35 | Europe |
| Oceania | 0.10 | 0.95 | South and Southeast Asia |

**M10d balance pass (product manager, 2026-11-02):** Europe and East Asia shrink to 0.55 and 0.45 of North America's `D₀`, so blitzscale with expansion reaches 2.2× home-only blitzscale (19.8 target 2, band 1.4–2.5×); with rivals entering regions more readily (`geo.region_entry.unserved` 0.6, `cooldown_turns` 6) and slower, dearer localization (6 months, $80,000), at 0.80 and 0.70 it was 2.65×.

  When the HQ isn't in North America, sizes are taken relative to the home region's row. A region's growth is the category's growth × its `growth_mult` in `cities.yaml`: 1.0 for North America and Europe, 1.3 for East Asia, 1.6 for South and Southeast Asia, 1.2 for Latin America, 1.8 for Africa, 1.0 for Oceania.
- **Launching in a region** (immediate action, energy 4): the product must already be live at home. Localization costs `$40,000 × σ / 6` once (`6500_research_development`) and takes `markets.localize_months` (3). During those months the product's feature points grow 10% slower. It then sells there at the prices the player sets (default `p_ref × price index`).
- **Reach in a region.**
  - *Self-serve segments:* awareness × `markets.foreign_awareness` (0.6) until the company has an office or at least 5 people working in that region; then × 1.
  - *Sales-led segments:* capacity comes only from sellers working in that region, plus 50% of those in its neighbour.
- **Incumbents by region** (data: each incumbent product lists its regions and starting share per region; the M3a steady-state method again). v1 incumbents are present in North America and Europe unless their data says otherwise. New regional incumbents:

| Company | Personality | Builder skill | Product (category: segments; region) |
| --- | --- | --- | --- |
| SAP | premium | 13 | SAP Business ByDesign (B2B SaaS: mid-market, enterprise; Europe) |
| Kaspersky | cost_leader | 13 | Kaspersky (cybersecurity: SMB, mid-market; Europe) |
| Tencent | aggressive | 13 | QQ (consumer apps: consumer; East Asia) |
| Alibaba | aggressive | 12 | Alipay (fintech: consumer, SMB; East Asia) |
| Baidu | fast_follower | 12 | Baidu Brain (AI: SMB, enterprise; East Asia) |
| Infosys | cost_leader | 11 | Finacle (fintech: enterprise; South and Southeast Asia) |

### 19.6 Rivals and regions

- **Region entry.** Rival incumbents gain `enter_region`, with need `(unserved share − 0.4) / 0.4` in a region where the product's category has demand, and cash ≥ 12 months of costs; weights as `enter_segment` (§15.3).
- **Startups.** A rival startup is founded in a region drawn by that category's regional demand (stream `rival_region`, id 22, key `(startup_id,)`) and sells there first.
- **Entrants** (§18.7) start in North America.

### 19.7 What the API may show

Cities with their salary and rent indexes and talent bonuses. Offices with seats, members and cost per head. Each product's regions with status (localizing until a month, or live), prices, customers and revenue by region. The cross-region factor in the product's output breakdown. Regional market views (M3b's market view, with a region picker). Candidates' city and whether they'd relocate.

### 19.8 Balance targets (M9 acceptance, printed)

1. All v1 targets and the M8 targets still pass when the player never leaves the home region.
2. **Expansion lifts the ceiling.** blitzscale that launches in Europe at Series A and in East Asia at stage 3 reaches a median turn-120 ARR of at least 1.4 times the home-only blitzscale.
3. **Cheap talent has a cost.** A 30-builder team in Bangalore costs at least 50% less a month than the same team in San Francisco. A product split between them shows the cross-region factor.
4. **Cities differ.** Over 200 seeded software-engineer searches, San Francisco candidates' mean role-skill score is 0.8–1.2 points above Austin's.
5. **Rivals spread.** At turn 120 (do-nothing runs), every region with demand has at least one live rival product in each category.

### 19.9 Worked examples

**Lease.** 50 seats in Berlin: `50 × $600 × 0.45 × 0.75` = **$10,125** a month, plus a fit-out of $30,375.

**Market rate.** A senior software engineer (band mid $115,000) working in Bangalore: `$115,000 × 0.30 × 0.876` (pay level) = **$30,222** a year.

**Regional market.** B2B SaaS SMB in Europe: `D₀ = 400,000 × 0.55` = 220,000 (0.80 before M10d), and `p_ref = $50 × 0.90` = $45.

**Localization.** A cybersecurity product (σ = 7): `$80,000 × 7 / 6` = **$93,333**, live in the region six months later (M10d balance pass: $40,000 and three months before).

### 19.10 Notes from the build (M9)

Decisions the table above did not settle, recorded in the M9 brief's "Decisions made":

- **Cities.** `cities.yaml` adds a `talent_weight` per city (roughly the hub's tech workforce) for relocators' and "anywhere" candidates' cities. Africa has no hub: its people's home city is London (its sales neighbour's first city), `home_city_region`.
- **Where people work and live.** An office-policy unit's office is its own `office_id`, else its parent's, up to flexible space in the HQ city; the company root always works in flexible HQ space. Everyone working at an office lives in its city (moving a unit moves its people); remote staff work from their home city. Rivals have no offices: their people work from home.
- **Pay.** Market rates (morale, the underpaid trigger, exec pay on appointment, rivals' poaching offers) use the work city's multiplier x `geo.pay_level`. A candidate's ask uses the city they would work in: the search's city, or their own for "anywhere". Without the pay level, v1's ~12% discount from candidates in cheaper regions would be gone and hiring would cost 12-20% more (the first M9 guard run: the ten-year acceptance run went bankrupt at month 27).
- **Talent bonus.** Added to each role skill (primary and secondary) after the CA target is set, by skill, else by skill group; it raises CA and so the ask. The "role-skill score" of 19.8 target 4 is CA / 10 (primaries weigh 3, secondaries 1). All of a search's candidates get the search city's bonus (an "anywhere" candidate gets their own city's).
- **City draw.** One uniform u from the person's `people_gen` generator replaces v1's region draw: the search city below `geo.local_candidates`, else a relocator's city by talent weight among the other cities.
- **Relocation.** A player's hire into an office whose city is not their home city moves there for `hiring.relocation_cents` (6200_recruiting); remote hires stay put. Candidates who would move carry `relocate_to`.
- **Costs.** A seat in flexible space costs `$600 x the HQ's rent index`; a seat in a leased office costs nothing per head (the rent covers it). Rent, fit-out and the closing penalty go to 6100_rent, corporate.
- **Sellers by region apply at home too.** Sales-led capacity everywhere counts the player's sellers working in the region plus 50% of the neighbour's; for a company whose sellers all work in North America this is v1's capacity. Rivals' sellers sell everywhere.
- **Regional rows.** Other regions' markets, launches and segments are their own tables; the home region keeps v1's rows and keys. Regional revenue books with the product's revenue; hosting is charged on regional customers. Product history (`product_month`) stays home-only; the Regions panel shows current customers and MRR.
- **Prices abroad.** The reference price is `p_ref x price index` (relative to the home row), then x the CRO's pricing power in sales-led segments. Sizes and price indexes are relative to the home row when the HQ is not in North America; a non-home region grows at the category's growth x its `region_growth` (the home region at v1's growth).
- **Localizing.** Launching creates every home segment in the region at the default price; feature points grow `markets.localize_slowdown` slower while any region localizes. Segments added at home later are not added abroad automatically.
- **Rivals.** `enter_region` candidates come after v1's candidates in the `rivals` draw order (so v1's draws are unchanged), one per live product and region it does not sell in, weighted as `enter_segment`; a rival enters at most one region per `geo.region_entry.cooldown_turns` (12; without it, entries crowded out every other action). Rivals enter at once, without localization, at `p_ref x index x` their personality's price factor. Every regional price is computed from the data's decimals as exact fractions (`p_ref × index_region / index_home × factor`) and rounded half-to-even once (ADR-0003; M10r): an East Asia HQ's 5,000-cent product is 2,188 cents in South and Southeast Asia, a cost leader's 50-cent AI consumer price 32 cents in Europe. Startups may also enter regions, including the home region when founded abroad. A startup's region is drawn by its category's total addressable demand by region.
- **Regional incumbents' shares** (M3a steady-state method, 24 months of the market with fixed scores, drift of served share under ~1.4 points): SAP mid-market 1,400 bp, enterprise 2,100; Kaspersky SMB 1,900, mid-market 2,200. Tencent, Alibaba, Baidu and Infosys have no rival in their region at the start and keep the table's shares.

## 20. Capital and macro (M10, lane B)

Reece's decision (2026-10-31): the macro economy follows **history from 2010 through 2025, then seeded cycles from 2026**. Every run shares the same past and differs only in its future. M10 merges before M9.

### 20.1 Macro indicators (data: `macro_history.yaml`; phase 1)

Four indicators, set each month in phase 1:

| Indicator | Unit | History (2010–2025) | After 2025 (stream `macro`, id 21, key `(indicator_index,)`) |
| --- | --- | --- | --- |
| Base rate `r` | % a year | the US federal funds rate, monthly | AR(1) toward 3.0, φ = 0.97, shock sd 0.15, clamped to [0, 8] |
| Venture climate `v` | multiplier | `climate.yaml`'s value for that year, every month of it | AR(1) toward 1.1, φ = 0.95, shock sd 0.05, clamped to [0.6, 1.8] |
| Consumer confidence `cc` | index, 100 = the 2010–2019 average | real monthly series, rescaled | AR(1) toward 100, φ = 0.95, shock sd 2.5, clamped to [60, 125] |
| AI compute index `ai` | multiplier | `compute_index.yaml` (§18.6), by year | AR(1) of the yearly change toward −10%, φ = 0.8, shock sd 0.08 |

- **Downturns after 2025.** Each month, with probability `macro.downturn_monthly` (0.012), a downturn starts if none has run in the last 36 months. For 12 months it pushes climate −0.04 a month, confidence −1.5 a month and the rate −0.25 a month, before the AR(1) step.
- Phase 1's draws use one generator per indicator, plus one (key 99) for downturns.

**Effects:**
- **Climate.** `v` replaces `climate(year)` everywhere (§14.3, §14.5, §15.4). Through 2025 it equals the old table, so v1 rounds are unchanged.
- **Consumer confidence** scales adoption in consumer and SMB segments: `adoption × (cc / 100)^{0.5}`. From 2010 to 2019 this averages about 1.0.
- **Base rate.** Debt prices off it (§20.3). It feeds public markets in M13.
- **AI compute index.** M8's AI hosting index uses `ai`, so it continues past 2025.

### 20.2 Series C and D

| Series | Allowed when | Typical raise |
| --- | --- | --- |
| Series C | after a Series B and ARR ≥ $25M | $30M–$80M |
| Series D | after a Series C and ARR ≥ $60M | $60M–$200M |

- §14.5's mechanics apply unchanged. Heat is `clamp(ARR / gate, 1, 3)`. The round's lead takes a board seat, but no more than 2 seats per round series after B, and the board has at most 7 seats (the founder's included).
- **Growth investors** (appended to `investors.yaml`):

| Firm | Series | Check size | Bias | Response | Patience | From |
| --- | --- | --- | --- | --- | --- | --- |
| Insight Partners | B, C, D | $20M–$100M | 1.00 | 0.40 | 0 | 2010 |
| General Atlantic | C, D | $40M–$150M | 0.95 | 0.35 | −5 | 2010 |
| Tiger Global | C, D | $30M–$200M | 1.20 | 0.30 | +5 | 2010 |
| DST Global | C, D | $50M–$200M | 1.15 | 0.30 | +5 | 2010 |
| SoftBank Vision Fund | C, D | $100M–$500M | 1.30 | 0.25 | −10 | 2017 |

### 20.3 Debt (accounts `2500_debt`, `7000_interest`)

| Instrument | Available | Size | Rate | Term |
| --- | --- | --- | --- | --- |
| Venture debt | within 12 months after a priced round | up to 30% of that round's amount (50% from M10d) | `r + 6%` | 36 months: 12 interest-only, then equal principal; warrants of 0.25% of FD to the lender at signing |
| Bank loan | stage 3 and positive operating profit for the last 3 months | up to 1 × ARR | `r + 3%` | 48 months, equal principal |

- **Taking a loan** is an immediate action (energy 10): choose the instrument and amount. A lender answers at once (no draw): it says yes if the gate holds, and the rate is fixed at signing.
- **Each month in phase 7:**
  - interest `round(balance × rate / 12)` to `7000_interest`;
  - principal from `2500_debt`;
  - both paid from `1000_cash`.
- **Covenants,** checked in phase 7:
  - venture debt: cash ≥ 3 months of burn;
  - bank loan: operating profit over the last 3 months > 0, and cash ≥ 10% of the balance.
- **A breach** queues a critical event from the `lender` template category (new; templates written in M10). The choices are:
  - pay a waiver fee of 1% of the balance;
  - accept a 2-point rate increase for the rest of the term;
  - repay 25% of the balance at once.

  The event system's validator caps apply (§16.3). Its follow-up: a second breach within 6 months makes the whole balance due. If cash can't cover it, the shortfall counts toward bankruptcy (§14.7).
- **Repay early** (energy 5) at any time, with no fee.
- **Statements.** Debt appears as a liability, interest below operating profit, and principal in financing cash flow.

### 20.4 What the API may show

- The macro indicators with their history and the last 24 months, and "downturn under way" when one is running. Never the AR(1) parameters' draws ahead, or a future value.
- Loans with balance, rate, schedule and covenant headroom.
- Series C and D with term sheets as in §14.9.

### 20.5 Balance targets (M10 acceptance, printed)

1. All v1 and M8 targets still pass. Through 2019, venture climate equals the old table (golden snapshots may still move from consumer confidence; record the reason).
2. **Debt saves dilution.** steady at stage 3 that takes venture debt after its Series B instead of raising a Series C ends turn 120 with at least 5 points more founder ownership (median, 10 seeds) and no more than 10 points higher bankruptcy.
3. **Covenants bite sometimes.** blitzscale that takes the maximum venture debt after each round breaches a covenant on 20–60% of seeds by turn 120.
4. **The future varies.** Over 50 seeds of 2026–2039, at least 80% have a downturn, and the venture climate's 2030 values have a standard deviation of at least 0.15.
5. **Later rounds happen.** blitzscale reaches a Series C on at least 4 of 10 seeds by turn 120.

### 20.6 Worked examples

**Venture debt.** $6M after a $20M Series A with `r = 0.25%`: rate 6.25%. Month-1 interest = `$6,000,000 × 0.0625 / 12` = **$31,250**. From month 13, principal is $250,000 a month. (M10d balance pass: the limit is now 50% of the round, `debt.venture.max_of_round_bp` 5000, so a seed's loan carries blitzscale nearer its Series A and covenants bite on 60% of seeds rather than 80%; the example keeps 30%, and its test uses it.)

**AR(1) step.** Climate 1.30 in a month with shock +0.02: `1.1 + 0.95 × (1.30 − 1.1) + 0.02` = **1.31**.

**Confidence on adoption.** `cc = 81` gives `(0.81)^{0.5}` = × 0.90 on consumer and SMB adoption.

### 20.7 Implementation notes (M10)

- **History data.** `macro_history.yaml` holds the base rate and consumer sentiment by month (approximate monthly figures) and the venture climate by year (M4's `climate.yaml`, folded in unchanged and deleted). The AI index's history stays in `compute_index.yaml`. Confidence is rescaled so 2010–2019 averages exactly 100; the adoption factor then averages about 1.0 over those years (0.89–0.92 in 2010–2011, 1.04–1.07 in 2015–2019).
- **Which month is current.** Phase 1 of turn `t` sets month `t`. Between turns the API, actions and V_base read month `t` from history while the calendar is in it (it is public), and after 2025 the last month phase 1 set (`t − 1`), so nothing is ever drawn ahead. Through 2025 every reader therefore gets exactly the old `climate(year)`.
- **Draw order.** Each month after 2025: keys 0–3 (rate, climate, confidence, AI), one standard normal each, then key 99, one uniform, whether used or not. The AI index's yearly change steps each January, clamped to [−50%, +50%].
- **Downturn spacing.** "None in the last 36 months" counts from a downturn's last month: a new one may start when at least 36 months have passed since the previous one ended (48 from start to start).
- **The adoption hook** is `macro.adoption_factor(state, segment_key, balance)`: the segments and the exponent are balance data (`macro.confidence_segments`, `macro.confidence_exponent`), so it takes `balance` as a third argument. It reads the month phase 1 set (1 before any).
- **Series C and D.** The keys extend v1's maps (`finance.round.gate_arr_cents`, `typical_cents`, `board.expected_growth` 0.8 and 0.6, `board.seats`) plus `board.max_seats` 7. After Series B the board has 6 seats; the Series C lead takes the seventh; the Series D lead takes none.
- **Venture debt.** Offered while `turn < closed_turn + 12` of the latest priced round; the limit is 30% of that round's amount less what was already borrowed against it. Warrants are sized so the lender holds 0.25% of FD after they are issued: `round(FD × 25 / 9,975)`, a `warrant` cap-table entry in the lender's name.
- **Bank loan gate.** Stage 3 and an operating result above zero in each of the last 3 completed months; the limit is 1 × ARR less bank debt owed.
- **Schedule.** Interest `round(balance × rate_bp / 120,000)`, exact. From the first principal month, principal is the balance spread over the months left (`balance / months_left`), so it is equal principal ($250,000 a month in 20.6) until a partial repayment, which lowers each later payment and never extends the term; the last month pays what is left.
- **Covenants** read completed months: burn is last month's net cash used before financing (14.1), operating profit the sum of the last 3 months' operating results (each classified by account over the whole month's ledger, including what was posted before Continue: a waiver fee is interest, below the line; M10r); cash is this month's after the loan payments. "Above zero" means at least one cent.
- **Breach and follow-up.** A breach queues the critical `lender_covenant_breach` event for next month (engine-queued, trigger `covenant_breach`; never drawn, always written from its template because its choices are the §20.3 terms). Its effects are shares of `debt.breach`: `loan_fee` (1% of the balance to `7000_interest`, held to the critical cash cap of §16.3), `loan_rate` (+200 bp), `loan_repay` (25% at once). After a breach covenants rest for `debt.breach.cure_months` (3) months, so the answer can take effect; a breach found after that and within 6 months of the first calls the loan: the whole balance leaves cash at once (a shortfall is insolvency, §14.7) and the major `lender_loan_called` event follows.
- **Statements.** Debt is `2500_debt` (a liability), interest and waiver fees `7000_interest` (below operating profit; operating cash flow), principal is financing cash flow and never burn.
## 21. R&D tree and era milestones (M11, lane A)

Reece's decisions (2026-10-31): domain levels and research projects underneath, plus named, **market-changing era milestones** that arrive on their historical date unless a company researches them first (ADR-0019 §7). Principle: **a company that never researches plays as before M11.** Its tech factor is exactly 1, and the eras arriving on their historical dates reproduce the demand curves M8–M10 were tuned on, within the tolerance in §21.8. M11 merges before M12a.

### 21.1 Domains and levels

- **Domains:** software platform, AI, infrastructure, chip design and devices. Chip design and devices have levels and research now; their products come in M12b.
- **A company's level in a domain** is `D_d(t) + R_c,d`:
  - **Baseline `D_d(t)`:** the world's diffused know-how, free to everyone. From `tech_frontier.yaml`, by year: software platform 20 in 2010, +2 a year; infrastructure 20, +2 a year; AI 10, +1.5 a year through 2015, then +3 a year; chip design 30, +1.5 a year; devices 25, +1.5 a year. Each era adds +5 to its domain's baseline when it arrives.
  - **Lead `R_c,d` ≥ 0:** what the company knows beyond the baseline. It is 0 at game start for everyone.
- **Lead decays** each month by `R ← R × (1 − rnd.decay)` (0.015), as knowledge diffuses through papers, open source and job moves. A lead halves in about 46 months without research (spec §7.3: leadership decays without continued spend).
- **Which domains count for a category** (`tech_weights` in `tech_frontier.yaml`):

| Category | Domain weights |
| --- | --- |
| B2B SaaS | software platform 0.7, infrastructure 0.3 |
| Developer tools | software platform 0.5, infrastructure 0.5 |
| Consumer apps | software platform 0.8, AI 0.2 |
| Cybersecurity | software platform 0.5, infrastructure 0.5 |
| Fintech | software platform 0.7, infrastructure 0.3 |
| AI models | AI 0.8, infrastructure 0.2 |

  A company's lead for a category is `R_cat = Σ w_d × R_d`.

### 21.2 What a lead does

- **Quality cap:** `Q_cap × (1 + rnd.cap_per_point × min(R_cat, rnd.cap_points))`, with 0.004 per point and a maximum of 50 points, so at most × 1.20 (tuned in M11 to 0.010, so at most × 1.50; §21.10). It applies after the CTO factor (§18.3).
- **Features:** feature points gained × `(1 + 0.002 × min(R_cat, 50))` (tuned in M11 to 0.005; §21.10).
- **Rivals:** a rival's quality target `5 d` (§15.2) uses the same factor with the rival's own lead.
- All of this sits behind one function, `research.tech_factor(state, company_id, category)`. The product code calls it in one place.

### 21.3 Research projects

- **Start a project** (immediate action, energy 6): choose a domain and assign an org unit to it. A unit works on one product or one project, never both (§11.3). Stop a project with energy 2.
- **Researcher output** per month uses the domain's research skill:

| Domain | Research skill |
| --- | --- |
| Software platform | software engineering 0.5, data 0.3, product 0.2 |
| AI | ML research 0.6, data 0.25, software engineering 0.15 |
| Infrastructure | infrastructure 0.6, software engineering 0.25, security 0.15 |
| Chip design | chip design 0.7, hardware design 0.3 |
| Devices | hardware design 0.6, manufacturing 0.2, design 0.2 |

  Output is `o = coord(n) × Σ (r_i / 10) × m_i × λ_i` (§11.3 and §18.2 factors; the CTO multiplier applies).
- **Budget.** A project needs `rnd.budget_per_researcher` a month per researcher: software platform $2,000, infrastructure $3,000, AI $6,000 × the AI compute index (§20.1), chip design $12,000, devices $8,000. It posts to `6500_research_development`. Funding below that scales output by the funded share. The project's budget is set like a product's marketing budget.
- **Progress:**

```latex
\Delta R_d = \frac{rnd.rate \cdot o}{1 + R_d / rnd.half}
```

  with `rnd.rate` 0.25 (tuned in M11 to 0.4; §21.10) and `rnd.half` 30. Returns diminish: the first 15 points come about twice as fast as the next 15. Decay (§21.1) applies after progress.
- **Breakthroughs and dead ends** (phase 3, stream `research`, id 23, key `(project_id,)`): each active project each month draws:
  - **breakthrough** with probability `0.02 × q`, where `q = clamp(mean research skill / 12, 0.5, 1.5)`: +5 lead at once;
  - **dead end** with probability `0.015 / q`: −50% of the last 3 months' progress.

  Both go to the event director as triggers `research_breakthrough` and `research_dead_end` (minor templates written in M11), so they appear as events.

### 21.4 Era milestones (data: `eras.yaml`)

| Era | Domain | Historical arrival | What it accelerates |
| --- | --- | --- | --- |
| Mobile-first | software platform | Jan 2011 | consumer apps: growth +15 points for 36 months; consumer adoption × 1.2 for 24 months |
| Deep learning | AI | Oct 2012 | AI models: growth boost (fitted, §21.8) |
| Cloud-native | infrastructure | Jun 2014 | developer tools: growth +10 points for 36 months |
| Transformers | AI | Jun 2017 | AI models: growth boost (fitted) |
| Open banking | software platform | Jan 2018 | fintech: growth +10 points for 36 months |
| Zero trust | infrastructure | Jan 2020 | cybersecurity: growth +10 points for 36 months |
| Large language models | AI | Nov 2022 | AI models: growth boost (fitted); consumer adoption × 1.5 for 24 months |
| AI agents | AI | Mar 2025 | AI models: enterprise growth +40 points for 36 months; B2B SaaS mid-market and enterprise growth +5 points for 24 months |

- **Arrival.** An era arrives at its historical month, or earlier on the first month any company's level in its domain reaches the era's **threshold**: `D_d(historical month) + rnd.era_lead` (15). Researching an era early takes a real lead; 15 points is about two years of a strong lab.
- **On arrival,** the domain's baseline rises 5, and the era's boosts start from that month, so an early arrival pulls the whole acceleration forward.
- **First-mover window,** when a company caused the arrival: for `rnd.first_mover_months` (12) its products in the affected categories get +5 on the quality cap (points, after §21.2) and +10 on the brand target (§11.5), and its lead in that domain doesn't decay.
- **Already in the curves:** the M8 AI `growth_by_year` table is replaced by a base growth plus the three AI era boosts. Fit them so that historical arrival reproduces M8's demand (§21.8 target 1).
- **History** records each era's arrival, who caused it and how many months early. The Market screen shows eras to come as a timeline with their domain and threshold, and no historical dates past the present.

### 21.5 Licensing

- **License in** (immediate action, energy 8): from a rival (or the player, for rivals) whose lead in a domain exceeds yours by more than 10.
  - **Gain:** up to their lead − 10.
  - **Price:** `rnd.license_price_per_point` ($150,000 in 2010 dollars; tuned in M11 to $24,000, §21.10) × points × `(1 + ARR / $20M)`, once.
  - **Answer:** the licensor says yes unless they're a direct competitor in a category the domain feeds (a rival you share a segment with). Rivals answer by a rule, not a draw.
- **License out** (energy 8): grant a rival up to your lead − 10. It pays 2% of its revenue in the categories that domain feeds, monthly for 24 months (`4100_revenue_licenses`).
- **Leaks:** when a researcher on a project leaves for a rival, that rival gains `min(10, 0.1 × your lead)` in the project's domain.

### 21.6 Rivals research

Incumbents gain a `research` action. Its need is `(best lead in their categories' domains − own) / 15`, plus 0.3 if an era in their domain is within 24 months of its historical date. Weights by personality: premium 1.2, fast_follower 0.9, aggressive 1.0, cost_leader 0.6. While it runs (6 months), the rival's lead grows `rnd.rival_rate × builder_skill / 10` a month (0.8), and it pays builder-pool cost +10%. Startups don't research. Randomness: the existing `rivals` stream (utility noise) and stream `rival_research` (id 24, key `(company_id,)`) for breakthroughs, with the player's probabilities.

### 21.7 What the API may show

- Levels as `D + R`, with the baseline and lead split.
- Projects with researchers, output, budget, monthly progress and estimated months to the next era threshold.
- Breakthroughs, dead ends and licences.
- Rivals' levels as ranges: a rival's lead shows ±5 around the true value, narrowed to ±2 if you have a licence with them.
- The era timeline with thresholds.
- Researcher skill uses displayed ranges, as everywhere else.

### 21.8 Balance targets (M11 acceptance, printed)

1. **Without research, nothing moves.**
   - All v1, M8, M9 and M10 targets pass as before (the recorded misses stay recorded).
   - With eras at their historical dates, AI addressable demand in Jan 2024 is within ±10% of M8's value (359×), and every other category's Jan 2020 demand is within ±10% of before M11.
2. **Research pays.** steady with a 6-person research unit in its main category's top domain from stage 2 reaches a median turn-120 ARR at least 1.10 times steady without it, net of the research cost, with median quality at least 5 points higher.
3. **Eras can be pulled forward, but rarely by accident.**
   - A 10-person AI lab from Jan 2014 (ML research ≥ 14, fully funded) causes Transformers before Jan 2017 on at least 5 of 10 seeds.
   - In do-nothing runs, rivals pull an era more than 6 months early on at most 15% of seeds.
4. **Decay.** A lead of 30 with no research is 14–16 after 46 months.
5. **Licensing is a shortcut.** Licensing in half of a 30-point gap costs at most 0.7 times the median cost of researching it with a 6-person unit.

### 21.9 Worked examples

**Progress.** A 6-person AI unit with research skill 12 each, morale 50, no tax: `o = 0.98 × 6 × 1.2 = 7.06`. At `R = 0`: `ΔR = 0.25 × 7.06` = **1.76** a month. At `R = 30`: 0.88.

**Quality cap.** A B2B SaaS product with `Q_cap = 60`, software platform lead 20 and infrastructure lead 10: `R_cat = 0.7 × 20 + 0.3 × 10 = 17`, so `Q_cap = 60 × 1.068` = **64.1**.

**Era threshold.** Transformers (AI, Jun 2017): `D_AI(2017.5) = 10 + 1.5 × 6 + 3 × 1.5 = 23.5` (before the Deep learning +5, which makes it 28.5), so the threshold is 28.5 + 15 = **43.5**. In Jan 2016 the AI baseline is 10 + 9 + 5 = 24, so a company needs a lead of 19.5 to cause it then.

**Licence price.** 12 points with ARR $10M: `$150,000 × 12 × 1.5` = **$2.7M** (spec value, pinned by the test; at the tuned $24,000 it is $432,000).

### 21.10 As built (M11 notes)

- **Baseline accrual.** `D_d(t)` accrues month by month: `start` plus `per_year / 12` for each month before `t`, the rate of the month's calendar year. An era's **threshold** reads the baseline at the end of its historical month (`t_hist + 1`), plus `rnd.era_baseline` for each era of the domain historically before it, plus `rnd.era_lead`. Both 21.9 era examples hold exactly: Transformers 23.5 + 5 + 15 = 43.5; the AI baseline in January 2016 is 24.
- **The hook.** `tst.sim.research.levels.tech_factor(state, company_id, category, balance, data)` (the balance and data follow the brief's three arguments) returns the cap multiplier, the first mover's cap and brand points and the feature multiplier; identity for a company with no lead and no window. `product_team` calls it once, so the quality cap (after the CTO), features gained (after the CPO) and the brand target (first mover, at most 100) all read the same factor; rivals' quality target calls it once. M12a reads `tst.sim.research.levels.lead(state, company_id, domain)` (the package's `__init__` stays import-light because `data_models` imports `research.data`).
- **Base growth.** `eras.yaml` `base_growth` replaces `categories.yaml`'s growth for demand (phase 9, home and other regions), for startups' founding rate and for the growth the API shows, for the categories whose eras are in the tuned curves; `categories.yaml` is unchanged (lane rule) and its AI `growth_by_year` is no longer read. AI models: 0.28 from 2010, 0.35 from 2016, 0.40 from 2020, 0.50 from 2025, 0.25 from 2030, with Deep learning +5 points for 60 months, Transformers +20 for 60 and Large language models +180 for 24 (consumer adoption x1.5 for 24): January 2024 demand 350x January 2010 (M8: 359x). Consumer apps 0.2568 until 2020 (Mobile-first's +15 for 36 months), developer tools 0.2208 until 2020 (Cloud-native's +10), fintech 0.2235 until 2021 (Open banking's +10), each then its `categories.yaml` rate: January 2020 demand is 1.000, 1.000 and 0.944 of before M11. Zero trust (2020) and AI agents (2025) arrive after the tuned decade and add growth. Boosts reach every region (x the region's growth multiplier, 19.5); adoption boosts multiply the segment's adoption with the macro factor (20.1).
- **Researchers** are the project unit's direct members in builder roles (and the founder), as on a product team; `lambda_i` is the tag multiplier x the seat and structure factor (CTO, 18.5) x event modifiers on the unit's builder output (23.2). Researchers cost the budget; their salaries are payroll as before.
- **Budget.** NULL means full funding (`n x budget`, x the AI compute index for AI, multiplied as exact fractions and rounded half-to-even once, M12r); a set budget spends at most the need. Setting it costs `rnd.budget_energy` (0, like a marketing budget).
- **Draws.** Stream `research`, key `(project_id,)`: a uniform for a breakthrough (below `0.02 q`), then, only without one, a uniform for a dead end (below `0.015 / q`), each month a project has funded output. A dead end removes `rnd.dead_end_share` of the last `rnd.progress_window` months' progress, this month's included, never below 0. A project whose unit is dissolved stops in phase 3.
- **Arrival order.** Phase 3: development, rival effects, projects, rivals' research months, decay, then eras in `eras.yaml` order (an earlier era's +5 counts for a later one's level the same month). Ties between companies reaching a threshold in the same month go to the higher level, then the lower company id. Existing saves (migration `0028_research`) record past eras as arrived on schedule.
- **Licensing.** The licensee may come within `rnd.license.margin` of the licensor's lead, never closer: at most `their lead - margin - yours` points. The price uses the licensee's ARR (last month's MRR x 12) and posts to 6500 (licensee) and 4100 (licensor). There is no inflation in the game, so "$150,000 in 2010 dollars" is nominal. A direct competitor is a company selling in a segment the licensee sells in, at home or abroad, in a category the domain feeds. Rivals accept any licence out that raises their level. Royalties post in phase 5 on the licensee's booked revenue (home and abroad) in the domain's categories, for 24 months including the signing month.
- **Leaks** apply when a builder-role member of a unit with an active project joins a rival (phase 1), at `min(rnd.leak.cap, rnd.leak.share x the company's lead)`.
- **Rivals' research.** One candidate per domain feeding the rival's live categories, scored after v1's and M9's candidates (their draws are unchanged), weighted by `rnd.rival.weights`; one research action at a time. While it runs the builder pool is `rnd.rival.pool_cost` larger, through the last month's payroll, and returned in phase 1 of the month after it ends (M12r), so all six monthly payrolls pay the premium; breakthroughs on stream `rival_research` with `q` from the rival's builder skill.
- **What the API shows.** A rival's lead is a range of whole points, `+-rnd.reveal.range` (`licensed_range` with a licence) around the true value offset by a seeded draw (stream `lead_reveal`, id 25, key `(observer, company id, domain index)`), so the midpoint is not the true lead. Licence limits on the screen use the range's low end; an action refused for too many points names no number. A project shows researchers, budget, funded share and estimated lead gained a month from displayed skill ranges (23.4) and executive seat factors from displayed ranges (18.8; M12r: the lab is built with `estimate=True`, never rescaled from true output); the output itself stays hidden (11.13's guard on `output`). The era timeline shows thresholds and no historical date of an era still to come.
- **Licence ceilings (M12r, Codex review 3 finding 1).** The licence actions offer exactly the screen's ceiling, in whole points: licensing in, `floor(low - margin - yours)`; licensing out, `floor(yours - margin - high)`, never below 0, `low` and `high` the displayed range. The range always contains the true lead, so the ceiling never exceeds the true limit. A request is checked for whole points, then the ceiling, then cash, then energy, and the licensor's refusal ("not more than 10 points ahead") also reads the public ceiling, so no answer depends on the hidden lead.
- **Tuned keys (21.8; M11 brief).** `rnd.rate` 0.4, `rnd.cap_per_point` 0.010, `rnd.feature_per_point` 0.005, `rnd.license.price_per_point_cents` $24,000, `rnd.rival.era_bonus` 0.15, `rnd.rival.need_span` 30. The 21.9 examples keep 21.2-21.5's values and their tests pin them.
- **Events.** The research triggers' strengths sit in `events.trigger` (`research_breakthrough` 0.7, `research_dead_end` 0.6), which must list every trigger.

## 22. Cloud, data centres and supply shocks (M12a, lane B)

Reece's decisions (2026-10-31): simplified facilities (ADR-0019 §2); own capacity can be unprofitable when under-used, and **spare capacity can be sold to others** (ADR-0019 §8); component prices and supply **follow history to 2025, then seeded shocks** (§9). Principle: **a company that never builds plays as before.** Products buy compute at the spot price (v1's `h`, with AI on its index), and nothing changes. M12a merges after M11.

### 22.1 Compute units and the spot price

- **One compute unit (CU)** is the compute a product buys for $1,000 a month at index 1.0. A product's compute need is its hosting cost (§11.8, §18.6) ÷ $1,000 × the relevant index:
  - **General CU** for every category except AI. Its index stays 1.0 (v1's `h` is unchanged).
  - **GPU CU** for AI. Its index is M10's AI compute index (§20.1).
- **Spot hosting** (no own capacity) posts to `6300_compute` exactly as now.

### 22.2 Data centres (facility)

- **Build** (immediate action, energy 12): choose a region (§19.5), a kind (general or GPU) and a capacity in CU (100, 500, 2,000 or 10,000).

| | General | GPU |
| --- | --- | --- |
| Capex per CU (2010 $) | $24,000 × the server component index (§22.4) | $40,000 × the GPU component index (§22.4) |
| Build time | 12 months | 9 months, plus allocation delay (§22.4) |
| Operating cost per CU per month | $250 | $500 (power) |
| Life | 60 months | 48 months |

- **Capex** is paid as built: equal monthly payments during the build, to `1500_ppe`. Depreciation runs straight-line over the life from completion: `6700_depreciation` (new account) and `1510_accumulated_depreciation` (new). Debt from M10 can fund it.
- **Staff.** A data centre needs one infrastructure-role person (DevOps or security engineer) per 200 CU, from a unit assigned to it. Coverage `c_f = min(1, staff / need)`.
- **Reliability** `rel = 100 × c_f × (0.7 + 0.3 × mean infrastructure skill / 20)`. It feeds outages (§22.5) and the quality of capacity sold (§22.3).
- **Your own products use your capacity first:** cheapest first, in the product's region or its neighbour (§19.5). Their spot cost falls by the CU they use.
- **Economics at full use** (server index 1.0): a general CU costs `$24,000 / 60 + $250` = **$650** a month against $1,000 spot, so it breaks even at 65% utilization. Building early and small usually loses money, which is the design intent.
- **Close or sell** (energy 12): sell for 50% of book value; staff stay in their unit.

### 22.3 Selling spare capacity: Cloud and GPU hosting (new category `cloud_hosting`)

- **Segments:** SMB, mid-market, enterprise and hyperscalers. Hyperscalers are a new sales-led segment with appeal weights quality 0.40, price 0.40, brand 0.05, features 0.15, base churn 0.5% and adoption 0.3%.
- **Customers buy CU.** `D₀` and `p_ref` per CU are in `categories.yaml` (appended): `p_ref` is $1,000 for general and $1,000 × the GPU index for GPU.
- **A company sells only when it owns spare capacity.** Its product's "quality" is mean reliability, and its features come from its infrastructure lead (§21.1; 50 + 2 × lead, capped at 100). Customers are capped so that CU sold ≤ spare CU in the region and its neighbour.
- **Revenue** posts to `4000_revenue_subscriptions`. The CU sold count as used for utilization.
- **Incumbents and entrants** (data):
  - Amazon Web Services (aggressive, from 2010);
  - Microsoft Azure (fast_follower, from Feb 2010);
  - Rackspace (cost_leader, 2010);
  - IBM SoftLayer (premium, 2010);
  - Google Cloud (scheduled entrant, Apr 2012);
  - CoreWeave (scheduled entrant, GPU only, Jan 2019).

  Rivals' capacity is abstract: they always have enough, and their prices follow §15.3.

### 22.4 Components, allocation and supply shocks (data: `components_history.yaml`)

- **Two component indexes:** server (general) and GPU, at 1.0 in 2010.
  - **History to 2025:**
    - server: −8% a year to 2020; +30% from Q2 2021 to Q2 2022 (the chip shortage); back down by 2023;
    - GPU: −10% a year to 2016; +20% in 2017–2018 (crypto); +60% from Q1 2023 to Q2 2024 (the AI crunch);
    - allocation: 70% in 2021–2022 for servers, 40% in 2023–2024 for GPUs, otherwise 100%.
  - **After 2025** (stream `supply`, id 26, key `(index,)`): each index takes an AR(1) step on its yearly change toward −8%, with shock sd 0.06. With probability `supply.shock_monthly` (0.01) a shock starts if none has run in 30 months: the index rises 25–60%, and allocation falls to 40–80% for 6–18 months. Draws are in a fixed order.
- **Allocation.** While allocation is below 100%, a data centre under construction completes only that share of its capacity on time; the rest arrives 1 month later for each 10 points of shortfall.
- **Contracts** (immediate action, energy 6): lock a component price for 12–36 months on a stated volume of CU builds (take-or-pay: an unused volume is charged 30% of its value at the end). Contracted builds get 100% allocation.

### 22.5 Outages (phase 6, stream `facility`, id 27, key `(facility_id,)`)

- **Each month, each data centre** has an outage with probability `0.002 × (100 − rel) / 10`. At reliability 50 that's 1% a month; at reliability 95, 0.1%.
- **An outage is a critical event** (new `outage` templates):
  - every product it hosts loses `customers_pct` within critical caps, and cloud customers churn × 3 that month, at home and abroad (M12r: the extra churn comes off every home and regional Cloud segment, counts in the outage's customers lost, and the event targets the segment that lost most);
  - the choices trade cash (overtime and credits) against brand.

### 22.6 What the API may show

Data centres with capacity, utilization (own and sold), reliability, staff coverage, monthly cost per CU against spot, book value and build progress. The component indexes and allocation, with history, never the future (M12r: only supply months before the save's turn are loaded or read, and the view, quotes and contracts ignore a later month even if one is in memory). Contracts. The Cloud hosting market like any market. Outage history.

### 22.7 Balance targets (M12a acceptance, printed)

1. **Without building, nothing moves.** All earlier targets pass as before.
2. **Ownership needs utilization.** A general data centre costs at most 0.70 times spot per used CU at ≥ 80% utilization, and at least 1.2 times spot at 40%.
3. **Spare capacity sells.** A company with a 2,000-CU general data centre at 50% own use, selling its spare, reaches at least 85% utilization within 24 months on at least 6 of 10 seeds.
4. **History bites.** The 2021 server shortage raises the server index 20–40%, and the 2023 crunch raises the GPU index 40–80%. An AI company with its own GPU capacity built before 2022 keeps a gross margin at least 15 points higher in 2023 than the same company on spot.
5. **The future varies.** After 2025, at least 70% of seeds see a supply shock by 2035.
6. **Staffing matters.** A data centre at staff coverage 0.5 averages at least 1 outage a year; at full coverage with skill 14, at most 0.2.

### 22.8 Worked examples

**Unit cost.** 500 general CU, full: depreciation `500 × $24,000 / 60` = $200,000, plus operating `500 × $250` = $125,000, for $325,000 a month, or **$650** per CU against $1,000 spot. At 40% use, $325,000 / 200 = **$1,625** per used CU.

**Reliability.** 2,000 CU needs 10 staff; with 8 at mean infrastructure skill 15, `c_f = 0.8` and `rel = 100 × 0.8 × (0.7 + 0.225)` = **74**, giving an outage chance of `0.002 × 2.6` = **0.52%** a month.

**GPU build in the crunch.** 500 GPU CU in Jul 2023 (GPU index 1.60, allocation 40%): capex `500 × $64,000` = $32M. 200 CU complete on time and 300 arrive 6 months late.

### 22.9 Implementation notes (M12a)

- **CU need.** A product's need is its hosting at index 1.0 (11.8) / $1,000: GPU CU for AI do not grow with the AI index; their spot price does ($1,000 x `ai`). Own capacity takes the share served off each region's spot hosting, so a company with no live data centre posts exactly v1's numbers.
- **Facility lifecycle.** Capex is `units x capex per unit x the input good's index` (a contract's index for the units it covers), paid in equal parts over the build months from the order month. Units on time go live at `ready = order + build months`; late units at `ready + ceil(shortfall / 10 points)`. Depreciation runs from each part's live month, straight-line over the life, ending at exactly the capex; after its life a data centre keeps running at operating cost only. Sale: half the book value in cash, the rest a loss in `6700`. Depreciation is a cost of revenue with hosting; in the cash flow `6700` and `1510` count with investing, where they cancel or leave the sale proceeds.
- **Staff.** A unit is assigned to a data centre (energy 2; a unit staffs one); its active DevOps and security engineers count. Reliability uses their true infrastructure skill; only reliability reaches the API. Cloud quality is reliability weighted by live units.
- **Cloud hosting.** Each segment's customers buy `units_per_customer` CU (SMB 4, mid-market 20, enterprise 200, hyperscalers 2,000) at $1,000 a CU reference; GPU spare sells in the same market at its spot value in general CU. The cap is applied at the end of phase 5, region by region (home first), each region taking what its data centres and its neighbour's still have free. Rivals' capacity is abstract: their hosting is 55% of the reference price.
- **Supply after 2025.** Per good, a January AR(1) step on the yearly change (mean -8%, phi 0.6, sd 0.06, bounds +-40%); a shock starts with probability 0.01 a month when no shock month fell in the last 30 months; its rise holds while it runs and then fades linearly over as many months. Five draws a month per good, in a fixed order.
- **Tuning (22.7).** `facility.outage.base` 0.016 (0.002 gave 0.13 outages a year at coverage 0.5; the 22.8 example keeps 0.002 as its stated coefficient). Cloud `brand_constant` 25 and SMB at 4 CU a customer (target 3). Target 2 is measured for a build in January 2016: at index 1.0 (2010) the 80% bound reads 0.81, and for builds after 2017 the 40% bound falls below 1.2. Target 4's margin gap is not met: 2023 spot GPU compute is $718 a CU (`ai` 0.73), below a GPU data centre's $500 power plus depreciation ($965 for a 2021 build).

## 23. Feel fixes from Reece's v1 playtest (M10b)

From Reece's playtest on 2026-11-01 (Playtest Log): "It is fun, works well. Needs some fine tuning." His decisions the same day: visible, lasting event effects; major and critical events block Continue; self-serve sells abroad without a local presence. These rules change what the player sees and decides. Tuning waits for M10d.

### 23.1 Inbox

- **Answered events archive themselves.** Choosing (or the default at Continue) moves the event's inbox item to the archive. It stays readable from History and its deep link.
- **Auto-archive:** any read, unbookmarked item older than `inbox.auto_archive_months` (3) is archived at month end. A **bookmark** (star) action keeps an item in the inbox.
- **Blocking:** an open **major** or **critical** event blocks Continue (and Holiday's next month) until answered. The top bar says "Answer 2 events first". Minor events still take their first choice at Continue. This replaces §16.3's rule that major events default at Continue.
- **Holiday** still stops for events at or above the chosen severity (§17.1). A major event below the chosen stop level is answered with its first choice during Holiday, as now; blocking applies only when the player is at the controls.

### 23.2 Events with visible, lasting effects

- **New effect type `modifier`:** `{target, stat, value_pct, months}`. Targets are a product, a unit, a person or the company. Stats are brand target, quality cap, builder output, seller capacity, awareness, churn, morale target and founder energy. It applies every month for `months`, then expires.

| Severity | Modifier cap | Longest duration |
| --- | --- | --- |
| minor | ±5% | 6 months |
| major | ±10% | 12 months |
| critical | ±20% | 12 months |

  The validator clamps modifiers like every other effect (§16.3). The LLM may attach modifiers from the template's allowed list.
- **Effects show as numbers.** This replaces §16.9's words-with-a-size. Each choice lists its effects plainly, for example "+3 brand target for 12 months", "costs $8,000", "Priya's morale +5", "−10 founder energy next month". Caps and trigger strengths stay hidden.
- **Active effects panel** on Overview, Product and Person: every running modifier with its source event, value and months left.
- **Month-end report:** one "Your choices this month" line listing the effects applied and the modifiers that started or expired.
- **No empty choices.** Every template choice carries at least one effect, except an explicit "Do nothing" choice labelled as such. Templates whose story implies a benefit (a domain for sale, a conference talk, a press feature) carry a matching modifier.
- **Energy effects** show in the top bar's energy tooltip ("−10 from the board dinner") and reduce the energy available that month.

### 23.3 More critical events

New critical templates and triggers, so a growing company meets a crisis now and then:

| Trigger | Holds when | Critical template |
| --- | --- | --- |
| `key_exit` | a seat holder, president or top-10% employee resigns or is poached | the exit: counter-offer (a big raise), let go with a handover (an output modifier), or emergency hire |
| `security_breach` | monthly chance `0.004 × (1 − security coverage)` for a live product with 1,000+ customers, where coverage is the product team's mean security skill / 15, capped at 1 | breach: disclose, pay, or patch quietly (churn and brand modifiers, cash) |
| `outage` | monthly chance `0.003` for a live product with quality < 45 and 5,000+ customers | outage: credits (cash) against churn and brand |
| `pr_crisis` | an event chain or a storyline step marked critical | press crisis: brand modifier choices |

- Critical spacing stays at most one in any 6 months (§16.1).
- Draws use the existing `events` stream with keys in a fixed order.
- **Target:** a company with 20+ staff meets on average at least one critical event per 18 months (§23.7).

### 23.4 Explanations

- **Product team strength.** The product profile shows output against two lines: **maintains** at `0.25 σ` and **full speed** at `σ` (§11.4). For example: "Output 1.1. Below 1.5 your product slips; full speed at 6. Add about 1 builder to stop the slide."
- **The slipping message** distinguishes "Nobody is working on {product}" (no builders) from "{product}'s team is too small to maintain it (output 1.1 of 1.5 needed)". Reece read the old message as a bug.
- **Sales capacity message:** "{n} sellers win up to {cap} {segment} customers a month; {demand} wanted to buy. Each extra seller adds about {per_seller}."
- **Role descriptions** (`roles.yaml` gains `summary` and `why_hire`): what the role does, its product function, the skills that matter, and when to hire one. Shown in Recruitment, the hiring-plan dialog and the profile.
- **Structure guide** on the Org screen: a panel explaining what departments, teams and divisions do, with this company's live numbers: span of control and manager quality (§13), layer tax and cross-division factor (§18.2), support coverage (§18.4), and executive effects (§18.3).

### 23.5 Regions

- **Self-serve segments** (consumer, SMB) sell abroad at full awareness once localized: `markets.foreign_awareness` becomes 1.0 for self-serve. This replaces §19.5's 0.6 without presence.
- **Sales-led segments** still need sellers in the region or its neighbour (§19.5).
- **Marketing by region:** a product's marketing budget may be split across its live regions (default: in proportion to revenue). Brand stays global; awareness in a region uses that region's share of marketing points. A region with no marketing spend uses 70% of the global awareness.
- The Regions panel explains these rules in one line per segment type.

### 23.6 Former staff profiles

Former employee profiles (M7c) add their job history at the company (each role, level and unit, with months) and what they led: units, products they built as part of a unit's team, seats held, research projects (once M11 exists), and storylines they appeared in.

### 23.7 Acceptance targets (printed)

1. Critical events: at least one per 18 months on average for companies with 20+ staff, over 10 seeds × 120 turns of the steady strategy; spacing never under 6 months.
2. Every event template has at least one choice with an effect (data test), and every "benefit" template carries a modifier (data review list in the brief).
3. Event balance (§16.10) stays within ±5% of revenue for cash and ±3 for morale on every seed, now counting modifiers' effects. Tuning, if needed, uses only `events.*` keys.
4. Earlier targets: recorded misses stay recorded. Any other guard that moves is reported for M10d, not tuned here.

## 24. Executives with authority (M10c)

Reece (2026-11-01): executive seats need more power, and the player needs better ways to let teams run without him as the company grows. This is the delegation layer before M13's CEO.

### 24.1 Authority (per seat, immediate action, energy 2 to change)

Each filled seat (§18.3) can be given **authority** over its function, with guardrails the player sets. With authority, the executive acts each month in phase 2 as a delegate (ADR-0015), through the same actions as the player. It uses its own energy (100), with randomness on stream `delegate` keyed by person id.

| Seat | Acts on | Guardrails (player sets) |
| --- | --- | --- |
| CTO | Assigns builders between units, products and projects, so every live product stays at or above its maintenance line and products in development reach a target pace; opens builder hiring plans | headcount cap for builders; max salary ratio; protected units it can't move |
| CRO | Opens seller hiring plans when sales capacity limits a segment; sets sales-led prices within ±10% of the player's last price | seller headcount cap; price band |
| CMO | Splits the total marketing budget across products and regions, toward products with the best brand gap and growth | total marketing as % of revenue |
| COO | Keeps support coverage at or above a target by opening support hiring plans; flags crowded offices and proposes leases | coverage target; lease approval above a monthly rent (proposals need the player's OK) |
| CFO | Watches runway. Below a threshold it proposes a round or a loan, with a recommended term sheet the player approves. Above a cash threshold it repays debt early | runway threshold; cash threshold; approval always needed for rounds |

- **Proposals** are inbox items with Approve and Decline (major severity, so they block Continue under §23.1).
- An executive without authority still gives its seat effect (§18.3) and its reports.

### 24.2 Decision quality

An executive's choices use the company's displayed knowledge (ADR-0015), and their quality comes from their true skills. With seat score `s`:
- each monthly decision runs the right rule with probability `clamp(0.55 + 0.03 s, 0.6, 0.98)`;
- otherwise it takes a plausible but worse option: the second-best candidate, a slower pace or a budget split off by 20%.

Mistakes are logged with the executive's name in the decision log and History, so a weak CTO shows up as visibly worse staffing.

### 24.3 Reports and executive events

- **Quarterly report** from each seat holder: their function's KPIs for the quarter, what they did with their authority, and one or two concerns (written by the LLM within the budget, or a template). It appears in the inbox and on the Executive team panel.
- **Executive events:** new templates triggered by executives, for example a CTO asking for a research budget, a CRO wanting a price change, a CMO proposing a campaign, a CFO warning about runway, and executives clashing (relationships). Their choices carry modifiers (§23.2).
- **Ask my COO** (§17.3) answers from the named COO's report when the seat is filled.

### 24.4 What the API may show

Each seat's authority, guardrails, decisions this month (with outcomes), proposals and reports. Never the decision-quality probability or the executive's true score.

### 24.5 Acceptance targets (printed)

1. **Delegation works.** A stage-3 steady company with all five seats given authority, and the founder taking no actions for 36 months, ends within 15% of the same company played by the steady script (median ARR, 10 seeds), and never lets a live product drop below its maintenance line for more than 2 months.
2. **Quality matters.** The same run with every seat holder at score 8 against score 15 differs by at least 15% median ARR.
3. **No runaway hiring:** headcount never exceeds the guardrail caps, and support coverage stays within 0.1 of the target.
4. **Founder energy:** delegated runs leave the founder at least 60% of their monthly energy unspent on average.

## 25. IPO, public company, and Chair and CEO (M13, lane B)

Reece's decisions (2026-10-31, ADR-0019 §10–§12): the IPO is an event chain; public life runs on quarterly earnings that the player guides; when the founder steps up to Chair, the CEO runs day-to-day operations. ADR-0020 §7: listings, shares and prices belong to a `company_id`, so a subsidiary can list in v3. Stage 4 begins at the listing.

### 25.1 Eligibility

- **Stage 3,** ARR ≥ `ipo.min_arr` ($241M at real-world scale, the 2015–2024 median sales of US tech IPOs in 2025 dollars from Ritter's Table 4a; read × `economy_scale.money` as §48.1's thresholds are, about $20.5M in the game's economy; M43, PM ruling 2026-11-20; was $80M), and the last 4 quarters either profitable at the operating line or growing revenue ≥ 40% a year.
- **Board approval:** average director confidence ≥ 50 at the decision.

### 25.2 The IPO chain (an event chain; templates and LLM within §16)

1. **Hire banks** (immediate action, energy 10): choose a lead underwriter from `banks.yaml` (Goldman Sachs, Morgan Stanley, J.P. Morgan; each with a fee of 5.5–7% and a quality from 0.9 to 1.1).
2. **File (S-1),** month 1: a major event (regulator questions, restating a metric). Choices carry delay, cost and brand modifiers.
3. **Roadshow,** months 2–3: three major events whose choices set the ambition (price range high, middle or low), the share sold (10–25% of post-IPO fully diluted shares, new shares), and dual-class shares, which keep the founder's voting control but price 5% lower.
4. **Pricing** (month 4, a critical event):
   - **Fundamental value** `V_f` (§25.3) × bank quality × the ambition factor (high 1.15, middle 1.0, low 0.9) gives the offer price.
   - **Book demand** `d = clamp(N(1.0 + 0.6 × (v − 1), 0.2), 0.3, 3.0)`, where `v` is the venture climate (§20.1); stream `ipo` (id 33), key `(company_id,)`.
   - The player chooses to price at the range, raise it 10% (only if `d ≥ 1.3`), cut it 15%, or pull the IPO. Pulling costs the bank fee × 0.3 and damages board confidence (−10).
5. **Listing day:** first-day return `r = clamp(0.25 × (d − 1) − 0.15 × (ambition − 1)/0.15, −0.3, +0.8)`. The company raises `price × new shares` minus the bank fee (posted to `3000_common_equity`, net of fees). The closing share price after day one is `price × (1 + r)`.

### 25.3 Share price each month (phase 7; stream `market_sentiment` id 34, key `(company_id,)`)

- **Fundamental value:**

```latex
V_f = ARR \times m, \qquad m = clamp\big(2 + 25\,g + 15\,margin - 1.5\,(r_{base} - 2)\big,\ 1,\ 30) \times v
```

  with `g` the trailing annual revenue growth, `margin` the trailing operating margin, `r_base` the base rate in percent (§20.1), and `v` the venture climate.
- **Price:** `P = V_f / shares × S`. Sentiment `S` follows an AR(1) toward 1.0 (φ 0.9, shock sd 0.06), clamped to [0.5, 1.8], plus earnings jumps (§25.4).
- **Analysts:** 3–8, more as market cap grows. Each holds a rating (buy, hold or sell) and a target price, `V_f × (1 + N(0, 0.1))`, refreshed after each earnings report. Ratings follow `target / P`: above 1.15 buy, below 0.9 sell, otherwise hold.

### 25.4 Quarterly earnings and guidance

- **Guidance:** at each quarter start the player sets revenue and operating-margin guidance for the quarter (immediate action, energy 4). The default is the analysts' consensus, the trailing trend.
- **Report** at quarter end. With surprise `s = (actual revenue / guided revenue − 1)` and margin surprise `sm = actual margin − guided margin` (points):
  - sentiment jumps `S × (1 + clamp(3 s + 0.02 sm, −0.25, +0.20))`;
  - two consecutive misses (`s < −0.02`) cut every director's confidence by 8;
  - beating three quarters in a row adds +5 sentiment points.
- **Activists:** when `P` is below 0.7 × `V_f / shares` for 6 months, or after 3 misses in 4 quarters, an activist investor builds a stake. That starts a critical event chain: board seats demanded, a buyback or spin-off demanded, or a proxy fight.
- **Takeover interest:** when market cap stays below 0.6 × `V_f` for 6 months, a takeover-bid event can arrive. Accepting or fighting is handled as an event in M13; acquisitions themselves are M14.

### 25.5 Capital actions once public

- **Buyback** (energy 6): buy shares at `P × 1.02`. Cash leaves to `3000_common_equity` (treasury); shares outstanding fall.
- **Dividend** (energy 4): a cash amount per share, paid next month.
- **Secondary offering** (energy 10): new shares at `P × 0.95`, less a 3% fee.
- **Founder's stake:** shown as shares × `P` (personal wealth, read-only until v3's trading).

### 25.6 Chair and CEO

- **Appoint a CEO** (stage 4, energy 10): an employee at exec level, or an exec-level search. The founder becomes **Chair**.
- **What the CEO does.** Each month in phase 2, as a super-delegate (ADR-0015, §24), the CEO uses every authority the player allows: all five seats' functions (§24.1) plus product priorities (assigning teams, launching ready products, setting prices within ±10% of the player's last price) and hiring plans within headcount guardrails. CEO decision quality follows §24.2 with the CEO's score (weights: leadership 0.3, strategy 0.3, communication 0.2, product 0.1, finance 0.1).
- **The Chair keeps** capital decisions (rounds, debt, buybacks, dividends, the IPO and later M&A), executive appointments, guidance and strategy. An **override** of a CEO decision costs 6 energy.
- **The board and the CEO:** with confidence below 30 for 3 months, directors may vote to replace the CEO (an event). The founder as Chair can only be removed under §14.6's rules, with public-company seats.
- The founder's monthly energy as Chair is `ceo.chair_energy` (40). A Chair's job is fewer, larger decisions.

### 25.7 Stage 4 and the board

- Listing sets stage 4.
- **The board** gains two independent directors (generated people) and moves to a public mix: founder, two common seats, investor seats (lapsing one per year after listing as funds sell), and independents. Patience follows the analysts' consensus.
- **Board confidence** adds an earnings term: +4 per beat, −6 per miss, in the month of the report.

### 25.8 What the API may show

The IPO chain's status and choices; the price range and book demand as words ("strong demand", from `d`), never the draw; the share price and its history; market cap; analysts' ratings and targets; guidance against actuals; the founder's stake; the CEO's decisions and overrides. Never `V_f`'s components beyond what the analysts publish, future sentiment, or the takeover threshold.

### 25.9 Balance targets (M13 acceptance, printed)

1. All earlier targets pass as before (no new xfails).
2. **IPOs happen.** blitzscale and steady reach an IPO on at least 4 of 10 seeds each by turn 180 (15 years), with median first-day return 0–30%.
3. **Guidance matters.** A company that guides 10% above trend misses in at least 60% of quarters, and its median share price after 3 years is at least 15% below a company that guides at trend.
4. **Prices are believable.** The median price-to-sales multiple at listing is 15–30× in 2012–2019 and 25–45× in 2020–2021, falling at least 25% between Jan 2022 and Dec 2022. (Re-banded by Reece, 2026-11-19, M43 sub-task 3: with 25.1's ARR floor read at the game's economy, companies list young, about $7M of game ARR growing about 100% a year; was 4–15×, 8–25× and 30%.)
5. **The CEO runs things.** A CEO with score 14 and full authority keeps a stage-4 company within 15% of the scripted strategy's median ARR over 36 months, with the founder spending at most 40% of the Chair's energy.

### 25.10 Worked examples

**Fundamental value.** ARR $120M, growth 45%, operating margin −5%, base rate 1.5%, climate 1.2: `m = (2 + 11.25 − 0.75 + 0.75) × 1.2 = 13.25 × 1.2` = **15.9**, so `V_f` = **$1.908B**.

**Listing.** With 100M fully diluted shares before the IPO and 15% sold as new shares: 17.65M new shares. A middle-ambition offer at `V_f / 117.65M` = $16.22 raises 17.65M × $16.22 = $286M before a 6% fee ($269M net). Book demand 1.4 gives `r = 0.25 × 0.4` = **+10%**, so the stock closes day one at $17.84.

**Earnings.** Guidance $32M; actual $33M (`s = +3.1%`); margin on guidance: sentiment × `(1 + 0.094)`, a +9.4% jump.

### 25.11 Notes from the build (M13)

- **The chain's months.** Banks hired in month 0; the S-1 event in month 1 (restating a metric adds `ipo.filing_delay_months`); the roadshow's ambition and share-sold events together in month 2 and the share-class event in month 3; the book is drawn (stream `ipo`) in phase 7 of the month the last roadshow answer is given, and the pricing critical event follows in month 4. The company lists in phase 7 of the month the price is set (its `listed_turn`).
- **Events with engine choices.** The chain, earnings misses, activists, takeover bids and the board's CEO vote are `public` templates the engine queues by id (`data/events/public.yaml`). Each choice carries a `public_step` effect (a stat from a fixed list) that the engine applies. The LLM may write a public event's title and body; its choices are always the template's.
- **Pricing in three choices.** Templates allow at most three choices (16.3), so pricing has two templates: with `d ≥ 1.3`, price at the suggestion, raise 10% or pull; otherwise, price at the suggestion, cut 15% or pull. The Pricing card shows all four with the unavailable one greyed out.
- **First-day ambition.** In step 5's `r`, `a` is the final price over the fair price `V_f / shares` × bank quality (before the dual-class discount), so a raise or a cut moves the first day as ambition does.
- **Shares.** New shares are common, held by "Public shareholders" on the cap table; `V_f / shares` uses fully diluted shares (pool and options included). Dividends are paid on issued shares (pool and unexercised options excluded). Preferred shares do not convert at the IPO yet (follow-up).
- **Analysts.** 3, plus one for each doubling of market cap above `public.analysts.base_cap_cents` ($1B), at most 8. Ratings follow `target / P` every month; targets refresh at listing and after each report.
- **Earnings.** A beat is `s ≥ 0`, a miss `s < −2%`, anything between is in line. The consensus is the last quarter's revenue grown at a quarter of the trailing year's growth, and the trailing year's margin. Guidance must lie within ±50% of the consensus. The second miss in a row (and each while the streak lasts) costs −8 on top of −6. Every third beat in a row adds +0.05 to sentiment.
- **Activists and takeovers.** Once triggered, each waits 24 months before it can trigger again. An activist's choices are a board seat, a buyback of 10% of cash, or a proxy fight costing 1% of cash. A takeover bid can be rejected, met with a rights plan, or answered with talks (sentiment × (1 + 35% premium × 0.5)); nothing is sold before M14.
- **The public board.** Each year after listing, one investor seat lapses: its director stays as an independent without the fund's patience. Dual-class shares stop a board vote from removing the founder.
- **Chair and CEO.** The CEO runs each function in its scopes that no seat holder with authority covers, under that seat's guardrails, with `ceo.price_band_pct` around the player's last price. It acts only through operating actions (plans, moves, prices, marketing, launches); debt repayment and every capital, guidance, strategy or appointment action is the Chair's. An override applies the decision's reverse as the Chair at exactly `ceo.override_energy`, and the CEO's price anchor follows the Chair's price. Launches cannot be overridden. The Chair's energy (40) applies from the month after the appointment.
- **Stage 4 elsewhere.** Hiring's stage-keyed appeal and equity values treat a public company as stage 3 (no `hiring.*` key changes in this lane).
- **Trailing history.** The player's monthly operating result is kept for 12 months (was 6), for 25.1's four quarters.
- **Tuned for 25.9 (M13).** `public.multiple`: growth 25 → 18 and margin 15 → 5. The scripted companies list at +30–40% margins, which gave P/S 20× at listing in 2012–2019; the 25.10 worked example keeps 25.3's coefficients. `ipo.min_growth` 0.40 → 0.20: blitzscale passes $80M ARR loss-making and growing 20–25% a year, and never listed at 40%.

## 26. Hardware, devices and fabless chips (M12b, lane A)

Reece's decisions (ADR-0019 §8, §13): factories are allowed from the start, alongside contract manufacturing; an early factory is likely unprofitable, and its spare capacity can be sold to others. Fabless chips sell to a chip market and go into the player's own devices and data centres. ADR-0020: assembly plants are a **kind** in M12a's facility model (`balance.facility.kinds`), components and foundry wafers are **goods** in `components_history.yaml`, and chips used in-house are internal supply at cost. Principle: **a company that never enters hardware plays as before.** M12b merges after M13.

### 26.1 Unit-sale categories (appended to `categories.yaml`, `revenue_model: units`)

| Category | Segments | Replacement cycle (base churn) | Development skill |
| --- | --- | --- | --- |
| Devices (`devices`: phones, laptops, wearables) | consumer, SMB, enterprise | 1/30 a month consumer, 1/40 SMB and enterprise | hardware design 0.40, manufacturing 0.20, design 0.20, software engineering 0.10, chip design 0.10 |
| Servers (`servers`) | enterprise, hyperscalers | 1/48 | hardware design 0.40, infrastructure 0.25, manufacturing 0.20, chip design 0.15 |
| Chips (`chips`) | device OEMs (new, sales-led), hyperscalers | 1/24 (design wins renew) | chip design 0.60, hardware design 0.20, software engineering 0.10, manufacturing 0.10 |

- **The market rules of §11.7 apply** with one change. A customer in play who chooses a product **buys one unit** (revenue `price × units`, once, to `4000_revenue_subscriptions`, renamed "Product revenue" in statements). The replacement cycle brings customers back into play.
- **Units are capped by manufacturing capacity** (§26.2). Demand above the cap is lost to the next-best product that month.
- **Launch** needs quality ≥ 30 and a manufacturing source (a contract or a live plant).
- **Expected features** move fast: ΔF of 8 for devices and servers, and 10 for chips. A hardware team must keep designing or the product ages.
- **Quality cap** uses M11's devices domain (devices and servers) and chip-design domain (chips) through `research.tech_factor`.

### 26.2 Cost of a unit and manufacturing

- **Bill of materials:** `bom = bom_base × good index` (goods `device_bom` and `server_bom`, appended to `components_history.yaml` with the 2021 shortage), plus the chip (§26.3: bought at the chip market price, or own at cost), plus assembly. It posts to `5000_cogs` when sold.
- **Contract manufacturing** (immediate action, energy 6): a contract with a contract manufacturer (Foxconn, Pegatron; data) for `V` units a month for 12–24 months, at a fee per unit (Shenzhen cheaper). Take-or-pay: 50% of the fee on unused volume each month. A contract signed before a shortage keeps 100% allocation.
- **Own assembly plant** (facility kind `assembly_plant`; unit `units/month`):
  - capex `$300 × equipment index` per unit a month of capacity; build 12 months; life 96 months;
  - operating cost `$20,000` a month fixed plus `$3` a unit;
  - staff: one manufacturing-role person per 1,000 units a month;
  - **yield** `0.85 + 0.10 × mean manufacturing skill / 20`, so assembly cost per good unit = (fixed + variable) / (units × yield).

  Building in a city uses M9's city (Shenzhen's manufacturing bonus applies to its hires).
- **Selling spare plant capacity:** category `contract_manufacturing` (segment device OEMs; customers buy units a month), like M12a's Cloud hosting. Quality is yield × reliability. Capped at spare capacity, sold against Foxconn and Pegatron as incumbents.

### 26.3 Fabless chips

- **Chip product types:** `mobile_soc`, `server_cpu` and `ai_accelerator` (a product attribute), with chips per wafer 600, 150 and 60.
- **Foundry wafers:** a good, `foundry_wafer`, with an index and allocation history: tight in 2021–2022, advanced nodes tight in 2023–2024. A wafer contract (as §22.4) secures wafer starts a month from TSMC or Samsung Foundry (abstract suppliers, not rivals).
- **Unit cost:** `wafer price / (chips per wafer × yield) + $8` for packaging and test, with yield `0.70 + 0.003 × chip-design lead` (M11), at most 0.92.
- **Chip demand:**
  - device OEM demand grows with the devices and servers markets;
  - hyperscaler `ai_accelerator` demand grows with the AI models market (§18.6, M11's AI eras);
  - `server_cpu` demand grows with general cloud capacity.
- **Internal use** (ADR-0020 §4): the company's own devices and servers can use its own chip of the matching type at unit cost (no revenue). Its own GPU data centres using its own `ai_accelerator` cut GPU capex per CU to `capex × (0.4 + 0.6 × own unit cost / market chip price)`.
- **Rivals** (appended to `incumbents.yaml`):
  - chips: NVIDIA (aggressive; AI accelerators), Intel (premium; server CPUs), AMD (fast_follower; server CPUs and accelerators), Qualcomm (premium; mobile SoCs);
  - devices: Apple (premium), Samsung (fast_follower), Lenovo (cost_leader);
  - servers: Dell (fast_follower), HPE (premium), Supermicro (cost_leader);
  - contract manufacturing: Foxconn and Pegatron.
- **Entrants** (appended to `entrants.yaml`): Cerebras (Jan 2016, AI accelerators) and Groq (Sep 2016, AI accelerators).

### 26.4 Eras (appended to M11's `eras.yaml`)

| Era | Domain | Historical arrival | What it accelerates |
| --- | --- | --- | --- |
| Smartphone ubiquity | devices | Jan 2012 | devices: consumer growth +15 points for 36 months |
| AI accelerators | chip design | May 2016 | chips: `ai_accelerator` demand growth +40 points for 36 months |
| Custom silicon | chip design | Nov 2020 | devices with their own SoC: +5 quality cap for 24 months (everyone, not first-mover only) |

**Future eras (seeded windows; Reece, 2026-11-02, ADR-0019 §15).** The first eras after 2025. Each has a public **window** instead of a historical date; its scheduled month is drawn from the seed and never shown.

| Era | Domain | Window | What it accelerates |
| --- | --- | --- | --- |
| Chiplets and advanced packaging | chip design | Jan 2026 – Dec 2028 | chips: the yield cap rises from 0.92 to 0.95 for everyone from arrival; `server_cpu` and `ai_accelerator` demand growth +15 points for 36 months |
| Edge AI | devices | Jan 2027 – Dec 2030 | devices: consumer and SMB demand growth +20 points for 36 months; `mobile_soc` demand growth +20 points for 36 months |

- **Data.** In `eras.yaml` a future era has `window: [[y1, m1], [y2, m2]]` in place of `arrival`. The loader rejects an era with both or neither, and a window that starts before 2026.
- **Scheduled month.** `t_sched = t_start + floor(u × n)`, where `n` is the number of months in the window and `u` is one uniform from stream `era_window` (id 31) at turn 0, key `(era_index,)`, with `era_index` its position in `eras.yaml`. It is a pure function of the seed, so nothing is stored and a save made before M12b gets the same months. Eras are only appended, so adding one never moves another's month.
- **Threshold.** It is computed from the window's **midpoint** `t_mid = t_start + floor(n / 2)`, not `t_sched`: `D_d(t_mid + 1)`, plus `rnd.era_baseline` for each era of the domain scheduled before it, plus `rnd.era_lead`. The threshold is shown, so it must not reveal the drawn month. "Scheduled before" uses historical months, or windowed eras' midpoints, never `t_sched`.
- **Arrival.** At `t_sched`, or earlier when a company's level reaches the threshold, exactly as in §21.4 (baseline +5, boosts, first-mover window, History).
- **API.** The Market era timeline shows a future era's window ("expected 2026–2028") and threshold. `t_sched` never appears in a response or an LLM prompt until the era has arrived; extend the hidden-value test to it.
- **Example.** Chiplets: window 36 months, `u = 0.40`, so `t_sched` = Jan 2026 + 14 = **March 2027**. The midpoint is `t_start + floor(n / 2)` = July 2027, so the threshold reads the chip-design baseline at the end of July 2027: 211 months from January 2010 at 1.5 a year, 30 + 26.375 = 56.375. With AI accelerators and custom silicon before it (+10) and `rnd.era_lead` (+15), the threshold is **81.375**.

### 26.5 What the API may show

Bill of materials and unit cost by line; contracts with volume, use and take-or-pay; plants with capacity, utilization (own and sold), yield and staff coverage; chips with type, yield, unit cost, internal use and market sales; wafer and component indexes with history only.

### 26.6 Balance targets (M12b acceptance, printed)

1. **Without hardware, nothing moves.** All earlier targets pass as before (no new xfails).
2. **Devices can work.** A 15-person devices company on contract manufacturing reaches a gross margin of 30–45% by year 3 on at least 6 of 10 seeds.
3. **Plants need volume.** An assembly plant's cost per good unit is at most 0.7 times the contract fee at ≥ 75% utilization, and at least 1.3 times at 30%.
4. **Own chips pay off.**
   - A devices company using its own mobile SoC has a device gross margin at least 8 points higher after 3 years than one buying chips.
   - An AI company using its own accelerators cuts GPU capex per CU by at least 20%.
5. **History bites.** A contract-manufacturing-reliant company with no contract signed before the 2021 shortage ships 15–35% fewer units in 2021–2022 than one with a contract.
6. **Incumbents hold.** NVIDIA holds at least 50% of hyperscaler `ai_accelerator` units in 2023 on at least 7 of 10 do-nothing seeds.

### 26.7 Worked examples

**Unit cost (device).** BOM $180 at index 1.0, a bought SoC at $40 and a contract fee of $13: **$233** a unit.

**Plant cost.** A 20,000 units-a-month plant at 80% use (16,000 units), yield 0.92: `($20,000 + 16,000 × $3) / (16,000 × 0.92)` = $4.62 per good unit, plus depreciation `20,000 × $300 / 96` = $62,500 a month, or $4.25 per good unit. Total **$8.87**, or 0.68 times a $13 contract fee. At 30% use (6,000 units, 5,520 good): `($20,000 + $18,000) / 5,520 + $62,500 / 5,520` = **$18.21**, or 1.40 times the fee.

**Chip cost.** An AI accelerator at a wafer price of $9,000, 60 chips per wafer and a chip-design lead of 20 (yield 0.76): `$9,000 / 45.6 + $8` = **$205.37**.

### 26.8 As built (M12b notes)

- **Chips as three categories.** Chip demand differs by type (26.3), so each type is its own category in `categories.yaml` (`chips_mobile_soc`, `chips_server_cpu`, `chips_ai_accelerator`; `family: chips`, `chip_type` the product's type). Segments: mobile SoCs device OEMs; server CPUs and AI accelerators device OEMs and hyperscalers. A chip's demand growth follows other markets by segment (`growth_follows`): device OEMs' mobile SoCs follow devices, server makers' chips follow servers, hyperscalers' accelerators follow AI models (with its eras) and server CPUs Cloud hosting; the mean of the followed categories' growth, plus the chip category's own era boosts.
- **Unit-sale markets.** `revenue_model: units` (devices, servers, chips): base churn is `1 / replacement_months` (devices 30 consumer, 40 SMB and enterprise; servers 48; chips 24); a new customer buys `units_per_customer` units (consumer 1; SMB devices 5, enterprise 50; servers 20 and 5,000; chips 500-50,000) once, revenue `units x price`. Customers are the installed base. Rivals' cost of goods is the market's `hosting_cents` a unit (40-45% of reference); the player's is its bill of materials, chip and assembly. No hosting in phase 6 for unit-sale products.
- **The capacity cap** applies to the player's companies (`player_companies`; rivals' manufacturing is abstract). Phase 5 builds a production plan from the state: plants' runnable units (live x staff coverage, each run unit `yield` good units, a server taking 6) and each product's contracts after allocation; wafer contracts' chips for chip products. Segments sell in categories.yaml order, best appeal first; a capped product makes what it can and its lost customers go to the next-best product that still can (uncapped rivals always can). Plants first, then contracts by id; a device takes its company's own live chip of its type first (devices sell before chips).
- **Costs at sale** (`5000_cogs`): BOM at this month's good index, chips (own at unit cost; bought at the chip category's device OEM reference price), contract fees, plants' $3 a unit run (also for contract-manufacturing customers). A plant's $20,000 fixed cost posts in phase 6 as "Assembly plant operations" to `5000_cogs`; its depreciation to `6700` (cost of revenue). Take-or-pay each month a contract runs, from signing: 50% of the fee on undelivered-or-unused assembly volume (on what was delivered but not used), 30% on unused wafers, to `6900_general_admin` (as M12a's).
- **Allocation.** A contract signed before the running shortage began (history's allocation period start, or a seeded shock's first month) gets 100%, else the good's allocation: device and server BOMs 70% in 2021-2022; wafers 70% in 2021-2022 and 60% in 2023-2024 for advanced nodes (server CPUs and AI accelerators; `advanced_only` periods).
- **Plants.** Kind `assembly_plant` in `facility.kinds` with `fixed_opex_cents`, `variable_cents`, own `sizes` (5,000-100,000 a month) and `outages: false`; the build action takes a city (Shenzhen's talent applies to hires there, M9). Yield `(0.85 + 0.10 x mean manufacturing skill / 20) x (1 + N(0, 0.01))` within 0.5-0.99, drawn in phase 4 on stream `manufacturing`. Staff are the unit's manufacturing engineers (new role). M12a's compute allocation, Cloud quality, Infrastructure screen and outages ignore plants.
- **Contract manufacturing market** (`contract_manufacturing`, `assembly_market: true`): like Cloud hosting, started from Hardware (energy as create_product), live at reference prices; a customer buys 10,000 units a month at $130,000. Quality is plants' yield x reliability; features held at `compute.feature_base + feature_per_lead x devices lead`. Customers are capped at the end of phase 5 by the plants' run units left after own products (all regions together).
- **Chips.** Yield from the company's chip-design lead, cap 0.92, 0.95 after Chiplets (`yield_cap`). Unit cost uses the running wafer contracts' locked prices weighted by wafer starts (this month's TSMC price without one). Mobile SoC wafers are $2,000 (mature node), server CPUs $8,000, AI accelerators $9,000. The GPU capex cut applies at the build quote while the company has a live AI accelerator; its chips are not consumed by the build (M12b decision).
- **Eras.** Custom silicon's +5 cap is an era boost (`cap_points`, `own_chip`) added in `tech_factor` for companies with a live own chip of the device category's type. A future era's `arrival` property is its window midpoint, so M11's migration 0028 and the rival research bonus read a public month; `levels.scheduled_turn` draws `t_sched` (engine only) and `arrive_eras` takes the RNG.
- **Key people.** The twelve hardware and chip incumbents have 4 named key people each (`key_people` in incumbents.yaml), not `rivals.key_people`'s 8, to keep the turn within its time budget (product manager, 2026-11-03); their pools take the rest of the budget.
- **Old saves** (0031) get M12b's eras on schedule if past them, but no hardware markets or incumbents (as M12a's Cloud hosting).

## 27. Executive ambition and visible eras (M13b)

Reece's playtest 2 (2026-11-03): executives and the CEO kept the company profitable on Holiday but never made big moves, their reports were lifeless, the CPO had nothing to delegate, and eras did not push his product over the edge. Decisions (2026-11-03): big moves are **proposed and approved** (on Holiday, those under a spend limit go ahead); eras get a **stronger, visible** first-mover effect; this comes **before M14**, so M14's CEO proposes acquisitions through the same system.

### 27.1 Pitches (big moves an executive proposes)

- **Who pitches.** A seat holder with authority (§24.1), and the CEO (§25.6) for any function. An executive without authority never pitches.
- **When.** Phase 2, at most one open pitch per executive and one new pitch per executive per quarter. Each quarter an executive pitches with probability `clamp(pitch.base + pitch.per_ambition × (ambition − 10), 0.05, 0.9)` (base 0.15, 0.01 per point, tuned for 27.5 target 7; first written as 0.45, 0.04 and a 0.15 floor; true ambition), one uniform on stream `pitch` (id 36), key `(person_id,)`.
- **What they pitch.** The best-scoring candidate of their function, scored from **displayed** knowledge only (ADR-0015):

| Seat | Pitch kinds | Candidate score (higher is better) |
| --- | --- | --- |
| CPO (new authority) | a **new product** in a category the company doesn't sell in; a **sunset** of a product below maintenance and shrinking for 6 months | new product: displayed category revenue at reference price × growth × fit, where fit = the company's displayed skill match for the category's builder skills (0–1) × (1 + 0.01 × research lead in the feeding domain) |
| CRO | **launch in a region** (§19.5) | the region's displayed demand for the product's segments × the company's fit (language, office) |
| CTO | a **research project** in a domain feeding live products; a **data centre** when projected use ≥ 60% for 24 months | research: products' revenue in the domain's categories × room to the quality cap; data centre: (spot − own cost per CU) × projected CU |
| COO | an **office** in a city with a deeper hiring pool for open plans; an **assembly plant** when contract volume ≥ 75% of a plant size for 12 months | open plans unfilled × the city's pool depth; plant: (contract fee − plant cost per unit at projected use) × units |
| CMO | a **campaign**: a one-off marketing push for a product with a brand gap | brand gap × the product's customers |
| CFO | as §24.1 (rounds, loans, early repayment), plus once public a **buyback or dividend** to the Chair | as §24.1 |

- **Quality.** With probability `clamp(0.55 + 0.03 s, 0.6, 0.98)` (§24.2) the executive pitches its best candidate, otherwise its second best. A strong executive's pitches visibly succeed more often.
- **The pitch** is an inbox item (major, blocks Continue under §23.1) in the executive's voice: what, why (two or three driver numbers), the cost (capex, monthly cost, hires), a **low and high case** (revenue or saving at 24 months, from displayed estimates ± the executive's uncertainty, wider for a weaker executive), the risk, and Approve, Modify (open the action's own dialog prefilled) or Decline.
- **Approve** runs the move through the normal actions as that executive (a new product gets a unit, a hiring plan for the CPO's suggested team and a launch target), within the seat's guardrails, and spends the executive's energy, not the founder's.
- **Holiday and the spend limit.** The player sets `auto_approve_cents` (default 5% of cash, 0 = always ask). On Holiday a pitch whose total cost over 12 months is under the limit goes ahead automatically and is reported; above it, it waits. Holiday stops only for pitches above the limit when the player has ticked "stop for big pitches".
- **Follow-through.** Each approved pitch is tracked against its low and high case for 24 months and scored **hit** (≥ low case), **miss** or **too early**. The executive's record (hits / pitches) shows on their profile and in reports. Declined pitches lower that executive's morale slightly (−2, once), more for high-ego executives (−4 at ego ≥ 15).

### 27.2 Reports with a voice

The quarterly report (§24.3) is rebuilt around decisions:
1. **What I did**: the quarter's delegated actions grouped by product, with their effect (for example "moved two engineers from Pipeline to Forge; Forge's quality 41 → 47").
2. **What I'm pitching** (or why not), with the status of earlier pitches (hit, miss, too early).
3. **What worries me**: one or two concerns tied to a number.
4. **The numbers**: the function's KPIs against last quarter and the target.

It is written by the LLM within §16's budget from engine-supplied facts only, in the executive's voice from **revealed** personality (a blunt high-ambition CRO, a cautious CFO); templates do the same with personality variants when the LLM is off. The CEO's report is a company letter to the Chair covering all functions.

### 27.3 Eras the player can feel

- **Stronger first-mover window:** `rnd.first_mover_months` 12 → 24, `first_mover_cap` 5 → 8, `first_mover_brand` 10 → 15, and a new **appeal bonus** `rnd.first_mover_appeal` (×1.15) on the first mover's products in the era's categories for the window. All tunable for 27.5 target 5, which tuned them to 24 months, cap +5, brand +6 and appeal ×1 (no bonus; the mechanism stays). The arrival item names the appeal only when it is above ×1.
- **On arrival:** a critical inbox item names the era, who caused it and how many months early, and lists the player's affected products with their new cap, brand target and appeal.
- **At the window's end:** an **era report**: the products' customers and MRR against their pre-era 12-month trend, the category's demand against its pre-era path, and what the window added.
- **Charts:** the Market demand chart and the Product trend chart mark era arrivals (a labelled vertical line).

### 27.4 Small items from playtest 2

- **Market size.** The Market screen and the New product dialog show each category's displayed size: customers × reference price per year, by segment and region, with growth. Public data, as demand already is.
- **Research lead wording.** The Research screen explains "lead" as "points ahead of the industry in this field; start a project to build one" (Reece read it as a person to hire).

### 27.5 Acceptance targets (printed)

1. **They make big moves.** A stage-3 steady company with all seats given authority, auto-approve at 5% of cash and Holiday for 36 months: at least one new product launched **and** one new region entered on at least 7 of 10 seeds.
2. **And it pays.** That run's median ARR at month 36 is at least 10% above the same run with pitches off (M10c's delegated baseline).
3. **Good executives pitch better.** Seat holders at score 15 against score 8: hit rate at least **10** points higher (product manager, 2026-11-04). Every pitch's hit is scored against its **central case** from displayed estimates, the same for every executive (not the executive's own low case). The approved move's execution follows the executing executive's **true** seat score through the existing seat factor (18.3): a new product's team pace (its builders' output) and a region launch's sales ramp (regional awareness and capacity). Calibration: `pitch.region_capture` scales the CRO's central case to what launches reach. A new product's central case counts **only the months after its expected launch** at the displayed development pace (product manager, 2026-11-04): skill-10 builders (output 1 each, Q_cap 50) start after `pitch.team_ready_months`, from start quality and no features, until quality and the feature score reach the launch bars, plus the CPO's launch month. The case is × (24 − launch months) / 24, and there is no pitch if launch falls outside the window. The segment share behind the case, `pitch.new_product_share`, is calibrated so the central case sits near a score-12 CPO's median 24-month outcome (0.04; 2026-11-05). The CPO pitches only self-serve segments, with the team size (from `pitch.team_builders` up to its headcount cap) whose case best covers its pay; a campaign's central case adds the category's organic growth; an office is measured by the staff who live in its city, above the count at approval.
4. **The inbox stays calm:** at most 8 pitches a year per company on median.
5. **The first-mover window pays.** Measured alone (product manager, 2026-11-04): the same seed with the era forced to the same early month, with and without the window. The window adds **25–60%** customers in the era's categories at the window's end (7 of the seeds where the era arrives early); `rnd.first_mover_*` is tuned into it. The full early-era effect (the era on schedule against pulled forward) is printed as information only.
6. **Nothing else moves.** Every earlier guard as before; the T2 xfail stays (M15). A company that gives no authority plays exactly as before (golden snapshots unchanged by sub-tasks 1–2).
7. **Pitches don't outplay the founder by far** (product manager, 2026-11-04). Target 1's run's median ARR at month 36 is at most **1.2×** the founder's **steady + regions** script on the same seeds: M10c's steady script (seats filled at score 15, no authority), plus a launch of its live product in the best region by the CRO's candidate score whenever the CRO's gates are met, at most one launch per 24 months (in the balance scripts only; no game code). If it is higher, `pitch.*` is tuned down; it was tuned to `pitch.base` 0.15, `per_ambition` 0.01, `chance_clamp` [0.05, 0.9].

### 27.6 What the API may show

Pitches with their reasons, costs and low and high cases; each executive's pitch record. Never the pitch probability, the quality draw, an executive's true ambition, skills or score, or which candidate was best.

## 28. Mergers and acquisitions (M14)

Reece's decisions (2026-11-05): **anyone can be bought** (startups, private incumbents and listed rivals, by friendly offer or hostile tender); after each deal the player **chooses** to keep the company as a separate brand or to integrate it; **antitrust** applies a market-share test. M13b's pitch system gets an acquisition kind. Principle: **a company that never buys plays exactly as before.**

### 28.1 Valuation (every company, every month, phase 7)

- **Fundamental value** for any company uses §25.3's formula: `V_f = ARR × m`, with the company's own trailing growth and margin, the base rate and the venture climate. A company with ARR below $1M is valued at its cash plus `mna.min_value_per_builder` ($150,000) per builder on staff (acqui-hire value).
- **Listed rivals** (`listed_from: [year, month]` in `incumbents.yaml` and `entrants.yaml`, following history: for example Facebook from May 2012, Atlassian from December 2015; private companies have no field) have a **market cap** `V_f × S`, with sentiment `S` as §25.3 (stream `market_sentiment`, keyed by the rival's stable key). Their market cap is public.
- **Private companies** (startups, and incumbents never listed or not yet listed) show an **estimated value range**: `V_f × (1 ± mna.range)` (±30%), centred off the true value by a seeded offset (stream `mna`, the same rule as §21.10's lead ranges), so the midpoint is not the truth.

### 28.2 Due diligence (immediate, energy 6; 2 months; cost 0.5% of the target's estimated value, at least $50,000, to 6100 professional fees)

- Narrows the value range to ±10%.
- Reveals the target's key people as candidates are revealed by scouting (§5): skill ranges, known traits, for the player's knowledge.
- Reveals each product's quality and feature score as ranges ±5, and any **hidden problem** the target carries: `tech_debt` (quality −10 over the first year after closing), `key_person_risk` (one key person's flight chance doubled), `customer_concentration` (churn ×1.5 for 12 months after closing). Each target has each problem with probability `mna.problem_p` (0.15), drawn when it is first looked at (stream `mna`). Without diligence, problems are discovered after closing.

### 28.3 Offers

- **Make an offer** (immediate, energy 10): price, and consideration: **cash**, **stock** (only once the player is listed: new shares at the current price, posted to the cap table) or a mix. Financing from cash on hand, or a bank loan taken first (§20.3).
- **Private target.** It accepts when the price is at least its **reservation** `V_f × (1 + p)`, where `p` = `mna.premium` by personality (aggressive 0.50, premium 0.40, fast_follower 0.30, cost_leader 0.20; a startup founder 0.25 + 0.02 × (ambition − 10)), minus `mna.distress_discount` (0.25) when the target's cash covers fewer than 6 months. Below it, the target counters at its reservation × (1 + N(0, 0.05)) once; a second offer below the counter ends talks for 12 months.
- **Listed target, friendly.** Its board accepts when the premium over market cap is at least `p_board = 0.30 + N(0, 0.05)` (drawn once per approach). Shareholders then approve (always, above the board's bar).
- **Listed target, hostile tender** (energy 15; the player must be listed or hold cash for the whole price): succeeds with probability `clamp((premium − 0.15) / 0.5, 0, 0.9)`, minus `mna.defence` (0.20) for an aggressive target. A failed tender costs 1% of the price in fees and blocks a new bid for 12 months.
- **Closing:** 1 month after acceptance, or after antitrust review (§28.4). At closing the price posts (cash out; or new shares), the target's cash and debts transfer, and goodwill = price − the target's book equity posts to a new **1800 goodwill** account (no amortization; impairment is a follow-up).
- **Draws** on stream `mna` (id 37), key: the target's stable rival key (ADR-0013 amendment), or the company id for the player.

### 28.4 Antitrust (market-share test)

- For each segment, region and category where both companies sell, combined share `S_c` = acquirer's share + target's share (customers).
- `S_c < antitrust.review` (0.35) everywhere: cleared.
- The highest `S_c` in `[0.35, 0.50)`: a **review** of 3–6 months (uniform, stream `mna`), then blocked with probability `(S_c − 0.35) / 0.15 × strictness(year)`, with `strictness` from `antitrust.strictness` by year (2010–2019 0.6, from 2020 1.0; history, then flat).
- `S_c ≥ antitrust.block` (0.50): **blocked** unless the player accepts a **remedy**: divest the target's (or its own) overlapping product in that market. A divested product goes to the rival with the next-largest share in the segment, with its customers.
- The review and its outcome are events; the player may abandon during review (fees only). Rivals' deals use the same test.

### 28.5 After closing: the player's choice (once, at closing)

**Keep as a brand (subsidiary).**
- The target stays a company in the state with its own ledger, pools, key people and personality, with `parent_id` = the player's company. Its revenue, costs and cash consolidate in the player's statements (a "Subsidiaries" line, and a column per subsidiary on the Finance screen); its cash sweeps to the parent each month above 3 months of its costs.
- It decides with the rival decision code (§15.3) under a **directive** the player sets (energy 2): **grow** (aggressive), **harvest** (cost_leader, margin first) or **defend** (premium). Its products keep their names and brands. The player can move its key people into the parent's org (they become ordinary employees).
- Culture clash is low: its key people's flight chance is `integration.flight_brand` (3%) a month for 12 months.
- This is the per-company model M16 will extend with separate cap tables and boards (ADR-0020).

**Integrate (fold in).**
- Its products move to the player with their customers, quality, features and brand (brand blends toward the player's at 10% a month). Its key people become the player's employees in a new unit per product.
- **Only targets with at most `integration.max_staff` (250) staff** (key people and pools) can be integrated; larger ones must be kept as a brand (their key people may still move), and the Integrate control says why (product manager, 2026-11-05).
- Its **staff**: each acquired product keeps its share of the target's staff by revenue (all of it for a one-product target); then, by function, some are let go: sellers and marketers `integration.synergy_overlap` (0.40) where the acquirer already sells in that category, `integration.synergy_new` (0.15) otherwise; builders `integration.synergy_builders` (0.10); key people in other functions `integration.synergy_other` (0.30). Kept pool staff become generated individuals at the pool's skill and pay (stream `people_gen`, keyed by the target's stable key); those let go get severance of 3 months' salary (one-off, to 6000 payroll). That is the cost synergy (2026-11-05; it replaces the maintenance-line rule).
- **Culture clash:** for 12 months, acquired people's morale moves toward the player's by `integration.clash` × the personality distance between the companies (0–1), and each acquired key person leaves with chance `integration.flight_base` (2%) + 6% × distance a month (stream `integration`, id 38, key `(person_id,)`).
- **Customers:** churn × `integration.churn_mult` (1.3) on the acquired products for 6 months.
- **Technology:** the player's research lead in each domain becomes the higher of the two, plus 20% of the lower.

### 28.6 Being acquired, and rivals' deals

- **A takeover bid for the player** (§25.4) can now be **accepted**: the company is sold, and the game ends with an **exit** ending (the founder's proceeds from their stake, the price and the History). Rejecting and the rights plan work as in M13.
- **Rivals' M&A** (phase 2, stream `rival_mna` id 39, key: the acquirer's stable key): an incumbent with cash above 12 months of costs considers one startup a quarter in its categories, with probability `mna.rival_rate` (0.04), and buys it at its reservation if antitrust clears; the startup always integrates. History logs it and the Market news shows it.

### 28.7 Pitches (M13b) and the CEO

- **CEO** and **CPO** pitch acquisitions: the CEO any target; the CPO only startups priced under the auto-approve limit × 4. Candidate score: the target's displayed revenue in the acquirer's categories × fit (§27.1) ÷ estimated price, with antitrust risk shown. The pitch's central case is the target's displayed revenue at 24 months plus synergy (integration) or without (brand).
- Acquisitions never auto-approve on Holiday, whatever the limit.

### 28.8 What the API may show

Market caps of listed companies; value ranges for private ones (narrower after diligence); a target's revealed people and products as ranges; offers, counters, review status and outcomes; subsidiaries' statements; integration progress (people kept, let go, departed). Never `V_f`'s components for private companies, a reservation price, `p_board`, a tender's success chance, a hidden problem before diligence or closing, or a review's block probability.

### 28.9 Balance targets (M14 acceptance, printed)

1. **Nothing moves without deals.** All earlier targets as before; golden snapshots unchanged by sub-tasks 1–2; T2 stays the known miss (M15).
2. **Prices are sane.** Accepted private deals at 1.0–1.6 × `V_f`; listed friendly deals at a 25–50% premium over market cap (median of scripted deals over 10 seeds).
3. **Integration costs something.** Integrated deals lose 10–30% of acquired key people within 12 months (median); brand deals at most 10%.
4. **Integration saves something.** Integrated deals cut the acquired cost base by 15–35% within 12 months.
5. **Buying helps but doesn't dominate.** A new balance arm "acquirer" (steady + regions, plus one startup in its categories a year when cash covers 18 months, integrated) ends year 10 with median ARR 1.0–1.4 × "steady + regions" (M13b's arm).
6. **Antitrust bites.** A scripted deal to over 50% combined share is blocked without a remedy (deterministic test); deals at 40% are blocked on 15–50% of seeds after 2020.
7. **The market consolidates a little.** Incumbents buy 1–4 startups per decade in total (median over 10 do-nothing seeds), and the M5 living-market guard still passes.

### 28.10 Worked examples

**Startup price.** ARR $4M, growth 60%, margin −20%, base rate 2%, climate 1.0: `m = 2 + 25 × 0.6 + 15 × (−0.2) − 0` = 14, so `V_f` = $56M. A fast_follower founder with ambition 14: `p = 0.25 + 0.08` = 0.33; reservation **$74.5M**. With 4 months of cash: `p = 0.08`, reservation **$60.5M**.

**Antitrust.** In SMB CRM (North America) the player holds 22% and the target 20%: `S_c` = 0.42, a review; in 2022, block probability `(0.42 − 0.35) / 0.15 × 1.0` = **0.47**. In 2015 it is 0.47 × 0.6 = **0.28**.

**Integration flight.** Personality distance 0.5: each acquired key person leaves with chance 0.02 + 0.03 = 5% a month; over 12 months `1 − 0.95^12` = **46%** of them at most if none is retained, before the player's retention actions (raises and promotions lower it as §8's resignation rules do).

### 28.11 As built (M14 notes)

- **Accounts.** Diligence and a failed tender's fees post to `6900_general_admin` (the chart has no professional-fees account; 6100 is rent). Goodwill is `1800_goodwill`; a kept brand's book equity at closing sits in a new `1810_investment_subsidiaries`, which cash sweeps reduce and consolidation replaces with the brand's net assets.
- **Valuation.** `V_f` reads completed months (the last month's MRR, trailing growth and margin; rivals now record their monthly operating result for the margin). A listed rival's sentiment starts at 1 in its first listed month and steps each phase 7 on `market_sentiment` keyed by its stable key (the player's call site is shared). Private ranges are rounded outward to two significant figures of their high end, so nearby true values show the same range and the display is no oracle; the range always contains `V_f`.
- **Draws.** Stream `mna` keyed by the target's stable key and a tag: the range offset and the three hidden problems are fixed per target (turn 0 of the master seed), equivalent to drawing them when first looked at but independent of viewing; the counter, board bar, tender and review draw at the month of the bid. A product's revealed quality and feature ranges (after diligence) are off-centre by a fixed draw the same way.
- **Offers.** The mode (brand or integrate) is chosen with the offer and can change until closing, when it is final; without a choice it integrates. Once a target has countered, the counter is the bar: a later offer below it ends talks for 12 months even if it clears the hidden reservation. Counters are whole dollars, rounded up. A startup's premium uses its founder's true ambition; other companies use their personality. The board's bar is drawn once per approach and reset when a deal is agreed. A tender's outcome is drawn at the bid. A deal agreed in a month closes at that month's end (the next Continue); the cash part must be on hand then, or the deal falls through.
- **Antitrust.** Markets are (category, segment, region), home and abroad; a kept brand's customers count for its parent. A review's length and outcome are drawn when the deal is agreed; it ends at the end of its last month, then the deal closes or is refused (final). The remedy divests the target's overlapping product (not the acquirer's) to the rival with the next-largest share there, with its customers, and the deal is screened again.
- **Integration.** One new unit per product; key people spread over the units in employment order. Pool staff kept per product: its revenue share of each pool (equal shares with no revenue), less the function's synergy (sellers and marketers at the overlap rate when the acquirer sells in the product's category outside the acquired products), rounded per product; generated at the level whose skills sit nearest the pool's (below 8.5 junior, 11.5 mid, 14 senior, else staff) and paid the pool's rate (the function role's mid salary). Key people in roles with no product function: `synergy_other` of them let go, the lowest paid first, with severance at their own pay. Pool severance is 3 months at the function role's mid salary. The 250-staff limit is checked at the bid, at a mode change and again at closing (a target that grew past it becomes a brand); rivals buy only startups within it; an acquisition pitch proposes a brand for a larger target. A static incumbent product starts developing (its held feature score becomes feature points). The churn penalty is an M10b churn modifier on each product (+30% for 6 months; `customer_concentration` stacks +50% for 12). `tech_debt` takes quality down by 10/12 points a month for 12 months; brand blends 10% a month toward the acquirer's average product brand. The target closes (its books zeroed into equity) and its people's employments end as "acquired". `key_person_risk` names the target's best-paid key person.
- **Culture distance** is the mean gap between the two companies' average personality traits, over `integration.distance_span` (4) attribute points, capped at 1. Clash moves morale `integration.clash` (0.1) x distance of the gap a month. Flight, clash and cash sweeps start the month after closing; flight is tracked for the player's acquisitions only.
- **Brands** keep `parent_id`, are not listed and cannot be bought by others; they decide with the rival code under the directive's personality (grow aggressive, harvest cost_leader, defend premium) and never poach their parent. Consolidated statements: the parent's lines without 1810, each brand's balance-sheet accounts at its closing month as opening lines, then its later lines without equity accounts (a sweep stays inside the group).
- **Exit.** Opening talks on a takeover bid queues `takeover_offer` (data/events/deals.yaml) for the next month; accepting sells every share at the share price x (1 + `public.takeover.premium`) to the rival with the highest revenue, recorded as a closed deal; the game ends with outcome `exit` and the founder's proceeds are their shares at that price.
- **Rivals' deals** run in a quarter's first month: incumbents (not brands) with cash above 12 months of costs; one uniform for whether, one for which eligible startup; price is the startup's reservation; only below the review line; the deal closes in the same month's phase 7. The startup's pools merge into the buyer's (skill weighted by headcount); moved employments keep rival ids.
- **Pitches.** The acquisition kind is the CPO's (the CEO pitches it through its products scope). Score: displayed revenue in the acquirer's categories x fit / price, times the central case x 24 so it ranks with other kinds; central case: that revenue grown 24 months plus `mna.pitch_synergy` x the target's monthly costs. Approval bids the displayed range's high end (a listed target: market cap x (1 + `mna.pitch_bid_premium`)). Acquisitions never auto-approve.
- **Brands' cash (Reece's playtest 3, 2026-11-06).** After the sweep, the parent pays a brand's cash shortfall each month, up to `mna.funding_months` (1) of its monthly costs and the parent's cash (parent: Dr 1810, Cr cash; brand: Dr cash, Cr equity). A brand never counts insolvent months while its parent's cash covers the shortfall. `mna.loss_warning_months` (3) consecutive operating losses since closing raise one warning per streak.
- **Screening notes (playtest 3).** Every agreed deal of the player's gets an inbox note with its antitrust result: cleared with no overlapping market, cleared under `antitrust.review` (share and market named), under review, or blocked with the remedy. The answer's title leads with the outcome.
- **Group companies and feuds (29.4, 2026-11-05).** A player's company and its kept brands are never rivals for feuds, statements, jabs or head-to-head launches; a feud with a company resets to 0 at its closing; people moving because of an acquisition (reason `acquired`) never count as poaching.
- **Tuned keys (28.9).** `integration.flight_brand` 0.03 -> 0.007 and `integration.flight_base` 0.02 -> 0.01 (target 3); `mna.rival_rate` 0.04 -> 0.008 (target 7), then 0.005 at the lane merge (M12a's living-market guard). Target 4 is measured on payroll (salaries, benefits, offices and tools of the people who came over, 12 months on, against the target's at agreement) over every integrated deal; the 2026-11-05 synergy keys land it in band untuned. The 28.10 examples keep 28.5's values and their tests pin them.

## 29. People and press (M14b, lane B)

Reece (2026-11-03 and playtest 2): press and media matter, with **public promises about technology and products**; one-on-ones and private promises are not wanted. Rival founders become characters. Three recruitment fixes from playtest 2 ride along. Principle: **press raises the stakes of what the company already does**; it never replaces a system.

### 29.1 Press moments (events, category `press`)

- **Triggers** (each a press template the engine queues): a product launch; a quarterly earnings report once listed (§25.4); an era arrival the company caused (§27.3); a critical outage (§22.5) or security breach; layoffs of 10% or more; an acquisition announced (M14 adds the trigger when it merges); a rival CEO's public jab (§29.4). At most `press.max_per_quarter` (2) a quarter; the rest are skipped, highest stakes first.
- **Each moment is an interview** with three tones and an optional promise:
  - **Bold**: brand target +`press.bold_brand` (3) for 6 months, and an aggressive rival named in it may respond (§29.4); if results contradict the claim within 6 months (the product's share falls, a miss once listed), credibility −`press.bold_backfire` (6).
  - **Measured**: brand target +1; no risk.
  - **Deflect**: credibility −2; ends the moment.
- **Audience** scales every press effect: `a = 0.5` at stage 1–2, 1.0 at stage 3, 1.5 once listed.

### 29.2 Public promises

- **Kinds** (made in a press moment, at most `promise.max_open` (3) open at once):
  - **Ship:** launch product X (in development) by a date, 3–18 months out.
  - **Beat:** product X's displayed quality above rival Y's displayed quality by a date.
  - **Research:** reach a level in a domain, or cause an era, by a date.
  - **No layoffs** for 12 months.
  - **No price rise** on product X for 12 months.
- The engine checks each promise at its deadline (or when broken earlier, for no-layoffs and no-price-rise) from **displayed** values only, so the player can always see where a promise stands.
- **Kept:** brand target +`promise.kept_brand` (4) × `a` for 12 months, credibility +`promise.kept_cred` (5) × `a`; staff morale +2 for no-layoffs.
- **Broken:** brand target −`promise.broken_brand` (8) × `a`, credibility −`promise.broken_cred` (10) × `a`; once listed, sentiment −0.05 × `a`; for no-layoffs, every employee's morale −5 and trust in the founder (relationships) −10. A press reminder event follows within 3 months ("you said …").
- Bigger promises (shorter deadlines, harder targets) pay more: the kept bonus × `1 + promise.ambition` (0–1, from how far the target is from today's value, displayed). Breaking costs the same either way.

### 29.3 Credibility

- A public stat 0–100 per company, starting at 50, drifting 1 a month toward 50.
- **Effects:** brand gains from press × `(0.5 + credibility / 100)`; once listed, the analysts' consensus uses the player's guidance at weight `credibility / 100` (the rest is §25.4's consensus); hiring appeal +`press.cred_hiring` × (credibility − 50) / 50 (at most +0.05).
- Shown on the Overview with its last five changes and their causes.

### 29.4 Rival founders as characters

- **Each rival has a named CEO:** the key person with the highest leadership skill at an incumbent (re-chosen if they leave), the founder at a startup. Their personality is the person's; their company's personality still decides (§15.3).
- **Public statements:** at a press moment that names a rival, and at the rival's own launches and price cuts, its CEO may make a statement (LLM within §16's budget from engine facts, or a template in their voice).
- **Feud** between the player's founder and each rival CEO, 0–100: + `feud.bold_mention` (10) when a bold answer names them, +8 for a head-to-head launch in a segment both sell in, +15 for poaching their key person (either way), +20 for a hostile bid (M14); −2 a month. **Rivalry** at 50: the rival's decisions weight actions against the player's products ×`feud.target_mult` (1.5), it poaches from the player first, and storyline events follow (§16). Feud and its causes are public on the Rival screen.
- Draws on stream `press` (id 40), key `(company_id,)` for the player and the rival's stable key for rivals.

### 29.5 Recruitment fixes (playtest 2)

- **Replace (recruiter):** when an employee resigns or is poached and a recruiter is on staff, a Replace button opens a hiring plan with the role and level prefilled; with a recruiter the search takes `recruit.replace_speed` (0.6) of the normal time.
- **Search by interest:** a hiring plan may filter candidates by one interest, at `recruit.interest_fee_bp` (15% of the role's mid salary) per search; candidates' interests are those already revealed (§5).
- **Leadership fit** on the org chart and People screen: a 1–5 star range from **revealed** leadership, mentoring, communication and temperament (a range when any is unrevealed).

### 29.6 What the API may show

Press moments and choices, open promises with their displayed progress and deadline, credibility and its history, rival CEOs, statements, feud scores and causes, leadership-fit ranges. Never a backfire before it happens, true skills behind a fit range, or a rival's decision weights.

### 29.7 Balance targets (M14b acceptance, printed)

1. **Nothing else moves.** All earlier guards as before; T2 stays the known miss.
2. **Promises matter.** Over 10 seeds on a listed company, keeping three promises gives brand +5 to +15 more than making none at 24 months; breaking three gives −10 to −25, and sentiment 5–15% lower.
3. **The inbox stays calm:** at most 6 press moments a year (median).
4. **Rivalries happen:** in 10-year steady runs, at least one feud reaches rivalry on 5–9 of 10 seeds; a rivalry raises that rival's actions against the player by 20–60%.
5. **Replace helps:** time to fill with a recruiter's Replace is 30–50% shorter than a normal search.

### 29.8 Worked examples

**A kept promise, listed.** `a` = 1.5, ambition 0.4, credibility 60: brand target +4 × 1.5 × 1.4 × 1.1 = **+9.2** for 12 months; credibility +7.5.

**A broken no-layoffs promise, stage 3.** `a` = 1.0: brand target −8, credibility −10, every employee's morale −5.

## 30. v2 close-out: balance, long campaigns and game modes (M15a, M15b)

M15 closes v2 in two lanes (Reece, 2026-11-05: "build as much as we can at the same time"). **M15b** (lane B, merges first) adds the game modes and polish: the company score, Sandbox, historical scenarios, industry rankings, "continue until something needs me", and the History and glossary audit. **M15a** (lane A, merges second) is the v2 balance pass: new strategies, 30-year runs, eras to 2039, the known misses and the research check, measured on the combined code. Reece's playtest 3 notes (after `m14-done`) are added as an addendum to whichever lane they touch.

### 30.1 Company score (M15b)

A public score, 0–1,000, for any company, computed each December and at a game's end:

```latex
score = 400\,\frac{\log_{10}(\max(V, 10^6)) - 6}{6} + 200\,G + 150\,P + 150\,L + 100\,R
```

- `V`: market cap if listed, else `V_f` (§28.1), in dollars; $1M scores 0, $1T scores 400 (clamped to 0–400).
- `G`: growth, `clamp(trailing 3-year revenue CAGR / 0.5, 0, 1)`.
- `P`: profitability, `clamp((trailing operating margin + 0.2) / 0.5, 0, 1)` (−20% scores 0, +30% scores 1).
- `L`: leadership, the share of the company's markets (segment × region × category it sells in) where it holds the largest share, weighted by market revenue.
- `R`: reputation, `(mean brand + credibility) / 200`, from public values.

Rivals' scores use the same formula, so rankings and scenario goals compare like with like. **The founder's personal outcome** (the founder value used by T2) stays separate: the score rates the company, T2 rates the founder's result.

**Example.** A listed company worth $40B, 3-year CAGR 30%, margin 18%, leading markets with 35% of its revenue, brand 70 and credibility 62: `400 × (10.602 − 6)/6` = 306.8; `200 × 0.6` = 120; `150 × 0.76` = 114; `150 × 0.35` = 52.5; `100 × 0.66` = 66; score **659**.

*M15b note.* `V` for a private company is the midpoint of its displayed value range (§28.1), not `V_f`, so the score reads public values only. `G` compares trailing 12-month revenue with the December snapshot three years back (or the oldest one at least a year back); `P` is the trailing 12 completed months' operating result over revenue (`score.trailing_margin`); `L` weights each market led by its revenue (`score.market_revenue`); `R` takes credibility as `press.cred_start` when it has no record. Snapshots live in `company_score` (data dictionary, `0035_m15b`). Code: `backend/tst/sim/score.py`.

### 30.2 Sandbox (M15b)

A new-game mode (spec §3): choose the start year (2010–2025, with history to that date and the world built as it stood, as the fixture tools already do), starting cash, difficulty, how many rivals (none, half, all), and eras historical or all seeded. No campaign end (play past 2039 with seeded macro, supply and eras), the board cannot remove the founder (spec §17), and the company score is shown but the save is marked Sandbox and kept out of the Hall of Fame.

*M15b note.* The world before the start month is played in memory with the player's company dormant, then the founder is rebuilt at the start (`tst/sim/modes/world.py`); a Y start's world matches a 2010 game's in Y (tested). "Half the rivals" keeps every other company in each category by id (`sandbox.rival_share_half`); removed rivals close as a failed rival does. "All seeded" gives each historical era due after the start a window of its month ± `sandbox.era_spread_months`, drawn from stream `era_window` as future eras are. The Saves list keeps a Sandbox score out of comparisons.

### 30.3 Historical scenarios (M15b)

Each scenario is a start (year, company, cash, staff, products, research, rivals' state) and a goal with a deadline, data in `backend/data/scenarios.yaml`, built with the same world-building code as Sandbox:

| Scenario | Start | Goal |
| --- | --- | --- |
| The AI lab | Jan 2015, a 12-person AI research startup with a Series A | $100M ARR by Dec 2020; causing the Transformers era first is a bonus shown on the result screen, not a win condition (M15r addendum d) |
| Mobile first | Jan 2011, a consumer-app startup of 4 | 1M consumer customers by Dec 2014 |
| Survive 2022 | Jan 2021, a growth-stage SaaS with venture debt and 20 months of runway | still solvent with a positive operating margin in Dec 2023 |
| The chip startup | Jan 2016, a fabless chip startup with a Series B | 10% of AI accelerator units by Dec 2023 |
| The turnaround | Jan 2018, a stage-3 company losing money with a weak executive team | an operating profit by Dec 2020 without a down round |

The result screen shows success or failure, the company score at the deadline and a short History. Scenarios use difficulty "standard" and normal rules.

*M15b note.* Starts are in `scenarios.yaml`'s `historical:` section; staff are generated from stream `scenario` (43). A reach goal (era or ARR, customers, unit share) ends the scenario a success in the month it holds; solvency and profit goals are judged only at the deadline's month end; any other game end (bankrupt, removed) is a failure. `save_meta.game_state` becomes `scenario_done`. Code: `tst/sim/modes/scenarios.py`.

### 30.4 Industry rankings (M15b)

Each January, three lists are published as news and on a Rankings screen:
- **Top 50 by revenue**: every company.
- **Best places to work**: the top 20 by mean morale, pay against market and tenure (companies of 50+ staff).
- **Most innovative**: the top 20 by research leads, eras caused and launches in the last 3 years.

Effects: a top-10 place in Best places to work adds `rank.hiring` (+0.03) to hiring appeal for the year; a top-10 place in Most innovative adds `rank.brand` (+2) to the brand target for the year.

*M15b note.* Lists are built at December's month end and dated January. Best places to work uses revealed morale and pay against the market of key staff (pools count toward size, `rank.places_min_staff`); Most innovative sums research leads, eras caused and launches over `rank.years`, each capped. A rival CEO's profile piece follows a rival's first entry into the revenue list (addendum 12). Code: `tst/sim/modes/rankings.py`.

### 30.5 Continue until something needs me (M15b)

A button and CLI flag that advances turn by turn until an item needs the player (a blocking inbox item, a pitch above the auto-approve limit, a critical event, a promise coming due, a deal decision) or up to 12 months. Unlike Holiday it delegates nothing: decisions not made wait in the inbox.

*M15b note.* Stops, in order: the game ended, a critical event, a major event, a pitch above the auto-approve limit, an executive's proposal, a promise due, a deal waiting; otherwise after `modes.continue_until.MAX_MONTHS` (12). Each month runs as Continue does (one transaction a month). API `POST /continue-until`; CLI `tst advance --until-needed`.

### 30.6 v2 strategies (M15a, balance scripts only)

| Strategy | Plays as |
| --- | --- |
| steady_regions | M13b's arm: steady plus region launches |
| research_heavy | steady_regions, plus a research unit of 6 (12 from stage 3) on the domain feeding its products, pulling eras when it can |
| acquirer | M14's arm: steady_regions plus one startup a year in its categories when cash covers 18 months, integrated |
| integrator | steady_regions, plus its own data centre when compute spend passes $200k a month, and devices with its own plant when it sells hardware (the partial vertical integrator) |
| ceo | steady_regions with all seats given authority and a CEO appointed at stage 3, the founder as Chair (auto-approve at 5% of cash) |

With v1's do_nothing, bootstrap_frugal, steady and blitzscale, nine strategies.

### 30.7 v2 balance targets (M15a, printed)

**V1. Strategies split the wins.** By founder value at year 10 (T2's measure) over the nine strategies on 10 seeds, no strategy wins more than 5; at least four strategies win at least once over 30 seeds. T2 then leaves the known-miss list.

**V2. Research is strong, not dominant.** research_heavy's median ARR at year 10 is 1.0–1.4 × steady_regions, and it wins at most 4 of 10 seeds. Tune `rnd.*` (cap per point, rate, era keys) if not.

**V3. Integration pays modestly.** integrator's operating margin at year 10 is 3–10 points above steady_regions, with ARR 0.85–1.25×.

**V4. Delegation stays below good play.** ceo's median ARR at year 10 is 0.85–1.2 × steady_regions (M13b's target 7, at 10 years).

**V5. 30-year campaigns stay alive** (steady_regions and research_heavy, 10 seeds, to Dec 2039):
- at least 5 era arrivals from 2026 to 2039 per run (median);
- total market demand grows at least 4% a year in the 2030s;
- at least 30% of the 2026 rivals are still alive in 2039, and every category has at least one rival launch per decade;
- steady_regions reaches stage 4 (listed) on at least 5 of 10 seeds by 2039.

**V6. The late game stays quick.** A stage-4 company in 2039 (a 30-year research_heavy run's save) advances at a median of at most 1.0 s a turn on CI (median of three blocks after a warm-up, as M12r).

**V7. The known misses close.** M10.T3 (covenants) is re-measured as "breaches while cash is still positive", band 20–60%, and leaves the known-miss list; T5's bootstrap band is decided by Reece (§30.9); `docs/balance-targets.md` ends v2 with no known misses, or with any remaining one carried to v3 by Reece's explicit decision.

**Notes (M15a).**
- *Rival startups keep coming* (V5, product manager's rulings 2026-11-07): a startup's product starts with `rivals.startup.start_feature_share` (0.3) × (F_exp(t) − F0) feature points (11.4), so late founders reach the launch bar; rival startups need no manufacturing source to launch (rivals' manufacturing is abstract, 26.1); a rival startup below `rivals.startup.small_staff` (3) people for `rivals.startup.small_months` (24) consecutive month ends closes, shut down or acqui-hired, with its own History line.
- *V1* counts wins among the founder-played strategies; the ceo arm is a delegation benchmark measured by V4, re-banded to ≤ 1.4× (delegation with full authority within 40% of the hands-on script). *V3*: the software integrator's gap is at least −1 point; an `integrator_ai` arm against `ai_regions` must show +3 to +10 points (a known miss owned by M23). *V5's launch clause* is checked over the categories rival startups may enter: at least 90% of (run, category, decade after 2020) cells have a rival launch, and no category misses a decade in more than 2 of 10 runs (the stricter "every cell" clause failed on one empty cell of 160); scheduled-only categories are printed. *V7* is M10's target 3 as breaches while closing cash is positive.

### 30.8 Eras to 2039 (M15a, data)

Appended to `eras.yaml` as seeded windows (§26.4, stream `era_window` keyed by index, so earlier eras' months don't move):

| Era | Domain | Window | Accelerates |
| --- | --- | --- | --- |
| Post-quantum security | infrastructure | Jan 2028 – Dec 2031 | cybersecurity demand growth +15 points for 36 months |
| AR glasses | devices | Jan 2028 – Dec 2032 | a consumer device segment opens; devices demand +15 points for 36 months |
| Humanoid robotics | AI and devices | Jan 2030 – Dec 2035 | AI models and devices demand +20 points for 36 months |
| Photonic interconnect | chip design and infrastructure | Jan 2031 – Dec 2035 | data-centre cost per CU −15% from arrival; server CPU and accelerator demand +10 points |
| Practical quantum computing | infrastructure | Jan 2034 – Dec 2039 | cloud hosting demand +15 points for 36 months; a late frontier for research |

### 30.9 Decisions for Reece (defaults stand if not changed)

1. **T5 bootstrap risk:** default keep 0–50% (bootstrapping is a safe, slow path), rather than restore 20–50%.
2. **The scenario list** in §30.3.
3. **The chief-of-staff advisor** stays in the backlog (v4), not M15.

## 31. Holding company and subsidiaries (M16, v3)

Reece's decisions (2026-11-02, ADR-0020; defaults 2026-11-06 accepted 2026-11-08): subsidiaries are real legal entities with their own books, cap table and board; a **conglomerate discount** of 10–25%; **corporate venture investing** in M16; rivals as groups later (after M23). Built on M14's kept brands. Principle: **a company that never forms a holding company plays exactly as before.**

### 31.1 Group membership and consolidation by period (Codex review 4, findings 2 and 3)

- **Ultimate owner:** `owner_of(state, company_id)` follows `parent_id` to the top, cycle-checked (a cycle is a data error). `group_companies(state, root_id, turn)` returns every company whose ultimate owner was `root_id` at `turn`, at any depth, from **ownership history** (each company's `owned_from` and `owned_to` turns by owner), not from which companies are alive now.
- **Consolidation per period:** each reporting period consolidates the companies controlled during it. A failed or sold subsidiary keeps its contributions to earlier periods; its end posts a **disposal** (net assets out, the investment out, the difference to `4930 gain or loss on disposal`). Intercompany investments are eliminated at every level, and each subsidiary consolidates once.
- **Antitrust** (§28.4) counts the customers of every company under the same ultimate owner.
- **Read models (M43r, Codex review 9 finding 4):** the conglomerate view and the shareholder letter read a company's ledger only inside its ownership runs: the union of every run reaching it (the operating and holding-company paths), overlapping runs coalesced so each entry counts once, and a gap between a sale and a reacquisition left out.

### 31.2 Becoming a holding company (stage 5)

- **Gate:** listed (stage 4) and either two or more subsidiaries or group revenue of at least `group.stage5_revenue_cents` ($2B) a year.
- **Form a holding company** (energy 20; fees 0.1% of market cap to 6900): a new company "<Name> Holdings" takes the listing, the cap table and the founder as Chair; the operating company and every kept brand become its subsidiaries (100% owned). Shareholders swap one for one. It has no products of its own; its costs are a small group office (`group.office_monthly_cents`, $250k).
- **Screens:** a **Group** screen (an entity tree: ownership, mandate, CEO, revenue, operating margin, cash, value) and a company switcher scoping the existing screens to one entity.

### 31.3 How stakes are accounted

| Stake held | Treatment | Accounts |
| --- | --- | --- |
| ≥ 50% | Full consolidation; outside holders' share is non-controlling interest (NCI) | 3500 non-controlling interest; NCI's share of profit shown below net income |
| 20–50% | Equity method: the investment grows by the group's share of profit, less dividends | 1820 investments in associates; 4910 share of associates' profit |
| < 20% | Fair value (market cap if listed, else §28.1's value), marked each December | 1830 financial investments; 4920 fair-value gains and losses |

### 31.4 Subsidiaries as companies

- **Cap table and board:** each subsidiary has its own cap table (parent, minority investors, an option pool) and board (parent nominees, independents, one seat per 15% held by minorities).
- **CEO and mandate:** each subsidiary's CEO runs it under a **mandate** (energy 3): **grow** (revenue growth target), **margin** (operating margin target) or **return cash** (dividend payout target), plus a yearly capex limit and the categories and regions it may enter. Subsidiary CEOs pitch to the holding company through M13b's system, judged against the mandate. Kept brands' directives map to mandates (grow → grow, harvest → return cash, defend → margin).
- **Review:** each December the subsidiary's board scores its CEO against the mandate (§24's review); two misses in a row bring a replacement proposal.
- **Money:** a 100%-owned subsidiary keeps M14's sweep and funding; with minorities, cash moves up only as dividends, pro rata to every holder.

### 31.5 Capital actions

- **Sell a stake** (up to 49% keeps control): priced at the subsidiary's value less `group.private_discount` (20%) unless listed; the buyers are investors from `investors.yaml`.
- **Buy out minorities** at `group.buyout_premium` (25%) over value.
- **Subsidiary IPO (carve-out):** list 10–40% through M13's IPO chain; the subsidiary gets its own share price, analysts and earnings; the parent keeps control.
- **Spin-off:** distribute a subsidiary's shares to the holding company's shareholders (the player may keep up to 19.9%); it becomes an independent listed rival with its people, products and facilities. The founder receives their pro-rata shares personally (credited to M24's book as a holding, not cash).
- **Stakes in listed rivals:** buy on the market up to 49.9%; each 1% of the target raises the price paid by `group.stake_impact` (0.5%); public disclosure events at 5%, 10% and 25%; at 30% a full offer (§28.3) or no further buying.
- **Corporate venture:** invest in a startup's funding round (§15.4) for 5–25% at the round's price; information rights reveal its key people and products as ranges (scouting rules).

### 31.6 Transfer prices

- Each intra-group flow (chips to devices, compute to software, in v3 wafers and minerals) moves at a price the holding company sets per flow: **cost**, **cost plus** a margin, or **market** (the market-good price). M12b's internal supply at cost becomes the default "cost".
- Within 100%-owned companies it moves profit between entities only. Where the selling or buying company has minorities, a price more than `group.fairness_band` (10%) from market for 6 months raises a **minority complaint** event (critical), then a 10% valuation discount on that subsidiary and a legal cost of 0.5% of its revenue until corrected.
- Built to carry M22's regional tax and tariffs (follow-up).

### 31.7 The conglomerate discount

A listed holding company's market cap is the sum of its parts (§28.1 values, with listed subsidiaries at market, × ownership) × `(1 − d)`, where `d = clamp(group.cd_base + group.cd_per_segment × (segments − 1) − group.cd_synergy × intra_group_share, 0.10, 0.25)` (base 0.10, 0.03 per unrelated segment, synergy 0.15 × the share of group revenue that is intra-group). Analysts' notes name it.

### 31.8 Worked examples

- **Consolidation with NCI.** The group owns 80% of a subsidiary with net assets $100M and profit $10M: NCI $20M on the balance sheet and $2M of profit to NCI.
- **Equity method.** A 30% stake bought for $60M in a company earning $20M and paying $5M of dividends: investment $60M + 6 − 1.5 = **$64.5M**.
- **Conglomerate discount.** Parts worth $40B in 4 unrelated segments with 10% intra-group revenue: `d` = 0.10 + 0.09 − 0.015 = 0.175; market cap **$33.0B**.

### 31.9 Balance targets (M16 acceptance, printed)

1. **Nothing moves for a single company:** a game that never forms a holding company plays exactly as before (golden snapshots unchanged by sub-tasks 1–2 except the findings' fixes).
2. **Consolidation is right:** property tests on cash, NCI, eliminations and disposals; the §31.8 examples; a three-level group's statements equal hand-built ones.
3. **Spin-offs sometimes pay:** with the discount, spinning off an unrelated subsidiary raises the founder's total value (both stakes) on 40–80% of seeds; spinning off a closely integrated one lowers it on most.
4. **Mandates matter:** a subsidiary under "grow" grows 20–60% faster over 3 years than under "return cash", which returns 2–4× the cash.
5. **Fairness bites:** an unfair transfer price with minorities raises a complaint within 6 months on every seed.

### 31.10 What the API may show

The entity tree with stakes and treatments; every subsidiary's public statements; mandates and reviews; offers and stakes; the conglomerate discount and its parts. Never a minority investor's or target board's hidden thresholds, or private companies' true values (ranges as §28.1).

## 32. The founder's life (M24, lane C)

Reece's decisions (2026-11-07): **burnout from overwork** with a visible stress meter; **political influence with scandal risk**; **a personal foundation** funded from a personal account; **a public persona built from choices**. Built in parallel with v3 as a third lane (numbered after v3). Principle: **the founder is a person, not only a budget of energy**; nothing here changes the company's rules except through the effects named below.

### 32.1 Stress and burnout

- **Stress** 0–100 on the founder, public, starting at 20. Each month: `+ stress.load × max(0, used − stress.comfort)` where `used` is the share of the month's energy spent (0–1), `stress.comfort` 0.6 and `stress.load` 30; `− stress.recover` (8) if `used ≤ 0.6`; `− 25` for a month on Holiday; `+5` for each critical event answered that month; floor 0.
- **Burnout** when stress reaches 80: the monthly energy budget falls by `stress.burnout_cut` (30%), and a bold press answer's backfire chance doubles (§29.1). Burnout ends when stress falls below 40. A burnout raises a critical event the first month ("you are running on empty"), with choices: take a month off (Holiday 1 month), delegate more (opens the Executive team panel), or push on (stress +5).
- **Shown** on the top bar beside energy, with the last six months' causes.
- **Example.** Using all 60 energy (used 1.0) adds `30 × 0.4` = 12 a month: from 20, burnout in the fifth month. Using 45 of 60 (0.75) adds 4.5 a month: burnout after 14 months unless a light month or Holiday intervenes. (`stress.load` 30, product manager 2026-11-08; 40 at first: scripted strategies near full energy, research_heavy peaking at 82, tipped M15a's 10-year guard.)

### 32.2 The founder's personal account

- A separate double-entry book for the founder (ADR-0003; integer cents), **never** mixed with a company's: `9100 personal cash`, `9200 foundation endowment`, `9300 personal spending`, `9400 personal income`.
- **Income:** proceeds of the founder's secondary sales (§25.5), the founder's share of dividends (§25.5 and M16's), exit proceeds (§28.6, M15b's serial founder), and the founder's salary after tax at `personal.tax_rate` (35%).
- **Spending:** gifts to the foundation (§32.3), and nothing else in M24 (personal investing is v5).
- **API:** a Personal tab on the founder's profile (balance, income by source, gifts).
- **Hook:** `founder.credit(state, person_id, cents, source)` is the only way money enters the book; M16 calls it for group dividends when it merges.
- **When (M43r, Codex review 9 finding 1):** the salary after tax is credited in phase 6, with payroll, to the founder payroll paid (the same state, the same `monthly_salary_cents`), so a January death (§52.4, phase 10) settles an estate that already holds the final salary, and an heir is never credited the deceased founder's pay.

### 32.3 The foundation

- **Create** (energy 5) once the personal account holds `foundation.min_cents` ($1M), naming a **cause**: education, climate, health or local communities (a city).
- **Gifts** move personal cash to the endowment. Each year the foundation grants `foundation.payout` (5%) of its endowment.
- **Effects** of a year's grants `g` (dollars): persona *beloved* +`min(10, 2 × log10(g / 100,000))`; the cause adds: education, hiring appeal +`foundation.hiring` (≤ 0.03) in the founder's home region; climate, brand +2 on consumer products; health, staff morale +1; local, offices' hiring pools in that city +5%. Effects last 12 months.
- **Legacy:** lifetime grants count toward the founder's **legacy score** (§32.6).

### 32.4 Persona

- Four public traits, 0–100, each starting at 20 and drifting 2 a month toward 20:

| Trait | Raised by | Effects (at 60 or more) |
| --- | --- | --- |
| **Visionary** | causing an era (+15), bold press answers (+3), launches in new categories (+5), Most innovative top 10 (+5) | hiring appeal for builders +0.03; investor heat +0.05 in rounds |
| **Ruthless** | layoffs of 10%+ (+10), hostile bids (+10), poaching a rival's key person (+3), breaking a no-layoffs promise (+15) | rival feuds build ×1.3; staff morale −2; regulators' antitrust strictness ×1.1 |
| **Beloved** | kept promises (+4), foundation grants (§32.3), Best places to work top 10 (+5), raises across the company (+2) | resignations ×0.9; press bold answers +1 brand |
| **Reckless** | broken promises (+6), covenant breaches (+8), failed tenders (+8), burnout months pushed through (+4) | lenders' rates +1 point; credibility drifts toward 45 instead of 50 |

- **Reckless also rises (product manager's ruling, 2026-11-07, for §32.7 target 3):** +2 a month while burning cash with runway under 6 months (at most +12 a calendar year; `persona.sources.runway_burn`, `persona.burn_runway_months`, `persona.burn_year_cap`); a down round (`persona.sources.down_round`: the ruling's +8, tuned to 70 so a down round in years 7–8 still shows at year 10 through the 2-a-month drift); +5 once a year, in December, when headcount grew by more than 100% over the year (`persona.sources.headcount_doubled`, `persona.headcount_growth`; the first year counts from the founding headcount).
- Traits show on the founder's profile with their causes; press, staff and rival CEO texts (LLM within §16's budget, or templates) refer to the strongest one.

### 32.5 Political influence

- **Lobbying** (energy 5, a monthly company spend set per region, posted to `6950 lobbying`): influence in that region rises by `influence.rate × sqrt(spend / $100k)` (rate 3) a month, decays 3% a month, capped at 100.
- **Effects:** an antitrust review's block probability × `(1 − influence.antitrust × I/100)` (`antitrust` 0.4); M22 will use the same influence for export licences and tariffs (hook: `influence.of(state, company_id, region)`).
- **Scandal risk** (hidden): accumulates `risk += spend_k × influence.risk_rate` (0.002 per $1k a month), × 1.5 when Ruthless ≥ 60, decays 2% a month. Each month a scandal breaks with probability `min(0.2, risk / 1,000)` (stream `founder_life` id 46, key `(company_id,)`; M24: `founder` is taken by the founder build, id 7). The API shows exposure only as low, medium or high.
- **A scandal** is a critical press event: credibility −15, brand −6 on every product, influence in that region reset to 0, a fine of 0.5% of revenue, persona Ruthless +10 and Reckless +5; the founder chooses to apologize (credibility −5 more, stress +10), fire the head of government affairs (if any) or fight it (a 50% chance of a second story). History records it.

### 32.6 Legacy score

At the game's end and in the Hall of Fame: `legacy = best company score reached (§30.1) + 100 × log10(1 + lifetime grants / $1M) + 2 × (Visionary + Beloved) − (Ruthless + Reckless)`, shown with its parts. A serial founder's companies (M15b) all count toward one legacy.

### 32.7 Balance targets (M24 acceptance, printed)

1. **Nothing moves for a founder who never strains.** A founder whose energy use stays at or below 0.6 never burns out, and every earlier guard passes (the scripted strategies use energy as before; record any strategy whose results move and why).
2. **Burnout is real but avoidable.** A script that spends all its energy every month burns out within 3–6 months; one that takes a Holiday month twice a year with use ≤ 0.8 burns out at most once in 10 years.
3. **Personas diverge.** Over 10 seeds at year 10, blitzscale's top trait is Reckless or Ruthless on at least 6, and steady's is Beloved or Visionary on at least 6. A top trait counts only when it leads the next by at least 5; ties count for neither (product manager, 2026-11-07: with every trait at 20, the tie order alone had made steady "Visionary").
4. **Influence helps, with a price.** At $500k a month of lobbying in a region for 5 years, antitrust blocks there fall by 20–40%, and at least one scandal breaks in 10 years on 3–7 of 10 seeds.
5. **Giving is visible but small:** a foundation granting $10M a year raises hiring appeal by at most 0.03 and Beloved by 5–10.

### 32.8 What the API may show

Stress and its causes, burnout state, the personal account, the foundation, persona traits with causes, influence by region, exposure as low, medium or high, scandals, and the legacy score with its parts. Never the scandal risk number or a scandal's probability.

## 33. Commodities, offtake and regional power (M17, v3 lane A)

Reece's decisions (2026-11-02, 2026-11-06, playtest 4): commodity prices follow **history to 2025, then seeded**; the chain feeds **chips and devices first**; data centres should cost less where power is cheap. Data: `docs/v3-research/v3-data-dossier.md` §1, §2, §3. Principle: **commodities change what chips and devices cost; they do not yet change who makes what** (mines come in M19, refining in M20).

### 33.1 Commodity goods

Twelve goods in M12a's market-good model (key, unit, history then seeded, allocation, spot and contract), in `commodities.yaml` and `commodities_history.yaml`:

| Key | Unit | History source (dossier §1.1) |
| --- | --- | --- |
| `quartz_hp` | $/t | USGS ranges 2021–2025; flat at the 2021 level before (dossier §1.2) |
| `silicon_metal` | ¢/lb | SiM column |
| `polysilicon` | $/kg | Poly column; **semiconductor grade = solar × `commodity.semi_poly_multiple` (5, an assumption)** |
| `gallium`, `germanium` | $/kg | Ga, Ge columns (2010–2014 year-end values used as annual) |
| `copper`, `tin`, `tantalum`, `cobalt` | as dossier | Cu, Sn, Ta, Co columns |
| `lithium_carbonate` | $/t | Li column (MCS 2026 series from 2021) |
| `ndpr_oxide` | $/kg | REE column (Nd oxide to 2020, NdPr from 2021; the midpoint of a range) |
| `neon` | index | 1.0 to 2021, ×10 Mar–Jun 2022 easing to ×2 by Dec 2022, 1.2 from 2023 (dossier §1.2 proxies) |

- **Monthly history:** each year's annual value is held for the year, with the dossier §1.3 shocks placed in their months (for example lithium rising through 2021 to its November 2022 peak; neon March–June 2022). The loader rejects a year without a value.
- **After 2025 (seeded):** log-price AR(1) toward a long-run level (the 2015–2025 median in real terms) with `commodity.phi` 0.9 and annual volatility per good (`commodity.vol`, from the history's own volatility), plus **shocks** on stream `commodity` (id 47, key: the good's index): an export ban (more likely where one country holds over 60% of production or refining, dossier §2), a demand boom, or a supply disruption; size and length per good in `balance.yaml`. During a shock the good's allocation falls as M12a's components do.
- **Index:** each good's index is its price ÷ its 2010–2019 mean, so 1.0 is "normal".

### 33.2 What commodities cost the player

- **Devices:** `device_bom` index (§26) becomes `(1 − w) × components index + w × commodity mix`, with `w` = `commodity.device_share` (0.15) and the mix lithium carbonate 0.30, cobalt 0.25, copper 0.20, NdPr 0.10, tin 0.10, tantalum 0.05.
- **Servers:** `server_bom` likewise with `commodity.server_share` 0.08, mix copper 0.6, tin 0.2, tantalum 0.2.
- **Chips (wafers):** the wafer price (§26.3) × `(1 − v) + v × chip mix`, `v` = `commodity.wafer_share` (0.10): semiconductor polysilicon 0.5, neon 0.2, gallium 0.15, germanium 0.15.
- The **product cost breakdown** (Products and Hardware screens) shows each commodity's share of a unit's cost and its index.

### 33.3 Contracts and offtake

- **Spot** buying is automatic, at the month's price, with the good's allocation in a shortage.
- **Contracts** (M12a's: fixed price for 6–36 months, take-or-pay) extend to commodities.
- **Offtake agreements** (new, energy 5): 3–10 years with a named **supplier** (§33.4) for a volume a year, priced inside a **collar** (a floor and a ceiling around the price at signing, ±`offtake.collar` 25%), optional **prepayment** (up to 30% of year 1's value, buying 100% allocation during shocks). Take-or-pay at 70% of contracted volume. A supplier may breach in a severe shock (probability from its reliability; stream `commodity`).
- **Example.** Lithium carbonate offtake signed January 2020 at $8,000/t for 5 years: the collar is $6,000–$10,000. In 2022 (spot $63,700) the company pays $10,000; in 2025 (spot $9,000) it pays $9,000.

### 33.4 Suppliers

The dossier's §3.1 and §3.2 companies (Freeport-McMoRan, BHP, Rio Tinto, Glencore, Albemarle, SQM, Lynas, MP Materials from July 2020, Umicore, Wacker, Hemlock, GCL, Shin-Etsu, SUMCO, GlobalWafers, Siltronic, and the rest) join `suppliers.yaml`: region, goods, a production share, reliability and listing. In M17 they are counterparties only (no products or pools); M19 and M20 turn the relevant ones into rival mining and refining companies. **Their 2010 revenues are spot-checked against sources before entry** (the dossier marks about two-thirds as recalled).

### 33.5 Regional power (playtest 4)

- **Power** becomes a market good by region: an industrial price index, North America = 1.0, with history to 2025 from public sources (EIA, Eurostat, IEA; the brief's first sub-task researches and cites them) and seeded after (stream `commodity`, power's index per region). Default 2010–2019 levels if sources are thin: Europe 1.5 (×2.5 in 2022, easing to 1.6 by 2024), East Asia 1.2, South and Southeast Asia 0.85, Latin America 0.9, Africa 1.1, Oceania 1.3.
- **Who pays it:** data centres' power cost (§22.2) × the region's index; fabs and refineries later. M12a's tuning is for North America, which stays at 1.0, so §22.7 target 4 is unchanged for a North American build.
- **Example.** A GPU data centre's $200 a CU-month power (§22) costs $170 in South and Southeast Asia, and $300 in Europe in 2022's spike.

### 33.6 Balance targets (M17 acceptance, printed)

1. **History holds:** every good's monthly price equals the history file on every seed through 2025; nothing after the current month reaches the API.
2. **Shocks hurt devices:** the 2021–2022 lithium spike raises a reference phone's unit cost by 3–8% at its peak against 2020.
3. **Hedging pays:** a device maker with a 5-year lithium and cobalt offtake from 2020 has a gross margin at least 3 points higher in 2022 than a spot-only twin.
4. **Power spreads:** a data centre's operating cost per CU in the cheapest region is at most 0.85× North America's; §22.7 target 4 still holds for a North American build.
5. **After 2025:** each good has at least one shock in 2026–2039 on 6–10 of 10 seeds, and no good's index stays above 3.0 for more than 36 months.
6. **Nothing else moves for software companies:** a company without hardware or data centres plays exactly as before (golden snapshots for software-only seeds).

### 33.7 As built (M17 notes)

- **Goods.** Commodity and power months are `GoodMonth`s in `GameState.supply` after M12a's goods (sorted by key) and rows of `supply_month` after 2025. A commodity's `index` is its price over the 2010–2019 mean of its monthly history; power goods are `power_<region>`. History shocks are geometric paths between dated points (`shocks` in the history files) replacing the held annual value inside their months.
- **After 2025.** Monthly: `log base' = log L + phi^(1/12) (log base - log L) + (vol / sqrt 12) z`, `L` the 2015–2025 median (nominal: the game's other goods are not inflation-indexed) over the 2010–2019 mean. One start draw a month per good against the kinds' summed chance (export ban 0.002, x3 above 60% concentration; boom 0.003; disruption 0.003), a kind draw, then rise, allocation and length; no new shock within `commodity.gap_months` (24) of the last one ending. Power: the same AR(1) toward the region's 2010–2019 mean (`power.phi` 0.9, `power.vol` 0.08), North America held at 1.0. Stream `commodity` keys: `(0, good)`, `(1, region)`, `(2, deal)`.
- **Volatility.** `commodity.vol` per good is the robust sd of the 2011–2025 annual log changes (MAD x 1.4826) so the history's shocks are not counted twice; quartz and neon (flat in history) use the plain sd.
- **Use.** A unit's use of a commodity is `base x share x weight / (2010–2019 mean price in cents a volume unit)`; a chip's is its wafer's over `per_wafer x yield`. Neon trades in lots of $1,000 at index 1.0 (no public price).
- **Allocation.** A product's units are capped at `sum(weight x the company's allocation of that commodity)`, where the company's allocation is 100% on the share of last month's use covered by protected deals (a prepaid offtake, or a deal signed before the shortage began) and the good's allocation on the rest. History shortages: rare earths Jul 2010–Dec 2011 (0.8), neon Mar–Jun 2022 (0.6), gallium and germanium after the August 2023 licensing (0.8) and the December 2024 US ban (0.75 and 0.67), cobalt from February 2025 (0.85), quartz after Hurricane Helene (0.6); the shares are assumptions.
- **Deals.** Each month after production a running deal takes up to its monthly volume (x allocation unless protected) from the company's use, deals in id order; the hedge `taken x (deal price - spot)` posts to 5000 against cash; an offtake's take-or-pay is `0.7 x deliverable - taken` at the deal price (6900); a contract's is 30% of its unused volume at its end (6900). Prepayment (1200) is drawn against each month's purchases and take-or-pay; what is left comes back when the deal ends or breaches. Breach: when spot >= 2 x the ceiling, chance `(1 - reliability) x 0.10` a month; a supplier past its `until` month breaches at once (Ingas and Cryoin after February 2022).
- **Power.** A data centre's whole operating cost (22.2: mostly power) is x its region's index; assembly plants are not (33.5: data centres; fabs and refineries later). The cheapest-first ranking of own capacity (22.2) still uses the North American cost.
- **Tuning (33.6).** `commodity.mixes.device_bom.share` 0.15 → 0.033 (target 2: 0.15 raised the reference phone 43% at the lithium peak; target 3 then gives +3.1 to +3.3 points); `commodity.phi` 0.9 → 0.6 (target 5: at 0.9 lithium's trend stayed above 3.0 for 103 months). Target 2 measures 26.7's reference phone (components index 1.0), commodities at their monthly history against their 2020 mean; target 3 sizes the offtakes to 12 x the company's first month's use.
- **The examples.** 33.5's Europe figure ($300 in 2022's spike) implies an index of 1.5; the sourced Eurostat ratio in 2022 is 2.40 (the 2022 spike path peaks near 2.9), so a European data centre costs more than the example says. The unit test checks the formula at the example's indexes.

## 34. Prospecting and exploration (M18, v3 lane B)

Reece's decisions (2026-11-02, 2026-11-06): **hidden deposit grades revealed by drilling**; **protests and permits** are critical events. Data: dossier §2 (where each commodity is found) and §6 (economics). Principle: **you never see the truth, only estimates that narrow as you spend.** Mines are M19; M18 ends at a permitted, feasibility-studied project the player can sell or (from M19) build.

### 34.1 Geology

- Each region has a **prospectivity** per commodity (0–1, `geology.yaml`) following dossier §2: for example copper high in Latin America and Africa; lithium high in Latin America (brine) and Oceania (hard rock); cobalt and tantalum high in Africa; rare earths high in East Asia, medium in Oceania and North America; high-purity quartz high in North America; tin high in South and Southeast Asia and Latin America. Gallium and germanium are refining by-products (M20), not explored.
- At game start each region is divided into **blocks** (`geology.blocks_per_region`, 40), and each block holds hidden **deposits** drawn on stream `geology` (id 48, key: region index, block index), with probability from prospectivity: commodity, type (hard rock, brine, placer), tonnage, grade, depth, metallurgical recovery, infrastructure distance, permitting difficulty and community sensitivity. Most blocks hold nothing economic: tuned so roughly 1 in 25 surveyed blocks becomes a feasible project (a game-scale version of the dossier's 1 in 1,000).

### 34.2 The pipeline

| Stage | Cost and time | What it reveals |
| --- | --- | --- |
| **Desk study** (region and commodity) | $200k, 2 months, geologist-months | a heat map: each block's prospectivity as a band (low, medium, high), sharper with the team's skill |
| **Exploration licence** (a block) | a fee by region, held 5 years, renewable once | the right to explore; rivals' licences are visible |
| **Survey** (geophysics, geochemistry) | $1–3M, 6 months | whether an anomaly exists (a probability band) and its commodity |
| **Sampling** | $2M, 6 months | a first grade range (±60%) |
| **Drilling** (a programme of holes) | $150–400k a hole by depth and region | each hole draws a grade from the deposit's true distribution (stream `exploration`, id 49, key: block, hole); the estimate is the running mean, and its range narrows with holes and with the resource geologist's skill |
| **Resource estimate** | $1M, 3 months | categories: inferred (from 8 holes), indicated (20), measured (40), with tonnage and grade ranges |
| **Feasibility** (scoping, pre-feasibility, definitive) | $2M, $8M, $20M; 6, 12, 18 months | capex and operating cost ranges, recovery, and an NPV range at M17's price deck |
| **Permitting** | 1–7 years by region (North America slowest, dossier §6) | a permit or a refusal; community and environmental events |

- **Geologists:** a new role `geologist` with skills field geology, geophysics and resource estimation, hired in mining cities (new: **Perth, Santiago, Johannesburg**; existing: Toronto). Skill narrows every range (`range × (1.3 − 0.03 × skill)`), and a better desk study points the survey at better blocks.
- **Selling a project** at any stage to a supplier (§33.4) at a price from its estimate range and the price deck: the exit before M19 lets you build.

### 34.3 Critical events

- **Protests and permits:** a community blockade or a permit delayed or revoked, with probability from the block's hidden community sensitivity and the region; choices: consult (time and money), offer a benefit agreement (money, raises the odds), or push on (legal risk, persona Ruthless +5 from M24).
- **Minor events:** a drilling accident (a fine and a month's delay), a bonanza intercept (a hole far above the estimate, news), a dry hole streak.

### 34.4 Who explores

A company at stage 3 or more; at stage 5 usually a subsidiary (M16), so an exploration business can be carved out or sold. Rivals' suppliers hold licences on some blocks from the start (the real mines are theirs, abstractly).

### 34.5 What the API may show

Heat-map bands, licences, every estimate as a range with its category, holes drilled and their assays (each hole's result is public once drilled), feasibility ranges, permits and events. **Never** a deposit's true tonnage, grade, recovery or sensitivity, or an empty block's emptiness before it is tested. A differential test: two blocks with the same revealed results but different truths give identical responses.

### 34.6 Balance targets (M18 acceptance, printed)

1. **Estimates converge:** 20 holes narrow a deposit's grade range to ±15% (median); 40 holes to ±8%.
2. **Geologists matter:** a team at skill 15 finds a feasible project 1.5–2.5× as often per dollar as one at skill 8, with ranges 25–40% narrower.
3. **Exploration is a gamble:** the median spend per feasible, permitted project is $20–60M (game scale) over 3–8 years; at least 40% of surveyed blocks end in nothing.
4. **Geography is real:** the region with the most feasible projects per commodity matches dossier §2's leading producer region for copper, lithium, cobalt and rare earths on at least 7 of 10 seeds.
5. **Permits vary:** median permitting time in North America is at least 1.5× Latin America's.
6. **Nothing else moves:** a company that never explores plays exactly as before.



### 34.7 Implementation notes (M18)

- **Geology** (`tst/sim/exploration/geology.py`). A block holds a deposit of commodity c with chance `prospectivity × geology.deposit_rate` (one uniform walks the commodities in geology.yaml order; at most one deposit). Its tonnage and grade medians are x `1 − size_lift/2 + size_lift × prospectivity` (richer belts hold larger, richer deposits), grades also x `geology.grade_scale`; lognormal around them. Every block, empty or not, has a depth, a distance to infrastructure, a permitting difficulty (lognormal around 1) and a community sensitivity (around the region's mean).
- **The ore body.** A deposit has `geology.cells` drill positions whose log grades deviate from the deposit's by standard normals re-scaled to mean 0 and sd 1, so the true grade is their geometric mean. Hole n samples the n-th position of a fixed permutation (never one twice); its assay is `grade × exp(f × hole_sd × deviation)`, f the team's range factor. The running estimate is the mean log assay with half-width `z × hole_sd × sqrt(Σ f²)/n × sqrt((N − n)/(N − 1))` (finite-population correction): 20 holes give about twice the range of 40, which plain `1/sqrt(n)` cannot (target 1). Holes on a block without the commodity assay its `trace_grade` with the same spread.
- **Ranges.** Every range is a centre and half-width in log space at `exploration.confidence` (90%), shown as `±sinh(half-width)`. Sampling: `asinh(range) × f` around the truth plus matching noise. Tonnage (at the estimate): `z × tonnage_sd[category] × f_est`. Capex and operating cost (at each study): `z × accuracy[level] × f_est`; recovery likewise in absolute terms. Each centre is the truth plus noise of exactly the stated spread, so ranges hold their confidence (`tests/property/test_m18_estimates.py`, 30 seeds).
- **Skill.** `f = max(skill_floor, skill_base − skill_slope × skill)` with the team's mean geology (field: survey, sampling, holes) or mean of geology and data (estimation: tonnage and studies). Desk studies and surveys compound both judgements: their noise is x `f_field × f_est` (M18 decision, for target 2).
- **Desk study.** Each block's latent score is `desk.signal` if it holds the commodity, plus `desk.noise_sd × f_field × f_est` noise; the top `high_share` of the region's blocks show high, the next `medium_share` medium.
- **Survey.** Reading `signal × (tonnage / median)^size_weight` (0 for no deposit) plus noise; strong at `strong_at`, weak at `weak_at`. With an anomaly, its commodity is the deposit's (misread with chance `commodity_misread × f`) or, for a false anomaly, one drawn by the region's prospectivity. The stated chance of a deposit per reading (`survey.bands`) is shown with it.
- **Economics** (dossier 6). Annual product = tonnage × grade × recovery / `life_years`. Mines and mills are sized by ore: capex = ore a year × `capex_per_tpy_usd` × the commodity's reference product per tonne of ore (median grade × mid recovery) × type multiple × (1 + per km) × (1 + per metre); operating cost per tonne of product = `opex_per_t_usd × type multiple × reference / (grade × recovery)`. NPV: capex spread over the build years, then `deck_years` at the deck's current price and the rest at its long-run level, less royalty, at `discount_rate`. A study's NPV range takes every range's worst end (low) and best end (high); its midpoint the centres.
- **Geologists' time.** Desk studies and the geology stages (survey, sampling, drilling, estimate) each need a free geologist (`stages_per_geologist`); feasibility is engineers' work and permitting lawyers' (M18 decision).
- **Permits.** The decision month is drawn at application: the region's years (uniform in `permit_years`) × the block's hidden difficulty; never shown (the API shows the region's typical years). Monthly while pending: a protest (a critical event, one a company a month) with chance `protest_rate × sensitivity / 0.5`, halved by a benefit agreement; the decision waits while one is open. Refusal chance: the region's `refusal` × difficulty, x (1 − `benefit_odds`) with an agreement, + `refusal_on_push` per push.
- **Sale.** A supplier of the commodity (based in the region first; the copper majors where nobody supplies it) pays `sale.share[stage]` of the NPV at the deck at the **low end** of the revealed ranges (the latest study's low NPV, else the estimate's, holes' or sample's low grade with typical costs), so narrowing ranges raises the price (M18 decision).
- **Measuring target 2** (M18 decision, for review): "per dollar" is per dollar of discovery spend (desk studies, licences, surveys, sampling, drilling and estimates; the dossier's "$111M per discovery" counts exploration spend), with the ratio per dollar of all spend printed beside it. Target 3 is read for a team at skill 12; target 4 counts deposits whose true NPV at the deck is above zero, a tie counting for no region.

## 35. Mining operations (M19, v3 lane A)

Reece's decisions (2026-11-06): **critical mine events** are accidents and spills, protests and permits, nationalization, and price crashes. Builds on M18's permitted projects, M17's commodity prices and suppliers, M16's subsidiaries, and the generic facility model (ADR-0020). Principle: **a mine is a long, risky bet on a price you don't control.**

### 35.1 Founding a subsidiary (playtest gap from M18)

**Found a subsidiary** (energy 5, stage 3 or more): a new, 100%-owned company with a name, a region and an initial cash injection from the parent (an intercompany transfer), ready for a mandate (M16). Exploration projects, licences and facilities can be transferred into it at book value. This lets the player run "<Name> Mining" as its own business.

### 35.2 Building a mine

- **From a permitted project** (M18) with a feasibility study of any level: **Build mine** (energy 10). The mine is a facility kind, `mine`, with subtypes `open_pit`, `underground` and `brine`, a capacity (units of the commodity a year) chosen within the study's range, and the deposit's (hidden) reserves.
- **Capex** is the study's estimate × a hidden **overrun** drawn once (stream `mining`, id 50, key: facility id): 0–60%, narrower for a definitive study (`mining.overrun` by study level). It is spent over **construction** (open pit 2–3 years, underground 3–4, brine 3 plus a 2-year ramp) and capitalized to `1520 mineral properties`; M18's exploration and study spend on that project moves there too.
- **Ramp-up:** output reaches 40%, 75% and 100% of capacity over the first three years (brine: over 2 more).
- **Staff:** a new role `mining_engineer` (existing skills: engineering and operations), at `mining.staff_per_kt` per thousand units of capacity; coverage and skill set reliability (as data centres', §22.2) and the accident rate (§35.4).

### 35.3 Running a mine

- **Output** each month: `capacity × ramp × reliability`, limited by remaining reserves. Each month's **grade** comes from the deposit's true grade profile with noise (revealed as mined: the mine's reconciled grade is public).
- **Operating cost:** fixed (staff, site) plus variable per unit (energy at the region's power index, consumables), set so a typical copper mine's all-in sustaining cost sits at $1.5–3.0 a pound (dossier §6), lower for high grade.
- **Royalties** to the host government at the region's `royalty_rate` (new region field), posted to `6960 royalties`.
- **Depletion** of mineral properties per unit mined (units-of-production), to `6750 depletion`.
- **Revenue:** output sold at M17's monthly price (spot), into contracts and offtakes the mine signs as seller, or **to its own group at the transfer price** (M16 §31.6): own-group supply feeds the group's BOM and wafer costs at that price instead of the market's.
- **Closure:** at reserves' end or by choice; a **reclamation obligation** provisioned from the start of production (`2600 asset retirement obligation`, at `mining.reclamation_per_unit`) is paid over 2 years after closure.

### 35.4 Critical mine events

| Event | Trigger | Choices |
| --- | --- | --- |
| **Accident or spill** (tailings failure, fatal accident) | monthly probability `mining.accident_base` (0.1–0.5% a mine-year by subtype) × `(1.6 − 0.04 × staff skill) × (1.3 − coverage)` × safety spend factor | stop and investigate (months of lost output, smaller fine), compensate (money, persona Beloved), contest (legal risk, persona Ruthless); always: brand −, credibility −, a fine |
| **Protest or permit** | the deposit's hidden community sensitivity, region, expansions | consult, benefit agreement, push on (M18's choices) |
| **Nationalization** | the region's `resource_nationalism` (new region field) × the commodity's strategic weight; history to 2025 (Bolivia lithium; Zimbabwe's lithium ore export ban, Dec 2022; Chile's national lithium strategy, Apr 2023; Indonesia's nickel ore ban, Jan 2020; DRC's cobalt export ban, Feb 2025), then seeded | accept a state partner (sell 30–51% at book value), fight (arbitration over years; a seeded award), sell out (at a discount); an export ban instead cuts the mine's sales to its own region |
| **Price crash** | the commodity's price below the mine's all-in cost for 3 months | care and maintenance (output 0, fixed cost × 0.3, restart cost and 6 months), hedge (offtake at the current price), keep running |

Draws on stream `mining` (accidents, crashes' timing comes from M17's prices) and stream `region_risk` (id 52, key: region index) for nationalization.

### 35.5 Rival miners

M17's suppliers become operating rivals for their commodities: each has abstract mine capacity per region (from its production share), output following prices (cutting in crashes, expanding after spikes with a 3-year lag), and can buy the player's projects (M18 §34.2) or sell its mines (M14's deal code, with mines as products' equivalents).

### 35.6 Balance targets (M19 acceptance, printed)

1. **Mines are good bets on average, bad ones often:** a mine built on a definitive study at the deck's price returns a median project IRR of 10–20% over its life; at least 25% return below 5%.
2. **Costs are real:** copper mines' all-in sustaining cost $1.5–3.0 a pound (median), with high-grade mines in the bottom quartile.
3. **Accidents happen at real rates:** 0.1–0.5% per mine-year at average safety; skill-15 crews cut it by at least 40% against skill 8.
4. **Nationalization bites where it should:** in 2026–2039, at least one nationalization or export-ban event hits a high-risk region's mines on 3–7 of 10 seeds.
5. **Integration steadies costs:** a device maker owning a lithium and cobalt supply at transfer price has a BOM-cost volatility (2021–2024) at most half a spot buyer's.
6. **Nothing else moves:** a company that never mines plays exactly as before.

### 35.7 Implementation notes (M19)

- **The record.** A mine is a facility of kind `mine` (module `mining`: the generic capex, depreciation, operating cost, outage and sale skip it) plus a `Mine` keyed by the facility's id (`tst/sim/mining`). Phase 4 (`build_month`): construction, restarts, resource nationalism, rivals' bids. Phase 5, after the markets (`operate_month`): output, sales, costs, depletion, reclamation, crashes, accidents and protests. A game with no mine skips both.
- **Founding (35.1).** A company with no personality (rivals' decisions skip it), parent the listed company, HQ the region's first city, 100% held from the month before (nothing pre-acquisition); the parent's 1810 against cash, the subsidiary's cash against 3000. Transfers at book value, paid in cash by the receiver: a project is nil (exploration is expensed), a facility moves its gross cost and depreciation, a mine its 1520 book and its reclamation duty.
- **Building (35.2).** Subtype: brine deposits brine; placers and hard rock whose top is at most `mining.underground_depth_m` (250 m) open pit; deeper hard rock underground. Capacity within `mining.capacity_range` (0.75-1.25) of the study's design (estimated tonnes x grade x recovery over the feasibility life); capex = the study's capex centre x (capacity / design)^`capex_scale` (0.7). Construction months and the hidden overrun are drawn at the order (stream `mining`, keys (facility, 0) and (facility, 1)). Capex is paid at the estimate's monthly rate until `reveal_at` (half) of construction, when the cost to complete is revised (the whole capex with its overrun shown), then the rest over the months left. The project's exploration and study spend moves from 6600 to 1520 at the order.
- **Running (35.3).** Ore a month = the mill's ore capacity (capacity at the design grade and recovery) / 12 x ramp x reliability (22.2's formula with the crew's coverage and mean of mining engineering and operations), at most the ore left. Product = ore x the month's grade x the true recovery; the grade is the true grade x exp(`profile_share` x the commodity's hole sd x the deviation of M18's drill position the pit has reached) x exp(`grade_noise` x z) (key (facility, 2)). Cost a tonne of ore = the commodity's typical cost a tonne of product x the deposit type's opex multiple x its reference grade x recovery x the subtype's `opex_mult` (so a richer deposit costs less a tonne of product, from public numbers only): `fixed_share` a month at capacity (x `care_fixed` on care and maintenance, x the safety level's cost), the rest variable with `energy_share` x the region's power index; sustaining capital `sustaining_share` (7%) of the capex a year, expensed with operations. Royalties at the region's `royalty_rate` on output at spot, however it is sold. Sales in order: the group buyer's commodity use (M17's `company_use`) at the transfer price (31.6's cost, cost plus or market, the cost being the month's cash cost a tonne; the buyer's spot purchase reversed, 5900 and 4300 as M16), the mine's contracts and offtakes, then spot. Depletion is units of production on the **estimated** tonnage (the book left x ore mined / estimated ore left), so the ledger never reveals the true reserves; closure writes off the rest. Reclamation is provisioned a tonne of product (`reclamation_per_t_cents`, to 2610 against cost of goods) and paid in equal parts over `reclamation_months` after closure; a buyer or the state that takes a mine takes the duty.
- **Accidents (35.4).** The chance a month is the subtype's `accident_base` / 12 x f(s, c) / f(`skill_ref`, 1) x the safety factor, with 35.4's f(s, c) = max(floor, 1.6 - `skill_slope` s) x max(floor, 1.3 - c): normalised so a full crew of skill 10 at normal spend has the base rate (M19 decision). Always a $5M fine, brand -5 on the group's products and credibility -8 on its listed company; then the event: investigate (3 months without output, half a fine more), compensate ($15M, Beloved +5), contest (Ruthless +5; 40% chance of three fines more).
- **Protests (35.4).** At an operating mine with M18's monthly `protest_rate` x the deposit's hidden sensitivity / 0.5 (halved by a benefit agreement), answered with M18's choices and costs: consult (a month of lost output), a benefit agreement, push on (Ruthless +5; with `push_legal`'s chance a 3-month blockade and legal costs). No expansions exist in M19.
- **Nationalization (35.4).** History to December 2025 in `nationalization_history.yaml` (dossier 5, each cited; nickel and bauxite events are news only). After it, one generator a region a month (stream `region_risk`, key (region index,)) draws a uniform per geology commodity, then the kind and the months: a (region, commodity) event comes with chance `monthly_base` x the region's `resource_nationalism` x the commodity's `strategic` weight; `ban_share` of them are export bans of 6-24 months. The events are a pure function of the seed and the month, so the screen recomputes them. An export ban: the region's mines of the commodity sell at `ban_price_share` (70%) of spot and not to group companies headquartered elsewhere. A takeover is one critical event a month for every hit mine: accept a state partner (a 30-51% stake drawn, bought at book value; the state then takes that share of the cash margin, to 6960), fight (the mine is seized and written off to 4930 with its reclamation duty; arbitration 24-60 months at $500k a month; then a 50% chance of an award of 60-100% of the book value at seizure), or sell out (50% of book value).
- **Price crashes (35.4).** The month's all-in cost (operations, royalties and sustaining, over output) above spot for `months_below` (3) months running raises one critical event (not again until the price is back above cost): care and maintenance, hedge (an offtake on half the capacity for 3 years in a 20% collar), or keep running. A restart costs $500k a thousand t of capacity and 6 months.
- **Events reach the player.** Every mine event is queued to the player's company (the director shows only its queue) and finds its mines by the month it is shown; at most one of each kind a month. The same fix now applies to M18's protests on a subsidiary's project, which never showed before (M19 integration fix).
- **Rival miners (35.5).** A pure function of the price path and the region's events: each M17 supplier of an explored commodity holds its production share in its own region; capacity grows by `expand` (15%) `lag_months` (36) after a year whose mean index tops `spike` (1.3), within [`floor`, `cap`] x its start; output is cut by `cut` in a month under `crash` (0.8) and by `rival_cut` while an event of its commodity runs in its region. A supplier of the commodity bids for the group's permitted projects without a mine (`buy_share` x M18's sale price) and producing mines (`mine_bid` x book value), each with `buy_monthly` chance a month (key (project or mine, 5, 0 or 1)); a bid is open three months. Buying a rival's mine through M14's deal code is a follow-up.
- **Measuring 35.6** (`tools/m19_targets.py`, `tst/balance/m19.py`). T1-T2: on each seed, mines built in January of 2012-2020 (by seed) on up to three positive-NPV definitive studies per commodity (copper, lithium, cobalt, NdPr), full crews of skill 12, run to the end of their lives; the IRR from each mine's yearly cash flows (exploration excluded); copper's all-in sustaining cost is the median of its producing months. T3 is the exact expected chance a mine-year. T4 counts seeds where an event hits a lithium mine in each of the two highest-risk regions (Africa, Latin America) in 2026-2039. T5 is a reference phone (M17's 33.6 target-2 method: components at 1.0, the device mix at spot) with lithium and cobalt from the group's mines at cost plus 10%, its 2021-2024 monthly cost's standard deviation over its mean, against spot. T6: the same game with the mining phases and with them replaced by no-ops, identical month ends, and the golden snapshots.

## 36. Refining and wafers (M20, v3 lane B)

The middle of the chain: turning ores and concentrates into the materials chips and devices use. Facility kinds with **recipes** (inputs → outputs, yield, power per unit), owned like any facility, selling to the market (M17's goods) or the group (transfer price). Principle: **refining is a thin-margin, power-hungry business that pays off through control, not profit.**

### 36.1 Refinery kinds and recipes

| Kind | Inputs → output | Yield | Power (MWh/t, ×region index) | Notes |
| --- | --- | --- | --- | --- |
| `silicon_smelter` | quartz → silicon metal | 0.4 | 11–13 | submerged-arc furnaces; power is most of the cost |
| `poly_plant` | silicon metal → polysilicon (solar) | 0.9 | 50–70 | |
| `poly_plant_semi` | silicon metal → semiconductor polysilicon | 0.8 | 90–110 | needs process research (§36.3) |
| `wafer_plant` | semiconductor polysilicon → 300 mm wafers | 2,000 wafers/t (indicative) | per wafer | crystal growth, slicing, polishing |
| `li_converter` | spodumene or brine concentrate → lithium carbonate | 0.85 | moderate | |
| `co_refinery` | cobalt hydroxide → cobalt cathode | 0.9 | moderate | |
| `ree_separator` | mixed rare-earth concentrate → NdPr oxide | 0.2 (NdPr share) | moderate | complex chemistry; long ramp |
| `byproduct_recovery` | an add-on to a smelter or refinery: gallium (from alumina refining) or germanium (from zinc) | small | small | a gallium or germanium line on an existing plant |

- Inputs come from the owner's group (its mines, at transfer price), contracts, or spot (M17), with allocation in shocks. Ores and concentrates are new goods priced off their refined product (`refining.concentrate_share` of the refined price by commodity).
- **Capex** per unit of capacity, `refining.capex` by kind (silicon smelter about $3,000 per t/yr; lithium conversion about $20,000; rare-earth separation the highest), with M19's overrun rule; construction 2–3 years; staff role `process_engineer` (existing skills: engineering, chemistry or data).
- **Operating cost:** inputs + power (the region's index from M17) + fixed staff and site; margins thin, set by `refining.margin` targets per kind.

### 36.2 Wafers for chips

- A group that owns a `wafer_plant` supplies its own fabless chip designs (M12b) and, from M21, its own fabs, at transfer price: the wafer cost in §26.3 uses the group's wafer cost instead of the market wafer price for its own volume.
- Spare wafers sell to the market (foundries buy at the wafer price) or contract.

### 36.3 Purity and process research

Semiconductor polysilicon and wafers need a **process** research level (a new R&D domain in M11's tree, `process`, levels 1–100, with its own baseline from 2010) of at least `refining.semi_min_level` (40); below it, yield halves. M21's fab nodes will build on the same domain.

### 36.4 Events

- **Power curbs** (history: China's "dual control" curbs, Sep–Oct 2021, then seeded): smelters and poly plants in the affected region run at 50–70% for 1–3 months.
- **Plant incidents:** a fire or chemical release (a critical event for rare-earth and polysilicon plants), with choices as M19's accidents.
- Draws on stream `refining` (id 51, key: facility id).

### 36.5 Balance targets (M20 acceptance, printed)

1. **Thin margins:** each kind's median operating margin over 2015–2025 at market prices is 2–15%, wider during its commodity's shocks.
2. **Power decides smelters:** a silicon smelter in the cheapest-power region costs 20–40% less per tonne than one in Europe.
3. **Control pays for chipmakers:** a fabless chip company with its own wafer plant has a wafer cost 10–25% below the market price on average, and keeps 100% allocation in shortages.
4. **By-products matter in bans:** in a gallium export-ban shock, a group with a gallium recovery line keeps its chip mix cost within 10% of normal while a spot buyer's rises by at least 30%.
5. **Nothing else moves:** a company that never refines plays exactly as before.


### 36.6 Worked examples (M20)

A unit's cost at full output (formulas.py): input price × input a unit + MWh × `refining.power_cents_per_mwh` ($68) × the region's power index + other + fixed a capacity unit a year over a year's output + depreciation (capex over the kind's life) over a year's output. Equipment index 1.0, no overrun, staff left out (`tests/unit/test_m20_formulas.py`).

| Recipe | Input at | Unit cost at power 1.0 | At 1.5 |
| --- | --- | --- | --- |
| Silicon smelter (a tonne) | quartz $40/t × 2.5 = $100 | $100 + $816 power + $1,386 other + $120 fixed + $150 depreciation = **$2,572** | **$2,980** |
| Semiconductor polysilicon (a kg) | silicon metal $2,800/t × 0.00125 t = $3.50 | **$52.90** | **$56.30** |
| Solar polysilicon (a kg) | silicon metal $2,800/t × 0.00111 t = $3.11 | **$9.54** | **$11.58** |
| 300 mm wafer | semiconductor polysilicon $65/kg × 0.5 kg = $32.50 | **$66.42** | **$66.93** |
| Lithium converter (a tonne) | concentrate $7,000/t × 1.176 = $8,235 | **$11,336** | **$11,438** |
| Cobalt refinery (a tonne) | hydroxide $28,000/t × 1.111 = $31,111 | **$33,977** | **$34,113** |
| Rare-earth separator (a kg NdPr) | concentrate $6,000/t × 0.005 t = $30 | **$46.18** | **$46.52** |
| Gallium line (a kg) | its host's stream | **$499.73** | **$501.43** |
| Germanium line (a kg) | its host's stream | **$1,174.73** | **$1,176.43** |

### 36.7 Implementation notes (M20)

- **Plants** are facilities of eight kinds on M12a's lifecycle (`facility.kinds`, capex at the equipment index, depreciation), with their own state in `Refinery` (`tst/sim/refining`). A recipe (`refining.recipes`) names the input good and how much a unit of output takes at the stated yield, power per unit, other cost a unit and fixed cost a capacity unit a year (4% of capex). Capacity is a year's output (tonnes; wafers for the wafer plant); a month makes `capacity / 12 × ramp × reliability × curb`, reliability as a data centre's (22.2: no staff, no output), ramped linearly over the recipe's `ramp_months` from completion. A by-product line needs one of the company's plants in the region as its host and takes no bought input.
- **Overrun** (M19's rule, 35.2): the quote is the estimate; the true capex is the estimate × (1 + u), u uniform in `refining.overrun` (0-25%, vendor quotes being firmer than a mining study), drawn once on stream `refining` key `(0, facility id)`. The API shows the estimate and what has been paid, never the true capex; the overrun shows as it is paid.
- **Goods.** M17's commodities at their monthly price; concentrates (`refining.goods`) at `concentrate_share` × the refined price (per unit of contained product: lithium concentrate in tonnes of carbonate equivalent, cobalt hydroxide in tonnes of cobalt, rare-earth concentrate in tonnes of oxide at 0.12 × 1,000 kg × the NdPr price a kg) with the refined good's allocation; solar polysilicon at the semiconductor price / `commodity.semi_poly_multiple`; a 300 mm wafer at $110 × (0.45 + 0.55 × the polysilicon index) with foundry wafers' allocation.
- **The month** (phase 4, after the facilities' month and exploration; plants in `refining.order`, upstream first). Input from the group's plants' output made earlier this month at the transfer price (the plant's full unit cost inside one company; M16's `materials` flow between companies, cost by default), then the company's buy contracts (100% allocation if signed before the shortage, else the good's; take-or-pay 30% of what a contract could deliver but did not), then spot at the good's allocation. Costs post to 5000: bought input, power at the region's index, other and fixed. Output goes to the group's later plants, then to its products (a wafer plant's wafers to the group's chip products' wafer starts in product order; commodities to the group's companies' use last month), then the seller's sell contracts, then spot (`4410_materials_sales`).
- **Own supply in products** (phase 5, after M17's deals). A wafer lot lowers the chip's wafer price by the share of starts it covers × (market wafer − transfer price), and those starts get 100% allocation (36.2); a commodity lot counts as protected volume in the buyer's allocation (33.1). After production a lot is taken up to what the buyer used (commodities after M17's deals took theirs); the buyer's market-price purchase is reversed (and, between companies, the transfer price moves 5900 → 4300); the rest sells at spot.
- **Own-group mines** (wired at M19's merge; `refining/mines.py`). Mines sell in phase 5, refineries run in phase 4, so after a mine has supplied its designated buyer (35.3) the group's live plants whose input is a concentrate of the mine's commodity (lithium, cobalt, NdPr) take, in facility order, up to the spot input they bought this month: a tonne of mine product is the concentrate for a tonne of the refined good. The refinery's spot purchase is reversed at the concentrate's price and it pays the mine the transfer price (the mine's price kind and margin; market = the concentrate's price), between companies through 5900 and 4300, inside one company not at all. Next month that volume keeps 100% allocation in a shortage.
- **Process** (36.3): the domain `process` (start 25, +1 a year: 40 in 2025 without research); semiconductor polysilicon and wafers below level 40 run at half yield (twice the input a unit, half the output).
- **Curbs** (36.4): history first (`refining.curb.history`: East Asia, September-October 2021, at 60%); from 2026 each live curbed-kind plant starts one with its region's monthly chance (three uniforms, key `(2, facility id)`), at 50-70% for 1-3 months.
- **Incidents** (36.4): rare-earth and polysilicon plants (`incident_rate` a year: 3%, 2%, 1.5%) × `(1.6 − 0.04 × staff skill) × (1.3 − coverage)`, at most one a company a month (key `(1, facility id)`): a critical event (`data/events/refining.yaml`, effect `refining_step`). Brand (3 points on every product) and credibility (4) fall at once; stop and investigate (two months at zero, half the $2M fine), compensate ($5M and the fine; Beloved +3) or contest (the fine, Ruthless +5, 40% chance of $8M legal costs, key `(3, facility id)`).
- **Measuring target 4** (M20 decision, for review): the chip mix's **gallium line** (what the mix pays for gallium) for the group with a gallium recovery line against a spot buyer, at the largest point of each seeded gallium export ban in 2026-2039 against the 12 months before it; the whole chip mix is printed beside it. The whole mix cannot rise 30% for a spot buyer when gallium weighs 0.15 in it (33.2) and an export ban raises gallium 50-150% (33.1), and it moves with polysilicon, neon and germanium, which a gallium line does not touch.
## 37. The founder's life, part 2: personal investing (M26, lane C)

Reece (playtest 4, 2026-11-07): "you should be able to act as a venture capitalist and buy a new startup and not put all of your money into the company." Builds on M24's personal account (§32.2). Principle: **the founder's own money is a second game beside the company, with its own risks, and it never mixes with company books.**

### 37.1 Personal accounts (additions)

New personal accounts: `9110 angel investments`, `9120 public shares`, `9130 family office`, `9410 investment gains`, `9420 investment losses`, `9430 dividends received`. Every personal investment moves money only within the founder's book or between it and a company's book through a balanced intercompany entry (the company issues shares for cash).

### 37.2 Angel and venture investing

- **Invest in a rival startup's round** (§15.4; energy 3): when a startup raises, the founder may take part, for a stake of `cents / post-money value` (post-money = 18 months of costs ÷ `angel.round_dilution` 0.2, unless M16's corporate venture has set a price). The startup's cash rises by the cents invested.
- **Back a new startup** (energy 8, `angel.min_cheque_cents` $250k): choose a category and a founder from the founder's **network** (people who left the player's companies, former colleagues in the Hall of Fame and revealed candidates); a new rival startup appears with that founder, the founder's cheque as its seed (for `angel.seed_stake` 20–40% by cheque size) and the usual §15.4 rules. Founders the player knows well (revealed skill ranges) give better odds, from their true skills.
- **Information rights:** the founder sees the startup's key people and product as ranges (scouting rules), its cash band and its funding history.
- **Outcomes:** if the startup is acquired (M14's rival purchases, or the player's own group, which is a related-party deal that M26 flags), the founder receives stake × price; at a listing, the stake becomes public shares; at failure, it is written off to 9420. Follow-on rounds dilute the stake unless the founder invests pro rata.
- **Conflict of interest:** the player's company buying a startup the founder holds (or an angel-backed startup competing with the player's company) raises a governance event: disclose and recuse (no effect), or not (credibility −10 and a board confidence hit if found later; stream `personal`).

### 37.3 Public shares

- **Buy or sell shares** of any listed company (listed rivals, suppliers, the player's own company and its listed subsidiaries) at the month's share price (§25.3, §28.1 for rivals), with a 0.1% cost. Dividends credit 9430.
- **Own-company trading:** only in open windows (not the month before an earnings report or a deal announcement); a sale above 1% of the company's shares in a month is a public filing (sentiment −0.02).
- **Insider trading:** trading a company's shares within 3 months before a public event the founder knew of in advance (the player's own pending deal, hostile bid, earnings, or a rival's deal the player's company was party to) raises hidden **regulatory risk**; each such trade is investigated with probability `personal.sec_p` (25%) within 12 months (stream `personal`, id 53, key: the trade id). A finding: a fine of 3× the gain, the gain disgorged, credibility −20, persona Reckless +15, and a board vote on whether the founder stays as Chair or CEO. The API shows only that a trade was "in a sensitive window".

### 37.4 The family office

- **Form** once personal wealth (cash + investments at value) passes `family_office.min_cents` ($50M): a personal company, not part of the group, with an **investment manager** (a hired person; skill 1–20) and a **mandate**: conservative, balanced or aggressive.
- **Returns** each month on its balance: the mandate's mix of a **market index** (the value-weighted return of all listed companies in the game, plus the base rate on cash) with `family_office.vol` by mandate, plus the manager's alpha `0.0005 × (skill − 10)` a month, plus noise (stream `personal`). Its fees: 1% a year.
- **Moving money:** the founder moves cash in or out each month (energy 1).

### 37.5 Wealth and legacy

- **Net worth** (personal cash, angel stakes at last round price, public shares at market, the family office, the founder's stake in their own company at market or §28.1 value) shows on the founder's profile, with history.
- **Legacy** (§32.6) adds `25 × log10(1 + net worth at the game's end / $1M)`, so a founder who built wealth outside one company is recognized.

### 37.6 Balance targets (M26 acceptance, printed)

1. **Angel investing is skewed:** over 10 seeds, a script that writes $250k into every new startup in its categories for 10 years has a median multiple below 1.0, a top-decile startup above 10×, and a portfolio multiple of 0.8–3.0.
2. **Backing people you know pays:** startups backed with a founder whose skills are revealed survive 5 years at least 1.3× as often as those backed blind.
3. **The family office behaves like a fund:** over 2010–2025 the balanced mandate's annual return is within ±4 points of the game's market index, and aggressive's volatility is at least 1.5× conservative's.
4. **Insider trading gets caught:** a script trading on every pending deal is investigated at least once in 10 years on 6–10 of 10 seeds.
5. **Nothing else moves:** a founder who never invests personally plays exactly as before.

### 37.7 What the API may show

Net worth and its parts, angel stakes with ranges, public holdings, the family office's balance, mandate, returns and manager's revealed skill range, filings, and "sensitive window" flags. Never the regulatory risk, an investigation's probability or timing, or startups' true values.

## 38. Fabs and process nodes (M21, v3 lane A)

Reece's decision (2026-11-06): **named process nodes on their historical timeline**, then seeded. Data: dossier §4. Builds on M12b's fabless chips (§26), M20's wafers and `process` research domain (§36.3), and the facility model. Principle: **a leading-edge fab is the biggest bet in the game: it pays only at the edge and at high use.**

### 38.1 Nodes

`nodes.yaml` lists 65, 40, 28, 20, 16/14, 10, 7, 5, 3 and 2 nm, each with: the first-volume month per historical foundry (TSMC, Samsung, Intel; dossier §4), whether EUV is required (5 nm and below; 7 nm has a DUV route at 0.85× yield and 1.15× cost), the capital per wafer-per-year (CSET: 16 nm $11,220, 10 nm $13,169, 7 nm $14,267; extrapolated +10% a node beyond, marked as assumptions), the market wafer price (history: 16 nm $3,984, 10 nm $5,992, 7 nm $9,346, 5 nm $16,988, 3 nm about $20,000, 2 nm about $30,000; earlier nodes from the dossier's mature-node prices), and the `process` research level a company needs to run it (`fab.node_level`). After 2025, future nodes (A16, A14, then seeded "sub-1nm" steps) arrive in **seeded windows** like §26.4's eras (stream `era_window`, appended indices), each with wafer price +20–50% and capital per wafer-per-year +8–17% (dossier §4's reading).

### 38.2 Building and running a fab

- **Fab** is a facility kind with a node and a capacity in wafer starts a month (10,000–100,000). **Capex** = capacity × 12 × capital per wafer-per-year × `fab.capex_scale`, with M19's hidden overrun; construction 2 years (mature nodes) to 3 (leading edge).
- **EUV tools** are a market good (`euv_tools`, one supplier, ASML), allocated with a 2-year lead time in shortages; a 5 nm-and-below fab can't complete without its tools. M22 can restrict them.
- **Yield learning:** a fab's yield on its node starts at `fab.yield_start` (0.35 at the leading edge, 0.7 for a node 3+ years old) and rises toward `fab.yield_mature` (0.9) with months of production, the company's `process` level over the node's requirement, and its fab engineers' skill (new role `fab_engineer`, existing skills).
- **Costs:** depreciation (5 years), staff, power (the region's index; fabs are heavy users), materials (wafers from M20's market or the group at transfer price, gases, chemicals tied to M17's neon, gallium and germanium).
- **Use:** the group's own chips first (§26: own-fab chips cost the fab's cost per good die instead of the foundry price), then **foundry sales**: spare wafer starts sell as slots in the foundry market at the node's market price × `fab.slot_discount` (0.9) to rival fabless designers, weighted by the fab's yield and reliability.
- **Node upgrades:** a fab can be converted to the next node at 60% of a new fab's capex if the company has the research level.

### 38.3 Rival foundries

TSMC, Samsung Foundry, Intel, GlobalFoundries, UMC and SMIC become operating rivals with fabs by region and node, following history to 2025 (nodes per dossier §4; GlobalFoundries stopping at 14/12 nm in August 2018; SMIC on 7 nm-class by DUV from 2022) and after it advancing by their own `process` research. Their capacity sets the foundry market's price and allocation (M12b's slots), so a shortage (2021) and a leading-edge monopoly (TSMC) emerge rather than being scripted.

### 38.4 Chips on better nodes

A chip product's quality cap and power efficiency rise with its node: `+fab.node_quality` (3) quality cap points for each node generation ahead of the category's median node, so being at the edge (own fab or a TSMC slot) is visible in AI accelerators and phone SoCs.

### 38.5 Balance targets (M21 acceptance, printed)

1. **History holds:** every historical foundry reaches each node on its dossier date on every seed through 2025.
2. **The edge is expensive:** a 5 nm fab of 50,000 wafers a month costs $15–25B with overrun; a 28 nm fab of the same size under $6B.
3. **Use decides:** a leading-edge fab returns a project IRR above 12% at 80%+ use while at the edge, and below 5% at 50% use or two nodes behind.
4. **Yield learns:** a new leading-edge fab's yield rises from 35–50% to 80%+ within 24 months with skill-12 engineers.
5. **Own fabs pay a chip company:** a fabless AI-accelerator company that builds its own leading-edge fab cuts its chip cost by 10–30% at high use, and its chips gain the node's quality.
6. **Nothing else moves:** a company that never builds a fab plays exactly as before (rival foundries' capacity reproduces M12b's foundry prices through 2025 within 10%).

### 38.6 As built (M21 notes)

- **Data.** `nodes.yaml`: ten historical nodes (65 nm to 2 nm, in generation order: 65 nm = 0) with first volume per historical foundry, EUV, capital per wafer-per-year and a market wafer price at a stated month (each tagged V, R or A); six future nodes (A16, A14, then seeded sub-1nm steps) with windows; six rival foundries (TSMC, Samsung Foundry, Intel, GlobalFoundries, UMC, SMIC) with the nodes they reached, capacity by year in thousand 300 mm-equivalent starts a month, the share open to customers (Intel's from March 2021), where they stop (GlobalFoundries and UMC at 16/14 nm; SMIC at 7 nm-class without EUV); ASML's EUV shipments a year.
- **Timeline.** A pure function of the master seed (nothing stored): history to December 2025; a future node's month is `t_start + floor(u x n)` with `u` from stream `era_window` (31) at turn 0, key `1000 + j` (j its place in `future`), and arrives with the first foundry, each foundry `lag` months after it (stream `fab`, key `(3, foundry, generation)`); its wafer price and capital are the previous node's x draws in `fab.future_wafer_mult` and `fab.future_capital_mult` (key `(2, j)`). The leading edge is the newest node in volume; a chip category's median node is the one in volume `fab.median_lag_months` (36) earlier.
- **Foundry market (38.3).** Rival capacity is history to 2025, then grows by a seeded rate a year in `fab.capacity.growth` (key `(4, foundry, year)`). Price factor `(expected / actual)^elasticity` and allocation factor `(actual / expected)^elasticity`, within `fab.capacity.bounds`, where expected is history then the mean growth, and actual adds the player's sold slots. Both are exactly 1 through 2025 when the player sells none, so M12b's prices and allocation (history shortages read as the rivals' capacity against demand) hold; every wafer contract's price is locked at signing x the factor, and its delivered share x the allocation factor.
- **Node prices.** `wafer_cents x foundry_wafer index now / index at the price month x (1 - fab.price_decay)^(generations behind the edge now - then) x price factor`; a future node's reference month is its arrival, its index December 2025's. A wafer contract may name a node (a foundry backing the contract key must run it): it locks the node's price x the foundry's multiplier; without one it buys M12b's wafer of the chip type.
- **Building (38.2).** Capex `starts x 12 x capital x fab.capex_scale` (x 1.15 at 7 nm by DUV), x a hidden overrun in `fab.overrun` (key `(0, facility)`). Construction 36 months for a node under 36 months past first volume at the order (or not yet in volume), else 24. A fab may be ordered up to `fab.preorder_months` before its node's first volume and goes live no earlier; it needs process level `D_process(first volume) + fab.node_level` (a future node: its window's midpoint). EUV fabs need `ceil(starts / 2,000)` tools: they arrive after `fab.euv.lead_months` (24 in a shortage of the `euv_tools` good) or once ASML's open share of shipments has covered them after the company's earlier orders, and must arrive `fab.euv.install_months` before completion. The tools' cost is inside the capex.
- **Running (38.2).** Yield starts at `start_leading + (start_mature - start_leading) x min(1, node age at go-live / 36)` (x 0.85 by DUV) and each month closes `learn x skill / 12 x (1 + 0.02 x min(20, process lead over the node's need)) x coverage` of its gap to 0.9 (x 0.85 by DUV), with noise (key `(1, facility)`). Starts on offer: capacity x staff coverage (fab engineers, one per 2,500 starts). Costs: depreciation of each capex part over 60 months from its live month (6700); fixed `fab.fixed_share` of paid capex a year, materials (M20's 300 mm wafer at market, gases and chemicals at 8% of the node's reference price moving with neon, gallium and germanium) and power (`0.6 + 0.2 x generation` MWh a start x $68/MWh x the region's index) to 5000; the engineers' pay is payroll.
- **Own chips.** A company's live fabs share their starts among its selling chip products by last month's need (equally at first); production takes fab chips first (`starts x chips per wafer x design yield x min(1, fab yield / 0.9)`), then contracts. A fab chip posts packaging only at sale (the fab's month carries the wafer); the unit cost shown and used for GPU capex blends the fab's cost per good die (last month's cost a start) and the contracts' unit cost by capacity. A chip product launches with a wafer contract or a live fab of its company.
- **Slots.** Spare starts sell at the node's market price x `fab.slot.discount`: `fab.slot.take x yield / mature x reliability / 100` of them, all of them while the foundry market or the foundry wafer good is short, to 4420; the chip incumbents are listed as the customers.
- **Node quality (38.4).** A chip's node is its largest fab share's, else its running contracts' newest; `+fab.node_quality` cap points for each generation it is ahead of the median node (nothing for being behind); M12b's wafer (no node) gains nothing.
- **Conversion.** To the next node once in volume and within research: `fab.upgrade.capex_share` of a new fab's quote x the overrun, offline `fab.upgrade.months` (or until new EUV tools are installed); yield restarts.

## 39. Geopolitics and export controls (M22, v3 lane B)

Reece's decision (2026-11-02): **regional blocs with export controls**. Data: dossier §5. Builds on M17's allocation, M19's region risk fields, M16's regional entities, M24's influence (§32.5 hook `influence.of`). Principle: **the world's politics decide who may sell what to whom; history to 2025, then seeded.**

### 39.1 Countries and blocs

- `countries.yaml`: every country the game uses (cities gain a `country` field), each with a region, a **bloc** (`us_aligned`, `china`, `non_aligned`) and history of membership changes. Facilities, cities and subsidiaries sit in a country.
- **Tension** between the US-aligned and China blocs, 0–100: history to 2025 (rising from 2018), then seeded AR(1) with escalation and détente shocks (stream `geopolitics`, id 55, key: the month's event index).

### 39.2 Rules

`export_controls.yaml` encodes the dossier §5 events with effective dates: **who** (the imposing bloc or country), **what** (goods: advanced AI chips above a performance threshold, chip equipment such as EUV and advanced DUV, fab services at 16/14 nm and below for listed destinations, HBM; from China: gallium, germanium, graphite, antimony, rare earths and their technology; resource nationalism from M19), **to whom** (a bloc, countries or listed entities), and the **regime**: ban, licence (approval probability), or quota. After 2025, new rules arrive with tension (an escalation adds a rule from a seeded list; a détente suspends one for 12 months, as November 2025's did).

### 39.3 Effects

- **Selling controlled goods** to a restricted destination: blocked (ban), or a licence request (approval probability × (1 + 0.3 × influence/100) from M24's lobbying), or capped (quota). A company can launch a **compliant variant** (energy 5): a lower-performance version under the threshold (as NVIDIA's A800 and H20), with a quality cap −10.
- **Buying controlled inputs** from a restricting bloc: allocation 0 (ban) or the quota's share; M17's prices take the shock (the 2023 gallium licensing, the December 2024 ban to the US).
- **Entity list:** a company that sells to a listed entity without a licence, or is ≥50% owned by one, risks listing (stream `geopolitics`): then no controlled inputs from the listing bloc. The player can be listed.
- **Tariffs:** a tariff schedule by year (Section 301: 2018–2019 tranches on China-origin goods into the US at 10–25%) applies to devices, servers and chips made in the taxed bloc and sold in the taxing one, posted to `5100 tariffs` (cost of revenue). Transfer prices carry them (M16).
- **Regional entities:** some rules apply by ownership, so a subsidiary in a country (M16 §31, M19's Found a subsidiary) can be the compliant seller; a few markets require a local partner (cloud in China: 50% local) for entry.

### 39.4 Balance targets (M22 acceptance, printed)

1. **History holds:** every dossier §5 rule takes effect on its date on every seed; tension follows history to 2025.
2. **Controls bite:** an AI-accelerator seller with 30% of revenue in China loses 15–30% of total revenue in the 12 months after October 2022 unless it launches a compliant variant (then 5–15%).
3. **Bans hit supply:** a chip company sourcing gallium only from China pays 30–80% more for it in 2024–2025 than one with a non-China source or its own recovery line (M20).
4. **Influence helps licences:** at influence 80 a licence is approved at least 1.2× as often as at 0.
5. **Tariffs cost:** China-assembled devices sold in North America cost 8–20% more from 2019.
6. **After 2025:** at least one escalation and one détente in 2026–2039 on 7–10 of 10 seeds.
7. **Nothing else moves for a domestic software company:** a software-only company in North America and Europe plays exactly as before: (a) its own books, snapshots and decisions (its events and products) are identical with and without M22's data; (b) every company's books are identical before October 2022. Rivals' books may differ from October 2022, when controls reach the rivals M23a put under them (PM ruling, 2026-11-11).


### 39.5 Implementation notes (M22)

- **Countries** (`countries.yaml`): 38 countries in the seven regions, each with a bloc (and changes: Russia to the China bloc and Ukraine to the US-aligned from March 2022) and a share of its region's demand (2010s GDP and ICT spend, an assumption). Cities name their country; a facility sits in its site's country, else its city's, else its region's default; a company in its site's country, else its headquarters city's. `china` is both a country and a bloc and means the country in rules.
- **Rules** (`export_controls.yaml`): the dossier's 41 rules with month, announced month, end, actor, goods, destinations (countries, blocs, `all`, `affiliates`, named entities), regime and source tag; `news` rules (goods the game does not trade) and `via: m19` rules (M19's mine export bans and nationalizations) show on the World screen and change nothing here. Busan's truce is a historical détente: it suspends October 2025's rare-earth rules, the gallium and germanium ban to the US and the affiliates rule from November 2025 for 12 months, after which they apply again unless a seeded détente suspends them.
- **Tension** after 2025 (stream `geopolitics` key (0,) at the new month, drawn in phase 12 of the month before): AR(1) toward `tension.mean`, then an escalation (`base + slope x (t - pivot)`) adding a seeded rule not in force, or a détente (`base - slope x (t - pivot)`) suspending a biting rule for 12 months, none within `gap_months` of the last.
- **Selling** (sales.py): a product's blocked share of a region is the demand share of countries where a rule restricts it (its chip type at or above the rule's threshold; the seller in the actor's jurisdiction, by ownership for `by_ownership` rules) and no licence, grey route or variant opens it; a quota opens its share. In the market (11.7) the product wins nothing in the blocked share, but for customers there still winding down (`exit_rate` a month leave the books, their replacements still sell meanwhile). A compliant variant sells to `variant.keep` of a restricted destination's buyers at quality - 10 (its choice share there is the one at that quality); the rest wind down as blocked. A rule that `voids_variants` closes variants launched before it.
- **Buying** (supply.py): a buyer in a destination of a commodity rule is exposed on the actor's share of world supply (top_share when top_country is in the actor's jurisdiction) for its spot volume and on its offtakes with suppliers sitting there; offtakes elsewhere and own refined supply are not exposed. The allocation falls by exposed x (1 - allowed) and the exposed volume pays the regime's premium over spot (a unit's cost carries it on its commodity lines, 33.2). HBM controls cut accelerators made in a destination by the good's weight; a company on an actor's entity list gets no wafers from foundries in its jurisdiction.
- **Tariffs** (tariffs.py, `tariffs.yaml`): after production, rate x cost of goods x the share made in the origin x the share sold in the market, to 5100 against cash. A device's origin is its contract's city (Foxconn in Shenzhen: China) or its plants' countries; a chip's its foundries' (TSMC: Taiwan).
- **Fabs (wired at the M21 merge, fabs.py)**: a fab order (a new fab or a conversion) whose country (its city's, else its region's default: East Asia's is China) is a destination of a biting rule on `euv_tools` (an EUV node) or `chip_equipment` (`geopolitics.equipment_node` n16 and below) is refused without an approved tool licence for that rule and country (a ban refuses it outright); a company on an entity list of a toolmakers' actor gets no EUV or advanced tools. Orders already placed are not recalled. M21's foundry customers are the chip incumbents, none in China: `fab_services` rules have no sale to stop.
- **Who is controlled**: the player's group (M16), subsidiaries included; rivals' sales and inputs are not (M22 decision; rivals' lobbying is out of scope).

## 40. Automation everywhere (M27a, M27b; v3.5)

Reece (2026-11-11): "Being able to automate anything would be nice. That is what makes FM fun." His decisions: **every area can be automated**; **one-off decisions always need his approval**; each delegate works under a **money limit**; a **monthly digest** reports what they did; and **delegates can be bad**, so whom he appoints matters. This section generalises §24 (authority), §25.6 (the CEO) and §27.1 (pitches) to every area of the game. Nothing here changes a company whose areas are all managed by the player.

### 40.1 Areas, owners and eligibility

An **area** is a part of the business with its own monthly rule. Each area of each company has an **owner**: the player (**Manage myself**, the default) or a person. Setting or changing an owner is an immediate action (energy `exec_authority.change_energy`, 2); taking an area back costs the same, and a high-ego owner (ego ≥ 15) loses 2 morale once when an area is taken back within 6 months of being given.

**Who may own an area:**
- **A seat holder** (§18.3) for the areas of its seat (table below). Giving a seat's authority (§24.1) is the same as making it the owner of its seat's areas; the two are one setting.
- **The CEO** (§25.6) for any area.
- **An area lead** (new): any active employee at `automation.lead_min_level` (senior) or above whose role is in the area's `roles` list in `balance.yaml`. An area lead has no seat effect (§18.3) and an empty lead post costs nothing, so area leads do not change §18's balance.
- **A subsidiary's CEO** for every area inside that subsidiary (§31.4); the mandate is its guardrail.

The founder is never an owner (the founder is the player). A person may own several areas; their workload is §40.3's energy.

| Area | Seat that owns it | Lead roles (examples; `balance.yaml` lists them) | What the owner does each month | Milestone |
| --- | --- | --- | --- | --- |
| Hiring | the unit's seat; else COO | recruiter, any team lead | hiring plans (§13.10) for the headcount targets the player sets per unit | existing (M2, §24) |
| Engineering teams | CTO | engineering manager | §24.1's CTO rule | existing |
| Product launches and roadmaps | CPO | product manager | §27.1's CPO rule: launches ready products, pitches new products and sunsets | existing |
| Pricing | CRO | sales manager | §24.1's CRO rule, plus self-serve and device prices (§40.6) | M27a |
| Marketing | CMO | marketing manager | §24.1's CMO rule | existing |
| Support and offices | COO | operations manager | §24.1's COO rule | existing |
| Treasury | CFO | finance manager | §24.1's CFO rule (repayments; rounds and loans are one-offs) | existing |
| Research | CTO | research scientist, research lead | §40.6 | M27a |
| Regions | CRO | sales manager | §27.1's CRO pitch; a launch under the limit goes ahead | M27a |
| Cloud capacity | CTO | infrastructure engineer, SRE | §40.6 | M27a |
| Press and communications | CMO | communications manager | §40.6 | M27a |
| Routine events | the owner of the event's area; else COO | — | §40.5 | M27a |
| Device production | COO | manufacturing engineer, operations manager | §40.7 | M27b |
| Supply and commodities | COO | procurement manager | §40.7 | M27b |
| Exploration | — | geologist (senior+) | §40.7 | M27b |
| Mines and refineries | — | mining engineer, plant manager | §40.7 | M27b |
| Fabs and foundry customers | CTO | process engineer, fab manager | §40.7 | M27b |
| Government affairs | — | legal counsel, public policy manager | §40.7 | M27b |
| Corporate development | CFO | corporate development manager | screens targets and pitches acquisitions (§28); every bid is a one-off | M27b |

Roles a lead needs that are not yet in `roles.yaml` are added by the milestone that adds the area (data only; no new skills).

### 40.2 The money limit and one-offs

- **Money limit.** Each owner has a limit per decision, `limit_cents`, that the player sets on the Automation screen. The default is `automation.default_limit_bp` (200 bp, 2%) of the company's cash at the moment of appointment, rounded down to $10,000, at least `automation.min_limit_cents` ($25,000). A decision's **commitment** is its cash cost over the next 12 months plus every fixed obligation it creates (a contract's take-or-pay over its term, capex, a lease's term). Under the limit the owner acts; at or above it the decision becomes a **proposal**. A commodity contract's or offtake's commitment is the integer-cent quote that signs it × its take-or-pay share in exact rationals (a contract: year value × months / 12 × `commodity.contract_take_or_pay`; an offtake: year value × years × `offtake.take_or_pay`, plus its prepayment), rounded half to even once (M36r, Codex review 7 finding 2). An owner also stops acting in a month once its decisions that month have committed `automation.monthly_limit_mult` (3) × its limit; the rest wait to next month (logged "over this month's budget").
- **One-offs** are always proposals, whatever their size, whoever owns the area (the CEO included), on Holiday or not:
  - buying a company or a stake, a bid of any kind, and selling a product, unit, brand, subsidiary or stake;
  - equity rounds, the IPO, secondary offerings, new loans or bonds, buybacks and dividends;
  - founding, closing, carving out or spinning off a subsidiary, and changing a subsidiary's mandate;
  - building, expanding, converting or closing a facility (data centre, assembly plant, wafer, refining or fab plant, mine) and a new process node;
  - the development decision on an exploration project, and selling a project;
  - sunsetting a live product;
  - layoffs of at least `automation.layoff_share` (10%) of a unit in one month;
  - appointing or removing an executive, a CEO or a subsidiary CEO;
  - terminating a contract that has a fee, and signing a contract longer than `automation.long_contract_months` (36);
  - lobbying above the government-affairs budget the player set.
- **Proposals** are §24.1's (major severity; Approve, Modify, Decline) with §27.1's low and high case where the move has one. An unanswered proposal expires after `automation.proposal_months` (3) as declined ("expired"), and the owner may not propose the same move again for 6 months.
- **Holiday** (§17.1): ordinary decisions under the limit go ahead and are reported in the digest. A one-off **stops Holiday** by default (setting `stop_for_approvals`, on); with it off, the proposal waits and Holiday carries on. M13b's `auto_approve_cents` (§27.1) becomes the pitching owner's limit for pitches that are not one-offs; pitches that are one-offs (data centres, assembly plants, offices with a lease above the limit, rounds) no longer go ahead on Holiday.

### 40.3 Decision quality and workload

- **Score.** An owner's area score `s` is their true skills weighted by the area's `weights` (sum 1, in `balance.yaml`); a seat holder uses its seat score (§18.3) for its seat's areas, the CEO its CEO score (§25.6). Each monthly decision runs the area's right rule with probability `clamp(0.55 + 0.03 s, 0.6, 0.98)` (§24.2's `exec_authority.quality`), otherwise the area's stated mistake (second-best option, a step off by 20%, or a month late). Draws for areas that are new in M27 come from stream `automation` (id 56), key `(person_id, area_index, n)`, `n` counting that person's decisions in the area this month; the existing seat rules keep stream `delegate` and are unchanged.
- **Workload.** Each owner has 100 energy a month (§13.10's delegate energy, × the support pool's coverage `c`, §18.4). Running an area for a month costs its `energy` (`balance.yaml`, typically 15–35); an owner runs its areas in the player's priority order on the Automation screen and skips the rest when energy runs out (logged "no time this month"; the digest says so). The CEO is no exception for the new areas. One excellent person cannot run the whole company well; a team can.
- **Visible record.** Every decision and every mistake is logged with the owner's name (§24.2). Each owner shows a record on their profile and the Automation screen: decisions this year, proposals and their outcomes, pitches hit or missed (§27.1), and KPIs of their areas while they owned them. Never the probability or the draw.

### 40.4 The monthly digest

- At month end (phase 12) each company with at least one automated area gets one inbox item of kind `digest` ("Your month: <Month Year>", minor severity, never blocks Continue).
- **For each automated area:** the owner; what they did (a count and up to three lines with effects, as §27.2's "What I did"); money committed against the limit; visible mistakes and their effect; proposals waiting, with links; the area's two or three KPIs against last month and the target; "no time" or "over budget" notes.
- **Worth your attention:** up to three lines across areas, ranked by the size of a KPI's move against its target or a proposal's commitment.
- **Opening paragraph:** written by the LLM within §16's budget from engine facts only, in the chief of staff's (COO's) voice, or a template.
- **What leaves the inbox.** Inbox items produced by automated areas (delegates' hires, executives' decisions, routine events answered for the player) are stored as before but flagged `in_digest`; the inbox's default view hides them and the digest links to them. The inbox keeps proposals, critical and major events, everything in areas the player manages, and board, earnings and press items.
- Quarterly reports (§24.3, §27.2) continue; in a quarter's last month the digest links them.

### 40.5 Routine events

- A non-critical event (§16, §23.1) whose category maps to an automated area, still unanswered when the player presses Continue, is answered by that area's owner (setting per area: "Let them answer routine events", on when the area is automated). The right rule picks the option with the best displayed effect on the area's KPIs (§23.2's modifiers as the player sees them), ties to the more cautious option; the mistake picks the second best. The answer is logged with the owner's name and appears in the digest.
- **Critical events always go to the player** and never resolve by automation.

### 40.6 Area rules added in M27a

- **Pricing (self-serve and devices).** Each quarter, for each priced segment of a live product, within ±`automation.price_band` (10%) of the anchor (the player's last price there, as §24.1): step the price down 5% if the product's shown churn is above the category's shown average and its price is above the segment's displayed reference price; step it up 5% if supply limits sales (sellers, devices or capacity short) or shown churn is at least 20% below the category average. Mistake: no move.
- **Research.** Keep research spending at or below a budget (guardrail: % of trailing revenue, default `automation.research_budget_bp` 800); when builders or researchers are free, start the project with the best §27.1 research candidate score that fits the budget; stop a project whose displayed months to finish exceed a guardrail (24) when no live product draws on its domain. Licensing deals are proposals. Mistake: the second-best project.
- **Regions.** §27.1's CRO candidate; a launch whose commitment is under the limit goes ahead.
- **Cloud capacity.** Keep projected data-centre use between guardrails (default 60–90%): sell spare capacity at spot above the upper band, buy spot compute below the lower; pitch a data centre (a one-off) when §27.1's CTO test holds. Mistake: a month late.
- **Press and communications.** Answer press moments (§29) with the option whose claim the company's displayed plans support (the measured answer); a bold claim only when the guardrail "allow bold claims" is on and the plan's displayed central case supports it. Mistake: the bolder answer. Promises follow §29 as if the player made them.

### 40.7 Area rules added in M27b (outline; the M27b brief settles the details)

- **Device production:** contract-manufacturer orders and plant use to the shown demand plan, within inventory guardrails (weeks of cover).
- **Supply and commodities:** keep each input's cover (contracts, offtakes and own supply over the next 12 months' need, M23c's planning view) within a guardrail band (default 60–100%); sign standard contracts and offtakes under the limit with the best displayed terms; never terminate (one-off).
- **Exploration:** run licensed projects through the pipeline within a yearly budget, licence blocks the best desk studies show, drop projects whose displayed range falls below a guardrail grade; the development decision is a one-off.
- **Mines and refineries:** output rate, maintenance, power contracts and sales routing (group first, then contracts, then spot) within guardrails; expansions and closures are one-offs.
- **Fabs and foundry customers:** wafer starts by node to own demand first, then foundry contracts at or above a margin guardrail; conversions and new nodes are one-offs.
- **Government affairs:** lobbying within the budget by region, licence applications for blocked sales, compliant variants proposed.
- **Corporate development:** screens targets each quarter and pitches; every bid is a one-off.

### 40.8 The Automation screen

- One table per company (the company switcher scopes it): area, owner (a picker of eligible people with their displayed fit band, §18.8), status (Manage myself, Automated, or **Can't automate yet** with the reason and how to fix it: "hire a senior procurement manager or fill the COO seat"), money limit, priority, this month's decisions, proposals waiting, energy used.
- **Automate everything:** assigns every area to the eligible person with the best displayed fit (seat holders first, then leads, never more areas than their energy covers at the area costs), shows the result for confirmation, and sets default limits.
- Every screen whose area is automated shows "Run by <name> (<role>) · Take back" in its header.

### 40.9 What must not move

- A company whose areas the player manages, with seat authorities as they stand, plays exactly as before: same books, people and products (state-cache check). Golden snapshots change only by new settings rows and, for companies with an automated seat, the digest item; that regeneration's reason goes in CHANGELOG.
- An owner never commits above its limit, and no one-off is ever carried out without the player's approval (property tests over random settings and states).

### 40.10 Balance targets (printed)

1. **Automate everything works.** A stage-3 steady company (§24.5 target 1's) with every area automated by score-15 owners spread over at least five people, the founder doing nothing but approving proposals whose central case is positive, for 60 months: median ARR at month 60 between 0.85× and 1.2× the steady + regions founder script (§27.5 target 7's), 10 seeds.
2. **Staff matter.** The same run with owners at score 8: median ARR at least 20% below the score-15 run, and at least twice the logged mistakes.
3. **Workload matters.** The score-15 run with every area given to one person: median ARR at least 10% below the spread run.
4. **The inbox stays calm.** In target 1's run, proposals at most 2 a month (median) and other inbox items at most 10 a month, not counting the digest.
5. **Founder energy.** Target 1's run leaves at least 80% of the founder's energy unspent on average.
6. **Nothing else moves:** §40.9, and every earlier guard as before.

### 40.11 What the API may show

Areas, owners, eligibility and its reasons, displayed fit bands, limits, priorities, energy used, decisions and mistakes as outcomes, proposals, digests and records. Never an owner's true skills or score, the quality probability, the draws, or which option was best.

### 40.12 Notes as built (M27a)

- **One setting.** Giving an existing seat area (engineering, products, pricing, marketing, support, treasury) to its seat holder also gives the seat its authority (24.1); taking it back withdraws it, and withdrawing authority takes the area back. Authority given the old way (24.1's dialog) creates no area row, so such a company plays exactly as before (40.9). A seat holder running its own seat's existing rule keeps stream `delegate` and the rule's old key; everyone else draws from `automation` (ADR-0013 row 56).
- **Commitment** (40.2), cents: a hiring plan's hires × the role's mid salary in the home region × 12; a marketing change's increase × 12; a repayment's amount; a research team's monthly cost × 12; a pitched move's cost over `pitch.cost_months` (capex plus 12 months' running cost). Setting a price, moving a person, launching a ready product and answering an event commit nothing.
- **Proposals** are `exec_proposal` rows of kind `auto` holding the action; approving runs it with the founder as actor. They expire after `automation.proposal_months`; a CFO's or COO's own proposals (24.1) still lapse at the next Continue. A move pitched through 27.1 (a region, a research team, a data centre) waits as a pitch.
- **Hiring** backfills: a plan for each role and unit someone is leaving or left last month, with the owner as delegate. Per-unit headcount targets are a follow-up.
- **Pricing**'s anchors are the prices when the area was given, kept in the CRO's authority record (disabled unless the CRO seat was given too). Shown churn is the product screen's (11.7, from current appeal).
- **Research** stops a project whose domain feeds no live product (projects have no displayed months to finish); a new team at most every `automation.research_every_months`, a region at most every `automation.regions_every_months` (40.10 target 1).
- **Cloud capacity** below the band starts selling spare capacity at spot (22.3); there is no separate buy action, since products already buy spot compute they lack. Above the band (or with no data centre) it pitches 27.1's data centre, a one-off.
- **Press** answers are the press moments' tones: measured; bold when the area allows it and monthly revenue grew for three months running; the mistake is the bolder answer. **Routine events** score a choice by its listed effects (cash per $10,000, morale, brand, quality and customers in points, a modifier per 5%), ties to a do-nothing or smaller choice.
- **Workload** is counted apart from the owner's action energy: 100 × the support pool's coverage a month, areas in priority order.
- **Digest filing** (40.4): while their area is automated, hiring-pipeline items (candidates, offers, plan activity), sales-capacity and region-live items, and executives' monthly decision lists are flagged `in_digest`.
- The Automation screen opens at stage 3, or as soon as someone could run an area. Subsidiaries keep their CEO and mandate (31.4); the runner acts for the player's company.

### 40.13 Notes as built (M27b)

- **Order.** The chain's seven areas are appended after M27a's twelve: production (12), supply (13), exploration (14), mines (15), fabs (16), government (17), corp_dev (18). Stream `automation` keys of the first twelve are unchanged.
- **Subsidiaries.** Owner rows may name any subsidiary of the player's group (`SetAreaOwner`, `TakeBackArea`, `SetAreaSettings` take `company_id`). Inside a subsidiary only the areas flagged `subsidiary` in `balance.yaml` can be automated (Hiring and the seven chain areas); the seat rules and pitched moves (regions, research, cloud) stay the player's. Its CEO is its leader as the board names it (29.4's `rival_ceo_id`, 31.4) and comes first in Automate everything. The mandate is the guardrail: its capex limit caps the owner's money limit, and a move into a category or region the mandate leaves out is a proposal. The runner acts for the player's company, then each subsidiary by id, each in its own books. A proposal made inside a subsidiary is filed with the player (inbox and proposals) holding the subsidiary's id; approving it runs the action as the proposing owner while still on its staff, else its CEO. The digest covers every group company; a subsidiary's areas carry its name.
- **Founder's name.** Several chain actions are the founder's alone (the group's mines, foundry contracts, lobbying, another group company's facilities and projects, a mine's development). An owner carries them out in the founder's name; the cost is the owner's workload (the area's energy), so the founder's energy is left as it was. Approving such a proposal runs it as the founder.
- **Commitments** (40.2, cents), from the quotes the player sees: a manufacturing contract's units × fee × `hardware.contract.take_or_pay` × months; a wafer contract's starts × wafer price × `chips.contract.take_or_pay` × months; a commodity contract's volume over its term × price × `commodity.contract_take_or_pay`; an offtake's yearly value × years × `offtake.take_or_pay` plus any prepayment; a desk study, licence, renewal, stage or drilling programme its cost; lobbying its monthly increase × 12; a diligence its fee; a bid its price; a mine its estimate. Staffing, safety, sales routing, mine sales contracts, foundry contracts (sales) and licence applications commit nothing.
- **One-offs added:** abandoning a deal, a fab upgrade, closing a mine or putting it on care and maintenance, a local partner, the grey route, and a compliant variant (a product decision). No delegate ever carries out the grey route or a termination: both are one-offs, and the runner refuses them even past that test (target (c)). Their proposals record the founder as the required actor (the proposal param `actor: founder`, as for every founder-only kind), so approving one inside a subsidiary acts as the founder (M36r, Codex review 7 finding 1).
- **Device production.** Cover is in weeks: next month's supply (assembly contracts running then, plus the company's plants' runnable units shared over its devices) over the shown demand (last month's units plus those lost to the capacity cap) × 52/12. Below `cover_low_weeks` (4) an order with the lowest displayed fee (Shenzhen) brings cover to `order_weeks` (5) for `contract_months` (24); above `cover_high_weeks` (10) contracts lapse. There is no plant production-plan action (the engine pools plants first), so the rule staffs the plants and sells their spare capacity as contract manufacturing. Mistake: an order 20% short.
- **Supply and commodities.** Each commodity input's 12-month cover (M23c's planning view with M23r's own-supply count) below `cover_low` (0.6) is brought to the band's middle with the best option: the group's own mine routed to the company (cost plus), then offtakes from suppliers in the company's bloc (39), then the rest by displayed price; the traders' standard contract (12 months) ranks by its price outside the bloc. A chip product's wafer starts follow the same band (contracts plus the group's fabs) with the cheapest open foundry. Refining deals are not signed by the rule (follow-up). Mistake: the option one place lower.
- **Exploration** spends only within the yearly budget the player sets (default 0: off), counted as the area's committed decisions over the last 12 months. It continues the fronts the player opened (desk studies): projects stage by stage (survey, sampling, `holes` (40) drilled, estimate, scoping, then definitive), renewals a quarter before a lapse, a project given up when its displayed grade range lies wholly below `min_grade` × the commodity's median grade or its study's mid NPV is not positive, and new licences on the best free blocks (high, then medium bands) while a front has fewer than `projects` (4) live. A permitted project's mine (the smallest the study allows) is a one-off proposal carrying the study's mid NPV as its central case. Mistake: the second-best block, or a pre-feasibility study in place of the definitive.
- **Mines and refineries.** Staffing gives an unstaffed facility a free unit holding its kind's roles, and opens a plan for the gap to its need. Safety is kept at `safety` (an index into low, normal, high; 1, the brief's "standard"). A mine's output goes to a group company that needs it (a live plant whose input is the mine commodity's concentrate, or that uses the good; the player's company first) at cost plus; with no group need, `contract_share` of capacity (default 0: all spot) is contracted for a year. Mistake: routing a month late.
- **Fabs.** The engine already gives own and group chips their starts first (38.2). Spare starts go under foundry contracts at the most each designer pays (the node's slot price over the designer's premium), if that is at least `margin` (0.2) over the fab's cash cost a start (last month's fixed, materials, power and staff costs over the starts run; depreciation is sunk and the spot slots that take the rest pay less), up to `contracted_share` (0.8), each designer up to its share. Mistake: a contract 20% under that price.
- **Government affairs.** Licence applications for each product and country a licence could open, a tool licence for each country the fabs sit in (the action refuses where none is needed), a compliant variant proposed, and lobbying at the yearly budget's monthly rate split over the regions the company sells in (the home region included; the player's company only). Mistake: a month late.
- **Corporate development.** In a quarter's first month and within its yearly screening budget (default 0: off): diligence on the best independent rival sharing a selling category (most customers there per dollar of displayed value, and affordable), and for a diligenced target a bid at the displayed range's midpoint, pitched as a one-off proposal with the range in its text (at most once per target within `automation.repropose_months`). Mistake: the second-best target.
- **Automate everything** hands out a chain area only where it has something to run now (devices or plants, inputs in use, a desk study or project, a mine or plant, a fab, a blocked sale, a deal or target file), so idle areas do not spend the founder's energy; any area can still be given by hand.
- **Headcount targets** (sub-task 9): `SetHeadcountTarget` (free) sets a unit's headcount in a role; the Hiring owner opens a plan for each unit short of its target after its open plans, as well as backfilling leavers. Mistake: waits a month.
- **Records** (40.3) follow the owner's own company and show the KPIs of the areas they run at the latest month.
- **Chain targets** (M27b sub-task 11; `tst/balance/m27b.py`, `tools/m27b_targets.py`): from each seed's full_integrator game at January 2025 (turn 180), three arms to December 2039: the script playing on, and every area automated in the company and its subsidiaries by score-15 (or score-8) owners spread over at least eight people, the founder approving proposals whose central case is positive (or that have none) and pitches likewise, with an exploration budget of $20M a year. ARR is 12 × the group's last month's revenue (M23b).

## 41. A living world (M28; v3.5)

The roadmap's first product risk: the world is shallower than the player. Miners, refiners and foundries are data; rivals don't form groups or fight each other. In Capitalism Lab rivals play the same game. Here they will, within the simulation's budget, and **2010–2025 history stays the anchor**: until 2026 prices, capacity totals and dated events follow the data exactly.

### 41.1 Chain companies

- The named suppliers (`suppliers.yaml`), rival miners (§35), refiners (§36) and foundries (§38) become **rival companies** in the generic company model (ADR-0020), each owning **facilities** in the generic facility model, in the countries the data names. Their capacity per good sums to the data's world supply each year to 2025 (each company's facilities scaled to its share, `world_share` in the data; the rest is "other producers", one aggregate company per good).
- They run **simplified operations**: monthly output = capacity × utilisation, cost per unit from the facility's region (power, labour index) and grade, sales at spot or under their contracts, and books (revenue, costs, capex, debt, cash) on the ledger. No individual staff below the CEO and a few named executives; a CEO from the rival characters (§13 rival personalities).
- The player's contracts and offtakes (§33.3) are with these companies; a supplier's breach risk (§33.3) reads its real cash and utilisation instead of a fixed rate from 2026.

### 41.2 Capacity decisions and prices after 2025

- **Each December** from 2025, each chain company decides capex (stream `world`, id 57, key: the company's stable key): **expand** when its 3-year displayed price outlook exceeds its cost per unit × (1 + `world.hurdle`) and net debt / EBITDA is under `world.max_leverage`; the size by personality (aggressive large, cost leader medium, premium small); **mothball** a facility when spot is under its cash cost for 6 months; **close** after 24 months mothballed. Expansions take the facility kind's build time (§35, §36, §38).
- **Prices from 2026:** M17's seeded path is multiplied by a **balance factor** `clamp((demand / supply) ^ world.elasticity, world.factor_min, world.factor_max)`, where supply is every producer's output (the player's included) and demand every buyer's need (the player's, rivals' and the rest-of-world baseline in the data). Through 2025 the factor is exactly 1.
- The player can now **move a market**: building large capacity lowers prices for everyone; rivals respond by mothballing.
- **The world starts with its pipeline** (M28r, product manager 2026-11-14). Capacity was being built before 2026, and the first December decisions (December 2026) cannot land before the good's build time after them. So each facility the world opens with grows month by month, from January 2026 to the month before December 2026 + the good's `build_months`, along its good's pre-M28 path: a named foundry's 38.3 seeded growth (the other foundries' aggregate: the named foundries' summed path); a commodity's (M17's goods, M20's refined goods among them) data `demand_growth`, the path on which supply at `base_utilisation` keeps pace with demand, so the factor stays at 1 and prices follow M17's seeded path as before M28. `world.pipeline_share` (1.0) scales it. After the pipeline capacity holds, and December decisions add to it; rivals' plans count the pipeline still to arrive (announced builds are public). The pipeline's capex is in the opening books at full replacement cost (paid before 2026). Example: TSMC's 5 nm-era capacity in January 2026 grows at its seeded 38.3 rate (3–9% a year) through November 2029; its December 2026 expansion arrives in December 2029.

### 41.3 Rivals form groups

- **Incumbents buy chain companies and each other.** §28.6's rival M&A extends to incumbents buying incumbents (any category, chain companies included) with antitrust (§28.7), at `world.rival_mna_rate` a quarter for a candidate with cash above 12 months of costs; a buyer prefers targets that supply its inputs (vertical) or share its categories (horizontal), by personality.
- **Rival groups.** A rival that owns another company runs it as a subsidiary (§31.4's model, with a mandate chosen by personality); its statements consolidate; the conglomerate discount applies to listed rival groups, and a group whose discount exceeds `world.spinoff_discount` spins off its least-related subsidiary (at most one a year).
- **Supply security.** Device and chip incumbents sign offtakes with chain companies when their cover of an input falls under 60% (as the player's supply rule in §40.7), so in a shortage the player competes with rivals' contracts.

### 41.4 Bids for the player

- §28.6's "being acquired" is now driven by rivals' own valuations: when the player's group is listed and its market cap is under `world.bid_discount` (0.7) × a rival's displayed-knowledge valuation (§28.1) and the rival can fund 1.3× the price, the rival may bid (a critical event), at most once a year per rival. The player's defences and the board's response are §28.6's. A private player is approached only for friendly offers.

### 41.5 Chinese chipmakers under export rules

- From October 2022 (and any later control), Chinese foundries' (SMIC and peers') research lag (§38.2) shrinks by `world.china_catchup` generations a year while a control on equipment binds, at capex × `world.china_subsidy`; Chinese device and chip rivals gain the share that controlled sellers lose in China (M23a's rivals under controls), and may launch in other regions where no rule blocks them.

### 41.6 Regional cycles

- After 2025, each region's demand multiplier follows a seeded cycle (stream `world` key `(1, region_index)`): AR(1) around 1 with recessions (−3 to −8% demand for 6–18 months) and booms, independent across regions except a global shock (`world.global_shock_rate` a year) that hits all. Through 2025, `macro_history.yaml` as now.

### 41.7 The world you can see

- **World news:** a feed of rivals' deals, capacity moves, launches, mothballings, executive moves and regional cycles, filterable by company, region, good and kind; links to each.
- **Company pages** for every rival, extending the existing Rival screen (Football Manager's club page): owner and group, CEO and named executives, products and shares, facilities on a map, public financials (listed companies) or estimated ranges (private), deals, and history.

### 41.8 Balance targets (printed)

1. **History holds:** to December 2025, every commodity, power and wafer price, every capacity total and every dated event identical to `main` before M28 on every seed (a state-cache check on those series).
2. **Markets respond:** a script that builds 20% of world lithium-hydroxide capacity by 2030 sees the 2031–2033 average price 15–40% below the same seed without it, and at least one rival mothballing.
3. **The world survives:** at least 80% of chain companies alive in December 2039 (median, 10 seeds), and no good's supply under 70% of demand for more than 24 months in a row.
4. **Rivals form groups:** at least two rival groups with a chain subsidiary by 2035 on 7 of 10 seeds; rival-on-rival deals at most 3 a year (median).
5. **Bids happen when deserved:** a listed player trading at 0.6× value receives a bid within 3 years on at least 5 of 10 seeds; a player at 1.0× on at most 1.
6. **China catches up under controls:** SMIC's lag at 2030 at least one generation shorter than with controls lifted (same seed).
7. **Nothing else moves for a software company** before 2026: books identical; after 2026 regional cycles may move them.
8. **Turn time:** a 2039 turn with the full world within the M30 budget measured on `main` (no worse than 1.3× `main` before M28).

### 41.9 What the API may show

Rival companies' public facts: names, owners, products, facilities, public financials or estimated ranges, deals and news. Never a rival's hidden valuation, true costs beyond published ranges, capex intentions before they are announced, or seeded cycle paths.

### 41.10 As built (M28 notes)

- **When the world starts.** Chain companies come into being in `world.start` (January 2026): before it nothing is drawn, posted or stored, so 2010–2025 play exactly as on main (target 1's fingerprint, `tests/fixtures/m28_history.json`). The first December decision is December 2026 (41.2's "from 2025" would date a decision before 2026).
- **Who they are.** `chain_companies.yaml` lists every supplier selling a commodity in December 2025 and every foundry, with a personality and a cost position (0–1); one "other producers" company per good holds the rest of world supply (`world_supply`, by year; foundry wafers are the foundries' nodes.yaml capacity over `1 − foundry_other_share`). A supplier's share is suppliers.yaml's, so capacities sum to world supply each year to 2025. An aggregate's capacity sits in `world.other_tranches` facilities along the cost curve (its position ± `other_spread`), so its dearest mothball first. Wafer makers (no M17 good) and suppliers whose share ended before 2026 have no company. Chain companies are `company` rows with `rival_key = (7, position)`; they are not 15.3's rivals (`rivals()` and `ledger_companies()` leave them out) and the world phase keeps their books. Their CEO and named executives are names drawn from the region's pool (stream `world`, key (4, 7, position, 0)), not people on a payroll; a CEO changes with `world.ceo_change` a year (key (4, 7, position, 1)).
- **Facilities** are `world_facilities` (a simplified kind of the facility model): capacity a year, cost position, status `building`/`live`/`mothballed`/`closed`. A unit's cash cost is the long-run price × `cost_range` at its position, its `power_share` moving with the region's power index; fixed costs are `fixed_share` of capacity × the long-run price a year (`mothball_fixed` of it when mothballed); plant depreciates over `life_years`. A foundry wafer's long-run price is `foundry_wafer_cents` × the foundry wafer index (wafers cheapen as nodes age), its price that × the foundry market's factor.
- **Supply and the factor.** Demand a year = December 2025's output (`base_utilisation` of capacity) grown at the data's `demand_growth`, × the regions' mean cycle multiplier, plus the player's purchases (deals, refineries' bought inputs). Supply is producers' output at normal running: `base_utilisation` × chain producers' live capacity, plus the player's output to the market (M28 decision: so a tight or slack market moves the price, not only one at the edge of capacity). What chain producers actually make is demand less the player's supply, inside `utilisation` of capacity. The factor `clamp((demand / supply) ^ elasticity, factor_min, factor_max)` multiplies the next month's seeded index (never the AR(1) base). In a real shortage (demand over actual output) spot buyers get what rivals' offtakes leave: allocation ≤ (output − contracted) / (demand − contracted). From 2026 the foundry market's 38.3 factor reads the named foundries' live chain capacity instead of their seeded growth.
- **The pipeline (M28r).** `tst/sim/world/pipeline.py`: an opening facility (`ordered_turn == ready_turn`) steps each month from last month's point on its path to this month's (`ratio`: 1 + `pipeline_share` × (path(t) / path(start − 1) − 1), held after `end_turn`), unless closed; a mothballed one keeps growing (its builds were committed). Decisions' `planned` capacity reads `committed` (capacity × the path's end / its current point). Before it the foundry market's 38.3 factor rose from 1.02 (2026) to 1.21 (2029) on seed 3, every named foundry's capacity flat for 47 months: §38.5 target 3's "two nodes behind" IRR went 4.1% → 5.07% (band < 5%).
- **December decisions.** In order of cost, each company looks at each good it makes. It expands when the market at the build's arrival (`build_months` of the good) would be tight without it (that projected factor ≥ 1: M28 decision), its outlook (`outlook_spot_weight` × the last 12 months' mean price + the rest × the long-run price) × the projected factor with its expansion tops a new unit's full cost (cash cost + fixed + capex / life) × (1 + `hurdle`), and net debt is under `max_leverage` × a year's EBITDA. Size: `expand_share` by personality × its capacity × a draw in [0.75, 1.25] (stream `world`, key (0, 7, position, good index)). Capex is paid at the order, borrowed beyond cash within the leverage test. A mothballed facility restarts after spot tops its cash cost × (1 + hurdle) for `restart_months` (M28 decision: 41.2 names no restart).
- **Books.** One entry a company a month: revenue (4400; foundries 4420), cost of goods (5000), fixed costs (6900), interest at the base rate + `interest_spread` (7000), depreciation (6700/1510). Opening books in January 2026: cash `open_cash_months` of revenue, plant at `open_book` of replacement capex (`capex_years` × the long-run price per unit of yearly capacity), debt `open_leverage` × EBITDA, equity the rest. A cash shortfall is borrowed while net debt stays under the leverage line; otherwise it counts, and after `insolvent_months` the company fails and closes its plants. Cash above `repay_cash_months` of costs repays debt. Aggregates always borrow.
- **Breach risk** (from 2026): 33.3's chance × `breach_distress` when the supplier's costs top its revenue, it has insolvent months or a mothballed plant of the good; × `breach_healthy` above 80% utilisation; a failed supplier, or one with every plant of the good closed, breaches at once and signs nothing new.
- **Groups.** A quarter's first month: incumbents and named chain companies no one owns, with cash above `groups.cash_months` of costs, draw (stream `world`, key (3, *rival_key, 0)) against `rival_mna_rate`. A buyer scores the chain companies (and, for an incumbent, incumbents) it can pay for from cash beyond the buffer by `groups.fit` for the deal's kind ÷ price, and considers only vertical deals (an incumbent selling devices, servers or chips buying a producer of a secured input or foundry wafers) and horizontal ones (the same good, or a shared category). Price: value × (1 + `groups.premium`), a chain company's value `ev_multiple` × EBITDA less net debt, an incumbent's market cap or V_f. Antitrust is 28.4's lines and strictness on the two groups' combined share of a good's world capacity (28.4's customers test for two incumbents); a review lasts `groups.review_months`, its outcome drawn at agreement. At closing the buyer's cash goes to 1810, an `ownership` row records the holding, and the target runs under `groups.mandate[buyer personality]` with that mandate's personality (grow aggressive, margin premium, cash cost leader); a `cash` subsidiary does not expand, a `margin` one doubles its hurdle. Spin-offs (December): a listed rival owner whose group's 31.7 discount (segments: its distinct goods and categories) exceeds `spinoff_discount` spins its least related subsidiary off to its shareholders (1810 against equity), one a year. Supply security (January): each incumbent selling hardware needs, of each `security_goods` input, its revenue share of `security_need` × world demand; under `security_cover` of it under offtakes it signs one with the producer with most uncontracted capacity, up to `security_target`, for `security_years`.
- **Bids.** From 2026 the 25.4 takeover trigger gives way to rivals' own valuations: while the player's group is listed and no bid is open, each incumbent no one owns values it at V_f × (1 + `bids.tilt[personality]` + `bids.view_sd` × z) (stream `world`, key (3, *rival_key, 1); drawn each month, never stored); under `bid_discount` × that, with `bids.fund` × the price in cash, it bids with chance `bids.monthly` (at most once a year per rival), at the share price × (1 + `bids.premium`). The bid is 25.4's critical event next month; accepting sells to that rival at its bid; rejecting ends it; it lapses after 3 months. A private player gets no bids.
- **China.** A Chinese foundry's lag is generations behind the leading node; each month it grows by the leader's new generations and shrinks by `china_catchup` / 12 while a biting rule on `china_control_goods` to China, every destination or the foundry by name applies (from October 2022's rules on), else `china_free_pace` / 12. When the leader's generation less the lag reaches a node, the foundry reaches it that month (whatever its EUV gate), never before the node's first volume; the market timeline uses these reaches for it after 2025. While controls bind it spends `china_subsidy` × its plant's capex a year on research, funded by an equal state grant.
- **Cycles.** Stream `world`: key (2,) three uniforms a month (a global shock's start, depth and months); then each region, key (1, region index), a normal and four uniforms. A recession (`recession_depth`) or boom (`boom_depth`) starts with `recession_rate` + `boom_rate` a year in a region with none running and lasts `cycle.months`; a global shock (`global_shock_rate`, `global_depth`) replaces every region's phase. The effect is a sine arch to its depth; the multiplier is the AR(1) level × (1 + effect). Each market's addressable demand grows by the ratio of its region's multiplier to last month's (the home market reads the founder's default region).
- **What the API shows** (41.9): capacities, statuses, a facility's cost band (its third of the cost curve), listed chain companies' revenue and EBITDA (private ones' as 28.1's displayed ranges), owners, mandates, deals, offtakes, executives and World news; a market as tight, balanced or slack. Never a rival's view of anyone, a cost position, a capex decision before its news, a cycle's level, depth or months, or the factor itself.

## 42. Onboarding, navigation and the launcher (M29; v3.5)

The roadmap's third product risk: complexity has outgrown the experience. About 40 screens, many concepts, and a PowerShell setup. Nothing here changes a simulation rule.

### 42.1 Progressive unlocking

- Each screen and system has an **unlock condition**, a pure read-only function of state (`tst.sim.unlocks`): its stage (§12), or the first fact that makes it relevant (Exploration when the company or group holds a licence or a desk study, or when the player opens "Explore for minerals" from Markets; Mines when a project is feasible; Fabs at stage 4 or with a chip product; Group at stage 5 or with a subsidiary; World when the company sells in two blocs or buys a controlled input).
- Locked screens are hidden from the side navigation. When a screen unlocks, an inbox item of kind `unlock` (minor) and a toast say what it is, why it unlocked, and link to its guide page. A setting **Show everything** turns unlocking off. Saves started before M29 unlock what they already use.

### 42.2 A guided first year

- New games (setting on by default) show a **Getting started** checklist for the first 12 months, from state only: hire a first engineer, set a product's team, reach the launch bars, launch, open a hiring plan, raise a seed round, give a seat authority or automate an area. Each step links to its screen and ticks itself when done; the chief of staff's one-line note explains why it matters. Dismissible at any time.

### 42.3 What next

- A **What next** panel on the Overview: up to five items from §17.3's COO briefing, extended with proposals waiting (§40.2), areas that could be automated and have an eligible owner (§40.8), new unlocks, and the most urgent risk (runway, covenant, a critical event set aside). Read-only, no energy.

### 42.4 The inbox and navigation

- **Inbox tabs:** Needs you (proposals, critical and major), Digest (kind `digest`, §40.4), News, Everything; filters by area, company and kind.
- **Navigation:** the side bar grouped (Company, People, Products, Markets, Chain, Finance, World, Automation), a **command palette** (Ctrl+K) to jump to any screen, person, product, facility or rival by name, recent items, and breadcrumbs.
- **One Overview:** KPI tiles with Explain (M25), runway, What next, the latest digest's attention lines, and alerts.
- **Interruptions:** a setting for which severities stop Continue and Holiday (critical always stops; major by default; minor never), and §40.2's `stop_for_approvals`.

### 42.5 The launcher

- **Double-click to play on Windows:** a `Tech Startup Tycoon` shortcut runs `tools/launcher.py`, which on first run checks for `uv` and installs dependencies, builds the front end if it is missing or stale, then starts the API serving the built front end on one local port and opens the browser. No PowerShell commands.
- **Saves in the game:** the launcher opens the existing Main menu and Saves screen (M7b), which gain Continue (the last-played save), last-played dates and Back up, so nothing needs the CLI.
- The launcher writes its log to `saves/launcher.log` and shows a plain error page if something fails (port in use, missing uv).


## 43. v3 balance targets (M23b)

Measured by `tst/balance/v3.py` (printed by `tools/v3_targets.py`, checked weekly by `tests/balance/test_v3_balance.py`) on seeds 1–10, with the v3 scripts in `tst/balance/strategies_v3.py`. A group's margin and ARR are its consolidated figures: the members' P&L summed with intercompany sales and purchases dropped (31.6); ARR is 12 × the last month's group revenue. (Numbered 43 because M29's brief took §40–§42 for v3.5.)

- **I1. Vertical integration pays modestly (margin).** full_integrator's group operating margin over year 30 (the trailing 12 months to December 2039) is 3–10 points above devices_regions' (steady_regions plus the same phone and SoC on contracts, no owned chain; PM rulings, 2026-11-11 and 2026-11-12).
- **I2. Vertical integration pays modestly (ARR).** full_integrator's ARR at December 2039 is 0.9–1.4 × devices_regions'.
- **I3. It doesn't dominate.** full_integrator has the highest founder value at December 2039 on at most 4 of 10 seeds, among steady_regions, research_heavy, acquirer, integrator, full_integrator, mineral_baron and foundry.
- **Year-20 readings (printed only).** I1 and I2 at year 20 (2029) against devices_regions, and against steady_regions, print for information: at year 20 a group fab built in the mid-2020s is still inside its 5-year depreciation (38.2), costing more a start than the market wafer price, so integration cannot yet pay.
- **S1. Chains feel the lithium spike.** An unhedged phone's peak unit cost in 2021–2022 is at least 3% above 2020's (M17's reference phone).
- **S2. The gallium ban limits output.** An unhedged chip maker's output allocation falls at least 5% after December 2024 (median of 10 seeds), not only its price.
- **F1. Foundry demand.** The foundry script's first 28 nm fab, with foundry contracts, reaches 70%+ use within 36 months of going live on at least 7 of 10 seeds.
- **L1–L3 (30 years).** By December 2039: an era arrives in 2026–2039 in each of chip_design, devices, infrastructure and ai; a rival is alive in every chain category (miners, refiners, foundries; a derived good's spot market counts as its seller); no commodity index stays outside [1/3, 3] of its base for more than 36 months in 2026–2039. A learning-curve good (`learning_curve: true` in commodities.yaml: battery_cells, M38) is read against its December 2025 price instead of its 2010–2019 mean (product manager, 2026-11-16), since its price falls on the curve rather than reverting to a mean.
- **L4 (printed).** full_integrator has ordered its whole chain (mine, refinery, wafer plant, fab, devices) by December 2024 (year 15).

## 44. Platforms and ecosystems (M31; v4)

Reece (2026-11-13): the player can run **its own app store and developer ecosystem**, and rivals' stores (Apple's, Google's and others) are real competitors and **gatekeepers**. Platforms are where tech's profits pooled in the 2010s: whoever owns the store owns the customer. This section adds platforms, developers, network effects, lock-in, fees, gatekeeping, open source and standards. **History holds to 2025:** platform shares, fee schedules and dated rule changes follow `platforms.yaml` (research: `docs/v4-research/platforms-dossier.md`); seeded after.

### 44.1 Platforms

- A **platform** is a record owned by a company (ADR-0021): a kind, a name, a region list, a fee schedule, rules (§44.5) and a state (users, developers, catalogue).
- **Kinds:**
  - **device platforms**: an OS and its store, attached to the owner's `devices` products;
  - **developer platforms**: a model API, a cloud marketplace or a developer tool ecosystem, attached to the owner's `ai_models`, `cloud_hosting` or `dev_tools` products.
- **Historical platforms** come from the data with their dates, owners and regional shares to 2025:
  - iOS and the App Store (Apple);
  - Android with Google Play (Google, licensed to OEMs such as Samsung);
  - Android with Chinese stores (Huawei, Xiaomi, Tencent and others; Google Play absent in China);
  - BlackBerry, Symbian (Nokia) and Windows Phone (Microsoft), each ending on its historical date.
- **Device platform users.** A device platform's users in a region are the installed base of the devices running it: its owner's devices plus licensees'. Through 2025, installed-base shares by region follow the data exactly. From 2026, the installed base follows device sales and replacement (§26's `replacement_months`).
- **The player's devices** run a licensed platform (Android by default, licence fee `platforms.android_licence_cents` per unit, with the platform's rules) or the player's own OS.
- **Building an OS.** It is a product in a new pseudo-category `os`, with dev weights like `devices`' software side and a long build. When launched, it is attached to the player's chosen device products. Switching a device line between platforms is a one-off (§40.2).
- **Licensing an own OS** to other OEMs (free or per unit) adds their devices' users. Rival OEMs choose a licence by fee and catalogue each December after 2025.

### 44.2 Developers and the catalogue

- **Developers** are a population per region (data: `developers_by_year`, then growing with `platforms.developer_growth`). Each platform holds a share of them. Every developer can be on several platforms; the share is of developer attention.
- **Attractiveness** of platform `p` in region `r`, each month:

  `A_p = U_p^α × (1 − f_p)^β × T_p × G_p`

  - `U_p` is users;
  - `f_p` is the effective fee (§44.4);
  - `T_p` is a tools score (from the owner's `dev_tools` and SDK work, 0.5–1.5);
  - `G_p` is developer goodwill (§44.5, 0.5–1.2);
  - `α` = `platforms.reach_exp` (1.0) and `β` = `platforms.fee_exp` (1.0).
- **Developer share** moves toward `A_p / Σ A` with inertia `platforms.dev_inertia` (0.97 a month, about 3 years' half-life).
- **Multi-homing:** the top `platforms.multihome_share` (35%) of developers by size are on every platform with at least `platforms.multihome_min_users` (5%) of users.
- **The catalogue** `C_p` accumulates developer months and decays by `platforms.catalogue_decay` (1% a month). It is shown as an index relative to the regional leader (100).

### 44.3 Network effects and lock-in

- **Devices.** A device's feature score gains `platforms.catalogue_points × (C_p / C_leader − 1)`, capped between −`platforms.catalogue_floor` (−25 points) and 0. A platform with a thin catalogue makes its devices less attractive, so users go to the leader, which draws more developers: the loop tips.
- **Lock-in.** A customer of a device on platform `p` who replaces their device stays on `p` with probability `platforms.stay` (0.85 at catalogue parity, falling 0.1 per 25 index points behind the leader). Otherwise they choose afresh. Lock-in also lowers churn for developer-platform products by `platforms.dev_churn_cut` (up to 30% at full catalogue).
- **The tipping guard (§44.9 target 2):** a challenger needs a large, sustained advantage (lower fee, better tools, better devices) for years to tip developers. Windows Phone's fate in 2010–2017 is the reference case.

### 44.4 Fees

- **The effective fee** `f_p` for a sale in region `r` comes from the platform's schedule: the standard rate, the subscription rate after a year, the small-business rate (sellers under the threshold), and regulated rates by region from their dates (§44.5).
- **To 2025** the schedules follow the data:
  - 30% standard since 2008;
  - Apple's 15% on subscriptions after a year (2016);
  - Apple's Small Business Program (15% under $1M, January 2021);
  - Google's 15% on the first $1M (July 2021) and on all subscriptions (January 2022);
  - South Korea's alternative-payment law (2021);
  - the EU's Digital Markets Act duties (March 2024);
  - US anti-steering rulings (2021, 2025);
  - Japan's smartphone act (December 2025).
- **Who pays.** Products in app-distributed categories (`platforms.app_categories`: `consumer_apps`, the consumer segment of `fintech`, `ai_models` and `b2b_saas`) pay the fee on a `paid_share` of their revenue in each region (per category: consumer apps 0.4 for in-app purchases and subscriptions; the rest smaller). Each platform's share of that revenue is its share of users in the region.
- **Calibration that keeps history:** each app category's reference price is raised by the 2010–2025 average fee drag, so that net revenue per user to 2025 is unchanged (§44.9 target 1). The books now show gross revenue and a platform-fee cost (account `5150_platform_fees`, new).
- **An own platform's revenue:** `fee × paid_share × revenue of every other company's app-distributed products × the platform's share of their users`, posted monthly (account `4150_platform_fees`). Rivals' apps on the player's store pay it, so the store is a business.
- *As built (M36r, Codex review 7 findings 3 and 4):* the fee is exact. `revenue` is the region's integer-cent app revenue (`round(Σ customers × price)`, from the exact decimals), and `paid_share`, the user share and the fee are exact rationals of the decimals they are written as; each (seller product, owner) pair's month is summed exactly over regions and platforms and rounded half to even once, and the owner earns exactly what its sellers pay. A licensed own OS's licence a unit (§44.1) is posted between two companies of the player's group as 5900 / 4300, like a group store's fees, so consolidation removes it; outside the group it is 5150 / 4150.

### 44.5 Rules and gatekeeping

- **A platform owner sets rules:** fee rates (within its regions' regulated limits); review strictness (lenient, standard, strict); **self-preferencing** (off, mild, strong: its own apps get `platforms.self_pref_share` (up to +20%) more share in their category on its platform); **anti-steering** (allowed or not, where law permits); and **side-loading** (allowed or not, where law permits).
- **Developer goodwill** `G_p` falls with higher fees, strong self-preferencing and removals of large apps; it rises with fee cuts and tools.
- **Gatekeeping the player.** Each month a rival platform owner reviews the player's app-distributed products on its platform. The chance of an action rises when the player competes with the owner's first-party products in that category, when the player's own store or payments compete with it, or when the player steers users to pay outside (stream `platforms`). Actions are a rejected update (a month's delay to the product's next feature release), a fee dispute, or a **removal**: the product loses that platform's users in the affected regions until resolved.
- **A removal is a critical event** with three choices:
  - **comply** (drop the feature or the steering link and pay the fee);
  - **appeal** (1–3 months, with odds shown as a range);
  - **go to regulators** (in regions with rules, which also feeds M34).
- **The player as gatekeeper** reviews rivals' apps by its strictness. Strict review removes a few rivals in a category (more share for its own apps) at a goodwill and regulatory cost.

### 44.6 Open source

- **Open-sourcing a product** is a one-off. Its base becomes free:
  - customers rise by `platforms.open_adoption` (×3 over 24 months, toward the category's addressable market);
  - revenue comes only from a paid tier (`platforms.open_paid_share` of customers, 3–8% by category);
  - the community adds `platforms.open_feature_mult` (×1.5) to the product's features per month;
  - an open-sourced OS or developer platform gains `T_p` and goodwill.
- It cannot be closed again without a large goodwill loss and a fork: a rival product appears with the open version's features.
- **Historical cases** in the data: Android (open-source base), and open AI model releases from 2023.

### 44.7 Standards wars

- A **standard** is a format in a category: a connector, a codec, a wireless charging format, an AI model format, a cloud API. Each has sponsors and adopters.
- Each December after 2025, a few seeded standards contests appear per `platforms.standards_rate`. Adoption moves toward the standard with the larger installed base and the better terms, with inertia.
- **A contest tips** when one standard reaches `platforms.tip_share` (60%) of new products. Products on the losing standard lose `platforms.standard_penalty` (5 feature points) until they adopt the winner, which costs development months and, for a standard a rival owns, a licence.
- **History to 2025 in the data:** USB-C over Lightning (the EU's common-charger rule from December 2024) and Qi over PMA.

### 44.8 Rivals

- **Rival platform owners** set their fees and rules by personality and history to 2025. From 2026 they respond to developer share and regulation (M34).
- **Rival app makers** pay fees the same way.
- **Rival OEMs** licence platforms (§44.1).
- **A rival may launch its own store** where law allows side-loading or alternative stores (EU from 2024, Japan from December 2025), at most one a year per region.

### 44.9 Balance targets (printed)

1. **History holds.** Every platform share, fee schedule and dated rule to 2025 follows the data. Every app-category company's net revenue to 2025 stays within 1% of `main` before M31 (median, 10 seeds), and every earlier guard is unchanged.
2. **Tipping is hard.** A scripted challenger platform launched in 2027 with fees 10 points lower and equal devices reaches at least 15% of developers in its regions by 2035 on at most 3 of 10 seeds. With fees 20 points lower and better tools (T 1.3), it does so on at least 5 of 10.
3. **An own store pays.** A device maker that reaches 30% of users in its regions by 2032 earns platform fees of at least 5% of group revenue by 2035 (median).
4. **Removals matter.** A consumer app removed from a platform with 50% of a region's users loses 30–50% of its customers there within 3 months, and recovers to 85%+ within 6 months of compliance.
5. **Open source works.** An open-sourced developer tool has at least 2× the customers and at most 0.7× the revenue of the closed version after 36 months (median).
6. **A software company's game** changes only through fees and rules on its apps (books otherwise identical to `main` before M31).
7. **Turn time** within M30's budget.

### 44.10 What the API may show

Platforms' public facts: owners, users and developer shares as published (exact for the player's own platform; ranges for rivals' developers), fee schedules, rules, the catalogue index, removals and disputes, standards and their adoption. Never a gatekeeper's review draw or chance, rivals' private plans, or seeded future rules before they are announced.

### 44.11 Implementation notes (M31)

- **When things act.** Shares, fee schedules and rules follow `platforms.yaml` to December 2025; developer shares and catalogues are computed every month from the data's users and fees (no draw before 2026). Fees post from 2010 (`platforms.fees_from`). §44.4's calibration is exact to 2025: a seller's store revenue is grossed up by the month's fee and the fee booked against it (no cash moves), so 2010–2025 net revenue, cash and every decision are main's, and M28's §41.8 target 1 holds but for its books series (re-recorded; Reece, 2026-11-14). From 2026 the reference price carries the category's 2010–2025 average drag (gross store revenue × 1 / (1 − drag)) and fees are paid in cash. Every demand effect (catalogue points, self-preferencing, a developer platform's churn cut, open source, standards, removals) and the platform licences start in January 2026 (`platforms.start`).
- **Users from 2026** (§44.1, §44.3): a platform's users in a region = its in-game device lines' customers / the region's devices addressable customers + (1 − in-game coverage) × its share of the rest of the market. The rest replaces at 1/R a month (R = devices' consumer `replacement_months`): each platform keeps `stay(index)` of its replacers; the others choose by share × (C / C_leader)^`rest_tilt` among platforms open to OEMs (not ended; an own OS only when licensed, × (Android's licence + 1) / (its licence + 1) within `licence_factor`). In January 2026 the rest is set so users equal December 2025's data. An Android line counts for Google Play and China's stores in proportion to their users; a switched line's old devices stay on the old platform and are replaced at 1/R a month.
- **Developers** (§44.2): a region's developers are the world's (Evans Data's professional count, linear between points) × its share of categories.yaml's market sizes. Fees weighed are a large seller's effective consumer-apps fee. A developer platform competes with the rest of its category (attractiveness of the rest's users at no fee); its catalogue index is against a platform holding half the region's developers at steady state.
- **Effective fee** (§44.4): (1 − subscription share) × base + subscription share × the subscription rate (after a year: on `renewal_share` of subscriptions), base = the small-business rate for sellers whose trailing 12 months of revenue are under its threshold; then each regulated path (a country's share of the region × `alternative_share`, at its rate) and each rival store (the side-loading share × `alternative_share`). A steering seller sends `steer_share` through the outside paths.
- **Gatekeeping** (§44.5): a rejected update costs a month of the category's features; a fee dispute charges a month's fees on that platform again; a regulator's answer takes 6 months. The appeal odds shown are `review.appeal_odds`; the chance is drawn inside them on the answer month and never stored.
- **Tuning for §44.9 target 2:** `reach_exp` 1.0 → 0.5 and `fee_exp` 1.0 → 3.0.

## 45. Family and succession (M36; v5, lane D)

Reece (2026-11-14): **the player plays the heir**, and the old founder becomes a board member and adviser with opinions. This section adds a partner and children, children growing up, heirs in the company, succession, estate planning and a dynasty legacy. It builds on §32 (stress, persona, the personal account) and §37 (wealth and the family office). **Nothing here changes a company's rules** except through the effects named below, and a founder with no family plays exactly as before.

### 45.1 The family

- **Setting up.** A new game has a **Family** setting with three options: none (the default for scripted strategies and balance runs); a partner; or a partner and children, with the number and ages chosen at the start.
- **Family members** are people (§2's generation, stream `family`, id 59, key `(founder_id, member_index)`): attributes, hidden potential, personality and interests. They sit outside any company until they join one.
- **Children's traits.** A child's personality blends the founder's and the partner's (`family.inherit` 0.5) plus noise. Their interests come from both parents' interests and the child's own draw.
- **Life events** (stream `family`), all minor unless stated:
  - meeting a partner (founders aged 24–45 with stress under 60, `family.partner_rate` a year);
  - marriage (a choice);
  - children (while the partner is under 45, `family.child_rate` a year, at most `family.max_children`);
  - milestones at ages 5, 12, 18 and 22.
  - These events never block Continue except where §45.2 marks them critical.

### 45.2 Family time, the relationship and its strain

- **Family time.** The founder sets **family time** each month, 0–20 energy taken from the monthly budget (default 10 once a family exists).
  - Each month, stress falls by `family.calm × time / 20` (up to 6).
  - The **relationship** score (0–100, starting at 70) moves by `family.bond × (time − 8) / 8` a month (±2 at the extremes), and falls by 3 for each burnout month (§32.1).
  - Each child's **closeness** (0–100) moves the same way.
- **Strain.** Below a relationship of 30, a critical event offers three answers: more time (family time at least 15 for 6 months), counselling (personal cost, +10), or carrying on (−10).
- **Divorce.** Below 15 for 6 months, divorce follows. The partner leaves with half of the personal account and investments, and `family.divorce_share` (50%) of the founder's shares in each company. The partner's shares become an independent holder: ADR-0018's cap table, voting with the board by default. The persona's Beloved trait falls by 10, and History records it.

### 45.3 Children growing up

- **Development.** Children's attributes develop each month from age 5 by §2's growth formula, using their age and potential. An education multiplier `e` and the founder's closeness multiply the growth term (`× e × (0.8 + 0.4 × closeness / 100)`).
- **Education** is a choice at ages 12, 18 and 22, paid from the personal account (`9300 personal spending`) at `family.education_cents.<tier>`:
  - **school:** standard or elite (`e` 1.0 or 1.2);
  - **university:** none, standard or top (`e` 1.0, 1.15 or 1.3, with a degree field that weights its skills: engineering, business, design, science or medicine);
  - **a later MBA** (+management skills).
- **Seeing a child's ability.** A child's ratings show as ranges, narrowing with the founder's time with them (§18.8's reveal rules). Potential is never shown exactly (CLAUDE.md §8).

### 45.4 Heirs in the company

- **Joining.** From 22, a child may join a group company in any role, with an offer like any hire (§7). The child accepts if their closeness is at least 40 and the role matches their interests; otherwise they may join a rival or found their own company (an occasional event, `family.own_way_rate`).
- **Mentoring** (founder energy 3 a month per heir) adds `family.mentor_growth` (+30%) to the heir's growth in management and leadership skills, and closeness +1.
- **Succession readiness.** Each heir shows a readiness band (not ready, developing, ready, strong) from three things:
  - their displayed CEO-seat fit (§25.6, from revealed ranges);
  - their years in the group and the seats they have held;
  - the board's confidence in them (§14.6, rising with their visible results).
- **Staff reactions.** Staff see a family member's promotion: morale −2 in their unit if the heir's displayed fit is below the median of the people passed over (nepotism), and +1 if above.

### 45.5 Succession

- **When it happens:**
  - **By choice:** a one-off, at any time.
  - **On health grounds:** from age 70, each year a seeded health event (stream `family`) asks the founder to step back, with chance `family.step_back_rate × (age − 69)`. The founder can delay twice; the third is final.
  - **Through the board:** removal (§14) also triggers succession instead of game over, when an heir is at least "developing" or a professional CEO is named.
- **The choice** (a critical event):
  - **An heir** (any child at least 25 in the group), or
  - **a professional CEO** (the CEO seat, §25.6, from inside or a search, §13).
- **Choosing an heir:** **the player now plays the heir.** The heir becomes the founder person, with the founder role and energy. Stress starts at 20, the persona starts from the heir's own traits (each at 20 plus the parent's at a quarter strength), and the heir's own relationships carry over. The old founder joins the board as **adviser**.
- **Choosing a professional CEO:** the player continues as **the family's head**, acting through the board and the Automation screen (M27). They can name an heir later, as a new succession.
- **The adviser** (the old founder) gives opinions on proposals and one-offs in their voice (LLM within §16's budget, or templates), from their persona and past choices. When the adviser opposes a decision, that director's board confidence falls (−5). The adviser retires from the board at 80, or by choice.

### 45.6 Estate planning and estate tax

- **Estate tax.** At succession by health and at the founder's death in dynasty mode (M37), the estate pays tax by the founder's home region: `estate_tax.<region>.rate` above `.exemption_cents`. Data and dates come from the M36 research dossier; for the US, 40% above the exemption.
- **Paying it.** The estate pays from personal cash first, then by selling shares. That can cost the family control: a sale above the free float may need a secondary offering (§25.5).
  - *As built (M36r, Codex review 7 finding 5):* the estate realises every taxable asset in the quote, in this order, until the tax is paid: personal cash, the family office (drawn to cash), public holdings (sold at their share price, by company), angel stakes (sold at their last-round value; status `sold`), then the founder's shares in the listed (or operating) company, `ceil(rest / price)` of them. Gains and losses on the sales post to 9410 / 9420. Only what is paid is recorded (`family.estate_tax_cents`, the history line, the inbox). Since the quote values each asset at the price it is realised at, the whole tax is always paid. The quote's shares to sell count the other assets first, and shares bought in the listed company itself are counted once (in the founder's cap-table shares).
- **Planning** (one-offs, set up in life):
  - **gifting shares** to heirs (gift tax at the same rates above the lifetime exemption);
  - **a family trust** (holds shares outside the estate; set-up cost; the founder still votes them; distributions to heirs);
  - **the foundation** (§32.3: shares given to it leave the estate and count toward legacy).
- **Hidden values:** none. Estate tax, trusts and exemptions are public rules.

### 45.7 The dynasty legacy

- Each generation's legacy is §32.6's score for their years.
- **The dynasty score** sums the generations' legacies, plus `100 × log10(1 + family-held value at the game's end / $1B)`, minus 50 for each loss of family control.
- **Shown** in the Hall of Fame as a family tree with each generation's score.

### 45.8 Balance targets (printed)

1. **Nothing moves without a family:** with Family set to none, every earlier guard and the state-cache check are unchanged.
2. **Family time matters:** over 10 years with a partner and two children, family time of 10 keeps the relationship above 50 on at least 8 of 10 seeds; family time of 0 with burnout leads to divorce on at least 3 of 10.
3. **Upbringing matters:** at 22, heirs with elite school, top university and closeness above 70 have a median CEO-seat score at least 3 points above heirs with standard education and closeness under 40, from the same potential.
4. **Succession is a real choice:** a strong heir and a professional CEO of equal displayed fit lead to median company value within ±20% of each other 10 years after succession (neither is always right).
5. **Estate planning pays:** a founder with $10B in shares and no planning loses family control on at least half of seeds at a health succession; with a trust set up 10 years earlier, on at most 1 of 10.
6. **Turn time** within M30's budget.

### 45.9 What the API may show

Family members' public facts (names, ages, relationships, education, roles), their ratings as revealed ranges, readiness bands, closeness and relationship scores, the adviser's opinions, estate-tax rules and quotes, and the dynasty score with its parts. Never a family member's potential or hidden traits, or the draws behind life events.

## 46. Power and owned plants (M32; v4)

Reece (2026-11-13): the player can **buy power contracts by region** and **build and own plants** (gas, solar with storage, wind and nuclear, small modular reactors later) for its fabs and data centres; owned plants unlock at **stage 4**. M17 already gives each region a power price (a market good, §33). This section makes power an input to every facility, adds contracts, plants, grid queues and carbon prices, and lets power decide where data centres and fabs can be built. **History holds to 2025:** regional power prices, carbon prices and dated rules follow the data (`power.yaml`, research `docs/v4-research/power-dossier.md`).

### 46.1 Demand

- Every facility kind and data centre has a **power draw** in MW (`power.draw.<kind>`, scaled by capacity and use): data centres by compute capacity, fabs by wafer starts and node (EUV nodes draw more), mines and refineries by output, assembly plants and offices small.
- A company's monthly demand per region is the sum of its facilities' draws × hours. It replaces the region index cost in each facility's books (§35, §36, §38, §26) with the energy actually bought, at the same total to 2025 (§46.8 target 1).

### 46.2 Supply: grid, contracts and owned plants

- **The grid** (default): energy at the region's monthly price (M17's path; from 2026 also × M28's balance factor for power).
- **Power-purchase agreements** (PPAs): a fixed price for a fixed volume for 5–20 years from a named generator (M28's chain companies gain power producers by region from the data), at the forward price minus a term discount. Take-or-pay as §33.3. Termination as M23a's contracts.
- **Owned plants** (stage 4 or later, a one-off): a facility of kind `plant` with a type: `gas` (combined cycle), `solar_storage`, `wind`, `nuclear` (large, from the data's dates) and `smr` (small modular, from its seeded era, §26.4). Each type has, by build year (data to 2025, then a seeded learning curve): capex per kW, build months, capacity factor, fuel cost (gas from M17's path), fixed and variable operating cost, carbon intensity, and a hidden overrun (nuclear's large: `power.overrun.<type>`, as §35's mines).
- **Dispatch each month:** own plants first (their energy at marginal cost), then PPAs, then the grid; surplus own energy sells to the grid at the regional price minus `power.export_discount`.
- **Behind the meter:** a plant on the same site as a fab or data centre skips grid charges (`power.grid_charge_share` of the price) and is not exposed to grid outages.

### 46.3 Grid queues

- A new plant, and a new data centre or fab above `power.queue_min_mw`, must join its region's **interconnection queue** before it can draw from or sell to the grid. The wait is `power.queue_months.<region>` by year (data to 2025: US queues lengthening to about five years; then seeded with load growth), shown as a range at ordering. Behind-the-meter supply sized to the whole load skips the queue.
- A queued project's build can finish before its connection; it then waits (holding cost: its fixed costs).

### 46.4 Carbon

- **Carbon price** per tonne by region from its start date (EU ETS from 2005, others from their dates; data to 2025, then a seeded path with policy steps). Each plant's and the grid's carbon intensity × price adds to the energy cost; the grid's intensity falls by the region's data and then a seeded decarbonisation.
- **Disclosure:** the company's emissions (scope 1 from owned plants, scope 2 from purchased energy) appear in the annual report; persona and brand react above `power.green_brand_tonnes` per $1M revenue (consumer brands −1 to −3, Beloved −2) and below a clean share (+1 brand).

### 46.5 Outages and reliability

- Grid outages by region (stream `power`, rate from the data's reliability index, rising when reserve margin is thin under M28's balance factor): a fab loses `power.outage_wafer_loss` of the month's starts in progress, a data centre its SLA credit (§10). Own behind-the-meter plants and batteries cut the loss by their share of the load.
- Plant outages (forced outage rates by type) take the plant offline for 1–3 months; nuclear's rarer and longer.

### 46.6 Siting

- When ordering a data centre or fab, the screen shows each candidate city's expected power price, queue wait, carbon price, outage rate and whether behind-the-meter supply is possible. **By the late 2020s power is the binding constraint**: in congested regions the queue dominates the build time.

### 46.7 Rivals

- M28's chain companies gain **power producers** (utilities and independent generators by region, from the data) with plants, capacity decisions (§41.2's rule on the power price) and books. Rival hyperscalers and foundries sign PPAs and, from 2026, build plants by personality.

### 46.8 Balance targets (printed)

1. **History holds:** to December 2025, every power and carbon price and dated rule follows the data, and every facility's power cost is within 1% of `main` before M32 (median, 10 seeds); every earlier guard unchanged.
2. **Power binds later:** for a data centre ordered in 2028 in the US's most congested region, the median time to power is at least 3 years without behind-the-meter supply and at most 2 with it.
3. **Owning plants pays at a price:** a fab with an owned gas or solar-storage plant sized to its load pays a median energy cost at least 15% below grid over 2030–2039, at a capital cost with IRR 6–12%; nuclear's IRR range is wider (−5 to 12%) with at least one overrun above 50% on 3 of 10 seeds.
4. **Carbon moves the cheapest plant:** in the EU, the cheapest new plant type by levelised cost changes from gas to solar-storage or wind between 2020 and 2035 on at least 7 of 10 seeds.
5. **Outages matter:** a fab on the grid in the least reliable region loses at least 1% of a year's starts to outages; behind-the-meter supply halves it.
6. **Turn time:** within M30's budget and the 500 ms guard on the `full_integrator` save (re-measured in M35).

### 46.9 What the API may show

Prices, carbon prices, queue waits as ranges, plant types' published costs, the player's plants and contracts, emissions, outages that happened. Never a plant's hidden overrun, the outage draws or seeded future prices and policy steps before they happen.

### 46.10 Notes (M32)

- **One meter, one price** (ADR-0022): every metered facility pays its energy x `refining.power_cents_per_mwh` x the grid multiple (`tst.sim.power.grid`), which is M17's index exactly to December 2025. Data centres meter live CU x power.yaml `draws` (set so MWh x the reference price is the old opex), fabs starts x MWh a start, refineries output x MWh a unit, mines the energy part of variable cost / the reference price. Assembly plants and offices are not metered: their power stays in their fixed costs (the history guard).
- **After 2025** the multiple is M17's index x M28's balance factor for the region's power good `power_<region>` + the carbon pass-through: (carbon now - carbon in 2025) x grid intensity / the reference price in dollars. Data prices to 2025 already carry carbon.
- **Settlement** at the end of phase 6 (`tst.sim.power.settle`): behind-the-meter plants to their site, then the company's other connected plants in the region (paying `grid_charge_share` of the price on what they deliver; gas runs while its marginal cost is under the grid price), then PPAs in signing order, then the grid. Matched energy is credited back at the grid price to `5950 energy`; plant fuel, operations, carbon and grid charges and PPA payments (the untaken volume at `ppa.take_or_pay`) debit it; surplus sells at the grid price x (1 - `export_discount`) to `4950 energy sales`. Worked example: a 100 MW gas plant behind a 50,000-start North American fab (50,000 MWh a month) in 2030 replaces $3.40M of grid energy at $68/MWh; fuel at 6.23 MMBtu/MWh x $2.38 and variable O&M come to about $0.86M and fixed O&M about $0.09M, so the month's energy costs about $0.95M (settlement -$2.45M).
- **Plants:** capex = the type's $/kW for the year (data to 2025, then x (1 - its seeded learning) per year after 2025) x `plants.capex_premium`; the hidden overrun lo + (hi - lo) x u^`overrun_skew` raises capex and stretches the build by `overrun_delay` x overrun; capex is paid in equal parts until paid, then the plant generates once connected and depreciates straight-line over its life. Forced outages: `outages_a_year` / 12 a month, lasting `outage_months`.
- **Queues:** from `power.start`, a data centre or fab above `queue.min_mw` (and any grid-tied plant) joins its region's queue; after `queue.min_share` x the median it connects with a monthly hazard 1 - 0.5^(1 / (median x (1 - min_share))), so the median wait is the region's. A built load waits (held two months ahead so it is never live between turns); live behind-the-meter plants whose energy a year covers its load connect it at once.
- **Paths after 2025** (each January, stream power (0, region, 1)): carbon x exp(drift + sd z), policy steps and new schemes; intensity x (1 - decarbonise + sd z); queue median x (1 + growth x load growth) x exp(sd z), clamped.
- **Outages** from `power.start`: a region's chance a month is its data's rate x (1 + `outage.tight_factor` x (factor - 1)) / 12. A fab loses `outage.wafer_loss` x its exposure of the month's starts; a data centre fails 22.5's outage on its own draw with chance its exposure; exposure is 1 less its behind-the-meter plants' firm MW (`plants.firm_share`) over its draw.
- **Disclosure** each December from `power.start`: scope 1 and 2 tonnes over the revenue-account change since last December; above `carbon.green_brand_tonnes` a $1M, consumer products' brand target falls by `brand_hit` (low to high between the threshold and twice it) for a year and the founder's Beloved by `beloved_hit`; at or above `clean_share` own and contracted energy, +1.
- **Rivals:** power producers are chain companies of the power goods, after every earlier stable key; rival foundries keep `rivals.ppa_share` of their load under 10-year offtakes with their region's largest producer and order plants with chance `rivals.plant_rate` each December.

## 47. Semiconductor equipment (M33; v4)

Reece (2026-11-13): first the **chokepoint**, one supplier (ASML), allocation queues, prices and export controls, with rivals competing for slots; building the player's own lithography tools is a **late, very expensive research path** (a decade or more, tens of billions, with failure risk). M21 made EUV tools a market good with a two-year lead in shortages, and M22 controls them. This section makes the supplier real and adds the race and the long bet. **History holds to 2025** (`equipment.yaml`, research `docs/v4-research/equipment-dossier.md`).

### 47.1 The supplier and its tools

- **ASML** becomes a chain company (§41.1) making tools by **generation**: DUV immersion (ArF-i, the 28 nm to 7 nm workhorse), low-NA EUV (NXE, from the data's first volume, about 2018–2019 for 7 nm-class), and high-NA EUV (EXE, first shipments in the data, about 2024–2025), with price, throughput (wafers an hour), uptime and the nodes each serves. Rival DUV makers (Nikon, Canon) supply older generations; no one else supplies EUV to 2025.
- **Capacity:** tools shipped a year by generation follow the data to 2025, then ASML's December capex rule (§41.2) on its order book.

### 47.2 The queue

- Each December every buyer (the player, rival foundries, IDMs) places orders by generation for delivery from the next year. Orders join a queue; deliveries are allocated each quarter by `queue order × buyer weight`, where the weight rises with the buyer's order history and prepayment (`equipment.prepay_weight`) and falls when a rule blocks the destination (§39). Lead time is shown as a range at ordering.
- A fab's EUV node completes only with its tools (as §38). A conversion to an EUV node waits for its tools.
- **Prices** rise by generation and with the queue's length (`equipment.price_scarcity`); a prepayment (`equipment.prepay_share` of the price, a one-off) moves the buyer up.

### 47.3 Export controls on tools

- M22's rules on `euv_tools` and advanced DUV keep biting as dated (Netherlands and Japan rules from 2023, with the US's); from 2026 seeded tightening and loosening by bloc relations. A blocked buyer's queue place is lost; servicing of installed tools may be restricted (`equipment.service_ban_uptime_cut`).

### 47.4 The player's own lithography programme

- A **lithography** research domain (the R&D tree, §21) unlocks at stage 5 with the player's chip design and fabs: generations `litho_1` (a DUV-class tool), `litho_2` (low-NA EUV-class) and `litho_3` (high-NA-class), each needing the previous and a minimum research spend and staff (optics, precision mechanics, light source: existing skills `chip_design`, `manufacturing`, `research` weights).
- Each generation's programme has a hidden success draw and overrun (stream `equipment`, as §35's mines): a cost range in the tens of billions, 4–8 years per generation, with a chance of failure that falls with research spend and staff skill. Results arrive as **prototype tools** with lower throughput (×0.4–0.7), lower uptime and lower yield (−5 to −15 points at first) that improve with installed use.
- The player's tools can equip its own fabs (skipping the queue and controls on ASML's tools) and, from `litho_2`, be **sold** to rival foundries, which buy when the queue for ASML's is long and the price is lower. ASML responds by cutting price and accelerating its next generation.

### 47.5 Balance targets (printed)

1. **History holds:** tool shipments, prices, generations and dated controls to 2025 follow the data; every earlier guard unchanged.
2. **The queue is real:** in 2027–2032 a new EUV buyer's median wait is at least 18 months and a long-standing buyer's at most 12; a buyer under a tool ban gets none.
3. **The long bet rarely pays early:** a programme started in 2028 with funding at the 60th percentile reaches `litho_2` by 2039 on 2–5 of 10 seeds; when it does, the fab's cost per good die on its tools comes within 15% of ASML-equipped within 5 years.
4. **China under controls:** a Chinese foundry's EUV-class capability arrives later than the leading foundries by at least 8 years (median) while the bans hold.
5. **Turn time** within the guards.

### 47.6 What the API may show

Tool generations, published prices and throughput, the player's queue place as a range, deliveries, controls. Never the allocation weights, a programme's hidden success draw or overrun, or ASML's capex intentions before announced.

### 47.7 As built (M33 notes)

- **Data.** `equipment.yaml`: ASML (DUV immersion, low-NA NXE, high-NA EXE), Nikon (ArF immersion) and Canon (KrF, i-line, nanoimprint, not queued); each generation's models with rated throughput (EUV at 30 mJ/cm²), uptime, price and shipments a year 2010-2025 on ASML's 20-F "units recognised" basis (low-NA 26, 31, 42, 40, 53, 42, 47 for 2019-2025; high-NA 2 and 3 in 2024-2025; ArF immersion 82 ... 133), prices as sales over units at the ECB's annual rate, buyers' shares, queue rules and China's own EUV-class window. Every value is tagged V/D/R/A with its source (`tests/unit/test_m33_equipment.py` checks every value line). DUV generations are shown, not queued: their cost stays inside a fab's capex as before.
- **The queue.** Rivals (TSMC, Samsung, Intel, memory makers, SMIC at a zero share) top their open orders each December up to `queue.rival_order_share` x next year's capacity x their share (from 2026 a Chinese foundry no rule blocks orders `china_share`). Each quarter's tools are `floor(C x (q + 1) / 4) - floor(C x q / 4)`, so a year delivers its shipments exactly. Allocation is in order of **place**: `month placed - history_months x min(1, delivered in history_years / history_tools) - prepay_months x prepaid + jitter_months x (u - 0.5)` (47.2's "queue order x buyer weight", M33 decision: a proportional share let one large order from a new buyer outrun TSMC). The lead range shown runs the queue forward with the place `estimate_months` earlier and later.
- **Prices.** List: the data's by year, then `price.growth` a year; from 2026 x `1 + price.scarcity x max(0, open / next year's capacity - 1)` (at most `max_scarcity`) x ASML's response multiplier. A fab's tools stay inside its capex; from 2026 its order changes the capex by `tools x (price - list)`, a prepayment adds `prepay_share x price x tools`, and tools from stock reduce it by their value (at most `programme.tool_capex_share`).
- **ASML's December rule** (from January 2026): with open orders above `expand_backlog_years` x this year's capacity it builds to its plan (equipment.yaml `capacity_plan`: 90 low-NA by 2027, 20 high-NA by 2028, linear from 2025's shipments, then `plan_growth` a year), else `hold_growth`; after the player sold own tools in the 12 months before, the newest generation grows `accelerate` more and prices fall `sales.asml_cut` (at most `asml_cut_max`).
- **Fabs.** An EUV fab's tools: ASML stock, then (with `own_tools`) its own, then an order for the fab. It goes live no earlier than its last tool plus `fab.euv.install_months`; while the order is open (or lost to a rule, until a new order completes) its live month or conversion stays a quarter and the installation away. A conversion to another generation's node orders the full set. A live fab's starts on offer are x its tools' factor (a service ban, or own tools' uptime and yield cut).
- **Controls.** An order is lost when equipment.yaml's dated queue rules (to December 2025: the Netherlands' 2019 EUV practice, high-NA never licensed to China, January 2024's DUV revocation) or a biting M22 rule on `euv_tools` covers its country (or names the buyer) and, for the player, no tool licence covers it. A biting ban cuts installed tools' uptime by `service_ban_uptime_cut`.
- **China.** After 2025 a Chinese foundry reaches a node that needs EUV only with EUV-class tools: ASML's delivered to it, or its own in `china_tools.window` (stream `equipment` key (2, foundry)). 41.5's lag still shrinks; the reach waits.
- **The programme.** The `lithography` domain (tech_frontier.yaml; research skill hardware design 0.4, manufacturing 0.35, chip design 0.25: the brief's "research" weight is not a skill) opens at stage 5 with a chip product and a fab. A stage needs the previous one to have worked, a lithography project of `staff` researchers and the `level`. At its start it draws work `U(months) x work_scale x (1 + overrun)`, the overrun and the success draw (hidden). It spends `funding x cost / middle months` a month and progresses `funding x min(1, researchers / staff) x clamp(skill / 10, 0.5, 1.5)`; at the end it works when `u < clamp(success_base + success_funding x (mean funding - 1) + success_skill x (skill - 10) / 10)`. A working stage draws its first tools' throughput and yield cut and opens a line of `tools_per_year` at `tool_cents`; maturity `1 - exp(-installed tool-months / learn_tool_months)` lifts throughput, uptime and yield. From `litho_2` rivals buy the line's stock each December when ASML's book is long (sales.py).
- **ASML, Nikon and Canon** are chain_companies.yaml `equipment_makers`, run by these rules; not the world's goods, groups or bids (M33 decision; books are a follow-up).
- **Readings (47.5, seeds 1-10, the initial keys):** a new buyer's median tool wait 18 months, a long-standing buyer's 9; SMIC and a player order to China get none; `litho_2` by 2039 on 5 of 10 seeds (2-5), die cost 0.94-0.98 x ASML-equipped 5 years on; China's EUV-class lag 9.1 years (median).

## 48. Regulation with teeth (M34; v4)

Reece (2026-11-13): regulators **can force a break-up or unbundling** (for example separating the app store from the devices business), as a **rare and visible threat with warning signs years ahead**; most outcomes are lesser remedies. This section adds designations, duties, investigations, fines and structural remedies, by region, for the player and rivals alike, using M31's platforms and the existing antitrust review (§28.7), influence (§32.5) and persona (§32.4). **History holds to 2025** (`regulation.yaml`, research `docs/v4-research/regulation-dossier.md`).

### 48.1 Regulators and designations

- Each region has a **regulator** record (EU Commission, US DOJ and FTC, UK CMA, Japan JFTC, Korea KFTC, China SAMR) with a strictness path (data to 2025; seeded after, moved by politics and §32.5 influence).
- **Gatekeeper designation** (EU from 2023, others from their dates): a company is designated in a region when it runs a platform (§44) or a core service with users and revenue above that region's thresholds (data: the DMA's 45M monthly users and €7.5B turnover or €75B value). Designation brings duties (§48.2). The test runs each December; a warning arrives a year before a likely designation (when within 80% of thresholds).
- **The game's economy (PM ruling, 2026-11-15).** In-game companies earn about a tenth of their real revenue, so every money and user threshold, and the investigation revenue floor (§48.3), is multiplied by `economy_scale` (balance.yaml, shared) before the game compares it: `money` = the designated incumbents' in-game 2025 booked revenue over their real 2025 revenue (Apple 0.095, Microsoft with Azure 0.128, Meta 0.032; mean **0.0849**, `tools/m34_economy_scale.py`, seeds 1-3); `users` = 1.0, because the game's user tests read shares of a region's users, which are already at real scale. Screens show the law's figure with the game-scale amount beside it. Fines stay a share of turnover, unscaled.

### 48.2 Duties

- Duties by region and date: side-loading and alternative stores, alternative payments and anti-steering, interoperability, no self-preferencing (§44.5's setting forced off), data portability, fee caps. They change the designated platform's rules and fee schedule (`platform_fee_rule`, ADR-0021) and cost compliance (`regulation.compliance_cents` per duty a year).
- **Non-compliance** (the player may keep a forbidden setting) raises an investigation's chance and size.

### 48.3 Investigations

- Each month a regulator may open an **investigation** of a company (stream `regulation`) with a chance rising with: market share in a category above `regulation.dominance_share` (40%), self-preferencing, removals of rivals' apps, fee level, acquisitions of nascent rivals (§28), non-compliance, the persona's Ruthless trait, and complaints (M31's "go to regulators"); falling with influence (§32.5) and compliance.
- **Visible stages:** inquiry (6–12 months), statement of objections (or a US complaint), ruling, appeal (12–36 months). Each stage is an inbox item; the player can **settle** (commitments: a duty or a fee change, ending it), **contest** (odds shown as a range), or **lobby** (§32.5).
- **Outcomes:** dismissal; **fines** up to `regulation.max_fine_share` (10% of global turnover, 20% for repeat) posted to `6970_fines` (new); behavioural remedies (duties as §48.2); and, rarely, **structural remedies** (§48.4).

### 48.4 Break-ups and unbundling

- A structural remedy is possible only after a **ruling against the company in the same market within the previous 5 years that it failed to comply with**, or after two rulings in 10 years, and only where the region's strictness allows it. **Warning signs** start at least 3 years before: press coverage (§29), a regulator's report naming the remedy, a political event, board concern (§14).
- The order names the unit to separate (the platform from the devices, the store from the OS, an acquired company): the player has 24 months to **spin it off** (§31's spin-off, the player keeping shares pro rata, distributed to shareholders) or **sell it** (§28); doing neither brings daily fines. Appeals can delay it by 12–36 months with odds shown as a range.
- Rivals face the same rules: Google, Apple, Meta, Amazon and Microsoft follow their 2010–2025 histories (fines, duties, rulings) and from 2026 the same model.

### 48.5 Balance targets (printed)

1. **History holds:** every dated rule, designation, fine and ruling to 2025 follows the data; every earlier guard unchanged.
2. **Most big platforms meet a remedy:** a player platform with 40%+ of users in the EU and US by 2028 faces at least one duty or fine by 2034 on at least 7 of 10 seeds.
3. **Break-ups are rare and warned:** a dominant player who ignores warnings and keeps self-preferencing receives a structural order by 2039 on at most 2 of 10 seeds, never with less than 3 years of warning; a compliant one on none.
4. **Compliance and influence help:** settling early and $500k a month of influence in a region cut the expected fines there by 30–60%.
5. **Rivals are regulated too:** at least one rival platform owner faces a new duty or fine after 2026 on 8 of 10 seeds.

### 48.6 What the API may show

Regulators, rules and their dates, designations and the thresholds, duties, investigations and their stages, rulings, fines, warnings, odds as ranges. Never the investigation draws or chances, regulators' hidden strictness path or future rules before announced.

### 48.7 Implementation notes (M34)

- **When things act.** To December 2025 designations, duties, cases, fines and rulings are `regulation.yaml`'s and platforms.yaml's (dated fee rows and rules); the model posts, logs and draws nothing before `regulation.start` (January 2026), for the player as for rivals. In January 2026 history's designations of in-game companies (Apple, Microsoft and Meta under the DMA; Apple under Japan's, the UK's and Korea's regimes) become duties dated as the data has them; their compliance costs start then, and a duty platforms.yaml already carries for that country is not added twice (so Apple's UK duties from April 2026 are its first new ones). Companies outside the game (Google, Amazon's retail arm, ByteDance, Booking) are history and precedent only.
- **Designation** (§48.1): the users test reads platforms only (a device platform's share of device users; a developer platform's of its category's customers): the game counts no individual users of other products. Thresholds: the DMA's 45M is 10% of the EU's 447M; Japan's 40M is 31.7% of its 126M; Korea's law covers every app store; the UK's "entrenched market power" reads `regulation.dominance_share`. Money: turnover in the region (the regulator's part's population share of it) or market value for listed companies, converted at `regulation.fx`. A company over the thresholds is warned in its first December and designated in the next, so a warning always comes a year ahead.
- **Duties** (§48.2) add `regulated` rows to the group's platforms in the region (ADR-0021 3): side-loading and anti-steering as dated rules, alternative payments as a path at the standard rate less `alt_discount`, a fee cap on the standard rate; no self-preferencing and anti-steering set those rules off. Only the player can breach a duty (by turning a forbidden setting back on); rivals comply.
- **Investigations** (§48.3): a case needs a cause and `min_revenue_cents` of revenue in the region; one regulator has at most one open case on a group and waits `cooldown_months` after one closes. Settling at the inquiry costs no fine; at the charges `settle_share` of the fine at the middle of its range. A ruling's fine posts at once; a won appeal returns it. Lobbying a case costs `lobby_cents` and counts as `lobby_influence` on its odds.
- **Structural orders** (§48.4) are a ruling's outcome (stream `regulation`, (1, case, 3)); the order names the player's own platform (its OS and store) for a devices case, a single subsidiary selling in the market, or the group's products there. A sale goes to the rival with the most customers in the market at `sale_multiple` x the unit's year of revenue (4930 for the seller, 1800 for the buyer). A spin-off is §31.5's and needs the unit in a subsidiary of a listed holding company; otherwise the order stays open and periodic penalties follow its deadline.

## 49. Electric vehicles (M38; v5)

Reece (2026-11-14): **electric vehicles first** among v5's new industries, on the chain v3 and v4 built: lithium from the player's mines and refineries, chips from its fabs, the car's software as a platform (§44), power for charging (§46). **History holds to 2025:** EV sales and shares by region, battery prices, subsidies, tariffs and rivals' line-ups follow `vehicles.yaml` (research `docs/v5-research/ev-dossier.md`); seeded after. Money and market sizes follow the `devices` category's convention (the game's economy scale, M35a's audit), not raw real figures.

### 49.1 The category family

- **`vehicles`** joins the unit-sale categories (§26.1) with segments: `consumer` (passenger cars), `fleet` (rental, ride-hailing, corporate) and `commercial` (vans and light trucks). Each segment has an addressable market of *new car buyers* in a region, of which an **EV share** buys electric: the share follows the data by region to 2025, then a seeded S-curve moved by battery cost, charging coverage, subsidies and fuel prices (§49.5).
- **A vehicle product** has the unit model's features and quality, plus **range** (from pack size and efficiency), **charging speed**, **autonomy level** (§49.4) and **software** (its platform, §49.3). Development weights add `automotive_engineering`'s skills as an existing-skill mix (`hardware_design`, `manufacturing`, `design`, `software_engineering`, `chip_design`); no new skills.
- **Cost of a unit** (§26.2's bill of materials): battery pack (kWh × the cell price + pack integration), motors and power electronics, chips (count and type by autonomy level: SoCs and AI accelerators from §26.3's categories, the player's own or bought), body and interior, assembly. Assembly is in an owned **vehicle plant** (a facility kind: capex, build months, capacity in units a year, staff, power from §46) or a contract manufacturer (as §26.2).
- **Rivals** from the data with their line-ups and shares to 2025: Tesla, BYD, Volkswagen Group, Toyota, Hyundai-Kia, GM, Ford, Stellantis, Geely, SAIC, NIO, Xiaomi (from 2024), Rivian; from 2026 they launch and price by §26's rival rules and personality.

### 49.2 Batteries

- **Cells** are a market good (§33): price per kWh by year to 2025 from the data (BloombergNEF pack-price survey: about $1,100/kWh in 2010 falling to about $115 in 2024 *(verify)*), then a seeded learning curve tied to cumulative production and M17's lithium, nickel and cobalt prices. Suppliers are chain companies (CATL, BYD, LG Energy Solution, Panasonic, SK On, Samsung SDI) with capacity and countries.
- **Own cell plants** (gigafactories; a facility kind, stage 4, a one-off): convert lithium hydroxide (M20's refined good), nickel, cobalt, manganese and graphite (M17 commodities; graphite added if missing) into cells by chemistry (`nmc` or `lfp`, with different inputs, energy density and cost), with yield learning like §38's fabs. Group supply follows M23a's rules.
- Battery chemistry choice is a product setting: LFP cheaper and heavier (less range), NMC denser and dearer.

### 49.3 The car as a platform

- A vehicle product runs a **car platform** (§44's device platform kind, `car`): the player's own OS, a licensed one (Android Automotive), or a closed in-house system with no apps. Catalogue and developer rules apply as §44, with car-specific apps (navigation, media, charging, autonomy subscriptions).
- **Software revenue:** subscriptions per car (`vehicles.software_attach` by year) for connectivity and driver assistance, booked monthly over the car's life (§10's subscription revenue), and over-the-air updates that raise a model's features after sale (`vehicles.ota_features`).

### 49.4 Autonomy

- An **autonomy** research domain (§21) with levels L2 (driver assistance), L2+ (hands-off on highways), L3 (conditional), L4 (driverless in a zone). Each level needs the domain's lead, AI model quality (§26's ai_models), chips (TOPS per car), and **regulatory approval** by region (§48's regulators, with an `automotive` kind: approval stages and dates from the data, seeded after).
- Higher levels raise feature scores and software attach; incidents (stream `vehicles`) at L3+ can trigger recalls and investigations. Robotaxi services are out of scope here (a follow-up for M39).

### 49.5 Charging, subsidies and tariffs

- **Charging coverage** by region (public chargers per EV, data to 2025, then growing with EV stock and investment) raises the EV share and the feature score of cars with fast charging. The player can build a **charging network** (a facility kind: sites, chargers, power from §46, revenue per kWh sold) open to all EVs or exclusive to its own (an exclusivity boosts its cars' features but draws §48 scrutiny once its share is large).
- **Subsidies** by region and date (China's purchase subsidies to 2022 and tax exemption, the US federal credit including the 2023 IRA rules and its 2025 end, EU countries' schemes; data to 2025, seeded after) lower the buyer's effective price for eligible cars (price caps, local content, battery sourcing rules: an IRA-style rule checks the cars' cell and mineral origins against §39's blocs).
- **Tariffs** on imported cars by origin (US 100% on Chinese EVs from 2024, EU countervailing duties from October 2024, others) through §39's tariff model.

### 49.6 Balance targets (printed)

1. **History holds:** EV shares, battery prices, subsidies, tariffs and rivals' shares to 2025 follow the data; every earlier guard unchanged (a software or chip company's game unchanged except through shared commodity and chip demand).
2. **The S-curve:** global EV share of new cars reaches 35–65% by 2035 (median, 10 seeds), faster with cheaper batteries.
3. **Integration pays in cars:** a car maker with its own cell plant and lithium supply has a median gross margin at least 4 points above the same maker buying cells, by 2034.
4. **Software matters:** a car with an own platform and L2+ earns 4–15% of its lifetime revenue from software by 2035 (re-banded from at least 10% by the product manager, 2026-11-16; read on a December 2035 car: its month's subscriptions per car on the road over its segment's replacement months, lengthened by over-the-air updates, against its price).
5. **Tariffs and rules bite:** a Chinese-made car's share in the US stays under 2% while the 2024 tariff holds.
6. **Turn time** within the guards.

### 49.7 What the API may show

Vehicle products and their specs, EV shares, battery prices, subsidies and tariffs, charging coverage, rivals' public line-ups and shares, approvals and recalls. Never incident draws, seeded future rules or prices before they happen, or rivals' plans.

**Conglomerate view (M43r, Codex review 9 finding 3):** a build's committed capital in the capital-allocation panel is the facility screens' public projection (`tst.sim.facilities.public`): the quote (fab, refinery, power plant, cell plant), a mine's estimate or revision, else the open capex, less payments, never below 0. A hidden overrun never moves it.

### 49.8 As built (M38 notes)

- **Scale.** A region's game buyers are its real new car buyers x `vehicles.scale` (0.085, M34's `economy_scale.money`, the devices incumbents' in-game over real revenue), at real prices in 2010 dollars. The vehicles market's addressable customers are set each month (phase 9, and at a new game) as `car sales x segment share x EV share x scale x replacement_months / 12 / units_per_customer`, so a month's replacements are about a month's EV sales; categories.yaml's D0 is North America's January 2010 value of it. New car sales hold at 2025's after the history. Regions use vehicles.yaml's own sizes, not categories.yaml's region sizes. Segments: `consumer` (1 car, 96 months), `fleet` (sales-led, 50 cars a customer, 48 months), `commercial` (sales-led, 20, 84).
- **History holds by a pin.** To December 2025 each car maker's customers in a region's segment are its vehicles.yaml share of the market not held by other companies' lines (`D - others`), set after demand each month; a line has no price before its launch month (NIO June 2018, Rivian September 2021, Xiaomi April 2024); car makers do not decide or fail before 2026 (rivals' month and insolvency skip them) and open with `vehicles.rival_cash_cents` of capital. A rival car maker's cost of goods is 82% of its own price (`rival_cost_share`), not the market's `hosting_cents`. From 2026 they decide by 15.3's rules; each December one may refresh its line (stream `vehicles` (3, rival key)); a maker stays out of a region whose vehicles tariff on its origin is at least `tariff_block`.
- **The S-curve** (49.1): the logits start at December 2025's shares; `k` is drawn per region in December 2025's phase 9 and the logit rises `k_eff / 12` a month from January 2026, `k_eff = max(floor_k, k x (1 + battery x (1 - cell price / Dec-2025's) + charging x coverage + subsidy x subsidy / reference price))`, capped at `s_curve.cap`. Fuel prices are not modelled (a follow-up).
- **Cells** are the M17 commodity `battery_cells` ($ a kWh in 2010 dollars): history = BNEF's pack price x the cells' share (checked against vehicles.yaml at load); after 2025 M17's AR(1) reverts to the learning curve `p_2025 x ((1 - m) x (C / C_2025)^log2(1 - rate) + m x NMC metals now / Dec-2025's)`, with `C` growing with the world's EV sales; M28's chain companies (CATL, BYD Battery, LG Energy Solution, Panasonic Energy, SK On, Samsung SDI and the rest) add their balance factor. Nickel, manganese and graphite join M17's commodities (graphite's export rules now bite on cell plants' graphite).
- **A car's cost** at sale (5000): cells at the market x the chemistry's and supplier's factors, pack integration at the market's share, the drive by year, chips for its level (own chip at unit cost, else the device-OEM price), the body at `hardware.bom.vehicles` x the `vehicle_bom` index (held at December 2025 after it); assembly is 26.2's (vehicle plants, kind `vehicle_plant`, or contract assembly). Own cells: the cell plant's costs post in phase 4 (materials at spot, power at the region's grid price, `other_share` x the market price, fixed `fixed_share` of capex a year); its kWh go as lots to the group's lines on own cells (last month's cars x pack), after sales the market price of the cells taken is reversed and a sister company pays the transfer price; the rest sells at spot (4410). A cell plant's materials count as its company's commodity use, so the group's lithium converters and mines supply it through M20's own supply.
- **Software** (49.3): every car on the road pays connectivity (`attach(year) x attach_mult x price_cents` by platform; attach rises `attach_growth` a year after 2025 to `attach_cap`) and its level's subscription (`level.attach x level.price_cents`) each month, to 4000; a licensed platform pays `licence_cents` a car sold (5150). An own platform needs a live own OS product; an over-the-air platform cuts churn by `ota_churn_cut`. Car platforms are not M31 `Platform` records (a follow-up: catalogues and developers for cars).
- **Autonomy** (49.4): the `autonomy` domain (`tech_frontier.yaml`; vehicles weigh devices 0.6, autonomy 0.4); a design reaches the highest level at or below its aim its lead (and, for L3/L4, its best live AI model) allows, and runs in a region the highest of those approved there and not suspended. Approvals: vehicles.yaml's automotive regulators to 2025, then a December chance per region and level. Incidents at L3/L4 recall the region's cars running the level (6900), cost brand and suspend the level for the company there; regulators' cases (M34) are not opened by incidents (a follow-up).
- **Charging** (49.5): public chargers are the data's to 2025, then grow with EV sales, plus companies' networks at real scale; coverage = chargers per EV sold a year / `coverage_ref`. A network sells `chargers x kwh_per_charger_month x use` at the region's price (4440), buys its energy at the grid price (5000); an exclusive one gives the owner's cars points and is ordered open once it holds `scrutiny_share` of public chargers.
- **Subsidies and tariffs** (49.5): buyers weigh a car's price less the region's average subsidy it qualifies for (`Effects.price_cut`), the price paid is unchanged; vehicles.yaml's tariffs join tariffs.yaml's schedules for the `vehicles` good (39.3), so a player's imported car pays them on its cost of goods. Rates are capped at 100%.
- **Saves made before M38** have no vehicles market and no records (as M12a's and M12b's markets).


## 50. Medical devices (M41; v5)

Reece (2026-11-14): **medical devices with realistic approval stages** (FDA-style 510(k) and PMA, studies, recalls). This section adds medical devices as a category family with their own regulators, clinical evidence, reimbursement and hospital buyers, reusing M34's regulator machinery (§48) with health kinds, and M21–M26's hardware and chips. **History holds to 2025:** market sizes, approval timelines and rates, dated rules (EU MDR) and rivals follow `medical.yaml` (research `docs/v5-research/medical-devices-dossier.md`); seeded after. Money and market sizes follow the game's scale (M35a's audit).

### 50.1 The category family

- **`medical_devices`** with sub-categories (each a category with its own market, rivals and risk class):
  - `wearables_diagnostics`: consumer and clinical wearables, glucose monitors, home diagnostics; ties to the player's `devices`;
  - `imaging`: ultrasound, CT, MRI and imaging software;
  - `surgical_robotics`: robotic surgery systems, instruments and service;
  - `implantables`: cardiac devices, neuromodulation;
  - `samd`: software as a medical device, including AI diagnostics, built on the player's `ai_models`.
- **Customers:** hospitals and health systems (the `enterprise` segment, buying through value-analysis committees and group purchasing: a long sales cycle and a price set per contract), clinicians (who adopt through training and evidence), and consumers for wearables. Revenue models per sub-category: units, units plus consumables (robotic instruments and sensors per procedure), and subscriptions (software and service).
- **Rivals** from the data with shares to 2025: Medtronic, Johnson & Johnson MedTech, Abbott, Stryker, Boston Scientific, Siemens Healthineers, GE HealthCare, Philips, Intuitive Surgical, Dexcom, Edwards Lifesciences, BD; Apple in consumer health features from 2018.

### 50.2 Risk classes and routes to market

- Each device design has a **risk class** (US class I, II or III; EU class I, IIa, IIb or III) from its sub-category and intended use, and a **route** by region:
  - **US:** exempt (most class I); **510(k)** (substantial equivalence to a predicate device, needs a predicate in the market); **De Novo** (novel, low-to-moderate risk, no predicate); **PMA** (class III, needs pivotal clinical evidence).
  - **EU:** CE marking through a notified body under the **MDD** to May 2021 and the **MDR** from 26 May 2021 (more clinical evidence, longer reviews, notified-body capacity limits); legacy devices' transition dates from the data.
  - **Other regions:** Japan (PMDA), China (NMPA), others by data, with a simplified route of the nearest kind.
- **Review time** by route and region from the data (FDA's performance goals and observed totals, MDR's notified-body backlogs), shown as a range; **outcomes** by route with historical rates (a request for more information, approval, or refusal).
- **AI and software:** SaMD and AI-enabled devices follow the same routes (most by 510(k) or De Novo); a model update that changes intended use needs a new submission unless a **predetermined change control plan** was approved (FDA guidance, from its dates).

### 50.3 Clinical evidence

- **Studies** are research projects of a new kind: feasibility, pivotal and post-market. Each has enrolment (patients, sites), duration, cost per patient by sub-category, and an endpoint. The result is drawn (stream `medical`) with a success chance from the device's quality and the design's evidence strength, shown as a range; failures can be redesigned.
- PMA needs a successful pivotal study; MDR class III and implantables need clinical evidence too; 510(k) usually needs only bench and sometimes clinical data.
- **Evidence strength** also drives clinician adoption and reimbursement (§50.4).

### 50.4 Reimbursement and adoption

- **Reimbursement** by region: in the US, coverage (national or local decisions), a payment code, and payment levels; elsewhere national health technology assessment with a price. A device without coverage sells only to early adopters at `medical.no_coverage_share` of its market. Coverage decisions take months to years and read evidence strength.
- **Clinician adoption** follows an S-curve driven by evidence, training (the player's clinical education spending) and peer use; switching costs are high for robotic systems (training and installed base), like §44's lock-in.

### 50.5 Manufacturing quality, recalls and surveillance

- Medical devices are made in plants with a **quality system** (a facility setting: investment in quality raises audit outcomes and lowers defect rates). Regulators inspect (§48's investigation machinery with a `health` kind): findings range from observations to warning letters, import bans and consent decrees.
- **Recalls** (stream `medical`), classes I (serious harm) to III, from defect rates and post-market signals: cost (field actions, replacements), brand and clinician-trust damage, and possible investigations and lawsuits. A class I recall is a critical event.
- **Post-market surveillance** (adverse-event reporting, registries) is a monthly cost that lowers recall severity when signals are caught early.

### 50.6 Balance targets (printed)

1. **History holds:** market sizes, approval timelines and rates, the MDR's dates and rivals' shares to 2025 follow the data; every earlier guard unchanged (a company without medical devices plays exactly as before).
2. **Routes differ:** median time from submission to US clearance is 4–12 months for 510(k), 8–18 for De Novo and 12–36 for PMA including the review (not the study); EU class III under the MDR takes longer than under the MDD on 8 of 10 seeds.
3. **Evidence pays:** a device with a successful pivotal study reaches coverage and 30% clinician adoption at least 2 years earlier than one without.
4. **Quality pays:** a plant at high quality investment has at least 60% fewer class I recalls than at low over 10 years.
5. **A real business:** a `surgical_robotics` entrant from 2026 with competitive quality earns at least 40% of its revenue from instruments and service by year 8 (the razor-and-blade model).
6. **Turn time** within the guards.

### 50.7 What the API may show

Devices, their classes and routes, submissions and their stages, review ranges, studies' designs and results once read out, coverage decisions, adoption, inspections and recalls that happened, rivals' public products and shares. Never study draws before readout, recall or inspection draws, or seeded future rules before they happen.

### 50.8 As built (M41 notes)

- **Markets to the game's scale:** D0 = medical.yaml's real 2024 world revenue x `economy_scale.money` (0.0849) / (a customer's yearly spend x 2.236, the regions' size x price index summed, x 0.65, the incumbents' starting share), taken back to 2010 by `growth_by_year`; a test holds 2010 and 2024 within 25% of real. Study costs per patient are real money, as salaries are (the economy-scale audit decides later).
- **The gate:** a device's share of a region's demand = (the parts cleared by their health regulator, M34's part shares, plus the rest by reliance) x (1, or `no_coverage_share` until covered where payers pay) x (`adoption.floor` + (1 - floor) x clinicians' adoption); zero during a recall's stop and, in a regulator's part, an import ban or consent decree. It multiplies new wins through M22's access map; existing customers keep buying. Rivals' devices are history's, cleared wherever they sell.
- **Consumables and service:** installed units x `consumables_cents` a month at the region's price index (4050), with its cost share (5000), for every selling device, rivals' included.
- **Reviews:** at filing, months = U(window by date) + U(more_info months) when a request is drawn + the change control plan's months, x the regulator's drift after 2025; the decision at that month: approve = route rate + `review.quality_weight` x (quality - 50) + `review.evidence_weight` x evidence, within bounds. A warning letter holds that regulator's decisions.
- **Studies:** chance = kind's rate + `study.quality_weight` x (quality - 50) + `study.evidence_weight` x evidence; shown +/- `shown_band`. Evidence adds the kind's strength (pivotal 0.6) on success.
- **Coverage:** months ~ U(lo, lo + (hi - lo) x (1 - 0.8 x evidence)); approve = lerp(approve range, evidence). **Adoption:** a += r x a x (1 - a), r = `rate` x (1 + `evidence_weight` x evidence) x (1 + `training_weight` x min(1, training / `training_full_cents`)), from `seed` at first clearance.
- **Recalls:** monthly chance = `chance_year` / 12 x the quality level's defect x (1 + `install_weight` x log10(1 + installed units)); class by the data's mix, one class lower when surveillance catches it. **Inspections:** monthly chance = `chance_year` / 12 x strictness; findings x the level's (and a for-cause visit's) multiplier.

## 51. v4 balance targets and follow-ups (M35b)

### 51.1 Rules added by the balance pass

- **Regulators' strictness after 2025** (§48.1's "seeded after"; `tst.sim.regulation.strictness`, `regulation.strictness`): to `history_end` the data's index; then each January adds a drift `(2u − 1) × sd × √3` (a yearly step of sd `sd` 0.02) and, every `election_years` (4, the first in a seeded year of the first cycle), a political swing uniform in `swing` (±0.05); clamped to `bounds` [0.3, 1.3] each year. Stream `regulation` key (3, regulator index, year − 2010), uniform draws only. The value read is the path × (1 − `influence_cut` 0.30 × I / 100), I the most §32.5 influence any company holds in the regulator's region, clamped again. Investigations' chance (§48.3) and the structural gate (§48.4) read it. Hidden (§48.6).
- **Mergers review reads the regulators** (§28.4, the brief's "§28.7"): from `regulation.start` a review's block probability is also × (the region's strictest regulator's strictness ÷ its 2025 value) × `regulation.merger_review.open_case` (1.5) while one of that region's regulators has an open case on the acquirer.
- **Rival foundries' EUV growth waits on deliveries** (§47.2, §38.3; `market.euv_gated`): from `equipment.start`, for a foundry at an EUV-only node (in a queued generation's nodes and not DUV's), a year's seeded growth `g` becomes `g × (1 − s + s × r)`, `s` = `equipment.rival_growth.euv_share` (0.5), `r` = min(1, EUV tools ASML delivered it in the year to date ÷ its buyer share × the generation's capacity × months played / 12).
- **The lithography gate reads the group** (§47.4): "stage 5" is the group's (a holding company's, §31.2), so an operating company at stage 4 under its Holdings, which keeps the chip and the fab, may research lithography and start the programme. Before M35b the gate read the operating company and could never open.
- **Google Play's regulated rates** (platforms.yaml): the EU from March 2024 at 27% (DMA alternative billing, 3 points off); the US from October 2025 at 0% (Epic v. Google's injunction; no fee collected on linked-out purchases by December 2025).

### 51.2 Targets (printed by `tools/v4_targets.py`, weekly `test_v4_balance.py`)

The v4 scripts (`tst/balance/strategies_v4.py`) and their comparisons are played January 2010 to December 2039 on seeds 1–10 (the weekly also 11–30). ARR is 12 × the group's last month (§43).

- **T1 viable, not dominant:** median ARR 0.9–1.4 × the comparison: `platform_owner` / `devices_regions`, `power_hyperscaler` / `cloud_steady` (steady_regions with integrator's data centres selling spare capacity, no plants), `litho_bet` / `full_integrator`.
- **T2 no strategy always wins:** no v4 strategy has the top founder value in December 2039 on more than 4 of 10 seeds among §43's seven and the four v4 strategies.
- **T3 regulation bites platforms:** `platform_owner` has a duty or a fine by December 2034 on at least 7 of 10 seeds; `compliant_platform`'s median fines to 2039 are at least 30% below it.
- **T4 power binds:** the capacity each cloud company ordered by December 2032 (all of it serving its home market, North America, the most congested region) is all live at least 12 months earlier for `power_hyperscaler` (median of the seeds' paired gaps; not live by 2039 counts as 2040).
- **T5:** §44.9, §46.8, §47.5 and §48.5's targets and §43's on the combined code (their own tools). **T6:** the known misses, reported.

The rows are named `V4.T1.1` … `V4.T4` (the known-miss list matches by name). M35b carries `V4.T1.2` (known while |ratio − 1.15| ≤ 0.35) and `V4.T4` (known while the gap is ≥ 0) to M43 (`tst/balance/known_misses.py`).

## 52. Dynasty mode: the second 30 years (M37; v5)

Reece (2026-11-14): an optional **dynasty mode** continues the campaign past December 2039 to **December 2069**, with seeded eras beyond history. The standard campaign stays 360 turns. This section defines the mode, what the game does at the standard end, how every system's data continues past its last dated or seeded entry, and how rivals and the founder age. Nothing here changes a game before January 2040.

### 52.1 The mode and the end of the standard campaign

- **New game setting:** Campaign length: standard (to December 2039, 360 turns) or dynasty (to December 2069, 720 turns). Existing saves can switch to dynasty at any time before their end (a one-off confirmation).
- **At December 2039 in a standard game:** the **campaign summary** (Hall of Fame entry, legacy and dynasty scores, §32.6 and §45.7) and a choice: end, or continue in dynasty mode. A standard game that continues becomes dynasty from that turn.
- **At December 2069:** the final summary; the save stays open for browsing (read-only), with "continue in sandbox" (no score) as a later option (out of scope).

### 52.2 Data beyond its end: seeded continuations

Every series with a last dated or seeded entry before 2069 continues by a rule, from stream `dynasty` (id 65, keyed by the series' stable key and year):

- **Eras** (§26.4, `eras.yaml`): a second wave of seeded future eras with windows 2040–2065 (the M37 dossier lists candidates: fusion power, general-purpose humanoids, brain–computer interfaces, quantum advantage at scale, molecular manufacturing, space industry), each with a domain and an acceleration like §26.4's.
- **Process nodes** (§38, `nodes.yaml`): seeded successors to the last node (A10), each arriving `dynasty.node_gap_years` later than the previous (lengthening by 20% a step: Moore's law slows), with cost per transistor falling less each step and capex rising.
- **Technology frontier** (§21): research generations continue with longer gaps and rising costs (`dynasty.frontier_slowdown`).
- **Commodities, power and carbon** (§33, §46): the seeded paths continue (they already run open-ended); depletion and new discoveries (§34) continue; carbon's policy steps continue to a seeded long-run level.
- **Demographics and demand:** category growth rates decay toward `dynasty.mature_growth` by category, unless an era renews them; regions' populations follow a seeded path; new segments arrive only through eras.
- **Platforms, regulation and geopolitics** (§44, §48, §39): their seeded post-2025 rules continue; no new dated history.

### 52.3 Rivals age

- Every rival company has a **founder or CEO** person (already true for named rivals; generated for chain companies) with an age. From 2026, rival leaders retire (by age and performance, stream `dynasty`) and are succeeded by an heir, an insider or an outside hire, each with its own personality, which can change the rival's personality type (§13) and strategy.
- **New rivals** keep entering after 2039 (§9's entrants with seeded categories and dates), so the market never empties.
- **Rival companies can die and be reborn**: a bankrupt rival's brand may be bought and relaunched.

### 52.4 The founder's lifetime

- With M36's family, founders and heirs age; **death** becomes possible from age 75 (stream `dynasty`, annual chance from `dynasty.mortality` by age, lowered by low stress and family time), triggering §45.5's succession and §45.6's estate tax at once. If no heir is ready, the board appoints a professional CEO and the player continues as the family's head (§45.5).
- Without a family (Family: none), the game ends with the founder's death, or at the founder's choice to retire, with the campaign summary.

### 52.5 Balance targets (printed)

1. **Nothing moves before 2040:** every game state and guard to December 2039 identical to `main` before M37 (state-cache and golden checks), dynasty mode on or off. **As checked from M43r** (Codex review 9 finding 14): mode parity (both settings against `m37_pre_2040_hashes.json`) and a same-code differential: each run against a reference arm on the same code with M37's rules disabled (the data loaded with `dynasty.start_year` and `end_year` 200 years later, `tst.balance.m37.reference_loaded`), so a rule moved before January 2040 in both settings still shows at its first differing month.
2. **The world keeps moving:** in 2040–2069 at least 4 of the seeded eras arrive (median, 10 seeds), every category has at least 3 active rivals in each decade on 9 of 10 seeds, and no commodity's price stays below a third or above three times its 2030s average for more than 60 months.
3. **Moore's law slows:** the gap between seeded nodes after A10 lengthens, and leading-edge wafer cost per transistor falls by at most half from 2040 to 2069.
4. **Succession happens:** in a dynasty run with a family, at least one succession by 2069 on 9 of 10 seeds.
5. **Turn time:** a 2069 turn on the `full_integrator` save within M30's 500 ms guard on the CI runner, and a 2069 save within 400 MB.

### 52.6 What the API may show

The mode, the end date, eras' public windows, nodes' announced windows, rivals' leaders and successions, the founder's age and health events as they happen. Never seeded dates before their window is public, mortality draws, or rivals' succession plans.

## 53. Robotics and robotaxis (M39; v5)

Reece (2026-11-14, 2026-11-15): **robotics** among the first new industries, with **robotaxis** in the same milestone. Industrial robots first, sold to factories including the player's own; **humanoids** from the existing `humanoid_robotics` era (window 2030–2035, §26.4); **robotaxi services** on M38's L4 cars. **History holds to 2025** (`robotics.yaml`, research `docs/v5-research/robotics-dossier.md`); markets and money follow the game's scale (M35a's audit).

### 53.1 Industrial robots

- **`industrial_robots`**, a unit-sale category (§26.1) with segments by buyer industry (`automotive`, `electronics`, `general_industry`), the addressable market sized from installations a year by region (data to 2025), a reference price per robot and a service attach. Development weights from existing skills (`hardware_design`, `manufacturing`, `software_engineering`, `chip_design`). Rivals from the data: FANUC, ABB, Yaskawa, KUKA (Midea), Kawasaki, Universal Robots (collaborative), Estun and other Chinese makers.
- **Robots in the player's own plants:** any assembly, vehicle, cell or fab plant can install robots (own or bought). Each robot replaces `robotics.labour_per_robot` workers' worth of plant labour cost and raises output consistency (defect rate −), at the robot's capex and service cost. The plant's automation level is shown and drives its cost per unit (§26.2, §38, §49.1).

### 53.2 Humanoids

- **`humanoid_robots`** opens with the `humanoid_robotics` era's arrival (§26.4): general-purpose robots sold to businesses (logistics, retail, manufacturing) and, from a later seeded window, to homes. A humanoid's capability score combines hardware (actuators, a learning-curve good like §49.2's cells, measured as L3 against its first-year price), its AI model (the player's or a licensed `ai_models` product) and its chips (`ai_accelerator`, edge class).
- **Demand** grows with capability over the price of the labour it replaces (by region's wage index, §2), so adoption is fastest where labour is dear.
- Rivals: Tesla (Optimus), Figure, Agility, Unitree, UBTech, Boston Dynamics (Hyundai), and entrants after the era opens.

### 53.3 Robotaxis

- **A robotaxi service** is a product in a new category `mobility` (subscription-like revenue per ride): a fleet of L4 cars (the player's own from M38, or bought), **zones** by city where a regulator (§48, `automotive` kind) has approved driverless operation, and depots (a facility kind: chargers from §46, cleaning, remote assistance staff).
- **Rides** per car per day from demand (a city's ride market, data to 2025 for the first services, then seeded), wait times (fleet density), price, and the service's safety record. **Utilisation** drives economics: revenue per ride minus energy, depreciation, insurance, remote assistance and depot costs.
- **Safety incidents** (stream `robotics`, rate falling with the autonomy level's maturity and the AI model's quality): a serious one is a critical event that can suspend a zone's permit (as Cruise's 2023 suspension), open an investigation (§48) and hurt the brand.
- Rivals from the data: Waymo, Baidu Apollo Go, Pony.ai, WeRide, Tesla (from 2025), Zoox; Cruise ends in the data (December 2024).

### 53.4 Balance targets (printed)

1. **History holds:** installations, robot prices, robotaxi services' dates and rivals to 2025 follow the data; every earlier guard unchanged (a company without robots plays exactly as before).
2. **Automation pays where labour is dear:** a plant in a high-wage region with automation at the target level has a cost per unit at least 15% below the same plant without robots by 2030; in a low-wage region at most 5%.
3. **Humanoids follow their era:** humanoid revenue is under 1% of robotics revenue before the era's arrival and at least 20% within 8 years of it (median).
4. **Robotaxis are a utilisation business:** a fleet above `robotics.breakeven_rides` rides per car per day earns a positive contribution; a zone suspension cuts the service's revenue by at least 30% for its duration.
5. **Turn time** within the guards (500 ms on both V6 saves).

### 53.5 What the API may show

Products, fleets, zones and permits, rides and utilisation, plant automation levels, rivals' public products and services, incidents that happened. Never incident draws, seeded approvals or windows before they open, or rivals' plans.
### 52.7 As built (M37 notes)

- **Nothing before 2040.** Every rule here starts in January of `dynasty.start_year`, the rival leaders' too (52.3's "from 2026" yields to target 1; before 2040 rival CEOs still age and retire by §10). The rules are gated on the year, not the mode: only a dynasty campaign or a Sandbox reaches 2040. Proof: `tst/balance/m37.py` replays M30's nine runs to December 2039, mode off and on, identical month by month to the digests before M37.
- **The standard end is derived.** A standard campaign with December 2039 played waits at its end (`CampaignEndError`, 409; the API's `campaign_end`) until the player ends it or continues; nothing is stored in that month. After December 2069 every game ends (`dynasty_end`).
- **Eras** 2040-2065: seven in eras.yaml, drawn as 26.4's (stream `era_window`); none arrives, is aimed at or is shown before 2040 (`levels.in_play`). Their boosts are renewals, 0.03-0.05.
- **Nodes:** six successors to A3 (nodes.yaml's last future node, not A10), windows from `dynasty.nodes` at load (centred 3 years after A3's midpoint, each gap x1.2), drawn on stream `dynasty` (0, 0, j); offered from 2040 only. Cost per transistor: wafer price / density, A3's density = 1.
- **Frontier and markets** continue at load: each domain's rate x0.85 a decade from 2040; research budgets +3% a year; base growth decays to `markets.mature_growth` (0.01-0.015) with a 3-year half-life. Carbon reverts to a seeded long-run level ($120-300/t) at 15% of the log gap a year.
- **Rivals:** each January a leader retires with chance 0.06 x (age - 61), +0.10 after a losing year; an heir, insider or outside hire succeeds (25/45/30%), and the personality type may change (20/10/50%). A category below 3 active rivals gets as many seeded entrants as it takes; 30% carry a failed rival's brand.
- **The founder:** from 75, q = the SSA 2021 male period table x 0.70 x stress (0.85-1.25) x family time (to 0.90). A death settles the estate at once and hands over to the readiest heir; with none ready, the eldest living child (else the partner) becomes the head and the board appoints a CEO; with no family the game ends (`founder_died`). Without a family a founder may retire in dynasty years (`founder_retired`).

### 53.6 As built (M39 notes)

- **Industrial demand:** `D = installations a year (robotics.yaml) x segment share x robotics.scale (0.085) x replacement_months / 12 / units_per_customer`, set each month; after 2025 a region's installations grow by a rate drawn each year in `growth_after` [0%, 8%]. Industrial makers' customers are their data share of `D - others` to December 2025 (as 49.1's pin).
- **Plant automation:** line workers `W = capacity x workers_per_unit[kind]`; replaced `R = min(robots x labour_per_robot, W x max_share)`; level `a = R / W`; saving a unit run `a x min(variable_cents x labour_share, workers_per_unit x wage(region) x hours_per_month)` (wage: robotics.yaml's manufacturing labour cost an hour), taken off the variable cost a unit at sale; robots depreciate over `life_months` and cost `service_share` of the robot's price a year; yield loss x (1 - defect_cut x a). Target 2 reads the plant's conversion cost a unit at full use (line labour, fixed cost, depreciation, robots).
- **Humanoids:** capability `0.4 quality + 0.4 AI (own or 70) + 0.2 chips (own or 60)`; adoption share `cap x sigmoid(logit)`, the logit from `logit(seed / cap)` at the era's arrival rising `max(floor_k, adoption_k x (value - 1)) / 12` a month, `value = best capability / 100 x a worker's labour a year / (price / life years + service)`; `D = workers x share x scale x replacement_months / 12`; homes from a seeded 5-10 years after arrival. Actuators `first-year cost x (made / base_units) ** log2(1 - 0.18)`. A robot market that shrinks below its lines' customers takes them down in proportion.
- **Robotaxis:** covered trips `= city trips x scale x zone share`; rides `= covered x acceptance x (fare / price) ** elasticity x d / (d + wait_cars) x (0.5 + brand / 100) x cars / (cars + rival cars there)`, at most `cars x 30 x days x depot cover`; acceptance `lo + (hi - lo) x y / (y + acceptance_years)` from the city's first driverless service. Incidents `Poisson(million km x incident_rate x 0.5 ** (company km / maturity_km) x (1 - ai_cut x AI above L4's threshold))`, serious with `serious_share`. Zones' L4 approvals are M38's automotive regulators (vehicles.yaml), not regulation.yaml.

## 54. Market sizes and saturation (M43a; v5)

M37's diagnosis (2026-11-17, decision 22) found the game's economy running away: the AI-models market is about **$1.2–1.6 trillion a year in 2025** at real-dollar equivalent (`economy_scale.money` 0.0849), about **$1,600–2,600 trillion in 2039**, and about **$100,000 trillion in 2069**. World GDP is about $110 trillion. The cause is growth with no ceiling: from 2030 `ai_models` grows 25% a year for ever, era boosts add on top, and nothing makes a market slow as it approaches the size of the economy that buys from it. This section adds that ceiling for every category, recalibrates 2025 against published market sizes, and keeps the history the player has seen as close as it can.

### 54.1 A ceiling for every market

- Each category has a **ceiling** `C_c(t)`: the most its addressable market can be in a region, as a share of that region's economy (`markets.ceiling_share.<category>`, from the research dossier: for example, all IT spending is about 4–6% of world GDP, and no single category may take more than a set share of that), times the region's GDP path (`macro_history.yaml` to 2025, then a seeded path with long-run growth about 2–3% a year real plus inflation).
- **Ceilings start in January 2026** (`markets.ceiling_start_year`; PM ruling, 2026-11-18): the history to 2025 grows as before M43a. A market that comes out of the history already past its ceiling (AI models in Africa and South and Southeast Asia, about 70x) is held at its size, never cut, until its region's economy catches up; that pre-2026 excess is left for M43.
- **Saturation:** from 2026, each month a category's growth `g` (base growth plus era boosts, §21.4, §26.4) is applied as `g × (1 − A / C)`, where `A` is the addressable market. Far below the ceiling, growth is as before; near it, growth fades; a market can't pass its ceiling. Era boosts lift the ceiling of the categories they renew by `markets.era_ceiling_lift` (an era makes a market bigger, not infinite).
- **Long-run growth** after 2030 decays toward the region's economy's growth plus a category premium (`markets.mature_premium`), replacing open-ended rates such as `ai_models`' 25%.

- **As built (M43a):** A for a (category, region) is a year of its addressable customers at reference prices: addressable × p_ref × the region's price index (relative to the home region, as the game sells) × the units a customer buys a month (units / replacement months in a unit-sale market, else 1) × 12, plus a medical device's consumables (units × `consumables_cents` × 12). C = `ceiling_share` × GDP (trillions, `macro_history.yaml` `gdp` at listed years, geometric between them; after 2025 × (1 + `markets.gdp_growth[region]`) a year × the region's cycle multiplier, §41.6) × 10^14 cents × `economy_scale.money` × (1 + `era_ceiling_lift` × arrived eras with any boost to the category). Phase 9 multiplies each segment's annual growth (base + boosts, or the followed categories' mean for chips) by max(0, 1 − A/C) before the region's multiplier, then scales a (category, region)'s segments back to max(C, its value before the month's growth) if growth or the cycle took them past (`tst/sim/markets/saturation.py`), so a market held past its ceiling never grows and is never cut. Markets whose demand data sets each month (vehicles) have no growth and no ceiling here. The long-run decay applies at load for years `mature_start_year` (2030) + 1 to the year before dynasty mode (`tst/sim/markets/longrun.py`): g(y) = target + (g_s − target) × 0.5^((y − s) / `mature_half_life_years`) with s = `mature_start_year` and g_s the rate there, target = `mature_gdp_growth` + `mature_premium[c]`, only where g_s is above target; rates a table lists after s are replaced. M37's maturity (§52.2) then runs from 2040.

### 54.2 Calibration to 2025

- Each category's 2025 **served revenue** (what companies book: customers × price × units a month, plus medical consumables, × 12; Reece, 2026-11-17, M43a decision 2: published sizes are spending) at real-dollar equivalent (game value ÷ `economy_scale.money`) is compared with published 2025 market sizes (research dossier), with a band of 0.5–2× (market definitions vary). The ceilings of §54.1 bound the addressable market, so a share sits above the category's real spending share. Categories outside the band are recalibrated by their `growth_by_year` and starting sizes, keeping their 2010 starts and the shape of the curve where they can.
- **M8 target 4** (January 2024 AI demand 100–400× January 2010) is re-measured. If calibration needs it outside that band, the session reports the numbers: changing M8's band is the product manager's call (CLAUDE.md §9).

### 54.3 What may change, and how it is checked

- Unlike every milestone since M28, **history before 2026 may change** where §54.2's calibration requires it, because the history the game currently shows is wrong in scale. **As ruled (PM, 2026-11-18):** ceilings start in 2026, so the history is main's except the categories whose 2025 size was outside 0.5–2× its published figure, recalibrated by their starting sizes or growth (M43a brief, decisions). Every change to a series before 2026 is listed with before and after values. M28's history fingerprint and M30's state cache are re-recorded with the reason.
- Every earlier guard is re-run, and rules 1–4 apply. Guards that measure ratios (most of them) should hold; guards on absolute sizes are re-measured and reported.

### 54.4 Balance targets (printed)

1. **The economy is believable:** in every year to 2069, no category's addressable market exceeds its ceiling, and the sum of all technology categories' served revenue (`markets.non_tech` excluded: vehicles, medical) stays under `markets.tech_share_max` (15%) of world GDP; the addressable sum is printed beside it.
2. **2025 matches the world:** every category's 2025 market sits within 0.5–2× its published size (real-dollar equivalent), or is reported with a reason.
3. **Growth fades, not stops:** every category grows at least 1% a year (nominal) on average through the 2060s unless an era ended it; a market whose demand data sets each month (vehicles) is printed, not judged.
4. **Headroom:** no money value in a dynasty run passes 1.0e18 cents (M37's `M37.money` guard closes as met).
5. **Ratios hold:** v1–v4 strategy ratios (V1–V6, M23b's and M35b's targets) stay in their bands, or are reported under rules 1–4.
6. **Turn time** within the guards.

## 55. Pharmaceuticals (M42; v5)

Reece (2026-11-14): **pharmaceuticals**, as realistic as medical devices, reusing M41's machinery (health regulators, studies with unknown readouts, coverage, quality and recalls), which Reece approved as built (2026-11-17). **History holds to 2025** where M43a has set it: market sizes, approval rates, dated rules and rivals follow `pharma.yaml` (research `docs/v5-research/pharma-dossier.md`); seeded after. Markets and money at the game's scale (§54).

### 55.1 Molecules and the pipeline

- A **programme** is a molecule aimed at an **indication** in a **therapeutic area** (`oncology`, `metabolic`, `immunology`, `neuroscience`, `infectious_disease`, `cardiovascular`, `rare_disease`), of a **modality** (`small_molecule`, `biologic`, `cell_and_gene`), with a hidden true efficacy and safety (never shown; ranges narrow with evidence, CLAUDE.md §8).
- **Stages:** discovery, preclinical, Phase I, Phase II, Phase III, submission, approval, then post-marketing (Phase IV). Each stage has a duration range, a cost (patients × cost per patient by area and modality, plus fixed), and a **transition chance** from published rates by area and stage (for example, from Phase I to approval roughly 8% overall, with oncology lowest and haematology and rare diseases highest *(verify)*). Each readout is drawn (stream `pharma`) from the molecule's hidden values and the trial's design; the chance shown is a range.
- **Research staff** use existing skills (`research`, `data`, `ml_research`, `science` where present; no new skills); the R&D tree (§21) gains a `drug_discovery` domain whose level raises discovery throughput and the hidden efficacy distribution's mean.

### 55.2 AI-driven discovery

- A company with `ai_models` products of sufficient quality (and `drug_discovery` level) can run **AI discovery**: more candidates per year from discovery, a shorter preclinical stage (`pharma.ai_preclinical_cut`), and a modest lift to Phase I and II transition chances (`pharma.ai_transition_lift`, small: historical evidence is early). Licensing an AI discovery platform to others is a product (`dev_tools`-like revenue).

### 55.3 Approval, regulators and rules

- Submissions (NDA or BLA in the US, MAA in the EU, and the others by data) go through M41's health regulators with pharma-specific review times (standard and priority review, accelerated approval, breakthrough designation, orphan designation) and outcomes from the data, including advisory committees and complete response letters.
- **Exclusivity:** patents (20 years from filing, with term extension), US data exclusivity (5 years for small molecules, 12 for biologics), the EU's 8+2+1, orphan exclusivity (7 years US, 10 EU) *(verify)*.

### 55.4 Revenue, pricing and the cliff

- A drug's demand is its indication's patient population (by region, data) × diagnosis and treatment rates × share (efficacy and safety relative to the standard of care, class competition, the company's medical affairs and sales force).
- **Pricing and reimbursement** by region: the US list price with net discounts, Medicare negotiation under the 2022 Inflation Reduction Act from its dates (first negotiated prices from 2026) *(verify)*; elsewhere a health-technology-assessment price. Coverage reuses §50.4.
- **The generics cliff:** at loss of exclusivity, generics enter (small molecules: price −80–90% within a year with several entrants *(verify)*), biosimilars more slowly and less deeply. Rivals' generic makers (Teva, Sandoz, Viatris, Sun) and biosimilar makers enter by data and seeded rules.

### 55.5 Manufacturing, licensing and rivals

- **Plants:** a small-molecule API plant and a **biologics** plant (bioreactor capacity, long build, high quality demands), or contract manufacturers (Lonza, Samsung Biologics, WuXi Biologics, Catalent) as chain companies. Quality, inspections and recalls reuse §50.5.
- **Licensing and partnering:** in-license or out-license a programme at any stage (upfront, milestones, royalties), co-development with a partner (shared cost and revenue); acquisitions of biotechs through §28.
- **Rivals** with portfolios, pipelines and patent cliffs from the data: Pfizer, Johnson & Johnson, Roche, Merck & Co., AbbVie, Novartis, AstraZeneca, Novo Nordisk, Eli Lilly, Bristol Myers Squibb, Sanofi, GSK; biotechs and entrants from seeded rules.

### 55.6 Balance targets (printed)

1. **History holds** where M43a set it; every earlier guard unchanged (a company without pharma plays exactly as before).
2. **Attrition is real:** across seeds, the share of Phase I programmes reaching approval is 6–12% (median), with oncology at least 30% below the average.
3. **It takes a decade:** median time from Phase I start to approval 7–11 years.
4. **The cliff bites:** a small-molecule blockbuster loses at least 70% of its revenue within 24 months of exclusivity ending.
5. **AI helps, modestly:** AI discovery raises a portfolio's approvals per dollar by 10–40% (median), not more.
6. **Turn time** within the guards.

### 55.7 What the API may show

Programmes, stages, designs, readouts once read out, efficacy and safety as ranges, submissions and stages, approvals, exclusivity dates, prices, rivals' public pipelines and approvals. Never a molecule's true efficacy or safety, a readout draw before readout, or seeded future rules before they happen.

### 55.8 As built (M42 notes)

- **Scale:** game patients and all pharma money = real x `pharma.scale` (0.085): trials, plants and deals as well as sales, so a trial's cost and a drug's revenue stand in their real proportion. Drugs are programmes, not products; the seven areas are pseudo-categories (no market segments), and pharma revenue (drugs' and rivals') is booked by `tst.sim.pharma` and joins the month's MRR.
- **Readouts:** p = sigmoid(logit(T_area,stage) + w_e,stage x (efficacy - 0.5) / 0.15 + w_s,stage x (safety - 0.7) / 0.12 + design + AI), within `readout.bounds`; T is BIO 2021's rate (preclinical: Paul et al. 2010's 69%); an observed efficacy = true + N(0, noise_stage). Shown: the same formula on the readouts' mean (the prior's before any), +/- `shown_band`; efficacy shown as the mean +/- 2 noise / sqrt(n).
- **Stages:** months = the range's midpoint x the area's `months_mult` x the design's (trials), x (1 - `ai.preclinical_cut`) with AI (preclinical), x (1 - `breakthrough_cut`) with breakthrough (Phase III); cost = patients x cost per patient x the area's and modality's factors + fixed (discovery and preclinical: fixed a month), spent evenly. A redesign re-runs the stage at cost x (1 + `redesign_cost_share`).
- **Approval:** review months ~ U(the regulator's standard or priority range; a resubmission's `crl_resubmit_months`); priority when the estimate is `priority_margin` above soc, orphan, or breakthrough; an advisory committee (FDA `adcom_share`) votes half way; approve = sigmoid(logit(T_area,submission) + `efficacy_weight` x (estimate - soc) / sd - `adcom_weight` if negative) x `resubmit_factor` on a resubmission. Accelerated approval (oncology and rare disease, estimate `accelerated_margin` above soc after Phase II) starts a confirmatory Phase III at approval; its failure withdraws the US approval.
- **Demand:** treated(indication, region) = market_b(t) / the world's mean net price x the area's region share; w = exp(6 (efficacy - soc)) x exp(-3 (1 - safety)) x (1 - exp(-m / 30)) x support x (reference / list)^1 in the US; patients = treated x w / (brands + sum w) x access x (1 or `no_coverage_share` without HTA). Net price = list x (1 - the area's gross-to-net) x the region's index; Medicare's share of US patients at (1 - the IRA's discount) once picked. After exclusivity ends in a region the brand keeps floor + (1 - floor) exp(-m / months).
- **Rivals:** revenue to 2025 = their data less the modelled molecules' share of their key drugs' indications; after it, the rest of their 2025 portfolio decaying `rest_decay` a year + key drugs (held and grown to US LOE, then the cliff, IRA-cut from their data's year) + seeded approvals; generic makers grow their base and take `generics_share` of generic sales of modelled molecules past exclusivity. Costs and payouts are shares of revenue.
- **Markets under M43a's ceilings (54.1):** the areas are pseudo-categories, so `tst.sim.pharma.ceilings` applies 54.1's rule itself: from `markets.ceiling_start_year` each (area, region) level multiplies its indications' data paths, and each month the area's uncapped growth u is applied as 1 + (u - 1) x factor(A, C), A the area's sales value there a year (every indication's market x the region's share of patients x its price index x the level) and C = `saturation.ceiling_cents` with `markets.ceiling_share.pharma_<area>`; a market at its ceiling is held, not cut. Rivals' seeded approvals' peaks are x the world's factor (every area and region summed). **When (M43r, Codex review 9 finding 6):** the month's levels are computed in phase 5, before demand reads them (they were set in phase 12, after the month's sales), from the cycle and eras in force at that point; a final clamp keeps a market that was under its ceiling at it (a large data step can otherwise pass it), and one already over is held as before.
- **Measuring 55.6:** target 2 on cohorts of 100 programmes an area from Phase I (January 2021), target 5 on 700 from discovery with and without AI, played on the engine's own steps with a sensible policy; target 4's cliff is revenue 24 months after exclusivity has ended in every region against the month before it ends in any.

## 56. Space and satellites (M40; v5)

Reece (2026-11-14): **space** after EVs and robotics. Launch, satellites and constellations, and connectivity sold like cloud: capital-heavy and failure-prone. **History holds to 2025** where M43a set it (`space.yaml`, research `docs/v5-research/space-dossier.md`); markets and money at the game's scale (§54).

### 56.1 Launch

- **Launch vehicles** are products in a new category `launch` (customers: satellite operators, governments, the player's own constellations): payload to orbit, price per launch, reliability and cadence. **Reusability** is an R&D path (`reusability` domain in §21): first-stage recovery, then full reuse, each cutting the cost per kg and raising cadence.
- **Cost per kg to low Earth orbit** follows history to 2025 (about $54,500 on the Space Shuttle, about $2,700 on Falcon 9 *(verify)*), then each vehicle's own cost from its build cost, reuse and cadence.
- **Launches** can fail (stream `space`, chance from the vehicle's maturity and reliability): a failure loses the payload (insurance pays part), grounds the vehicle for an investigation (2–9 months), and hurts brand. A failure with the player's own satellites aboard is a critical event.
- **Launch sites** are facilities (licences by region, range availability).

### 56.2 Satellites and constellations

- **Satellites** are built in a satellite plant (a facility kind) or bought, with mass, capacity (Gbps), life (5–15 years) and cost; chips from the player's fabs.
- A **constellation** (a facility-like record): shells of satellites, coverage by region (once enough satellites are up), capacity, ground stations, and replacement launches. Deorbiting and debris rules by data and seeded policy.

### 56.3 Connectivity and services

- **`satellite_broadband`**, a subscription category (consumer, enterprise, aviation and maritime, government): subscribers in a region need coverage, a user terminal (a device product with its own cost and subsidy), and licences (spectrum and landing rights by country, M22's geopolitics). Capacity limits subscribers per region; congestion lowers quality.
- **Direct-to-device** (phones connecting to satellites) from its seeded era, partnering with or competing against mobile carriers.
- **Earth observation and government services** as smaller categories; defence demand comes in M44.
- **Rivals** from the data: SpaceX (Falcon, Starship, Starlink), Blue Origin, ULA, Arianespace, Rocket Lab, CASC, ISRO, Eutelsat OneWeb, Amazon Kuiper, SES, Viasat; entrants from seeded rules.
- **Dated openings (M43r, Codex review 9 finding 11):** a line whose data date opens it (a provider's first orbital launch, a constellation's service, direct-to-device) is pinned before phase 5's markets in its opening month, as phase 9's pin would pin it, so it sells from that month (Starlink from October 2020), not the month after.

### 56.4 Balance targets (printed)

1. **History holds** where M43a set it; every earlier guard unchanged (a company without space plays exactly as before).
2. **Reuse changes everything:** a fully reusable vehicle reaches a cost per kg at least 5× below an expendable one of the same era, at least 6 years after starting the domain.
3. **Constellations are capital-heavy:** a broadband constellation needs at least 8 years to positive cumulative cash flow (median), and 20%+ of runs that start one by 2030 never reach it.
4. **Launches fail:** a new vehicle's failure rate in its first 10 flights is at least 3× its rate after 50.
5. **Turn time** within the guards.

### 56.5 What the API may show

Vehicles, launches and their outcomes, cost per kg, satellites, constellations and coverage, subscribers, licences, rivals' public launches and constellations. Never launch-failure draws, seeded policy before it happens, or rivals' plans.


### 56.6 As built (M40 notes)

- **Launch** rides the hardware production path: a `launch` unit is a launch, `launch_site` is its plant (a site unit flies `space.reuse.<level>.pad_rate` launches a month at the company's best level), and its cost of goods is the vehicle's flight cost `B x ((1 - r) + r / N + r x refurb) + ops`, with `B = payload x build_cents_per_kg x (payload / ref) ** (size_exponent - 1) x quality x learning` and ops scaled the same way; cost a kg = flight / (payload x (1 - payload_cut)). Full reuse is about 6x cheaper a kg than the same design expendable at every payload.
- **Reuse levels** need lead in the `reusability` domain **and** months since the company's programme began (its lead first rose): recovery 20 points and 30 months, full 45 and 84 (21.3's research alone reaches 45 in under two years with a large team; 56.4 target 2 asks for six).
- **Failures:** `floor + (new_rate - floor) x 0.5 ** (flights / half_flights) x (1 + quality_k x (60 - quality) / 100)`, 40% to 1% (half every 4 flights); a failure grounds the line 2-9 months (seeded) and costs brand; a bought launch flies at the floor.
- **Constellations:** built in satellite plants (or bought x1.6), capitalized, launched on an own line (pads left after customer launches) or bought (Falcon 9's price and payload), insured at 7% (90% paid on a loss), cohorts depreciated over their life, replaced `replace_ahead_months` (9) ahead into the shell that will be shortest; a shell (135 satellites) opens its regions at 90%. The cash flow (target 3) is the line's revenue in every region less its subscribers' hosting, satellites, launches, premiums, ground stations ($500,000 a covered region a month), disposal, debris fees and terminals, plus terminal sales and insurance.
- **Services** gate through M31's `Effects`: no appeal outside coverage and granted licences; congestion `(capacity / subscribers) ** 1.5` over capacity (Gbps x 20 subscribers), trimmed in phase 9; `Effects.segment_appeal` closes direct-to-device without D2D satellites or before July 2025; broadband churn x0.3 from 2026; EO sells from 10 satellites up.
- **History** to 2025: launch providers hold their share of the world's launches, operators their subscribers x 0.085; no price before a first launch, a service or D2D's opening. Space companies do not decide before 2026; the three categories are `family: space` (no startups, pitches or angel starts).

## 57. Defence and government contracts (M44; v5)

Reece (2026-11-15): **defence and government contracts**, with governments buying the player's chips, satellites, AI, cloud and devices. **History holds to 2025** where M43a set it (`government.yaml`, research `docs/v5-research/defence-dossier.md`); markets at the game's scale (§54).

### 57.1 Governments as customers

- Each region's governments have **budgets** for defence and civil technology by year (data to 2025, then seeded with geopolitics, §39: tension raises defence budgets), split into programme areas: `cloud` (sovereign and classified cloud), `ai`, `space` (launch, satellites, Earth observation), `chips` (trusted supply), `devices` (rugged and secure devices), `cyber`.
- Government demand arrives as **tenders**, not as market share: each tender has a programme area, a value, a term (1–10 years, often a base and options), a contract type (`fixed_price`, `cost_plus`, or an indefinite-delivery `idiq` vehicle with task orders) and requirements (clearances, domestic content, past performance, certifications).

### 57.2 Bidding and awards

- The player bids (a one-off when above the automation limit, §40.2): a price and a technical proposal (a product's quality and features), staffed by a capture team (existing skills: `sales`, `negotiation`, `strategy`, plus the products' domain).
- **Awards** score price, technical merit, past performance (a record of delivered contracts) and requirements met; rivals bid by personality (stream `defence`). The score bands are shown; the rivals' bids are not.
- **Protests:** a loser may protest (the player too), delaying the award by 3–6 months, with a chance of re-competition (the 2019–2021 JEDI history is the reference).
- **Delivery:** cost-plus contracts pay costs plus a fee; fixed-price ones risk overruns (as §35's mines); performance affects past performance and option exercise.

### 57.3 Clearances, rules and sourcing

- **Security clearances** for staff (a person's status: none, pending, cleared; months to clear; some people never clear) and **facility clearances** for sites. Classified work needs both.
- **Export rules** (§39) and **ITAR-style controls** on defence items: a product built for defence becomes controlled, limiting its sales abroad.
- **Domestic sourcing:** bans on components from named countries (Section 889-style rules from their dates), domestic-content shares, and trusted-foundry requirements for chips: they read the product's bill of materials and the chain's countries (M23a).

### 57.4 Reputation and politics

- Defence work moves the persona (§32.4) and brand by category: consumer brands lose a little; staff with matching interests or low tolerance react (morale, and a chance of an open letter or resignations, the 2018 Project Maven history as reference); political influence (§32.5) rises with the government. Some regions' governments won't buy from a company that sells to their rivals' militaries.

### 57.5 Rivals

- Defence primes (Lockheed Martin, RTX, Northrop Grumman, General Dynamics, Boeing Defense, L3Harris, BAE Systems) and newer entrants (Palantir, Anduril, SpaceX for launch), and the hyperscalers for cloud (AWS, Microsoft, Google, Oracle under JWCC-style vehicles), with histories from the data.

### 57.6 Balance targets (printed)

1. **History holds** where M43a set it; every earlier guard unchanged (a company that never bids plays exactly as before).
2. **Government is a real but slow customer:** a company with cleared staff and past performance wins at least 25% of the tenders it bids for in its areas (median); a company without past performance wins at most 10% of large tenders.
3. **Clearances take time:** median staff clearance 6–15 months; at least 5% of candidates never clear.
4. **It costs something:** a consumer-heavy company that takes defence work loses 1–3 brand points and sees at least one staff reaction on 5 of 10 seeds.
5. **Turn time** within the guards.

### 57.7 What the API may show

Tenders, requirements, the player's bids and awards, score bands, protests, contracts and their performance, clearance statuses, rivals' published awards. Never rivals' bids, award draws, clearance draws, or seeded budgets and tenders before they are announced.

### 57.8 Notes as built (M44)

- **Governments** are twelve buyers (government.yaml): the US, the UK, France, Germany, the other EU governments, Israel, Japan, South Korea, Australia, India, Brazil and China, each a country of countries.yaml with SIPRI's defence budget (current dollars, the April 2025 database, to 2010 dollars at load) and a civil technology budget (US federal IT; elsewhere `civil_ratio` x defence). After 2025 a budget grows each year by `budgets.trend` + `budgets.tension` x (T - 50)/50 + `budgets.noise` x N(0, 1), T the January's tension (39.1).
- **Areas** map to categories: cloud `cloud_hosting`; ai `ai_models`; space M40's `launch`, `satellite_broadband`, `earth_observation`; chips the three chip categories; devices `devices` and `servers`; cyber `cybersecurity`. An area takes `defence_share` of a defence budget and `civil_share` of a civil one.
- **Tenders.** Each January a government announces `tenders.per_year` tenders (57.1), the pool being its areas' budgets x `tendered_share` x `economy_scale.money` over the count, x a mean-one lognormal; each a term of 2-8 years (`option_share` of it option years), a contract type, a clearance level by buyer, an IDIQ's 1-4 awardees, an announcement month, bids for `bid_months`, the award `evaluation_months` later. Nine named tenders (JEDI, JWCC, Maven, NSSL Phase 2 and Phase 3's two lanes, SDA Tranche 1 Transport and Tranche 2 Tracking, Secure Enclave) are history: without a player bid each goes to its record's winners at its month; JEDI is held by AWS's protest until its July 2021 cancellation.
- **Score** = w.price x P + w.technical x T + w.past_performance x PP (`bids.weights`; `large_weights` from `tenders.large_cents`), P = 100 x the lowest price ratio / the bid's, T = 0.7 x the product's quality + 0.3 x the capture team's mean of sales, negotiation and strategy (0-100), PP = `newcomer_pp` blended to the mean performance of completed contracts over the first `pp_full`. Rivals: government.yaml's primes (data bidders: their awards are published records with no books) and company bidders (incumbents' hyperscalers, Intel, Dell, HPE; merit = their best live product's quality), each bidding with `rival_bid_chance` (a named tender's historical winners always, with `history_bonus`). Requirements are pass or fail (a bid that misses one is disqualified with its reasons). The API shows the player's bands (10 points) and the lowest winner's band.
- **Protests.** A losing rival protests the player's award with `protests.rival_chance` (x `large_mult` on a large one), held 3-6 months, sustained at GAO's effectiveness rate for the year (42-57%), re-competing once. The player may protest a loss within a month (`cost_cents`).
- **Delivery** (57.2): a month's work = value / term months (an IDIQ's x U(0.4, 0.9) task orders); cost = work x `cost_share[area]` x (1 + overrun), overrun ~ N(0.02, sd by type), floored at -10%; revenue = work (fixed price, IDIQ) or cost x 1.08 (cost-plus); 4070 and 5300 against cash. Performance = 100 - 2 x the overrun in percent; options are exercised at 70 or more; three months unable to deliver is a default.
- **Clearances** (57.3): months = `sponsor_months` (3) + 0.75 x the level's fastest-90% days (PAC: Top Secret about 540 in 2018, 249 in 2024) / 30.44, x a lognormal (0.45); never clear 5% (Secret) or 8% (Top Secret) x (1 + 0.5 x (10 - integrity)/10). Facility clearances 6-12 months. A cleared person who leaves lapses.
- **Sourcing** reads M22's `made_in` (a product's plants' and contract makers' countries, a chip's foundries'): Section 889 refuses any China share for US bids from August 2019; Buy American's domestic content (50%, 55% from 2020, 60% from October 2022, 65% from 2024, 75% from 2029) for US devices, chips and space; trusted foundry: every defence chip made in the US. Classified cloud needs a data centre in the buyer's country. A product delivering a defence contract in a controlled area (ai, space, chips, devices) keeps `itar_keep[bloc]` of a country's demand (US-aligned 1, non-aligned 0.7, China bloc 0) and none in 126.1's China and Russia (the hook in M22's `sales.access`).
- **Reputation** (57.4): a defence award costs consumer lines (`consumer_categories`) 2 brand points (0.5 after, at most 3 a year), moves the founder's persona (Ruthless +3, Beloved -2), adds 4 influence in the buyer's region, records the buyer's bloc (China's buyers refuse US-aligned suppliers' militaries and the reverse), and gives objectors (an `objector_interests` interest or adaptability at most 6) a -8% morale target for 6 months; an open letter (critical event `defence_open_letter`) follows with min(0.85, 0.25 + 1.2 x the objectors' share).


## 58. Negotiations by conversation (M47; v6)

Reece (2026-11-21, 2026-11-22): **conversations** are v6's first direction; the player **types freely with three suggested replies**; conversations have **their own monthly LLM cap** (default $10, a setting) after which they fall back to template choices; and **a bad negotiation can lose a deal**. The rule above all (CLAUDE.md §2.5, ADR-0005): **the engine sets what is possible, the conversation moves the player's odds only within it**, every effect is clamped and shown afterwards, and the LLM never sees a hidden value.

### 58.1 What can be negotiated

Every deal the game already prices: an acquisition (§28), a key hire or retention offer (§7, §13), a supplier contract, offtake or foundry contract (§33, §38), a power-purchase agreement (§46), a government contract award's final terms (§57), a regulator settlement (§48), a licensing deal (§44, §55). Each deal kind names its **terms** (price, length, volume, exclusivity, equity, milestones; at most four per kind) and the engine's existing pricing gives each term a **zone**.

### 58.2 The zone and the counterpart

- For each term the engine computes the counterpart's **reservation value** (the worst it will accept) and **aspiration** (where it opens), from the deal's existing pricing plus a draw (stream `negotiation`, id 70, key `(deal kind, deal id)`). Both are **hidden**; the player sees only the counterpart's opening offer and, as talks go on, ranges that narrow as §18.8's reveals do (by the player's or delegate's `negotiation` skill and the counterpart's openness).
- The **counterpart** is a person (a rival's CEO, a supplier's sales head, a candidate, a regulator's case officer) with personality (§2), relationship with the player (§16.7) and interests; their **patience** (rounds before they walk, 3–8) and **priorities** (weights on the terms) are hidden.

### 58.3 A round

- Each round the player writes a message (free text or one of three suggested replies, which the LLM proposes from public facts) and may change the offer's terms.
- **The engine decides the response.** A message is scored by the LLM into a small, validated set of **moves**: `concede` (on a named term), `anchor`, `justify` (with a reason drawn from displayed facts), `appeal` (to relationship or interests), `threaten_walk`, `package` (trade one term for another), `close`. Each move has a fixed effect in the engine: on the counterpart's next offer (up to `negotiation.move_step` of the zone per round), on its patience (±1) and on the relationship (±2). The LLM never sets numbers; an unrecognised or invalid scoring is a `neutral` move.
- **The counterpart's reply text** is written by the LLM from the engine's decided response (its new offer, its stated reason, whether it is close to walking), within §16.5's allowlist, or by a template.
- **Persona and skill** (§32.4, the negotiator's `negotiation`, `communication` and `strategy`) scale the moves' effects within `negotiation.skill_band` (0.8–1.2).

### 58.4 Outcomes

- **Agreement** at any terms inside the counterpart's zone; the deal executes through its existing action, so books, rules and one-offs (§40.2) apply unchanged.
- **Walk-away** when patience runs out or a `threaten_walk` is called with an offer outside the zone; the deal may return later (`negotiation.cooldown_months`), and the relationship falls.
- **Skip** (always available, any time): the deal closes at the **median outcome** (the midpoint between the opening offer and the reservation value), as the game's existing pricing gives today. Delegates (§40) negotiate by skip with their quality draw, unless the player takes the conversation.
- **Template mode** (no LLM, over the cap, or in tests): the player picks moves directly from labelled buttons; the engine is identical.
- After a deal, a **debrief** shows what each round's moves did, the final terms against the opening offer and the revealed range, never the hidden reservation value.

### 58.5 Balance targets (printed)

1. **Skip is fair:** skip outcomes match the pre-M47 prices for every deal kind within 1% (median), so a player who never talks plays as before.
2. **Talking matters, within limits:** a scripted strong negotiator (score 16) gets terms 10–25% of the zone better than skip on average; a weak one (score 6) 0–15% worse; nobody beats the counterpart's reservation value.
3. **Walk-aways happen:** a script that always threatens to walk loses at least 30% of deals.
4. **No leak:** a prompt-builder test with planted hidden values shows none in any conversation prompt or reply.
5. **Turn time** unchanged (conversations run outside the turn, between turns).

### 58.6 What the API may show

Opening offers, the counterpart's public facts and stated reasons, ranges as revealed, rounds and their moves, the debrief. Never reservation values, aspirations, patience, priorities or draws.

## 59. Board meetings, earnings calls and investor days (M48; v6)

Built on M47's conversation engine (§58, ADR-0023): the engine decides every outcome within fixed bounds, the LLM classifies the player's messages into moves and words the other side, and every conversation can be skipped (the default outcome, as today) or played in template mode.

### 59.1 Board meetings

- **When:** each quarter-end board meeting (§14.6's summary today), plus extraordinary meetings the engine already calls (a removal vote, an activist's demands, a large one-off proposal under §40.2).
- **Agenda:** from the engine's facts: results against plan, the next quarter's plan, proposals waiting, and any director's concern (confidence under 50, a missed guidance, a scandal).
- **Directors** are the board's people (§14.6), each with personality, confidence and priorities (growth, margin, risk, governance; hidden weights). Each agenda item is a short exchange: the director's question (LLM-worded from facts and their priority), the player's answer, scored into moves (`commit` to a plan figure, `explain` with a displayed fact, `defer`, `concede`, `push_back`).
- **Effects:** each move moves that director's confidence by at most `meetings.board_step` (±4) per meeting, scaled by persona and the founder's `communication` and `leadership` (0.8–1.2). A **commitment** becomes a tracked promise like §29's: kept, it lifts confidence; broken, it costs double. **Votes** on proposals follow each director's confidence and priorities; skipping gives today's outcome.

### 59.2 Earnings calls

- **When:** with each quarterly report once listed (§25.4).
- **Analysts** (§25.3's 3–8, each a person with a rating, a target and a focus: growth, margin, a segment, a risk) ask questions from the report's public numbers and the guidance. The player's answers score into moves (`reaffirm`, `raise` or `lower` guidance, `explain`, `deflect`, `promise`).
- **Effects:** sentiment `S` moves by at most `meetings.call_step` (±3%) per call beyond §25.4's surprise jump, and each analyst's target by at most ±5%. **Credibility** (0–100, new) tracks kept and missed guidance and promises: it scales future calls' effects (low credibility halves positive moves) and §25.4's jumps. A deflection on a question about a real problem (a miss, a recall, an investigation) costs credibility.

### 59.3 Investor days

- An optional event the player schedules (a one-off, at most once a year) to present a strategy change: a new industry, a capital plan, a restructuring. Investors' reception (sentiment ±8% at most, credibility ±10) depends on the plan's displayed economics (the conglomerate view's returns, M43), the company's credibility, and how the questions are answered.

### 59.4 Balance targets (printed)

1. **Skip is today's game:** with every meeting and call skipped, board confidence, sentiment and prices match pre-M48 `main` (state-cache check).
2. **Talking helps, within limits:** a scripted good communicator (score 16) keeps board confidence 3–10 points higher and sentiment 2–6% higher over 5 years than skipping; a poor one 0–8 points lower.
3. **Credibility matters:** breaking three guidance promises in two years cuts the next calls' positive effects by at least half.
4. **No leak:** no director's priorities, hidden weights or draws reach the API or a prompt.

### 59.5 What the API may show

Agendas, questions, answers, moves and their visible effects, directors' and analysts' public facts and confidence, credibility, promises and their status. Never directors' hidden priorities or draws.

## 60. Start years before 2010 (M50; v6)

Reece (2026-11-22): **start years, 2008 first**, then 2000, then 1995. M50 adds **2008** (the financial crisis, the iPhone's App Store and Android's launch). The 2010 start and everything from 2010 in a 2010 game stay exactly as they are.

### 60.1 The calendar

- ADR-0024 (new): turn 0 stays January 2010. Earlier starts use **negative turns** (January 2008 is turn −24); `tst.sim.calendar` converts them, RNG streams take negative turns, and the save records its start turn. Every series keyed by year gains 2008–2009 entries.

### 60.2 History for 2008–2009

Every system's data gains 2008–2009 (research `docs/v6-research/start-2008-dossier.md`):
- **macro:** the financial crisis (GDP, rates, the venture climate's collapse in late 2008 and recovery from mid-2009, credit availability);
- **markets:** category sizes and growth for 2008–2009 at the game's scale (§54); smartphones and app stores from their dates (the App Store July 2008, Android Market October 2008);
- **rivals:** companies at their real 2008 values, with those founded in 2008–2009 entering on their dates (for example Airbnb, Uber, WhatsApp, Square);
- **eras** and the R&D tree at their 2008 state;
- **commodities, power, chips and nodes** (45 nm, then 32 nm) for the two years;
- **regulation and geopolitics** as dated.

### 60.3 Balance targets (printed)

1. **A 2010 game is unchanged:** golden snapshots, every state cache and every guard on the 2010 start are byte-identical to `main` before M50.
2. **The crisis bites:** a 2008 start's venture rounds in Q4 2008 to Q2 2009 are at least 40% scarcer and 20% cheaper than in 2010 (median), and startups with under 12 months of runway in October 2008 fail at least twice as often as in 2010–2011.
3. **The world arrives at 2010 sensibly:** in a 2008 start, by January 2010, category sizes and the named rivals' revenues sit within 0.7–1.3× the 2010 start's values (median, 10 seeds).
4. **Every strategy plays:** V1's strategies started in 2008 finish 2037 within their v1 bands, or are reported.

## 61. Press conferences, interviews and one-to-ones (M49; v6)

The last of v6's conversation milestones, on M47's engine (§58, ADR-0023): the engine decides outcomes within bounds, the LLM classifies the player's messages into moves and words the other side, and every conversation can be skipped (today's outcome) or played in template mode.

### 61.1 Press conferences and interviews

- §29.1's press moments (launches, earnings, era arrivals, outages, scandals, recalls, investigations, accidents) become live **interviews** when the player takes them: a journalist (a person with an outlet, a beat and a stance toward the company) asks 2–4 questions from public facts and the moment's subject.
- Answers score into moves: `bold_claim`, `measured`, `deflect`, `apologise`, `promise` (§29.2's tracked promises), `attack_rival`, `no_comment`. Each maps to §29.1's tone effects (bold, measured, deflect) and promises, so **skip** gives the measured answer as today, and effects stay within §29's caps scaled by §29.1's audience.
- **Crisis conferences** (a class I recall, a robotaxi incident, a breach, a scandal) add `apologise` and `take_responsibility` moves, with brand and persona effects (Beloved, Ruthless; §32.4) and regulator attention (§48) for `deflect`.

### 61.2 One-to-ones

- The player can hold a **one-to-one** with any direct report or key person (seat holders, area leads, people flagged unhappy or likely to leave, high-potential juniors), costing founder energy (`talks.energy`, 2) and at most once a month per person.
- **Topics** from the engine's view of the person: morale and its causes (pay, workload, manager, recognition, role fit), ambitions (§2's interests and stated goals: promotion, a seat, a new area, equity), a rival's approach (§13 poaching), burnout risk (§32.1 for staff).
- Answers score into moves: `listen`, `promise_promotion`, `offer_raise`, `offer_equity`, `reassign`, `push_harder`, `praise`, `warn`. Promises are tracked: kept, morale and loyalty rise; broken, they fall by twice as much. Raises and equity execute through the existing actions with their money rules.
- **Effects:** morale ±`talks.morale_step` (up to 6) per talk, loyalty and a retention chance when a rival bids, revealed interests and ambitions (§18.8's reveal, faster in talks), and stress for `push_harder`. A person's personality (ego, ambition, loyalty) scales the effects.
- **Delegated:** a seat holder can hold one-to-ones with their own reports (§40), by skip with their quality draw.

### 61.3 Balance targets (printed)

1. **Skip is today's game:** with every press moment and talk skipped, the game matches pre-M49 `main` (state-cache check).
2. **Talks retain people:** a scripted founder who holds monthly one-to-ones with flagged staff keeps at least 30% more of the people rivals approach than one who skips (median, 10 seeds), at an energy cost.
3. **Promises bite:** promising a promotion and not giving it within 12 months costs that person at least 8 morale and doubles their chance of leaving.
4. **Crises reward candour:** in a class I recall, `apologise` and `take_responsibility` recover brand at least 25% faster than `deflect`, and `deflect` raises the chance of an investigation.
5. **No leak:** no hidden trait, potential, draw or rival offer amount reaches the API or a prompt.

## 62. Telecom (M53; v6)

Reece (2026-11-22): **telecom first** among v6's new industries, tying devices, satellites (§56), chips and geopolitics (§39) together. **History holds to 2025** (`telecom.yaml`, research `docs/v6-research/telecom-dossier.md`); markets and money at the game's scale (§54).

### 62.1 Networks and generations

- **`telecom`** is a category family: `mobile` (consumer and business subscriptions), `fixed_broadband` (fibre, cable, DSL) and `wholesale` (selling capacity to other operators). Subscribers by region follow the data to 2025, then demand by population, price and quality.
- **Networks** are facilities by region: **towers** (sites with radio equipment by generation: 3G, 4G, 5G and, from its seeded era, 6G), **fibre** (route kilometres and homes passed), **data centres and core** (shared with §22's), and **subsea cables** (named routes, capacity, landing countries). Coverage and capacity per region come from the sites and spectrum, and quality from capacity per subscriber.
- **Generations** arrive by data (4G about 2010–2012, 5G about 2019–2020) and seeded after; each needs equipment, spectrum and a buildout, and raises the quality ceiling.

### 62.2 Spectrum

- **Spectrum** is licensed by region in bands (low, mid, high) through **auctions** on the data's dates (US C-band in 2021, and others) and seeded after. Bidding is a multi-round auction against rival operators (stream `telecom`), within the player's limit; licences last 10–20 years.
- Without spectrum, a region's network can't carry mobile; a satellite link (§56's direct-to-device) partners with or competes against operators.

### 62.3 Equipment and geopolitics

- **Network equipment** (radio, core, optical) is a market good from Ericsson, Nokia, Huawei, ZTE and Samsung, and from the player's own products (a new hardware category `network_equipment`, using its chips).
- **Bans:** §39's rules exclude named suppliers in named countries from their dates (the US's Huawei and ZTE restrictions from 2019, the UK's removal of Huawei from 5G by 2027, and others), forcing rip-and-replace with costs and deadlines.

### 62.4 Rivals and regulation

- **Operators** by region (Verizon, AT&T, T-Mobile, Vodafone, Deutsche Telekom, Orange, China Mobile, NTT Docomo, Reliance Jio, América Móvil and others) with subscribers, spectrum and networks from the data.
- **Regulation** through §48's regulators with a telecom kind: licence conditions (coverage obligations), merger review (operator consolidation), net-neutrality rules by region and date.

### 62.5 Balance targets (printed)

1. **History holds** where M43a set it; every earlier guard unchanged (a company without telecom plays exactly as before).
2. **Spectrum is scarce and dear:** in a contested auction, the winning price is at least 1.5× the reserve (median), and a player without mid-band spectrum loses at least 20% of its mobile share in that region by the next generation.
3. **Networks are capital-heavy:** a national mobile network in a large region takes at least 5 years to positive cash flow.
4. **Bans bite:** an operator on banned equipment pays at least 10% of its network capex to replace it by the deadline.
5. **Turn time** within the guards.

### 62.6 As built (M53)

- **Data and scale.** `telecom.yaml` (every value tagged S/D/R/A with its source) holds, by game region, mobile and fixed broadband subscriptions 2008-2025 (millions, real), fibre's share, households, ARPU, the first 4G and 5G months, the macro sites a national low-band grid needs and the region's licence areas (countries or groups, with population shares; China's are `closed`: assigned administratively); mobile data a subscription by year; generations (3G, 4G from December 2009, 5G from April 2019, 6G seeded in `telecom.g6_window`); 23 operators' subscribers by region; five vendors' RAN shares; 28 dated auctions, 15 dated bans, 16 subsea cables, net-neutrality rules and operator mergers. Markets and money are x `telecom.scale` (0.085, the economy scale), at real prices.
- **Demand.** The four categories (family `telecom`) have no growth rate: phase 9 sets their addressable markets from the data (mobile and fixed: subscriptions x 10^6 x scale x `mobile_split`/`fixed_split`; wholesale: mobile subscriptions (millions) x `wholesale_per_sub` x scale; equipment: mobile subscriptions x 10^6 x `equipment_sites_per_sub` x scale), read at the month's year-end point, and from 2026 grow by a rate drawn each January within `growth_after[region]` (stream telecom (0, 0, year, region index)). M43a's ceilings leave them alone (`saturation.grows`). Each category has its own regional `price_index` (categories.yaml): `price_ratio(region, home, data, category)` reads it for that category only, in phase 5's appeal, a player's default regional price and a rival's regional entry.
- **History** (target 1). Before `telecom.start` an operator's line is pinned to its subscribers x scale x the segment's split (at most the market not held by others), a wholesale line to its share, a vendor's equipment line to its RAN share x `region_mult` less its banned share; no price before a line's `first` or from its `last`. Telecom companies hold (no decisions, never failed, not ranked) until 2026, as M40's space companies; M28's fingerprint writes their own lines to a series `telecom` and numbers later companies as main does.
- **Networks** (62.1). A region's sites are its live `tower` units; radios of a generation are its `tower` and `radio` records' working sites (less `dark`). Coverage on band b = min(licensed share_b, (sites / (sites_full x scale x density_b)) ** `coverage.exponent`); capacity (GB a month) = for each band, each site once at the best efficiency its radios reach there (5G and 6G reach theirs on mid and high band, 4G's on low band) x MHz (licences x their areas' shares) x sectors x 2,592,000 s x utilisation / 8,000. A mobile line's appeal is x its coverage (zero without spectrum; a satellite partner adds `satellite.partner_coverage` from direct-to-device's opening and keeps `partner_fee_share` of revenue there), x (capacity / demand) ** `congestion_k` over capacity (demand = its subscribers x the year's traffic, x (1 + `traffic_growth_after`) a year after 2025), and its features + the generations' points (a mid-band generation's in full only where mid-band coverage reaches, 4G's elsewhere). Fixed broadband sells to the share of households its fibre passes, trimmed to `max_take_up` of homes; wholesale to its spare capacity (mobile, fibre and subsea cables) over a contract's GB. An acquired operator keeps its data network (a follow-up).
- **Running costs.** A telecom category's `hosting_cents` a customer are North American; in another region they are x `price_ratio(region, home, data, category)` (exact), in phase 6 and in a network's cash flow, so a low-ARPU region's lines cost as little to serve as they earn (any other category's hosting is the same everywhere).
- **Spectrum** (62.2). Dated auctions are announced `notice_months` ahead; from 2026 each auctioning area gets seeded ones every `seeded_every` years (stream telecom (0, 2, area, n, ...)). A clock auction raises a block's price `increment` a round from the reserve while bidders still in want more than the blocks; winners pay the last price. Rivals' values a block (drawn when it runs, stream telecom (1, auction id), never stored): a dated auction's named winners at its real price a block x `winner_value`, bidders outside the game holding the rest, a marginal loser at x `loser_value`; a seeded auction's region's operators at the reserve x `seeded_value`. A licence is 1540, amortized straight line (6760), renews at `renewal_share`; its coverage obligation is checked yearly by the region's telecom regulator: a fine of `obligation_fine_share` x strictness, revoked after `obligation_grace_years`.
- **Equipment and bans** (62.3). A tower costs sites x (the year's civil cost + the generation's radios x the vendor's `price_mult`) x the equipment index; own radios (vendor `own`) cost the player's network-equipment line's BOM. A vendor whose bans cover `ban.refuse_share` of a region is refused; from a ban's deadline a record owes ceil(sites x its vendor's banned share) replaced, and sites owed and not replaced are dark. Rip-and-replace orders another vendor's radios at x `ban.swap_mult`; live, they count as replaced. Seeded bans after 2025 (`ban.seeded_*`, hidden until announced).
- **Regulation** (62.4). regulation.yaml's `telecom_regulators` (kind `telecom`); a telecom market's deal is reviewed from `merger_share` and its block chance is max(M14's, (share - merger_share) / (block - merger_share)) x `merger_mult` x strictness; zero-rating multiplies a mobile line's appeal by `zero_rating_appeal` only where no neutrality rule is in force.

## 63. Scenarios and challenges (M51; v6)

Reece (2026-11-21): **scenarios** are part of v6's second direction. §30.3 already has five historical scenarios; M51 adds more, challenge rules, and a scenario screen with results kept, using M50's 2008 start where a scenario needs it.

### 63.1 New scenarios

Each is a start (year, company, cash, staff, products, research, rivals' state) and a goal with a deadline in `scenarios.yaml`, built with §30.2's world-building code. **Candidates** (the M51 session confirms each is winnable and losable on seeds 1–10):

| Scenario | Start | Goal |
| --- | --- | --- |
| **The crash** | Jan 2008, a seed-stage startup with 14 months of runway | still solvent in Dec 2010 with a Series A raised |
| **The failing chipmaker** | Jan 2012, a fab-owning chipmaker two nodes behind and losing money | an operating profit and a node within one of the leader by Dec 2020 |
| **The EV maker** | Jan 2016, a car startup with one prototype and a Series B | 200,000 cars a year by Dec 2023 without going bankrupt |
| **Under controls** | Jan 2019, a Chinese foundry at 14 nm | 7 nm-class volume by Dec 2027 under export controls |
| **The platform war** | Jan 2010, a phone maker on a licensed OS | its own OS with 20% of developers in one region by Dec 2020 |
| **The dynasty** | Jan 2030, a founder aged 64 with three adult children | family control and a successor in place by Dec 2045 (dynasty mode) |

### 63.2 Challenges

- **Challenge rules** a player can add to any new game or scenario: no outside funding (bootstrapped); hardware only; no acquisitions; one region; hard rivals (their quality × 1.2); no automation. Each is a rule the engine enforces (actions refused with a clear reason) and a score multiplier on §30.1's company score (`challenges.<rule>.score_mult`).

### 63.3 The scenario screen and results

- A **Scenarios** screen lists every scenario with its brief, difficulty (from seeds 1–10's win rate), the player's best result and date, and the challenges used. Results are kept across saves (an app-wide results file, not in a save).
- The result screen (§30.3) adds the score breakdown, the challenge multipliers and a comparison with the player's best.

### 63.4 Balance targets (printed)

1. **Every scenario is winnable and losable:** a scripted sensible player wins each new scenario on 3–8 of 10 seeds, and a passive one on at most 2.
2. **Challenges are real:** each challenge rule lowers the scripted player's median company score by at least 10% before its multiplier.
3. **Nothing else moves:** a normal game with no challenge rules plays exactly as before (state-cache check).

*M51 notes.*
- *Scenarios* (63.1) join §30.3's five in `scenarios.yaml`'s `historical` list, in this order: The crash, The platform war, The EV maker, The failing chipmaker, Under controls, The dynasty. A start may now set the founder's age (past the new-game range; the new game builds the founder that many years younger in the world's first year, and the start sets the age) and region, the home city, a family (children's ages at the start, built in the world's first year and aged through the dormant years), named teams for its staff, a product still in development (a prototype), an assembly contract (26.2) and fabs already running (38.2: ordered as `BuildFab` orders one, then live for `age_months` with a mature yield, its capex on the books against the starting equity less the depreciation since). The crash plays on M50's 2008 world (60).
- *Goals.* `solvent_series` (solvent at the deadline with a round of `series` closed since the start), `platform_share` (an own platform's developer share in a region, 44.2; a reach goal), `vehicles_year` (cars sold in the trailing 12 months, 49), `fab_catch_up` (a fab running wafers within `node_gap` nodes of the leading edge and a trailing 12-month operating profit, in any month), `node_volume` (wafers run this month on a fab at `node` or newer) and `family_succession` (at the deadline: a child of the first head is the head and runs the company, not a professional CEO, 45.5, and the family holds `family.control_bp`). Goals and deadlines as tuned on seeds 1-10 are in the M51 brief's decisions; `sensible_wins` records the sensible script's wins.
- *Challenges* (63.2) are `GameMode.challenges` (`game_mode.data`; a campaign with rules has a mode record, one without has none, as before). `tst.sim.modes.challenges.check` runs in `apply_action` for every action (the player's, a delegate's, an automated one) and refuses with the rule named: Bootstrapped refuses rounds, term sheets, SAFEs, bridges, loans, the banks for an IPO and secondary offerings; Hardware only refuses a product in a category whose revenue model is not units; No acquisitions refuses bids, stakes and minority buy-outs; One region refuses region launches; No automation refuses automation areas, seat authority and CEO scopes. Hard rivals refuses nothing: in each market segment's month (11.6) a product of a company outside the player's group weighs in at its quality x `challenges.hard_rivals_quality_mult` (1.2), at most 100, its stored quality unchanged. The score multiplier is the product of the rules' `challenges.<rule>.score_mult` (1.25 each).
- *Results* (63.3) are `<saves>/results/<profile>.json` (beside M25's achievement profile, outside every save): one record a scenario save (keyed by its slug and seed) when its verdict is in: the result and month, the company score at the verdict (the snapshot of the month it ended, 30.1) in points, the rules, their multiplier and the adjusted score. The best is a success over a failure, then the higher adjusted score, then the earlier. Difficulty: the sensible wins of 10 at or below `challenges.difficulty_wins` (3, 6) are hard, then medium, else easy; the five M15b scenarios are rated with v1's steady script.
- *Target 2* is measured at December 2014 (60 months; at year 10 the score has saturated) on the scripted player each rule cuts into: steady_regions (Bootstrapped, Hardware only, One region, Hard rivals), acquirer (No acquisitions), ceo (No automation). Hard rivals, No acquisitions and No automation do not move those players' score and are carried by Reece's decision (M51 brief).

## 64. Financial services and currencies (M54; v6)

Reece (2026-11-21): **financial services at scale** in v6's third direction (banking, payments, insurance), with **currencies and hedging**, the backlog's last item. The player's fintech products (§18.6's `fintech`) can grow into a bank, a payments network or an insurer. **History holds to 2025** (`finance_services.yaml`, `fx_history.yaml`; research `docs/v6-research/finance-dossier.md`); markets and money at the game's scale (§54).

### 64.1 Banking

- **A bank** is a licensed business of a company (a charter by region, from the region's bank regulator; §48's machinery with a `bank` kind). Getting one takes `bank.charter_months` (12–30, by region and strictness) and minimum capital; a fintech can instead **partner** with a chartered bank (a share of interest kept, no capital needed) as most fintechs did before 2020.
- **Deposits** by segment (consumer, business) arrive by the bank's appeal (rate offered, brand, app quality from its fintech product, branches or none) and leave by churn and by **runs** (64.1's last point). The rate the bank pays follows the policy rate (`macro.base_rate`) by a **deposit beta** the player chooses within `bank.beta_range`: a lower beta earns more margin and loses deposits faster when rates rise.
- **Loans** by kind (mortgage, consumer, card, small business, corporate) with a yield over the policy rate, a term, a **risk weight** and a **loss rate** that rises in recessions (§20's confidence cycle): charge-offs = balance × loss rate × (1 + `bank.loss_cycle_k` × (100 − confidence) / 100).
- **Net interest income** = loans × yield + securities × their yield − deposits × deposit rate. Securities are fixed-rate: when the policy rate rises, their market value falls (duration × rate change), which matters only if they must be sold.
- **Capital rules:** CET1 capital / risk-weighted assets ≥ the minimum plus buffers (4.5% + 2.5% from 2019, plus a size surcharge; `bank.capital.*`). Below the line the bank can't grow loans or pay dividends; far below, the regulator intervenes (§48 stages). Yearly **stress tests** for banks above `bank.stress_size`: a seeded shock (rates, losses, deposits) must leave CET1 above the minimum, or dividends are frozen for a year.
- **Runs:** when a bank's unrealised securities losses exceed a share of its capital and its uninsured deposits are high, each month has a run chance (`bank.run.*`); a run withdraws a share of uninsured deposits, forcing securities sales at market value (losses realised). Insured deposits (`bank.insured_limit`) don't run. A run that leaves CET1 below zero is a failure: §17's insolvency for the bank, and its regulator takes it.

### 64.2 Payments

- **A payments network** (cards or account-to-account) earns a **network fee** on volume (`payments.network_fee_bp`); an **issuer** (a bank with cards) earns **interchange** (`payments.interchange_bp` by region, capped from the data's dates: US debit October 2011, EU December 2015); an **acquirer or processor** (the player's fintech for merchants) earns a merchant discount minus interchange and network fees.
- **Volume** by region follows the data to 2025 (cards and digital wallets), then consumer spending (macro) × the digital share's path. A network has a two-sided network effect: merchants accept it by cardholders, cardholders choose it by acceptance (as §44's developers and users).
- **Real-time rails** (UPI 2016, Pix 2020, FedNow 2023) take a share of volume in their regions at no network fee, from their dates.
- **Fraud and chargebacks** cost `payments.fraud_bp` of volume, lowered by the security skill of the product's team.

### 64.3 Insurance

- **An insurer** writes premiums by line (property and casualty, life; health insurance is out of scope) in regions where it holds a licence (§48, an `insurance` kind). **Underwriting result** = premiums − claims − expenses: the **combined ratio** follows the line's base, the product's data and pricing skill, and seeded **catastrophe years** (stream `finserv`) with losses by region.
- **The float** (premiums received before claims paid) is invested at about the policy rate; investment income is most of an insurer's profit in a normal year.
- **Solvency rules** (Solvency II from 2016 in Europe; US risk-based capital): capital must cover a share of premiums and reserves, or the insurer can't write new business.

### 64.4 Currencies and hedging (ADR-0025)

- Each region's **rate index** (its currency or basket in US dollars, ÷ its January 2010 value) follows `fx_history.yaml` monthly to 2025 and a seeded mean-reverting walk after (stream `fx`): index_{t+1} = index_t × exp(`fx.reversion` × (ln anchor_t − ln index_t) + σ_region × z), with a jump of ±`fx.jump_size` with chance `fx.jump_chance` a month.
- **Translation:** a regional price or local cost set in month s is worth price × index_t / index_s US cents in month t (rounded half-even). The player's regional lines translate from the start; rivals' from `fx.applies_from` (2026).
- **Hedging:** the player (or its CFO, §40) buys forwards: notional N (local terms, as US cents at today's index), term m months, forward index F = S × ((1 + r_home) / (1 + r_region))^(m/12) × (1 ± `fx.spread_bp`). At settlement the gain = N × (F − S_m) / S_0, posted to FX gain or loss. Region rates come from each region's policy rate path (`fx_history.yaml`'s `policy_rate`).
- **Exposure screen:** revenue, costs and debt by currency; the unhedged share of the next 12 months' net foreign revenue; a what-if of a 10% dollar move.

### 64.5 Rivals and regulation

- **Banks** (JPMorgan, Bank of America, Citigroup, Wells Fargo, HSBC, ICBC, BNP Paribas and others), **networks** (Visa, Mastercard, American Express, UnionPay), **payments companies** (PayPal; Stripe, Adyen and Ant as private or listed by their dates) and **insurers** (Allianz, AXA, Ping An, Berkshire Hathaway, Chubb and others), each with the data's 2010 size at the game's scale.
- **Regulators:** bank kinds (the Fed, OCC and FDIC as one US regulator; the ECB's SSM; the UK's PRA; China's PBoC and NFRA; India's RBI) and insurance kinds; charters, capital, stress tests, interchange caps, and the data's actions (Wells Fargo's asset cap 2018–2025, SVB's failure in March 2023 as history for its rival record, Ant's halted IPO in November 2020).
- A bank in a group: §16's consolidation applies; capital is the bank's own (a regulator can block dividends to the parent). Owning a bank inside a tech group draws a regulator's review (§48) above `bank.group_review_share`.

### 64.6 Balance targets (printed)

1. **History holds** where M43a set it; every earlier guard unchanged (a company with no bank, network, insurer or foreign sales plays exactly as before).
2. **Banks are rate businesses:** a sensible player's bank's net interest margin is within 2.5–4.0% on seeds 1–10 in 2015–2025, and its profit rises with the policy rate when its deposit beta is below 0.5.
3. **Runs are rare and real:** a bank that holds long securities through 2022's rate rise with more than 50% uninsured deposits has a run on at least 3 of 10 seeds; one with under 20% uninsured deposits on none.
4. **Networks compound:** a payments network that reaches 10% of a region's volume keeps or grows its share for 5 years on at least 7 of 10 seeds.
5. **Currency risk matters, hedging works:** for a player with at least 40% of revenue outside North America, the standard deviation of yearly operating profit in 2026–2035 is at least 15% lower with an 80% rolling hedge than with none (median of seeds 1–10).
6. **Turn time** within the guards.

## 65. Media and entertainment (M55; v6)

Reece (2026-11-21): **media and entertainment** close v6's third direction: streaming, a games studio and social networks, with content as an asset, hits drawn like trials, talent with egos, and platforms and advertising tying back to §44. **History holds to 2025** (`media.yaml`; research `docs/v6-research/media-dossier.md`); markets and money at the game's scale (§54).

### 65.1 Advertising

- **An advertising market** by region: total spend follows the data to 2025 (GroupM), then GDP-linked growth with the confidence cycle (§20); digital's share follows the data, then a slowing path toward `ads.digital_ceiling`.
- **Ad-funded products** (social networks, ad tiers of streaming, and §11's `consumer_apps`, which already book revenue a user) sell **impressions**: revenue = users × engagement (hours) × ad load × price an impression. The price an impression follows the region's ad spend ÷ the impressions all sellers offer, × the product's **targeting quality** (its data skill and data rules).
- **Privacy events cut targeting:** Apple's App Tracking Transparency (April 2021) lowers targeting quality on iOS for apps without first-party data by `ads.att_cut`; GDPR (May 2018) and the DSA lower it in Europe. A company that owns a platform (§44) is not cut on its own platform.

### 65.2 Content as an asset

- **A title** (a series, a film, a game) is a project with a budget, a team (its creative lead and staff), a genre and a development time (`media.dev_months` by kind). Its cost is **capitalised** as a content asset while in production and **amortised** from release on an accelerated schedule (`media.amortisation` by kind: series and films about 90% in four years; games by expected sales).
- **Hits are drawn like trials** (§55's readouts): at release a title's **audience** = the kind's base × quality multiplier × a lognormal draw (stream `media`, σ by kind, `media.hit_sigma`), so most titles underperform and a few earn most of the money. Quality comes from the creative lead's attributes, the team, the budget's ratio to the kind's typical budget (diminishing), and franchise strength (a sequel's prior audience, decaying).
- **The catalogue** keeps earning: a streaming service's titles keep subscribers (an engagement score from the catalogue's audience-weighted recency); a game earns sales, then a tail, and live-service games earn in-app spending while the team keeps updating them.

### 65.3 Streaming

- **Video and music services** by region with subscription tiers and, from the data's dates, ad tiers (65.1). Subscribers arrive by catalogue engagement, price and brand, and churn by price and engagement (`streaming.churn_*`); the leader's lower churn follows its catalogue, not a constant.
- **Licensing:** a service can license titles from rivals (cost a year by audience) or license its own out (revenue); the 2019–2020 pull-back of licences to own services is history in the data.
- **Music** pays rights holders a share of revenue (`streaming.music_payout`, about 65–70%), so margins stay thin unless the service owns content (a label as a later follow-up).

### 65.4 Games

- **A games studio** makes titles for PC, console and mobile. Console and store fees (30%, Epic's 12% from December 2018) apply; on the player's own store (§44) they're internal. Console generations (2013, 2020, seeded after) lift sales of titles on the new platforms and cut the old.
- **Free-to-play** titles earn in-app spending from a share of players (`games.payer_share`) at an average spend; loot-box rules (Belgium 2018, others) cut it in their regions.
- **Live service:** a title's players decay monthly (`games.decay`) unless updated; an update costs staff time and slows the decay.

### 65.5 Social networks

- **A social network** is a platform of users with a **network effect**: a user's value = the share of their region's users already on it, to a power (`social.network_k`). Growth needs a **format advantage** (feature points in the network's format; a new format era draws users from incumbents, as TikTok's feed did from 2018).
- Revenue is ads (65.1); costs are hosting and **moderation** (staff a million users, rising with regulation: the DSA from 2023–2024).
- **Regulation and politics:** privacy fines (§48's GDPR cases), the DSA's duties, and divest-or-ban laws by region (the US law of April 2024 as history for ByteDance's record; seeded after for a network whose owner is in a rival bloc, §39).

### 65.6 Talent with egos

- **Creative leads** (showrunners, directors, game directors, star creators) are people with `creative` and `vision` attributes, a **reputation** from their past titles' audiences, and hidden traits `ego` and `loyalty` (never shown; their effects are).
- **Overall deals:** a creative lead signs for a term and a fee (a share up front); during it, the studio has first look at their titles.
- **Egos:** cutting a title's budget, moving its date or overruling the lead's choices (an action the player can take) lowers the lead's morale by their ego; low morale lowers the title's quality and can make the lead walk (to a rival, which then gains their next title). A hit raises the lead's reputation and fee demands. One-to-ones (§61) work with creative leads as with any key person.
- **Strikes:** the 2023 writers' and actors' strikes as history (production paused for their months); seeded strikes after 2025 by region (`media.strike_*`).

### 65.7 Rivals

Netflix, Disney, Warner Bros. Discovery (Time Warner and WarnerMedia before April 2022), Comcast–NBCUniversal, Paramount, Sony, Spotify, Universal Music, Electronic Arts, Activision Blizzard (to October 2023, then Microsoft's), Take-Two, Ubisoft, Nintendo, Tencent, NetEase, Meta, Twitter (private from October 2022), Snap (listed from March 2017), ByteDance and Roblox, with the data's 2010 values; Alphabet's YouTube and Amazon's Prime Video as lines of those existing companies.

### 65.8 Balance targets (printed)

1. **History holds** where M43a set it; every earlier guard unchanged (a company without media lines plays exactly as before; `consumer_apps`' revenue a user is unchanged before 2026 unless it opts into ad pricing).
2. **Hits rule:** across a sensible player's titles, the top 20% earn at least 60% of the titles' revenue (median of seeds 1–10), and at least a third of titles don't earn back their cost.
3. **Content is capital-heavy:** a new streaming service with a $1B-a-year (real) content budget takes at least 5 years to positive cash flow.
4. **Networks tip:** a social network with under 10% of a region's users loses users each year unless it has a format advantage; one with a format advantage grows on at least 6 of 10 seeds.
5. **Egos bite:** overruling a high-ego lead twice in a title cuts its median quality by at least 10% and makes the lead walk on at least 3 of 10 seeds.
6. **Turn time** within the guards.

### 65.9 As built (M55)

- **Data and scale.** `media.yaml` (every value tagged S/D/R/A with its source) holds global ad spend, digital's share and regional shares 2008-2025 (GroupM), iOS's share by region, three privacy rules (GDPR, ATT, the DSA), internet users and multi-homing, Meta's ARPU by region, four format eras, divest laws, the paid video and music markets by region, games revenue and its regional split, three console generations, store fees, loot-box rules, the 2023 strikes, 33 rival lines' customers (or games revenue) with their splits by region, and box office. Markets and money are x `media.scale` (0.085), at real 2010 prices.
- **Categories.** `streaming`, `music_streaming` (segment `viewers`), `games` (`players`) and `social` (`users`), family `media`, each with its own regional `price_index`; demand set each month from the data (video and music subscriptions a region can hold; games revenue over a player's monthly spend; internet users x multi-homing), grown from 2026 by a yearly draw within `growth_after[category]` (stream media (3, 2, year, category, region)). "Advertising" is the ad market (`media.ads`), not a product category.
- **Rivals** (65.7). Twenty-two held records (incumbents 160-181, after M54's 135-159): Netflix, Disney, Warner Bros. Discovery, NBCUniversal, Paramount, Sony, Spotify, Electronic Arts, Activision Blizzard (its line closes October 2023; Microsoft Gaming's revenue includes it after), Microsoft Gaming, Take-Two, Ubisoft, Nintendo, Tencent Media, NetEase, Meta Platforms, Twitter, Snap, ByteDance, Roblox, YouTube and Amazon Prime Video. YouTube, Prime Video, Meta's networks, Tencent's media, Xbox and NBCUniversal are records of their own beside the existing Facebook, Tencent, Microsoft, Amazon Web Services and Comcast records (adding lines to those would move their books before 2026); Universal Music is not seeded (its business is the record label, out of scope). Before `media.start` a line's customers are pinned to its data x scale x split (at most the market not held by others) and its price to its North American price x the category's index (a social line's to the region's ARPU / 12 x `arpu_mult`); media rivals hold (no decisions, never failed, not ranked) and M28's fingerprint writes their lines to a series `media`.
- **Advertising** (65.1). A region's spend follows the data to 2025, then a yearly draw within `ads.growth_after` x (confidence / 100) ** `confidence_exponent`; digital's share closes `digital_approach` of the gap to `digital_ceiling` a year. A line's ad revenue a user a month = `hours[category]` x ad load x `impressions_per_hour` x targeting / 1000 x the price a thousand; targeting = `targeting_base` + `targeting_quality_weight` x quality / 100, cut by GDPR and the DSA in Europe and by ATT on iOS's share of a region (less a company's own platform's users). Before 2026 the price a thousand gives a reference line (quality 68, load 1) the data's ARPU; from 2026 it is December 2025's x (digital spend / then's) x (impressions then / now) (`AdRef`, once). Every social line's price is its ad revenue a user (set before phase 5); a consumer app opting into ad pricing (from `ads.consumer_apps_from`, 2026) is priced the same way. A video line's ad tier (from November 2022) books `1 - ad_tier_take x (1 - ad_tier_price)` of its revenue (buyers weigh that price) and its ad-tier subscribers' impressions to 4080.
- **Titles** (65.2). A title spends its budget evenly over `kinds.<kind>.dev_months` into 1560 (a strike in the home region pauses it); at release q = lead x team x budget x franchise (clamped), with lead = ((creative + vision) / 2 / 10) ** `lead_exponent` x (0.7 + 0.6 x m / 100), where m is the lead's average morale over production less `talent.grievance_keep` of what the title's overrules, cuts and moves cost them; expected audience = `audience_m` x q x reach (x platform shares, a game); audience = expected x exp(sigma z - sigma^2 / 2), z ~ N(0, 1) on stream media (0, title id) at release only. Under `impairment_ratio` of expected the book is written down. Revenue: licensed series and films earn audience x the kind's revenue a viewer (typical budget x scale x `revenue_mult` / `audience_m`) on a geometric profile (`tau_months`, to `tail_months`); premium games sell copies at each platform's price x scale less store fees (5150; Epic's 12% on PC with `epic_reach`), x `gen_lift` for a console title launched within `gen_lift_months` of a generation and x `old_gen_cut` after a later one; free-to-play games earn players x `payer_share` x `spend_cents` x scale less fees and loot-box cuts, players falling `decay` (`live_decay` with live service at `live_cost_share` of the budget a month, 5170). The book is amortised on the kind's schedule (exact; the last month clears it); a cancelled title is written off.
- **Streaming** (65.3). A video line's catalogue value: its own-window released titles' audience x revenue a viewer x exp(-age / `recency_months`) plus licences x `licence_value` x availability; a rival's: its revenue a year x `rival_content_share` x the series kind's `revenue_mult` x `recency_months` / 12, plus walked leads' titles. r = value / the median live line's: appeal x r ** `appeal_k`, churn x r ** -`churn_k`, clamped. A music line pays `music_payout` of its revenue (5160).
- **Social** (65.5). Share s = users / (internet users x 10^6 x scale) in a region: appeal x (s / `share_ref`) ** `network_k`, churn x (`share_ref` / s) ** `churn_k`, clamped; the newest format within `advantage_years` of its arrival x `format_advantage`, each era behind x `old_format`; strong moderation x `strong_appeal`; banned regions x 0. Seeded eras every `format_every` years (stream media (3, 0, year)); rivals move `rival_adopt_years` after an era arrives (stream media (5, product, year)); a player's switch costs `switch_quality_cut` of quality. Moderation `moderation_cents` a user x level x `dsa_mult` in Europe from `dsa_from` (5170); light moderation there risks a January fine (`light_fine_chance`, `fine_share` of the region's revenue a year, 6970). Divest-or-ban laws from 2026 for a player's network with `divest_min_share` of a region whose bloc differs from its home's (`divest_chance` a year; divest at `divest_revenue_mult` years of the region's revenue to 4930, or banned at the deadline).
- **Talent** (65.6). Each January `pool_size` leads are on offer for `pool_months`, regenerated from stream media (4, year, n): a person of role `creative_lead`, creative and vision ~ N(`attribute_mean`, `attribute_sd`), hidden ego and loyalty = the person's shown traits + N(0, `trait_sd`), and the shown ranges' offsets. Signing pays `upfront_share` of the deal at once (6000) and the rest as salary; the fee a year is `base_fee_cents` x scale x ((creative + vision) / 20) ** `fee_exponent` x (1 + `reputation_fee` x reputation). An overrule, cut or move costs morale (`overrule_morale`, `cut_morale`, `move_morale` x ego / 20); under `walk_morale` it may make the lead walk (chance `walk_chance` x (21 - loyalty) / 20 x (walk - morale) / walk, stream media (1, person, title, n)) to the rival with the most video subscribers, which gains a catalogue bonus. Reputation += `hit_reputation` x (ratio - 1) at release. Seeded strikes from 2026 (stream media (2, region, year)).
- **Screens and API.** `GET /api/saves/{id}/media` (one view: Studio, Streaming, Games, Social) and ten actions; Products > Studio, Streaming, Games and Social (unlock systems 40-43); Explain `title_result` and `lead_walk`. Never served: an audience before release, a lead's ego or loyalty, true creative or vision (ranges only), seeded eras, generations, strikes and laws before they come, drawn growth.

## 66. The editor and sandbox (M52; v6)

Reece (2026-11-21): **an editor** to make custom scenarios from a starting company, rivals, markets and rules, and **sandbox play past 2069** with no score. ADR-0026 fixes the file format, validation and determinism.

### 66.1 The editor

- **Start from** a blank 2010 game, a start year (2008 or 2010, more as M50's later starts land), or any scenario in `scenarios.yaml` (including M51's), and change:
  - **the player's company:** name, region, cash, debt, staff by role and level, products by category (quality, features, brand), research levels, facilities (fabs, data centres, plants, mines, as their builders allow), and the founder's age and family (§63.1's start fields);
  - **rivals:** each incumbent present or removed, its cash and its products' quality (± `editor.rival_quality_range`); added generic rivals by category (drawn as entrants are);
  - **markets:** each category's addressable market (× `editor.market_mult_range`) and growth (± `editor.growth_delta_range`);
  - **the world:** macro start (confidence, the policy rate's starting level), eras historical or seeded, commodity prices' starting levels (× a range);
  - **rules:** M51's challenges, campaign length (standard, dynasty, sandbox with no end), and a goal from §63's goal kinds with a deadline, or none.
- **Validation** is the loader's, plus the editor's ranges (`editor.*` in balance.yaml): a field outside its range or a combination the engine refuses (a fab at a node not yet invented in the start year) is refused with the reason. The editor never shows or sets hidden values (ADR-0026, point 3).
- **Preview:** the editor runs the start month (no turn) and shows the company summary, its rivals and a "difficulty" estimate (the scripted sensible player's result on 3 seeds, run on request in the background).

### 66.2 Custom scenarios

- **Saved** as `<saves>/scenarios/<slug>.yaml`, exported and imported as files; listed on M51's Scenarios screen under **Custom** with the player's best result kept apart from M51's results (custom results don't count toward M51's results or the Hall of Fame).
- **A game started from one** stores its canonical YAML and hash (ADR-0026, point 4).

### 66.3 Sandbox past 2069

- **Continue in sandbox** at December 2069 (the option §52.1 left out of scope) or start a sandbox with no end. Series continue by §52.2's rules year after year; rivals' leaders keep ageing and retiring; process nodes keep slowing; eras draw from a third wave (`eras.yaml`'s `beyond_2069` list: windows 2070–2120, with the same domain and acceleration fields).
- **Guards for long play:** no field may overflow its database column (money columns are 64-bit integers: the game's economy at 2100 stays at least 1,000× below the limit; tested); ages, years and ids grow without wrap; turn time at 2100 within the dynasty guard.
- **Score:** shown, kept out of comparisons, as §30.2's Sandbox.

### 66.4 Balance targets (printed)

1. **Nothing else moves:** a normal game, a scenario from `scenarios.yaml` and a dynasty game to 2069 play exactly as before (state cache and golden snapshots).
2. **Round trip:** every scenario in `scenarios.yaml`, opened in the editor and saved unchanged, starts a game identical to the original (state hash at month 12, seeds 1–3).
3. **Determinism:** a custom scenario exported and imported on another machine gives the same state hash at month 24 (the `determinism` job's Windows and Linux digests include one custom scenario).
4. **Long play:** a sandbox game continued from a 2069 save to December 2100 runs with no error on seeds 1–3, every money value within its column, and the late-month turn time within 550 ms (runner-adjusted).

*M52 notes.*
- *A custom game* is a scenario game (`GameMode.kind` `scenario`) whose `scenario` is `custom/<slug>` (never a `scenarios.yaml` key) and whose `scenario_sha256` is the file's canonical-text hash; its entry joins the game data beside `scenarios.yaml`'s (`tst.sim.modes.custom.with_custom`, and for a save `tst.db.custom_io.data_for_custom` from the save's own copy), so §63's start code and the monthly judge read it as any scenario. A custom entry's `goal` and `deadline` may both be left out: open play, no verdict. `length` gains `endless`.
- *Overrides* (66.1), applied in the start month after §63's start and before the rivals' balances are brought forward (`apply_overrides`): an incumbent (by its incumbents.yaml name; one gone by the start year is left as it is) removed as Sandbox's rivals option removes one (15.1), its cash x `cash_mult` against common equity, each product's quality + `quality_delta` clamped to 0-100; added rivals are 52.3 entrants (`tst.sim.dynasty.rivals.enter`) on stream `scenario`, keys 1,000,000 + category index x 100 + k, rival key (20, category index, k); a category's national and regional addressable markets x `market_mult` that month, and `growth_delta` (in `GameMode.growth_delta`) added to its annual growth every month (`annual_growth`, never below 0). Markets that follow their own data every month (cars, robots, telecom services) are not editable. From `editor.macro_from_year` (2026; history before it is the same on every seed) the macro month the start reads takes the confidence and base rate, and a commodity's trend and index x its multiplier; 20.1's and 33.1's AR(1) steps go on from there. Facilities: fabs only (§63's start builder).
- *Canonical YAML* (66.2): the spec's fields with defaults left out, numbers as their fields' types, keys sorted, block style, LF; `format: 1` always written. The editor's ranges are `editor.*`; refusals name every reason (`tst.sim.modes.custom.refusals`).
- *Difficulty* (66.1): the sensible script of the scenario it was opened from (M51's), v1's steady otherwise, on `editor.preview_seeds` for at most `editor.preview_months`; rated with M51's ten-seed bands scaled to the seeds.
- *Results* (66.2): `<saves>/results/<profile>.custom.json`, apart from M51's; a custom or endless game earns no achievements and shows no score on the Saves list.
- *Sandbox past 2069* (66.3): `ContinueSandbox` (only from `dynasty_end`) sets the length `endless` and reopens the game; a Sandbox may begin endless. An endless game never closes. `dynasty.beyond`: research baselines (by decade) and category growth's maturity are extended at load to 2120 (a later year reads the last rate), four more node successors (windows 2076-2117, the gaps growing by 52.2's rule), and eras.yaml's `beyond_2069` wave is appended after every other era (no earlier stream key moves) and in play only from January 2070 (`levels.in_play`). Every year to 2069 reads exactly what it did.
