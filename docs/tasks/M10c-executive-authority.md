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

- [ ] Each seat's authority acts within its guardrails (property tests) through the player's action path.
- [ ] Decision quality follows the true score; mistakes are visible by name; no API response shows the score or the probability.
- [ ] Proposals need approval and block Continue.
- [ ] Quarterly reports and executive events arrive; offline templates work.
- [ ] §24.5 targets met (printed, values recorded).
- [ ] `make check` green; `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m10c-done`.

## Manual check (Reece, after merge)

On `quick-stage3`, appoint all five seats, give them authority, and Holiday for two years. Do they run the company sensibly, and do their reports tell you what they did?

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
