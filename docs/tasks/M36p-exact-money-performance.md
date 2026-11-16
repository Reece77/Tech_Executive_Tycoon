# M36p: exact money, fast (a performance fix after M36r)

Not a pre-written brief: the record of a fix session (Reece's instructions, 2026-11-15). The
weekly run on `main` at 9530661 failed `tests/integration/test_m30_perf.py` on both V6 saves:
full_integrator 639 ms at the median (439 ms at m30-done) and plain V6 545 ms, against M30's
guard (500 ms on the full_integrator save, `TST_M30_MEDIAN_MS`; 400 ms on plain V6). M36r
(PR #64) was the only engine change between them, so its exact-money changes (Fractions in hot
paths) were the suspect.

## Scope

- Make exact money fast with identical results: integer arithmetic (an integer numerator over
  a power of ten, one half-even rounding), no Fraction built per call where a rate is fixed.
- Golden snapshots, M30's state-cache fixture and M36r's rational-reference properties stay
  identical; the float-money guard still passes.
- Both V6 medians under their guards on the CI runner (the weekly V6 jobs dispatched on the
  branch, CLAUDE.md §9 rule 7). `tst/sim/power/` (M32, running) untouched.

## What the profile showed

Measured on 2039 saves built by `tools/v6_save.py` (this container runs about as fast as a
middling CI runner; CI's runners differ by up to 2x):

| code | save | median, this container |
| --- | --- | --- |
| m30-done | built at m30-done (full_integrator) | 415 ms |
| 9530661 (M36r) | built at 9530661 (full_integrator) | 424 ms |
| m30-done | built at 9530661 (full_integrator) | 425 ms |
| 9530661 (M36r) | built at 9530661 (full_integrator) | 418 ms |
| m30-done | built at 9530661 (plain V6) | 343 ms |
| 9530661 (M36r) | built at 9530661 (plain V6) | 359 ms |

- On the same save, M36r's code costs at most ~5% more than m30-done's. Every Fraction and
  money helper together was 15-30 ms of a 2039 month (cProfile and py-spy agree): real, but
  not the 200 ms the weekly saw.
- The rest was the runner. The failing weekly job (9530661) took 482 s to build the
  full_integrator save that m30-performance's weekly job (297d2bb, run 17) built in 267 s, and
  that job measured 320 ms, not 439, for the same month. GitHub's `ubuntu-latest` runners
  differ by up to 2x; the 9530661 runner was a slow one.
- So the fix made the month cheaper wherever it could, with identical results, money first.

## What changed (results identical)

1. **Exact money in integers** (`tst/sim/money.py`): `scaled(x)` reads a float as `exact`
   does (its shortest repr) into `(n, k)` with x = n / 10**k; `times(amount, rate, *more)`
   multiplies int cents by any number of such rates as one integer and rounds half-even
   once (`round_half_even`, the same rule as `round(Fraction)`); `sum_times(rows)` sums
   amount x rate rows exactly at a common power of ten and rounds once; `exact_product`
   builds the one Fraction a later exact sum needs. A Fraction, a float amount (read as
   `Fraction(amount)`, as M23a's `times` did) or any other type falls back to the old path.
   Hot paths moved to them: product revenue and reference prices (`products/phases.py`),
   rivals' pooled benefits and offices (`hiring/phases.py`), app revenue and per-pair
   platform fees (`platforms/fees.py`), `monthly_salary_cents`.
2. **Regulation (M34) asked every company's owner for every regulator and group**:
   `state.owners_now` / `ultimate_owner` keep `owner_of` for every company once per state;
   history's designations are kept per state, turn and data.
3. **GameState replace**: `state.replace` copies a GameState's 160 fields through a C
   `attrgetter` and slot setters instead of a 160-keyword `__init__` (~11 µs, was ~32 µs;
   ~700 a month). Same object: every init field, the changes, a fresh `_memo` (GameState has
   no `__post_init__`, asserted by the test). Any other object goes to `dataclasses.replace`.
4. **`has_table`** keeps its answers per SQLite schema (the text of `sqlite_master`) in the
   process, so each session reads one query instead of two PRAGMAs a table.
5. **Cost lines** (`hiring.monthly_cost_lines`) are kept per state: payroll and its burn
   projection asked twice for each company's lines of the same state.
6. **Retirement rolls** build their RNG stream only when the chance is above zero (an unused
   stream draws nothing, so no other draw moves).
7. `weekly.yml`: a manual run takes an optional `parts` list (e.g.
   `["weekly-v6", "weekly-v6-integrator"]`), so the V6 jobs can run alone; the schedule and an
   empty input run all nine.

## Verification

- Golden snapshots unchanged (`tests/golden`), M36r's rational-reference tests
  (`tests/unit/test_m36r_review7.py`) and the float-money guard (`tests/unit/test_money_guard.py`)
  pass, the sim purity and literal guards pass.
- New `tests/property/test_m36p_exact_money.py`: Hypothesis properties that `exact`, `scaled`,
  `times` (one and several rates, float amounts), `exact_product`, `sum_times`,
  `round_half_even` and `monthly_salary_cents` equal the rational reference
  (`Fraction(repr(rate))`, rounded once) on arbitrary finite floats and ints, that inf and nan
  still raise, and that the fast state replace builds what `dataclasses.replace` builds.
- M30's state-cache fixture (360 months, 9 runs, nightly) on the branch's nightly run.
- CI (weekly V6 jobs on the branch): see "Decisions made" for the readings.

## Decisions made

1. The regression was mostly runner speed, with ~5% from M36r on the same save (table above).
   The fix still had to bring both medians under their guards on CI, so it made the 2039 month
   cheaper across the board (money first), each change with identical results.
2. Plain V6's guard is 400 ms (M30's brief), not 500: only the full_integrator save has 500
   (PM ruling 2026-11-15, Makefile). The branch is measured against both as they stand; no
   band was changed.
3. CI readings on the branch (weekly V6 jobs dispatched with `parts`):

   | commit | full_integrator (guard 500) | plain V6 (guard 400) | save build (integrator) |
   | --- | --- | --- | --- |
   | main 9530661 (weekly 18) | 639 ms | 545 ms | 482 s |
   | 3e9eaf5 (wip 1) | 455 ms | 380 ms | 403 s |
   | 36e1600 (all code changes) | 367 ms | 278 ms | 285 s |

   Locally, on the same 2039 saves, the branch's month is 11-15% cheaper than main's
   (full_integrator 440-461 -> 395-414 ms; plain V6 415 -> 349-360 ms).

## Follow-ups

- The weekly guards measure wall time on runners whose speed differs by up to 2x. A
  calibration step (a fixed CPU-bound workload timed beside the month) would let the guard
  scale by the runner, or at least show a slow runner in the log.
- What remains in a 2039 month is the database write (~30%: 4,600 reveal and 1,800 skill rows
  a month that do change) and the market phase; both are M35's.
