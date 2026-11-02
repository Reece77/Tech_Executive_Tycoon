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

- **Quality cap:** `Q_cap × (1 + rnd.cap_per_point × min(R_cat, rnd.cap_points))`, with 0.004 per point and a maximum of 50 points, so at most × 1.20. It applies after the CTO factor (§18.3).
- **Features:** feature points gained × `(1 + 0.002 × min(R_cat, 50))`.
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

  with `rnd.rate` 0.25 and `rnd.half` 30. Returns diminish: the first 15 points come about twice as fast as the next 15. Decay (§21.1) applies after progress.
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
  - **Price:** `rnd.license_price_per_point` ($150,000 in 2010 dollars) × points × `(1 + ARR / $20M)`, once.
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

**Licence price.** 12 points with ARR $10M: `$150,000 × 12 × 1.5` = **$2.7M**.

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
  - every product it hosts loses `customers_pct` within critical caps, and cloud customers churn × 3 that month;
  - the choices trade cash (overtime and credits) against brand.

### 22.6 What the API may show

Data centres with capacity, utilization (own and sold), reliability, staff coverage, monthly cost per CU against spot, book value and build progress. The component indexes and allocation, with history, never the future. Contracts. The Cloud hosting market like any market. Outage history.

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
