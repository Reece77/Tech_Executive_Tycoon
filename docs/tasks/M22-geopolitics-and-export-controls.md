# M22: Geopolitics and export controls (v3, lane B)

**Goal:** the world's politics enter the chain. Countries sit in blocs (US-aligned, China, non-aligned), and tension between the blocs follows history to 2025, then moves in seeded escalations and détentes. Real export controls take effect on their dates: the 2019 Huawei listing, the October 2022 chip rules, China's 2023 gallium and germanium licensing, the December 2024 bans. Controls block or license sales, cut supply, can put a company on an entity list, and tariffs tax cross-bloc goods. Lobbying influence helps licences; subsidiaries in the right country and compliant chip variants keep business alive.

**Spec sections:** §8, §9 · **ADRs:** 0002, 0003, 0013 (stream `geopolitics` 55), 0019 (§9 history then seeded), 0020 (region risk, regional entities) · **Formulas:** `docs/formulas.md` §39 (all), with §16, §31, §32.5, §33, §35.4 · **Data:** `docs/v3-research/v3-data-dossier.md` §5 · **Depends on:** M20 (`m20-done`) · **Lane:** B, alongside M21 (lane A)

## Lane

- Its own session and branch (`m22-geopolitics`). **Merge order: M22 merges second:** merge `main` (with M21), wire controls to M21's `euv_tools` and fab services, re-parent migrations, regenerate golden snapshots once with both milestones' reasons, re-run every guard and both milestones' targets.
- **M22 owns:** `countries.yaml` (and the `country` field on cities and facilities), `export_controls.yaml`, `tariffs.yaml`, new `backend/tst/sim/geopolitics/`, the compliant-variant action, the entity list, account 5100 tariffs, a **World** screen (blocs, tension, rules in force, licences, the player's exposure).
- **M22 must not edit:** M21's node, fab and foundry code.
- **Shared files:** `balance.yaml` (`geopolitics.*`, `tariff.*`), `docs/formulas.md` (§39 notes only), `CHANGELOG.md`, `docs/data-dictionary.md`.
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Corporate tax by country and transfer-pricing audits (later). Wars or invasions as events beyond their effect on goods. Rivals' lobbying.

## Sub-tasks (commit after each)

1. **Data and formula tests:** countries with blocs and history, every dossier §5 rule with its date and source tag (V, or R with "verify the day"), tariff schedules, `geopolitics.*` keys, stream `geopolitics` in ADR-0013; unit tests for licence probability with influence and for the tariff posting.
2. **Countries, blocs and tension** (§39.1): the `country` field across cities, facilities and subsidiaries; tension history then seeded.
3. **Rules and their effects** (§39.2–§39.3): selling (ban, licence, quota), buying (allocation and price shocks through M17), compliant variants, the entity list (the player included), tariffs, regional entities and local-partner markets. **Tests:** each rule on its date on every seed; a seeded escalation and détente; the entity-list ownership rule.
4. **Events:** rule announcements as major events (critical when the player is directly hit), licence decisions, listing, détente.
5. **API, CLI, screens:** the World screen; licence requests from the product and facility screens; the compliant-variant action on chip products; **CLI:** `tst world`, `tst licence-request --product --country`, `tst compliant-variant --product`. Hidden values: future rules and seeded escalations never reach the API before they're announced.
6. **Balance, merge and e2e:** §39.4 targets printed and recorded; tune only `geopolitics.*` and `tariff.*`. **Playwright:** (a) the World screen in October 2022 shows the new chip rules; (b) launch a compliant accelerator variant and keep China sales; (c) a gallium ban raises a chip's cost; (d) a licence request approved with high influence. The merge steps above. CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every dossier §5 rule takes effect on its date on every seed; no future rule reaches the API before its announcement.
- [ ] The ledger balances with tariffs (property test).
- [ ] A software-only company in North America and Europe plays exactly as before.
- [ ] §39.4 targets met (printed, values recorded), on the combined code with M21.
- [ ] `make check` and CI `e2e` green; merged after M21 through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m22-done`.

## Manual check (Reece, after merge)

Run an AI-chip business through October 2022 with China customers: launch a compliant variant, lobby for a licence, and watch the December 2024 gallium ban hit your supply. Then try building a fab in a non-aligned country.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
