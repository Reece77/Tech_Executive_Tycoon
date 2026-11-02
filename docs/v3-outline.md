# v3 outline: Conglomerate

**Status: OUTLINE (2026-11-02).** Scope and rough milestones only, written during v2 so that v2's systems are built to extend. Full briefs and formulas come at the v2 retrospective after M15, as v2's did after v1. The forward-compatibility rules v2 must follow now are in ADR-0020.

## What v3 is for

The spec's v3 fantasy is a vertically integrated empire, "from quartz mines to cloud software" (§1, §2): a holding company with subsidiaries, then integrating leftward through fabs, wafers and refining to prospecting and mining, under geopolitics and export controls. v2 leaves the player at the chip-design end (fabless chips, M12b) buying foundry slots, wafers and components from others. v3 lets them own those tiers, and makes owning them strategic: supply security in shortages, denying rivals, and margins captured upstream.

## Reece's decisions (2026-11-02, ADR-0020)

- **Subsidiaries are real legal entities:** separate books, their own cap table and board, minority investors. They can be sold in part, spun off or listed. The parent consolidates them.
- **Geopolitics follows history, then is seeded:** export controls, tariffs and regional risk follow real events to 2025, then seeded. Examples: entity-list restrictions from 2019; chip export rules from 2022; gallium and germanium export licensing from 2023. They restrict where a company can sell, build, or buy chips, equipment and minerals.
- **Exploration has hidden grades revealed by drilling:** each deposit has a hidden true grade, tonnage and metallurgy. Surveys, sampling and drilling narrow the estimate ranges, using the same reveal mechanic as people (ADR-0007). Discovery to production takes years (spec §11).

## Rough milestones (numbering continues from v2)

| # | Milestone | Lane | Notes |
| --- | --- | --- | --- |
| M16 | **Holding company and subsidiaries:** stage 5; legal entities with their own ledgers, cap tables and boards; consolidation; minority stakes; intercompany transfers at transfer prices; selling stakes, spin-offs, subsidiary IPOs | single | foundation for everything after; touches finance deeply |
| M17 | **Commodities and offtake:** the market-good model from M12a extended to commodities (quartz, silicon metal, polysilicon, gallium, germanium, copper, tin, tantalum, cobalt, lithium, rare earths, neon), with spot prices, contracts and offtake agreements, all history then seeded | A | |
| M18 | **Prospecting and exploration:** regions' geology profiles; deposits with hidden truths; the pipeline (desk study, survey, sampling, drilling, resource estimate, feasibility, permitting); geologists; estimate ranges | B | M17 and M18 in parallel |
| M19 | **Mining operations:** construction, capex, opex per tonne, recovery, strip ratio, power and water, environment, community relations, closure | A | |
| M20 | **Refining and wafers:** silicon metal, polysilicon and ingots and wafers as facilities that turn inputs into outputs | B | M19 and M20 in parallel |
| M21 | **Fabs:** process nodes tied to M11's chip-design and process domains, yield, wafer starts, capacity, foundry services sold to rivals, EUV-style equipment scarcity | A | |
| M22 | **Geopolitics and export controls:** blocs, entity lists, tariffs, licensing, sovereign deals, nationalization risk, all history then seeded | B | M21 and M22 in parallel |
| M23 | **v3 balance and polish:** vertical-integrator strategy, 30-year runs, Reece's playtests | single | |

**Rough size:** 8 milestones in 6 rounds. Expect review-fix and playtest-fix milestones as in v2.

## Open until the v2 retrospective

- How deep fabs go (process nodes as levels, or named nodes like 28nm, 7nm and 3nm on a historical timeline).
- Whether minerals and refining feed real input-output chains for every v2 product, or only for chips and devices.
- Environmental and community events: which are critical.
- Which real mining, refining and foundry companies join the rival roster (for example Freeport-McMoRan, Albemarle, Wacker, Shin-Etsu, TSMC, Samsung, Intel Foundry).
