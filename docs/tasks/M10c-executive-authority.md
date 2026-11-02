# M10c: Executives with authority

**Goal:** executive seats gain real power. Each filled seat can be given authority over its function within guardrails the player sets (CTO staffing, CRO sellers and prices, CMO marketing, COO support and offices, CFO runway and debt proposals). Executives report quarterly and drive their own events, and a growing company can run without the founder touching every decision.

**Spec sections:** §3 (stage 3 executive team), §6 (executive roles) · **ADRs:** 0014, 0015 (delegates act in phase 2), 0005 · **Formulas:** `docs/formulas.md` §24 (all), with §13.10, §18.3, §23.1–§23.2 · **Depends on:** M10b (`m10b-done`)

## Context

Reece, after his playtest (2026-11-01): "There needs to be more power to the executive seats ... we need to feel they have power and we need better ways to delegate to allow our teams the ability to function independently of us especially as our company grows." He chose functional delegation now, ahead of M13's CEO and Chair, which will build on this layer. Delegated actions go through the same `apply_action` path as the player's (ADR-0015), so rules, energy and logs stay one system.

## Out of scope

The CEO seat and Chair step-up (M13). Rival executives. Balance tuning beyond what §24.5 needs (M10d does the full pass).

## Sub-tasks (commit after each)

1. **Data and formula tests:** `exec_authority.*` keys (decision-quality formula, energy, defaults for each seat's guardrails); executive event templates; report templates.
2. **Authority and guardrails** (§24.1): the `set_authority` action with guardrails per seat; persistence (migration, data dictionary); API and screen controls on the Executive team panel.
3. **Executive decisions** (§24.1, §24.2): the rules for each seat in phase 2 through `apply_action` with the executive as actor; decision quality from the true score on stream `delegate`; mistakes logged by name. Unit tests per seat, a seeded quality test, and guardrail property tests (never over the caps).
4. **Proposals** (§24.1): the CFO's round and loan proposals and the COO's lease proposals as major inbox items with Approve and Decline (they block Continue under §23.1).
5. **Reports and events** (§24.3): quarterly reports (LLM within budget, templates offline); executive event templates with modifiers; the COO answers Ask my COO from their report. Hidden-value prompt test extended.
6. **API, CLI and screens:** authority toggles and guardrails, this month's decisions, proposals and reports on the Executive team panel; History entries; glossary; `tst authority --seat --on`, `tst reports`.
7. **Targets, golden snapshots and e2e:**
   - the §24.5 targets printed and recorded;
   - golden snapshots unchanged unless the scripts give authority (they don't by default);
   - **Playwright:**
     - (a) give the CRO authority and see a seller hiring plan opened when capacity limits sales;
     - (b) a CFO proposal blocks Continue and approving it opens the round;
     - (c) a quarterly report arrives;
   - close-out.

## Acceptance criteria

- [x] Each seat's authority acts within its guardrails (property tests) through the player's action path.
- [x] Decision quality follows the true score; mistakes are visible by name; no API response shows the score or the probability.
- [x] Proposals need approval and block Continue.
- [x] Quarterly reports and executive events arrive; offline templates work.
- [x] §24.5 targets met (printed, values recorded).
- [x] `make check` green; `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m10c-done`.

## Manual check (Reece, after merge)

On `quick-stage3`, appoint all five seats, give them authority, and Holiday for two years. Do they run the company sensibly, and do their reports tell you what they did?

## Decisions made

- **Seats with authority (2).** The five seats in §24.1 (CTO, CRO, CMO, COO, CFO); the CPO has none and still reports. `set_authority` (energy 2) turns a filled seat's authority on or off and merges guardrails over the seat's current or default values (`exec_authority.defaults`); a vacated seat keeps its authority row, so a new holder acts at once. The CFO's cash guardrail is `repay_above_months` (the hidden-field check forbids `cash_months`). The CRO's price band anchors on each sales-led price when authority is given (the player's last price). Migration 0027 (`exec_authority`, `exec_decision`, `exec_proposal`).
- **Acting (3).** In phase 2 after the hiring delegates, in seat order; each holder with authority gets `exec_authority.energy_per_month` (100) at reset and acts through `apply_action` as the actor. The quality draw is on stream `delegate` keyed (person id, 1,000,000 + seat index), one draw a month per seat; choosing uses the shown team (displayed ranges). The CMO spends its share of last month's MRR. A CTO plan for a product with no builders asks for ceil(needed / typical output) people (`builders_to_add` with no builders now uses a typical builder's output 1.0, so M10b's "team too small" message says 2 for one builder's gap).
- **Proposals (4).** Own records, not events: one pending per kind at a time, not re-proposed within `report_months` of a decline. Approve takes the proposed action (a round at the series' typical midpoint, a loan at half the limit, a 25-seat lease) as the player, at its own energy and rules; Decline closes it. Pending proposals block the player's Continue alongside major events (409 `events_open` gains `proposal_ids`; `EventsOut.blocking_proposal_ids`; "Answer N events and M proposals first", linking to the Org screen when only proposals block). Holiday will not start with one pending and stops on one; headless turns (CLI `advance`, scripts) let it lapse at the next turn.
- **Reports (5).** Every filled seat reports in the last month of each quarter: KPIs for its function from what the company can see, what it did with its authority (or that it had none), and up to two concerns. The template text is built in the sim; a `exec_report` text request lets the LLM rewrite it from those lines within the budget, and the written report replaces the inbox body. The panel shows each seat's newest report (`ScaleupOut.reports`); `tst reports` prints them with the quarter's decisions and proposals.
- **Executive events (5).** Triggers: `exec_cto`, `exec_cro`, `exec_cmo` (fixed strength 0.3) while that seat acts; `exec_cfo` while runway is below the CFO's own guardrail; `exec_clash` for two current seat holders at relationship ≤ −10 (strength as `team_clash`). Five templates, each with a modifier choice.
- **Ask my COO (5).** The COO seat's holder answers when the seat is filled (before the operations-manager rule); the prompt starts with their latest report and the offline reply quotes it.
- **History and glossary (6).** Timeline entries for `set_authority` and `answer_proposal`; reports (people) and proposals (finance) in the timeline; executives' own actions appear as delegate entries under their names. Glossary terms `exec.authority`, `exec.guardrails`, `exec.proposal`, `exec.report`.
- **§24.5 measurement (7).** `tst/balance/m10c.py`: from each seed's steady game at stage 3, five senior holders at score 15 (or 8). Executives resign and are poached at the game's usual rates (all five of seed 1's holders left within a year, with or without authority), so the delegated founder approves proposals and refills a vacant seat as the steady script does (and gives the new holder authority); nothing else. The caps count staff below exec level (the refill's exec hires sit outside them). Coverage is read at month ends that began with a COO acting, and target 3 holds the mean monthly shortfall to 0.1: one support person leaving costs 0.25-0.33 at 3-4 needed until the COO's plan fills (about two months), so the worst single month (0.27) is printed, not held.
- **One default tuned.** The CRO's default seller cap is 20 (10 held delegated ARR to 0.83 of steady, every run at the cap). Values: target 1 0.92, target 2 1.29, target 3 no cap exceeded and mean shortfall 0.009, target 4 94% unspent (`docs/balance-targets.md`, M10c).
- **Golden snapshots unchanged**: no script gives authority, and reports, triggers and Ask my COO need filled seats with authority or at stage 3.
- **Verification at close.** `make check`: lint, types, front end and the API sync pass; 1,146 backend tests passed with the recorded xfails unchanged (8 xfailed, 3 xpassed as after M10b). Two timing checks missed only inside the parallel nightly and pass alone, as in M10b: the product turn time (1,205 ms under load, 613 ms alone, budget 1,000) and S2 (35.4 worker-minutes under load, 18.8 alone, budget 20). On CI the product turn-time test then missed three runs of four (1.2-1.36 s on the 2-core runners; main passed, and locally main read 645 ms against the branch's 613 ms, so M10c added no turn cost). Two speed fixes, ahead of M10d's speed pass: `GameState.person` finds people by binary search (`people` is kept sorted; the top hot spot of the pure balance run), and the tests' `answer_critical` checks the event table before loading the whole state (a full load each month inside the timed loop): 434 ms locally. The GitHub `check` run on the branch is green. `make e2e` 52 passed. §24.5 targets as above (`tests/balance/test_m10c_balance.py` passes).
- **e2e.** `tools/e2e_m10c_save.py` builds a stage-3 company with a capacity-limited mid-market product and a CRO, and a garage start with a CFO and about three months of cash; the e2e helper declines proposals before Continue in flows not about them.

## Follow-ups

- **Executive retention.** Seat holders leave fast (the recorded "executive retention" xfail); with authority this empties seats and stops delegation unless the player refills them. For M10d's balance pass.
- **Growth hiring.** No seat's rule grows the company: the CTO keeps products at their maintenance line and in-development products at a steady pace, and the CRO hires when sales capacity binds. Delegated companies grow mostly through sellers and marketing. If Reece wants executives to scale the team, a "growth" guardrail for the CTO is the natural addition.
- **Coverage granularity.** The COO opens plans only below the target; a small buffer (one person over) would keep single departures from dipping coverage.
- **The CFO's round proposal** starts the round; picking a term sheet stays with the player (§24.1's "recommended term sheet" is the typical target, not a sheet).
- **COO leases** are always proposals (`lease_approval_rent_cents` 0); a positive value would let the COO sign small leases itself once that path exists.
