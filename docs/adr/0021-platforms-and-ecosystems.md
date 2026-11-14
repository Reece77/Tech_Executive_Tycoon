# ADR-0021: Platforms and ecosystems

**Status:** accepted (2026-11-14, product manager, from Reece's v4 decisions of 2026-11-13) · **Milestone:** M31 · **Formulas:** §44

## Context

v4 adds platforms (app stores, developer ecosystems, network effects, lock-in, fees and gatekeeping). They cut across products, devices, regions and rivals, and M34 (regulation) will act on them. They need one model that fits ADR-0020's rules: per-company everything, generic records with kinds, and history to 2025 followed by seeded futures.

## Decision

1. **A platform is its own record,** owned by one company (`platform`: id, owner company, kind `device` or `developer`, stable key, name, launched and ended turns, region list). It is not a product and not a facility. Products attach to it: device products run on one device platform, and developer-platform products (model APIs, cloud marketplaces, developer tools) are its base.
2. **Per-region state per platform** (`platform_region`: users, developer share, catalogue index, goodwill, tools score) is updated once a month in the market phase, before product demand reads it. Through 2025, users and shares are set from `platforms.yaml`. From 2026 they are computed (§44.1–§44.3).
3. **Fees are a schedule, not a number.** `platform_fee_rule` rows (platform, region or all, from turn, kind: standard, subscription after a year, small business, regulated) are data to 2025 and owner or regulator decisions after. The effective fee for a sale is looked up by platform, region, turn and seller size.
4. **Fees are real money between companies.** An app seller posts gross revenue and a platform-fee cost (`5150_platform_fees`); the platform owner posts `4150_platform_fees`. Both sides balance per entity (ADR-0003). When the owner and the seller are in the same group, the fee is intercompany and eliminates on consolidation (§31).
5. **Gatekeeping acts on products, through events.** A removal is a product-and-platform-and-region status (`platform_listing`: listed, under review, rejected update, removed, with dates). Demand reads it. The player's choices come through the event system (critical severity), so the engine disposes and the LLM only writes text.
6. **Hidden values.** Review chances and draws, rivals' rule plans and seeded future rules stay engine-side. The API shows public schedules, the player's own platform exactly and rivals' developer shares as ranges.
7. **Stream** `platforms` (58), keyed by platform keys and stable company keys (ADR-0013).

## Consequences

- Devices gain a dependency on their platform's catalogue, and app categories on fees. History calibration (§44.4) keeps 2010–2025 net revenue unchanged.
- M34 regulates through the same records: designations read platform users and developer shares, and duties change `platform_fee_rule` and the rules settings.
- The model also covers later platforms (consoles, cars, headsets) by adding device platforms in data.
