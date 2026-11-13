# M27b: Automation for the chain (v3.5, lane A, after M27a)

**Goal:** the v2 and v3 areas (device production, supply and commodities, exploration, mines and refineries, fabs and foundry customers, government affairs, corporate development) join M27a's automation layer, so a whole vertically integrated group can run under delegates, with one-offs still coming to the player.

**Formulas:** `docs/formulas.md` §40.7 (the M27b session settles each rule's details, records them in §40.7, and stops to ask only where §40 and this brief don't answer), with §28, §33–§39 · **Depends on:** M27a (`m27a-done`) · **Lane:** A, after M27a, alongside M28 or its successor

**Status:** outline. The product manager revises this brief after M27a's merge with what M27a actually built; start only from the revised version.

## Sub-tasks (outline)

1. **Device production:** contract-manufacturer orders and plant use to the shown demand plan, within guardrails for weeks of cover.
2. **Supply and commodities:** keep each input's 12-month cover within a band (default 60–100%) using M23c's planning view's numbers; sign standard contracts and offtakes under the limit; termination stays a one-off.
3. **Exploration:** run licensed projects through the pipeline within a yearly budget; licence the best blocks the desk studies show; drop projects below a grade guardrail; the development decision is a one-off.
4. **Mines and refineries:** output, maintenance, power contracts and sales routing (group first, then contracts, then spot); expansions and closures are one-offs.
5. **Fabs and foundry customers:** wafer starts by node to own demand first, then foundry contracts above a margin guardrail; conversions and new nodes are one-offs.
6. **Government affairs:** lobbying by region within a budget, licence applications, compliant variants proposed.
7. **Corporate development:** quarterly target screening and acquisition pitches; every bid is a one-off.
8. **Targets, e2e and close-out:** a full integrator (M23b's `full_integrator`) with every area automated by score-15 owners lands within 0.85–1.2× of the scripted integrator over 30 years; score-8 owners at least 20% worse; a practice save `pt-auto-chain`.

## Acceptance criteria (draft)

- [ ] Every §40.1 area marked M27b can be automated.
- [ ] §40.10's limit and one-off property tests cover the new areas.
- [ ] The targets in sub-task 8 printed and met, or carried with a recorded decision.
- [ ] Merged through a pull request with the trailer `Milestone-Tag: m27b-done`.
