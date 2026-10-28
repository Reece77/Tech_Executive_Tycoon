# M4c: Playtest fixes

**Goal:** fix what Reece's first full playtest (garage start to a Series A) found: founder energy that never limits, interviews and references that teach nothing visible, too few term sheets for a hot company, a board nominee the player can neither choose nor open, and an inbox that cannot be cleaned.

**Spec sections:** §4, §5.4, §10, §13 · **ADRs:** 0007, 0014, 0018 · **Formulas:** `docs/formulas.md` §4 (M4c interview PA strength), §6 (M4c energy), §14.5 (heat), §14.6 (nominee), §12 · **Depends on:** M4 (`m4b-done`)

## Reece's notes (verbatim summary)

1. Founder energy does not feel limiting in any way.
2. SAFEs feel fine and work smoothly.
3. Interviewing doesn't narrow potential enough to be a meaningful use of time.
4. References don't appear to do anything, at least on the main screen.
5. There is no way to clean the inbox.
6. At $6M ARR only two Series A term sheets arrived; a company like that should have offers "out of the woodwork".
7. The second board seat went to a nominee the player didn't choose, whose name links to a person that can't be found.
8. Cash fell to 3 months of runway; revenue covered it. The board was fine.
9. Game 2 (funded spinout, hiring fast): he could likely have survived without raising any money. Several of the notes above came from this game.

## Changes

1. **Energy** (`formulas.md` §6): `founder.energy_per_month` 60; costs interview 8, reference check 4, job post 5, recruiter 5. Update every test and golden that assumed 100 (regenerate with a CHANGELOG note). Delegates are unchanged.
2. **What you learned** (the main fix for notes 3 and 4): every interview, reference check and scout returns, and the Recruitment screen shows, a short panel for that candidate: each range that narrowed (before → after, skills, personality and the potential phrase), interests and work style if revealed, and any trait noticed. The candidate table gains a "Personality" column group (loyalty, professionalism, ambition, risk appetite as ranges) that references visibly sharpen. The API returns the before and after ranges from the action's result; the front end only formats.
3. **Interview potential** (`formulas.md` §4): interview PA strength 0.20; re-tune `reveal.initial_hw.pa` (60–120, smallest value that holds) so `test_judgment_spots_potential` still shows ≥ +3 PA. Record the value and the new typical phrase after a job post plus one interview.
4. **Investor heat** (`formulas.md` §14.5): term-sheet response × `heat`. Test: on the same seed, a Series A at $6M ARR receives at least twice as many term sheets as one at $1.1M (mean over 50 seeds).
5. **Board nominee** (`formulas.md` §14.6): the Series A acceptance dialog asks for the nominee (employees only, most senior preselected); `name_nominee` action (energy 2) for an empty seat; the nominee leaving empties the seat with an inbox note. Board directors who are not employees open a **board-member card** (name, firm, seat, since, confidence and trend), never the employee profile (fixes the dead link). Migration for existing saves: a generated nominee is replaced by an empty common seat with an inbox note asking the player to name one.
6. **Inbox cleanup**: "Mark all as read", per-item "Archive", "Archive all read", an "Archived" filter, and archived items hidden by default; `inbox_item.archived` column and migration. Archive is a UI action (no energy, no game effect, not in `decision_log`).
7. **Balance pass: growth must need money** (notes 8 and 9; M4a's diagnostics agree). Targets, on 10 seeds, with the M4a diagnostic scripts:
   - **(b) Fast growth without raising:** `funded_spinout`, hiring to 15 staff by turn 12, no fundraising: cash goes below zero (insolvent) on **at least 7 of 10** seeds before turn 36.
   - **(a) Lean without raising:** the M3a earn-and-burn script (6 people) in `funded_spinout`: survives to turn 36 on **at least 7 of 10** seeds. Staying small and self-funded stays a valid, slower path.
   - **(c) Fast growth with a Series A:** as (b), raising a Series A when allowed: survives to turn 60 on **at least 8 of 10** seeds.
   - The M3a earn-and-burn ARR at turn 36 stays inside its $500,000–$4M band.

   Levers, in this order; stop at the first combination that meets every target, and record the values:
   1. **Per-person running costs:** a new line, `costs.tools_per_head_cents`, from $0 up to $1,500 a month per active employee (software, equipment, travel; account `6900_general_admin`). 2010 startups paid about 1.3× salary per head all in, and the game's benefits plus office come to about 1.2×.
   2. **Self-serve awareness:** `market.awareness_scale` from 0.5 down to no lower than 0.3.
   3. **Mid-market and enterprise sales speed:** `products.seller_rate.*` down by at most a third.

   Do not change salaries, prices, investor terms or the incumbents. Update `docs/formulas.md` §8 (the new cost line), §11 and §12 with the final values and a CHANGELOG note. Also print the bridge size at a normal burn (Claude Code's M4b follow-up: $2.9M offered against a $1.1M deficit in an extreme script).

## Out of scope

Rival AI (M5), events (M6), new screens beyond the panels and dialogs above, any other balance change. Any balance lever not named in change 7.

## Sub-tasks (commit after each)

1. Energy values, tests and goldens.
2. "What you learned": API action results with before and after ranges; the panel; the personality columns.
3. Interview PA strength and the `initial_hw.pa` re-tune.
4. Investor heat and its test.
5. Board nominee choice, empty seats, the board-member card, migration.
6. Inbox mark-all-read, archive and filter, migration.
7. Balance pass (change 7) with the diagnostics table; Playwright additions: (a) interview a candidate and see the panel; (b) at a Series A, choose a nominee and open a director's card; (c) archive read items.

## Acceptance criteria

- [ ] A typical hiring month (one job post, four interviews, two reference checks) costs 45 of the founder's 60 energy.
- [ ] After an interview or reference check the screen shows what narrowed, before and after; references visibly change the personality columns.
- [ ] The potential target still holds (printed ≥ +3 PA) with interview PA strength 0.20; the tuned value is recorded.
- [ ] A $6M ARR Series A averages at least twice the term sheets of a $1.1M one.
- [ ] The player chooses the board nominee; every director's name opens a card that exists.
- [ ] The inbox can be marked all read and cleaned by archiving; archived items can be found again.
- [ ] Balance targets (b), (a) and (c) met, with the lever values and the diagnostics table recorded under Decisions made; formulas.md updated.
- [ ] No hidden value leaks through the new panels (exact-name test extended).
- [ ] `make check` green; `make e2e` passes all flows.

## Manual check (Reece)

Replay the first year of Game 1: does energy now force a choice, do interviews and references feel worth it, and at Series A do offers come in when the company is hot? Then replay Game 2: hiring to about 15 people by month 12 should now run you out of money unless you raise.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
