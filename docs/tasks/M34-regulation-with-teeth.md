# M34: Regulation with teeth (v4, lane C)

**Goal:** size brings scrutiny. Regulators by region designate gatekeepers, impose duties (side-loading, alternative payments, interoperability, no self-preferencing, fee caps), open investigations with visible stages, fine up to 10% of turnover and, rarely and with years of warning, order a break-up or unbundling. Rivals face the same rules and their real 2010–2025 histories. Compliance, settling and influence lower the risk.

**Formulas:** `docs/formulas.md` §48 (all), with §28.7, §29, §31, §32.4, §32.5, §44 · **ADRs:** 0002, 0003, 0005, 0013 (stream `regulation` 62), 0021 · **Research:** `docs/v4-research/regulation-dossier.md` · **Depends on:** M31 (`m31-done`) · **Lane:** C, alongside M32 (lane A) and M33 (lane B)

## Reece's decisions (2026-11-13)

- **Break-ups possible but rare, visible and warned years ahead;** most outcomes are lesser remedies.

## Lane

- Its own session and branch (`m34-regulation`) from `main`. **Merges first** of the three (it changes the fewest costs).
- **M34 owns:** new `backend/tst/sim/regulation/` (regulators, designations, duties, investigations, remedies, structural orders); `regulation.yaml` (new); where M31's platform rules and fee schedules read duties (`platforms/` rules: a forced setting and fee-rule rows); the antitrust review in `mna/` where it joins regulators; the Regulation screen and investigation events; `tst/balance/m34.py` (new).
- **M34 must not edit:** M32's `power/`, M33's `equipment/`, M36's family code. M31's platform model beyond the rule and fee hooks ADR-0021 names.
- **Shared files:** `balance.yaml` (add `regulation.*`), `accounts.yaml` (add `6970_fines`), `docs/formulas.md` (notes in §48 only), CHANGELOG, data dictionary, ADR-0013.
- **CLAUDE.md §9's decision rules apply.** §48.5 target 1 (history holds) is the guard, with M31's §44.9 targets re-run (fee schedules to 2025 must still follow history).

## Out of scope

Health regulators (M41 and M42 reuse this machinery with new kinds); data-privacy fines (GDPR) beyond a note (follow-up); export controls (M22's).

## Sub-tasks (commit after each)

1. **Research and data:** `regulation.yaml` from the dossier (regulators, strictness, thresholds, duties and dates, historical cases with fines, rulings and remedies for rivals), every value cited; `regulation.*` keys; stream `regulation`; migration and data dictionary.
2. **Regulators and designations** (§48.1): December tests, the year-ahead warning, rivals' historical designations.
3. **Duties** (§48.2): forced platform settings and fee-rule rows, compliance costs, non-compliance. **Test:** a designated platform's duties change its rules on their dates.
4. **Investigations** (§48.3): openings (seeded), visible stages, settle, contest and lobby, fines (`6970_fines`), behavioural remedies; rivals' cases to 2025 from the data. **Hidden-value test:** no investigation chance or draw in the API or a prompt.
5. **Break-ups and unbundling** (§48.4): the preconditions, warning signs at least 3 years ahead, the order, spin-off or sale within 24 months (§31, §28), appeals. **Property test:** a structural order never arrives without its preconditions and 3 years of warnings.
6. **Screens:** a **Regulation** screen (regulators by region, designations and thresholds, duties, investigations with stages, fines, warnings), investigation items in Needs you, M29 unlocks (Regulation at the first warning or investigation), glossary (gatekeeper, statement of objections, behavioural and structural remedy) and Explain on a fine and on designation thresholds.
7. **API, CLI, e2e, balance and close-out:** `tst regulation`; Playwright: (a) a designation warning arrives a year ahead, (b) settle an investigation with a commitment, (c) a scripted structural order after ignored warnings offers spin-off or sale; a practice save `pt-regulated` (a dominant platform owner in 2029 under an EU investigation); **§48.5 targets** printed and recorded, tuning only `regulation.*` (rule 1); re-run every earlier guard (M31 especially); CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `regulation.yaml` cites a source for every value; rules, designations, fines and rulings to 2025 follow it (tests).
- [ ] Every earlier guard unchanged (M31 §44.9 especially).
- [ ] A structural order never arrives without its preconditions and at least 3 years of warnings (property test).
- [ ] No investigation chance or draw reaches the API or a prompt (hidden-value test).
- [ ] §48.5 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m34-done`.

## Manual check (Reece, after merge)

Load `pt-regulated`. Read the investigation's stages, then either settle or contest. Turn self-preferencing back on and watch the warnings build.

## Decisions made

1. **The research** (`backend/data/regulation.yaml`, every value with its source or marked A). Every *(verify)* figure in the dossier was checked:
   - Confirmed: DMA thresholds (45M monthly end users, 10,000 business users, EUR 7.5B EU turnover or EUR 75B market value; CERRE and the EUR-Lex summary, not the Official Journal text itself); designations of 6 Sep 2023 and Booking on 13 May 2024; obligations from 7 Mar 2024; Google Shopping EUR 2.42B (2017, upheld 10 Sep 2024); Android EUR 4.34B (2018, cut to EUR 4.125B on 14 Sep 2022); AdSense EUR 1.49B (2019, annulled 18 Sep 2024); Apple music over EUR 1.8B (4 Mar 2024); Apple's DMA fine of EUR 500M and Meta's of EUR 200M (23 Apr 2025); US v. Google search (liability Aug 2024; remedies 2 Sep 2025: no Chrome or Android divestiture, no exclusive contracts, data shared); the ad tech liability ruling of 17 Apr 2025; Epic v. Google (verdict Dec 2023, injunction Oct 2024, affirmed 31 Jul 2025); NVIDIA-Arm terminated 8 Feb 2022; Adobe-Figma terminated 18 Dec 2023; Microsoft-Activision closed 13 Oct 2023 with the Ubisoft cloud remedy; the Microsoft break-up order of 7 Jun 2000, reversed 28 Jun 2001; AT&T's divestiture of 1 Jan 1984.
   - Resolved: FTC v. Meta ended for Meta (18 Nov 2025, no divestiture). Japan's MSCA: designations Mar 2025, full effect 18 Dec 2025, threshold 40M monthly users (Cabinet Order No. 376 of 2024). The UK's DMCC Act: in force Jan 2025; Google search designated 10 Oct 2025, Apple's and Google's mobile platforms 22 Oct 2025; thresholds GBP 25B global or GBP 1B UK turnover. Korea's law in force 14 Sep 2021 (already in platforms.yaml).
   - Left as A: regulators' strictness indexes; Japan's surcharge rate and Korea's fine cap; the UK regime's duties before any conduct requirement; currency rates (`regulation.fx`, near the 2023-2024 averages).
   - Not added: Google Play's DMA rates (M31's follow-up stands: a history fee row would move M28's books fingerprint).
2. **History holds by construction.** Nothing in `tst/sim/regulation/` runs, draws, posts or logs before `regulation.start` (January 2026), for the player as for rivals. History's designations and cases are data, shown from their months (a later step never before its month). M28's fingerprint and the golden snapshots are unchanged. In January 2026 history's designations of in-game companies become duties, dated as the data has them. A duty that platforms.yaml already carries for that country is not added twice, so Apple's UK duties (from April 2026) are its first new ones.
3. **The game's economy (PM ruling, 2026-11-15).** In-game companies earn about a tenth of their real revenue (Apple books $39.6B in 2025), so every money and user threshold, and the investigation revenue floor, is multiplied by a shared `economy_scale`:
   - `money` 0.0849: the designated incumbents' in-game 2025 booked revenue over real (Apple 0.0952 of $416.2B; Microsoft with Azure 0.1275 of $281.7B; Meta 0.0319 of $200.97B; `tools/m34_economy_scale.py`, seeds 1-3);
   - `users` 1.0: the game's user tests read shares, already at real scale.

   Screens show the law's figure with the game amount beside it; fines stay a share of turnover. Recorded in formulas §48.1.
4. **Turnover is booked revenue** (accounts 4000-4899 except intercompany sales), kept for 12 months from 2026 (`reg_turnover`), because `mrr_history` leaves out hardware sales. A region's turnover is the group's, split by its segments' customers x price there.
5. **Designation reads platforms** for the users test (the game counts no individual users of other products; A). A company over the thresholds is warned in its first December and designated in the next, so a warning always comes a year ahead.
6. **Duties** become `regulated` rows on the group's platforms and forced settings. The rows are: alternative payments at the standard rate less 4 points (Korea's precedent); a fee cap at 20%; side-loading and anti-steering as dated rules. Only the player can breach a duty; rivals comply.
7. **Investigations:** one open case per regulator and group, and `cooldown_months` before another after one closes; a $1B regional revenue floor ($85M in the game's economy). Settling at the inquiry costs no fine. Rivals settle at the charges unless aggressive or premium (Apple contests), and those that contest also appeal rulings.
8. **Structural orders** are a ruling's outcome. The unit is the player's own OS and store for a devices case, else a single subsidiary selling in the market, else the products there. A spin-off is §31.5's (it needs a subsidiary of a listed holding company); a sale goes to the rival with the most customers in the market. The order's event has three answers (sell, spin off, appeal), the most the event system allows, so "decide later" lives on the Regulation screen; an order left open pays periodic penalties after its deadline.
9. **ADR-0013:** stream 62's opening key uses the regulator's index, not the region's (East Asia and Europe each have several regulators); recorded in its row.
10. **A fix in M31's code (rule 8).** Event choices' `platform_step` answers lost their stat when saved (`tst/db/mappers.py` ENGINE_STEPS), so after a save a removal's comply, appeal or regulators answer did nothing; `regulation_step` had the same gap. Both are kept now.
11. **Balance scripts** (`tst/balance/m34.py`). The owner holds 45% of North America's and Europe's device users and 40M customers of a consumer app in each, re-set each month as M31's target 3 does (a scripted phone books no hardware sales, so the app is its business). Rule 2: the careful player keeps the commitments it settles with; my first script broke them again every month, which reopened cases and made settling worthless. Target 5 counts duties and fines the model made (designations, remedies, commitments, fines) on Apple or Microsoft from 2026; counting history's dated duties too, it is 10/10.
12. **Tuning (rule 1, `regulation.*` only):**

    | Key | Before | After | For |
    | --- | --- | --- | --- |
    | `investigation.base` | 0.002 | 0.004 | target 5 (2 of 4 seeds, then 8 of 10) |
    | `odds.complied_cut` | 0.5 | 0.3 | target 5 |
    | `investigation.influence_cut` | 0.5 | 0.35 | target 4 |
    | `fine.settle_share` | 0.3 | 0.4 (via 0.5) | target 4: contesting costs about 0.46 of a fine in expectation |

13. **§48.5 targets** (`tools/m34_targets.py`, seeds 1-10):

    | # | Target | Result | Band |
    | --- | --- | --- | --- |
    | 1 | History holds | unit tests; M28 fingerprint and golden snapshots unchanged | identical |
    | 2 | Big platforms meet a remedy | 10/10 seeds | at least 7 |
    | 3 | Defiant: structural orders by 2039 | 0/10 | at most 2, 36+ months warned |
    | 3 | Compliant: structural orders | 0/10 | none |
    | 4 | Settling and influence cut EU fines | 44% ($2.12B to $1.20B, mean) | 30-60% |
    | 5 | Rivals regulated after 2026 | 8/10 model-made | at least 8 |

    No scripted order arrived, so target 3's warning lead is guarded by the property test (`tests/property/test_m34_structural.py`) and its companion that does reach orders.
14. **The M30 state-cache fixture is re-recorded,** because M34 adds state (as M27b and M31 did).

## Follow-ups

- **Device sales in scripts and fixtures:** a phone line with a production contract and held customers books no hardware revenue, so the e2e and balance owners needed an app business to be believable. Worth a look by whoever owns hardware sales.
- **Google Play's regulated rates** (the EU DMA; Epic v. Google from October 2025) as platforms.yaml rows, once moving M28's books fingerprint is decided.
- **Seeded drift of regulators' strictness** after 2025 (politics, §32.5 influence): flat at 2025's values for now.
- **The antitrust review in `mna/`** still uses §28.4's strictness by year; joining it to the regulators' indexes would move M14's guards.
- **Data-privacy fines (GDPR)**; health regulators (M41, M42).
