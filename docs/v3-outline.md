# v3 outline: Conglomerate

**Status: OUTLINE (2026-11-02; decisions added 2026-11-06).** Scope and rough milestones only, written during v2 so that v2's systems are built to extend. Full briefs and formulas come at the v2 retrospective after M15, as v2's did after v1. The forward-compatibility rules v2 must follow now are in ADR-0020.

## What v3 is for

The spec's v3 fantasy is a vertically integrated empire, "from quartz mines to cloud software" (§1, §2): a holding company with subsidiaries, then integrating leftward through fabs, wafers and refining to prospecting and mining, under geopolitics and export controls. v2 leaves the player at the chip-design end (fabless chips, M12b) buying foundry slots, wafers and components from others. v3 lets them own those tiers, and makes owning them strategic: supply security in shortages, denying rivals, and margins captured upstream.

## Reece's decisions (2026-11-02, ADR-0020)

- **Subsidiaries are real legal entities:** separate books, their own cap table and board, minority investors. They can be sold in part, spun off or listed. The parent consolidates them.
- **Geopolitics follows history, then is seeded:** export controls, tariffs and regional risk follow real events to 2025, then seeded. Examples: entity-list restrictions from 2019; chip export rules from 2022; gallium and germanium export licensing from 2023. They restrict where a company can sell, build, or buy chips, equipment and minerals.
- **Exploration has hidden grades revealed by drilling:** each deposit has a hidden true grade, tonnage and metallurgy. Surveys, sampling and drilling narrow the estimate ranges, using the same reveal mechanic as people (ADR-0007). Discovery to production takes years (spec §11).

## Reece's decisions (2026-11-06)

- **Fabs use named process nodes on their historical timeline** (65nm through 2nm, arriving on the real dates for each foundry, then seeded): each node needs research in the process domain, EUV-class tools from 7nm, and rising capex.
- **The mineral and refining chain feeds chips and devices first** (wafers, chips, batteries, devices). Software and cloud keep their v2 inputs. Extending the chain to other products is a later choice, once v3's chain is playing well.
- **Critical mine events** (they stop the game for a decision): accidents and spills (tailings failures, fatal accidents), protests and permits (blockades, permits revoked or delayed), nationalization (seizure or forced stakes, history then seeded) and commodity price crashes.
- **v3 starts after a v2 retrospective:** M15a and M15b, Reece's last v2 playtest, a short retrospective and Codex review 4, then M16. v3 briefs, formulas and historical data are prepared in the meantime.

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

**Codex review 4 (2026-11-07):** M15r fixes nine findings alongside M16 and M24; findings 2 and 3 (consolidation by period, nested groups) are M16's first sub-task.

**A third lane (Reece, 2026-11-07, "expedite as able"):** **M24, the founder's life** (stress and burnout, a personal account and foundation, a public persona, political influence with scandal risk, a legacy score) runs alongside M16 and merges first. Its brief is `docs/tasks/M24-the-founders-life.md`. Later v4 and v5 pieces join that lane only when they don't depend on v3's chain (`docs/ideas-backlog.md`).

**Rough size:** 8 milestones in 6 rounds. Expect review-fix and playtest-fix milestones as in v2.

## Open until the v2 retrospective

- Which real mining, refining and foundry companies join the rival roster (for example Freeport-McMoRan, Albemarle, Wacker, Shin-Etsu, TSMC, Samsung, Intel Foundry).
