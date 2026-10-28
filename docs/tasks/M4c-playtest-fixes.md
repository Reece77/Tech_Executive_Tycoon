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

## Changes

1. **Energy** (`formulas.md` §6): `founder.energy_per_month` 60; costs interview 8, reference check 4, job post 5, recruiter 5. Update every test and golden that assumed 100 (regenerate with a CHANGELOG note). Delegates are unchanged.
2. **What you learned** (the main fix for notes 3 and 4): every interview, reference check and scout returns, and the Recruitment screen shows, a short panel for that candidate: each range that narrowed (before → after, skills, personality and the potential phrase), interests and work style if revealed, and any trait noticed. The candidate table gains a "Personality" column group (loyalty, professionalism, ambition, risk appetite as ranges) that references visibly sharpen. The API returns the before and after ranges from the action's result; the front end only formats.
3. **Interview potential** (`formulas.md` §4): interview PA strength 0.20; re-tune `reveal.initial_hw.pa` (60–120, smallest value that holds) so `test_judgment_spots_potential` still shows ≥ +3 PA. Record the value and the new typical phrase after a job post plus one interview.
4. **Investor heat** (`formulas.md` §14.5): term-sheet response × `heat`. Test: on the same seed, a Series A at $6M ARR receives at least twice as many term sheets as one at $1.1M (mean over 50 seeds).
5. **Board nominee** (`formulas.md` §14.6): the Series A acceptance dialog asks for the nominee (employees only, most senior preselected); `name_nominee` action (energy 2) for an empty seat; the nominee leaving empties the seat with an inbox note. Board directors who are not employees open a **board-member card** (name, firm, seat, since, confidence and trend), never the employee profile (fixes the dead link). Migration for existing saves: a generated nominee is replaced by an empty common seat with an inbox note asking the player to name one.
6. **Inbox cleanup**: "Mark all as read", per-item "Archive", "Archive all read", an "Archived" filter, and archived items hidden by default; `inbox_item.archived` column and migration. Archive is a UI action (no energy, no game effect, not in `decision_log`).
7. **Funding diagnostics** (rerun, printed, no tuning): the M4a table with the new energy and heat, plus the bridge size at a normal burn (Claude Code's M4b follow-up: $2.9M offered against a $1.1M deficit in an extreme script).

## Out of scope

Rival AI (M5), events (M6), new screens beyond the panels and dialogs above, any other balance change. Note 8 (runway pressure) is left as it is: hitting 3 months and recovering on revenue is the intended tension; Game 2 of the playtest (fast hiring in a funded spinout) will decide whether funding is too optional.

## Sub-tasks (commit after each)

1. Energy values, tests and goldens.
2. "What you learned": API action results with before and after ranges; the panel; the personality columns.
3. Interview PA strength and the `initial_hw.pa` re-tune.
4. Investor heat and its test.
5. Board nominee choice, empty seats, the board-member card, migration.
6. Inbox mark-all-read, archive and filter, migration.
7. Diagnostics rerun; Playwright additions: (a) interview a candidate and see the panel; (b) at a Series A, choose a nominee and open a director's card; (c) archive read items.

## Acceptance criteria

- [ ] A typical hiring month (one job post, four interviews, two reference checks) costs 45 of the founder's 60 energy.
- [ ] After an interview or reference check the screen shows what narrowed, before and after; references visibly change the personality columns.
- [ ] The potential target still holds (printed ≥ +3 PA) with interview PA strength 0.20; the tuned value is recorded.
- [ ] A $6M ARR Series A averages at least twice the term sheets of a $1.1M one.
- [ ] The player chooses the board nominee; every director's name opens a card that exists.
- [ ] The inbox can be marked all read and cleaned by archiving; archived items can be found again.
- [ ] Diagnostics printed and recorded under Decisions made.
- [ ] No hidden value leaks through the new panels (exact-name test extended).
- [ ] `make check` green; `make e2e` passes all flows.

## Manual check (Reece)

Replay the first year of Game 1: does energy now force a choice, do interviews and references feel worth it, and at Series A do offers come in when the company is hot? Then Game 2 from the playtest instructions, if you have time.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
