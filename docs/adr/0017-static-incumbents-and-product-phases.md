# ADR-0017: Static incumbents until M5, and where products run in the turn

- Status: Accepted. Extends ADR-0006 (phase use) and ADR-0010 (rivals).
- Date: 2026-10-25
- Spec sections: §7, §9, §17

## Context

M3 gives the player products and customers, but rivals with AI arrive in M5 (ADR-0010). A market with no competitors would make share, price and churn meaningless, and the M3 acceptance criterion ("share responds to price and quality") needs someone to take share from. ADR-0006 names phase 3 "R&D progress (v2)" and phase 5 "sales, revenue, churn (M3+)", and does not say where product development or brand updates run.

## Decision

1. **Incumbents.** M3 seeds the 2010 market from `backend/data/incumbents.yaml`: real companies as `company` rows with `is_player = false`, each owning live products with fixed quality, brand and prices, a feature score held constant, and starting customers (`docs/formulas.md` §11.9). They have no people, no ledger and no decisions. All market code treats their products exactly like the player's.
2. **M5 upgrade path.** M5 gives these same companies people, ledgers and the utility AI; no market code changes. New rival startups are also M5.
3. **Phases.** Phase 3 runs product development (quality and features); the v2 technology tree joins it later. Phase 5 runs appeal, customers and revenue. Phase 6 posts hosting and marketing costs. Phase 9 updates brand and grows addressable demand. Phase 10 applies the ARR stage gates. `test_turn_order.py` does not change.
4. **Randomness.** Development noise uses a new stream `product_dev` (id 15, key `(product_id,)`); demand noise uses the reserved `market` stream (id 4, key `(category_index, segment_index)`), indexes in `categories.yaml` order.

## Consequences

- Balance in M3 is tuned against fixed incumbents, so a player can learn the market; M5 makes it reactive.
- Incumbent scores are public and may be shown in full (no hidden values).

## Alternatives considered

- A share curve with no competitor products: cheap, but price and quality would have nothing to be compared against, and M5 would need a rewrite.
- Building rival AI in M3: doubles the milestone and couples market tuning to AI tuning.
