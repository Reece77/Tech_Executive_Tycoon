# v2 balance summary (M15a, for the v2 retrospective)

## What was built

Nine scripted strategies (v1's four plus steady_regions, research_heavy, acquirer, integrator and ceo) and two AI-models arms; five eras to 2039; 30-year runs, a weekly workflow (V1 over 30 seeds, V5, V6) and a 2039 stage-4 turn-time test; the v2 targets V1–V7 (`tst/balance/v2.py`, `tools/v2_targets.py`).

## What was tuned, and what moved

| Change | Why | Effect |
| --- | --- | --- |
| steady_regions family: a new-category product at most once per 36 months; marketing split over products | the ceo arm found consumer apps the script never entered; steady set 20% of revenue on every product | V4 1.61× → 1.39× |
| `rnd.rate` 0.4 → 0.3 | research_heavy won 5 of 10 | 4 of 10, ARR 1.25× → 1.17× |
| `debt.venture.covenant_burn_months` 3 → 2 | covenants bit on 70% of blitz_debt seeds | 60%, bankruptcy 20% → 0% |
| `rivals.startup.start_feature_share` 0.3 (new) | no startup founded after about 2020 reached the 30% launch bar | rival launches after 2020 in every startup category on most runs |
| rival startups launch without a manufacturing contract (bug) | rivals' manufacturing is abstract (26.1) | chip startups (Cerebras, Groq) launch |
| a startup below 3 people for 24 months closes | one-person startups held every startup place for decades | places free up; V5 cells 28% → 68–77% |
| ranking ties by revenue then rival key (bug) | ties went to the lowest id, the player's | the player no longer wins sparse lists by default |

Re-banded with the product manager: V1 and T2 count founder-played strategies (ceo is a delegation benchmark); V3 software gap ≥ −1 point with an AI arm; V4 ≤ 1.4×; V5's launch clause as cell shares; M8 §18.9 target 5 1.2 → 1.14; S2 65 → 140.

## What remains

- V3.ai, V5.cells, V5.cats: known misses owned by M23 (docs/balance-targets.md, Known misses).
- `rank.brand` stays 0: even with fair ties, a Most innovative bonus moves research_heavy's wins and V3/V4 out of band (M23).
- v3: the AR-glasses segment and the photonic data-centre cost cut (§30.8); seeded future entrants for hardware and cloud after 2025; late-round sizing to months of burn (a new investor rule).
