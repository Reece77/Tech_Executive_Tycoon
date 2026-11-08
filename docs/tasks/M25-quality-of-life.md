# M25: Quality of life: explain anything, achievements and a data editor (lane C)

**Goal:** three things that make a long game nicer to live in, none of which change the simulation. **Explain this:** click any number and get its driver breakdown, then ask your chief of staff why, in plain words written only from what you can see. **Achievements:** milestones across all your games (first launch, first IPO, causing an era, an exit, scenario wins). **A data editor:** change rivals, categories and balance values in the game, saved as named mods applied to new games and validated like the data files.

**Spec sections:** §16 (LLM), §17 (Hall of Fame) · **ADRs:** 0001, 0005 (the LLM explains, never decides), 0007, 0008 (data loading outside the sim) · **Formulas:** §16.5 (prompt allowlist), §17.3 (Ask my COO), §30 (Sandbox, Hall of Fame) · **Backlog:** `docs/ideas-backlog.md` (chief-of-staff advisor, achievements, data editor) · **Depends on:** M16 (`m16-done`) · **Lane:** C, alongside M17 and M18

## Lane

- Its own session and branch (`m25-qol`). It touches no simulation rules, so it can merge whenever it's ready; whichever lane merges later handles the merge (decision rule 8).
- **M25 owns:** new `backend/tst/advisor/` (outside the sim), new `backend/tst/profile/` (achievements, outside the sim), new `backend/tst/mods/` (the data-editor overlay, used by `loader.py`), `backend/data/achievements.yaml`, the Explain panel component, the Achievements screen and toasts, the Data editor screen.
- **M25 must not edit:** `backend/tst/sim/` (read the turn log and breakdowns only), M17's and M18's data files and code. The editor reads data schemas generically, so M17's and M18's new files appear in it automatically once they merge.
- **CLAUDE.md §9's decision rules apply.**

## 1. Explain this (the chief of staff)

- **Explain panel:** every KPI, product metric, person rating, cost line and market value on the main screens gets an "Explain" affordance. It opens the number's **driver breakdown** (extending `api/breakdowns.py` to every number that lacks one), with the last 12 months' trend.
- **Ask why:** a question box under the breakdown. The answer comes from the chief of staff (the Ask my COO person, §17.3, or a Chief of staff role if the player has one). Context: that number's breakdown, its 12-month history, related events in the last 6 months and the §16.5 allowlist. The prompt requires answers from the given numbers only and says so when it doesn't know. Model `llm.model_story`, within the monthly budget, logged in `llm_call_log`.
- **Offline or over budget:** a **template explanation** that names the two largest drivers of the change and their sizes ("Churn rose from 2.1% to 3.4%: quality fell 6 points (about +0.8 points of churn) and Salesforce cut its price 15% (about +0.5)").
- **Never** changes state, costs energy or sees hidden values. Extend the hidden-value prompt test to these prompts; add a differential test: two saves with the same revealed values but different hidden ones produce identical prompts.
- **CLI:** `tst explain --metric <key> [--entity <id>]` prints the breakdown and the template explanation.

## 2. Achievements

- About 40 achievements in `achievements.yaml` (key, title, description, condition kind, threshold, hidden until earned yes or no), for example: first product launched; first $1M, $100M and $1B ARR; profitable in year one; closed a Series A to D; IPO; market cap $10B and $100B; caused an era first; ran a data centre over 80% use; your own chip in your own device; bought a rival; integrated without losing a key person; exited, then founded again; won each scenario; survived a downturn without layoffs; kept five public promises; burnt out and came back; a foundation granting $10M a year; a holding company with five subsidiaries.
- **Checked** after each committed turn from the turn log and public state (outside the sim, no effect on the game), stored in a **profile file** in the saves folder (one per player profile, across saves), with the save and game date when earned.
- **Sandbox and modded games earn none** (they say so on the screen); scenario achievements count only from scenario mode.
- An **Achievements screen** (earned, locked, hidden with "???"), a toast when one is earned, and a count on the main menu.

## 3. The data editor (mods)

- A **Data editor** screen lists the editable data files (rivals and entrants, categories, cities, scenarios and `balance.yaml`), with forms generated from the loader's Pydantic schemas (lists as TanStack tables), each field showing its comment (unit and intent) from the YAML.
- **Edits save as a named mod**, `saves/mods/<name>.yaml`, an overlay of changed values only. The loader applies the chosen mod at **new game** and validates the merged data exactly as it validates the base files (invalid data never starts a game).
- **Determinism:** a save records its mod name and a hash of the merged data, and loads with the same merged data. A save never changes because a mod file changed later (it keeps a copy of its overlay).
- **Modded games** are flagged on the main menu, the save list and the Hall of Fame (a separate list), and earn no achievements.
- **CLI:** `tst mods`, `tst new-game --mod <name>`.

## Out of scope

Sharing mods online, editing a running save's data, an advisor that acts or recommends actions on its own, achievements with gameplay effects, Steam-style integration.

## Sub-tasks (commit after each)

1. **Breakdowns everywhere:** find every displayed number without a driver breakdown and add one (outside the sim, from public state); the Explain panel with trend. **Test:** every numeric field on the main screens' schemas has a breakdown or is listed as exempt with a reason (a scan test, as M15b's glossary test).
2. **Ask why** (§1): the prompt from allowlisted facts, the template explanation, budget and logging. **Tests:** hidden-value prompt test, differential test, the template naming the two largest drivers.
3. **Achievements** (§2): data, checks after commit, the profile file, the screen and toasts, the Sandbox and mod rules. **Tests:** each condition kind fires on a scripted state; a replayed turn doesn't award twice.
4. **Mods** (§3): the overlay format, merge and validation, the save's recorded hash and overlay copy, the editor screen. **Tests:** an invalid mod is refused with the loader's message; a modded save reloads identically after its mod file is edited; a game with no mod is byte-identical to before (golden snapshots unchanged).
5. **API, CLI, e2e and close-out:**
   - **Playwright:** (a) click Explain on churn and see the breakdown and a template explanation (LLM off); (b) launch a first product and see its achievement toast; (c) create a mod that halves a rival's starting brand, start a new game with it and see the change on the Rival screen; (d) a modded save shows its flag and earns no achievements.
   - Golden snapshots unchanged (nothing in the sim changes).
   - CHANGELOG, data dictionary (the profile file and the save's mod columns), README index row.

## Acceptance criteria

- [ ] No hidden value reaches an Explain prompt (hidden-value and differential tests).
- [ ] A game without a mod is byte-identical to before; a modded save reloads identically after its mod file changes.
- [ ] Achievements award once, from public state, and never in Sandbox or modded games.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m25-done`.

## Manual check (Reece, after merge)

Click Explain on three numbers that surprised you in your last game, and ask your chief of staff why. Make a mod that makes AI models twice as big a market and start a game with it.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
