# ADR-0020: Design v2 systems so v3 can extend them

- Status: Accepted
- Date: 2026-11-02
- Spec sections: §2, §6 (holding company, subsidiaries), §8 (value chain), §11 (minerals)

## Context

v3 adds a holding company with real subsidiaries, upstream facilities (mines, refineries, wafer plants, fabs), commodity markets and geopolitics (`docs/v3-outline.md`). Reece decided on 2026-11-02 that subsidiaries have separate books and minority stakes, geopolitics follows history then is seeded, and exploration reveals hidden grades by drilling. Several v2 milestones still to be built (M12a, M12b, M13) create the systems v3 will extend. Building them general now costs little; rewriting them later costs a lot.

## Decision

1. **The company is the legal entity.** Every ledger entry, facility, product, employment, loan, cap table and listing belongs to a `company_id` (already true for ledgers and rivals). New code takes a `company_id` and never assumes the player owns exactly one company. Where "the player" is meant, use one helper, `player_companies(state)`. It returns the player's single company until M16, when it returns the group.
2. **One facility model.** M12a's data centres and M12b's assembly plants are **kinds** of one facility model. Its fields: kind, owner `company_id`, region and city, capacity in the kind's unit, inputs per output unit, output good, utilization, staff role and ratio, reliability, capex and depreciation, operating cost, and status (building, live, closing). Kind-specific rules sit in small per-kind functions; the shared lifecycle (build, depreciate, staff, utilize, close or sell) is common. v3 adds mine, refinery, wafer plant and fab as new kinds with data plus their own rules.
3. **One market-good model.** M12a's component indexes (server, GPU) and M12b's chips and devices are **goods** with:
   - a key and unit;
   - a price index from history, then seeded;
   - allocation in shortages;
   - spot and contract purchasing with take-or-pay.

   v3 adds commodities as more goods.
4. **Internal supply.** When a company uses its own facility's output, it costs the facility's cost. When one company in a group supplies another (M16), the trade posts as an intercompany sale at a transfer price, which consolidation removes. M12b's chips used in its own devices go through this path with the same company, so no revenue is booked.
5. **Regions carry risk fields now.** `regions.yaml` gains `political_stability` (0–100) and `bloc` (for example `west`, `china`, `non_aligned`), with neutral defaults and no effect until M22.
6. **Hidden truths reuse ADR-0007.** Deposits' grade, tonnage and metallurgy are hidden values revealed as ranges per observing company, narrowed by skill and spend, never sent to the API or a prompt.
7. **Listings and cap tables are per company** (M13), so a subsidiary can later have its own investors and its own IPO.

## Consequences

- M12a, M12b and M13 briefs carry a "Design for v3" section pointing here, and reviewers check it.
- A little more structure in M12a and M12b (kinds, goods, a group helper) for much less rework in M16–M21.
- No v3 behaviour is built early: the fields and helpers exist, with neutral values, and nothing reads them until their milestone.

## Alternatives considered

- **Build v2 narrowly and refactor in v3:** simpler now, but M16 would have to touch every system that assumes one player company, and facilities would be rewritten for M19–M21.
- **Subsidiaries as a grouping only:** rejected by Reece; the spec asks for separate books, minority investors, spin-offs and sales.
