# ADR-0018: Equity in shares, post-money SAFEs, and how a game ends

- Status: Accepted. Extends ADR-0003 (ledger) and ADR-0011 (founder removal).
- Date: 2026-10-26
- Spec sections: §3, §10, §17

## Context

M1 stored employee equity as basis points with a fixed 10% pool. M4 brings rounds that dilute everyone, so ownership must be tracked in shares. M4 is also the first milestone in which a game can end: by bankruptcy, or by the board removing the founder (ADR-0011). The repository has no Sandbox mode yet.

## Decision

1. **Shares.** Every holding is an integer share count in `cap_table_entry` (holder, class: common, preferred series, option, SAFE conversion), with option grants and vesting on `option_grant`. A game starts at 10,000,000 fully diluted shares (`docs/formulas.md` §14.2). Offers keep stating equity in bp of the current fully diluted count, converted to options at hire; pre-M4 saves convert 1 bp to 1,000 options.
2. **SAFEs are post-money, cap only.** A SAFE's holders own `amount / cap` of the company immediately before the next priced round's new money. Discounts and convertible notes wait for v2.
3. **Round mechanics are in formulas.md §14.5**, including the pool top-up computed pre-money ("pool shuffle"). The closing is computed in one pure function with a property test: after a close, the unallocated pool is the target share of post-money FD (within one share), the new investor owns `amount / V_post` (within one share), and the cap table sums to FD.
4. **Game over.** A save has `game_state`: `active`, `bankrupt` or `founder_removed`, with the turn it ended. Once ended, `advance_turn` and every action refuse with a domain error (HTTP 409); reads still work, so the player can look back. The save stays loadable. Every difficulty ends the game this way; the future Sandbox mode (M7) will turn both endings into warnings.
5. **Randomness.** A new stream `finance` (id 16): key `(safe_id,)` for SAFE answers and `(round_id, firm_index)` for term sheets, with `firm_index` in `investors.yaml` order.

## Consequences

- Hiring code reads the unallocated pool from the cap table instead of summing bp.
- Exits, liquidation preferences and down-round anti-dilution are recorded but have no effect until v2.

## Alternatives considered

- Keep ownership in bp and rescale on each round: rounding drift compounds over several rounds and cannot reconcile with a share count.
- Pre-money SAFEs with discounts: closer to 2010 practice, but their conversion is harder to explain on screen and adds a second iteration to the closing math.
