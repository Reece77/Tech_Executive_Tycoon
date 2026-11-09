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

1. **Countries split a region's demand** (the spec has regions, not national markets): each country has a `demand_share` of its region (an assumption from 2010s GDP and ICT spend; China is 55% of East Asia, the US 88% of North America). A restricted destination's customers are that share of the region's.
2. **`china` is both a country and a bloc**; in a rule it means the country (China's own controls, and the US's on China). Bloc-wide rules use `us_aligned` and `non_aligned`.
3. **Who is controlled: the player's group** (M16, subsidiaries included), not rivals. Rivals' products are abstract and their lobbying is out of scope; controlling them would move a software company's world (target 7). Follow-up below.
4. **Blocked customers wind down**: customers in a newly closed destination leave the books at `geopolitics.exit_rate` 0.25 a month and, until they do, still buy replacements (orders already placed). Target 2: 33.7% → 23.9% on seed 1 (band 15-30%).
5. **A compliant variant** is a mode of the chip product, not a second product (wafer capacity is per product): from its launch it sells where a rule restricts the chip, to `geopolitics.variant.keep` 0.7 of that destination's buyers (new key, an assumption: some buyers will not take a cut-down chip), at quality - 10 there (its choice share is computed at that quality). The rest wind down as blocked. October 2023's update and April 2025's H20 rule `voids_variants`, so a variant launched before them must be relaunched. Target 2 with a variant: 3.2% → 10.8%.
6. **Buying exposure** is the actor's share of world supply (commodities.yaml `top_share` when its `top_country` is in the actor's jurisdiction) on spot volume, and offtakes with suppliers sitting there (countries.yaml `sites`); offtakes elsewhere and the group's own refined supply (M20) are safe. The premium is a share of spot on the exposed volume: ban 60%, licence 25%, quota 40% (assumptions for rerouted and grey supply); allowed volume 0 for a ban, the quota's share, 80% under a licence regime. Target 3: 41%.
7. **Licence chances are not sent to the API**: the World screen shows each rule's base approval (public data) and says influence helps; a pending licence's chance with influence stays in the engine, as M24's chances do.
8. **Events reach only a touched group**: a critical event when a rule would close a selling product or cut an input in use, a major one when the group has hardware, chips, non-data-centre facilities, mines or refineries, nothing otherwise (target 7). Answers: comply, licence, variant, grey route; absorb or lobby (a one-off $200k for 5 influence points in the actor's region); accept or appeal a listing ($500k, 15% chance off).
9. **Rules M19 already applies** (Indonesia's ore bans, Mexico's, Zimbabwe's, Namibia's, Chile's and Bolivia's lithium, DRC's 2025 cobalt ban) are in `export_controls.yaml` with `via: m19`: shown, never applied twice. Goods the game does not trade (nickel ore, bauxite, graphite, antimony, minor metals, technology) are `news`.
10. **The entity list** binds by grey sales (4% a month) and by ownership of at least half by a listed company (at once while an affiliates rule bites, else 5% a month). Named entities (Huawei, ZTE, SMIC, Fujian Jinhua) are destinations for the record; none is a company in the game.
11. **Tariffs** use effective rates on cost (Section 301 lists averaged; phones and laptops were never taxed): devices 10% (Sep 2018), 15% (Sep 2019), 20% (Apr 2025); servers 10%, then 25% (May 2019); chips 25% (Aug 2018), 50% (Apr 2025). Target 5: 13.2% from late 2019.
12. **Tension tuning**: `escalation.base` and `detente.base` 0.008 → 0.013 (target 6: 5 → 8 of 10 seeds).
14. **Fabs at the M21 merge** (M21's fab code untouched): the check runs in the shared action dispatcher before `build_fab` and `upgrade_fab`. EUV nodes need `euv_tools` clearance, nodes at n16 and below (new key `geopolitics.equipment_node`) `chip_equipment` clearance in the fab's country; a tool licence (`request_tool_licence`, `/world/tool-licence`, on the World screen) is a licence with product id 0, decided like a product's. A fab ordered in East Asia without a city sits in China (the region's default). Orders placed before a rule are not recalled. Foundry services: M21 sells slots only to the chip incumbents (none in China), so the `fab_services` rules stop nothing yet. Own-fab chips are not cut by HBM or entity-list wafer cuts (those apply to foundry wafer contracts).
15. **The ten-year API run opens every route again** (product manager's addendum, 2026-11-09): `tests/integration/test_ten_years.py` replaces M21's skip of GET routes with required query parameters by sample inputs (`QUERY_SAMPLES`: the refinery quote at silicon_smelter, North America, 10,000; the fab quote at n28, North America, 10,000 starts). A new route with required query parameters fails the test until it has a sample, rather than being skipped.
13. **Engineering**: one `geo_record` table holds every M22 collection (kind + JSON data); stream `geopolitics` key families (0,) tension, (1, licence) decisions, (2, company) listing, (3, company) an appeal.

## Follow-ups

- Rivals under export controls (NVIDIA's China sales, Huawei as a rival), and rivals' lobbying.
- Facility licences (EUV tools for a fab in China) and fab-service controls wire to M21's `euv_tools` and foundry at the merge; until then those goods' rules show and do not bite.
- A country choice for new facilities and subsidiaries (today: the city's, or the region's default country); a site override exists in the data model.
- Transfer prices carrying tariffs between group companies (the seller books them today).
- Corporate tax by country and transfer-pricing audits (out of scope, later).
