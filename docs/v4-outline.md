# v4 outline: Power, platforms and regulation

**Status: OUTLINE (2026-11-13).** Scope, decisions and rough milestones. Full briefs and formulas come milestone by milestone, starting with M31 once M27a merges. Historical figures named here are placeholders for the v4 research dossier (`docs/v4-research/`), which checks each against a source before a brief uses it.

## What v4 is for

v3 gave the player the whole physical chain, from quartz and lithium mines to fabs and devices. v4 adds the three forces that decided the real tech industry's 2010s and 2020s beyond the chain:

- **Platforms:** whoever owns the app store and the developers owns the customer. Network effects and lock-in make platforms the most profitable position in tech, and the hardest to dislodge.
- **Power:** data centres and fabs are now limited by electricity. Power contracts, owned plants, grid queues and carbon prices become the next upstream tier.
- **Regulation with teeth:** once a company is big enough, regulators can force it to change its business model, or to break up.

And one lane alongside: **semiconductor equipment**, the EUV chokepoint.

## Reece's decisions (2026-11-13, "defaults")

1. **Platforms:** the player can run an **own app store and developer ecosystem**. Rivals' stores (Apple's, Google's and others) are real competitors and **gatekeepers**: they set fees and rules for the player's apps, and can refuse or remove them.
2. **Power:** the player can **buy power contracts by region** (extending M17's regional power) **and build and own plants** (gas, solar with storage, wind, nuclear including small modular reactors later) for its fabs and data centres. Owned plants unlock at **stage 4**.
3. **Regulation:** regulators **can force a break-up or unbundling** (for example separating the app store from the devices business), as a **rare and visible threat with warning signs years ahead**. Most outcomes are lesser remedies: fines, fee caps, interoperability and side-loading duties.
4. **EUV:** first the **chokepoint**: one supplier (ASML), allocation queues, prices and export controls, with rivals competing for slots. Building the player's own lithography tools is a **late, very expensive research path** (a decade or more, tens of billions, with failure risk).

## Rough milestones (numbering continues from v3.5)

| # | Milestone | Lane | Starts | Notes |
| --- | --- | --- | --- | --- |
| **M31** | **Platforms and ecosystems:** an app store as a facility-like business per device family and OS; developers as a population that joins platforms by reach, fees and tools; apps as the market good (§33's model); network effects (more users bring more developers bring more apps bring more users); lock-in as switching cost per customer; platform fees (history: 30%, then 15% small-business tiers, then regulated rates) and rules; gatekeepers that review, reject or remove the player's apps; open-source strategy (open a product to win developers at the cost of margin); standards wars (two incompatible formats; the market tips) | C, after `m27a-done` | about 2026-11-17 | sits on products and markets, which M27a and M28 don't own |
| **M32** | **Power and owned plants:** power-purchase agreements by region and term; building gas, solar with storage, wind and nuclear plants (capex, build time, capacity factor, fuel and carbon costs, outages); grid interconnection queues (years of waiting by region); carbon prices by region (history, then seeded); data centres and fabs sited by power; selling surplus to the grid; rivals' plants via M28's chain companies | A or B, after `m28-done` | about 2026-11-20 | uses M28's facility and price work |
| **M33** | **Semiconductor equipment:** EUV and advanced DUV tools as a market good from ASML with allocation queues (M21) and controls (M22), now with rivals competing for slots and ASML's pricing and generations (low-NA, then high-NA); then the **lithography** research domain and the own-tools programme (generations of tools with lower throughput, more downtime and lower yield at first; ASML responds; overruns and failure as M19's mines); selling tools to rival foundries | A or B, after `m28-done` | about 2026-11-20 | the EUV lane; M32 and M33 in parallel |
| **M34** | **Regulation with teeth:** gatekeeper designations by region (from market share, users and platform position; EU-style rules from 2022–2024, US cases, then seeded); duties (side-loading, alternative payments, interoperability, fee caps); investigations with visible stages (inquiry, statement of objections, ruling, appeal); fines as a share of revenue; unbundling and break-up orders as the rare last remedy, with warning signs years ahead; rivals regulated by the same rules; the player's lobbying and compliance choices (M22's and M24's) | C, after `m31-done` | about 2026-11-21 | needs platforms to regulate |
| **M35** | **v4 balance and polish:** platform, power-integrator and equipment strategies; 30-year runs; targets for each system; review and playtest fixes | single | after M32–M34 | closes v4 |

Expect a review-fix milestone (Codex review 7) and a playtest-fix milestone as in v3. **Rough size:** 5 milestones in 3 rounds, plus fixes.

## What each system must deliver (targets to make precise in each brief)

- **Platforms:** a platform that reaches critical mass is hard to dislodge (a challenger needs a large, sustained advantage to tip developers); a player with its own store earns platform fees on rivals' apps; a player locked out by a gatekeeper loses a visible share of a category; fee and rule changes follow history to 2025.
- **Power:** by the late 2020s power decides where new data centres and fabs can be built; owning plants lowers and steadies power cost at a capital and risk price; grid queues delay projects by years in congested regions; carbon prices move the cheapest plant type over time.
- **Equipment:** the EUV queue is a real constraint for everyone; the own-tools programme is a long bet that rarely pays before year 20 but transforms the leading edge when it does.
- **Regulation:** most large platforms meet some remedy within the 2020s; break-ups are rare (at most 1 in 10 runs for a dominant player who ignores the warnings, and never without years of visible warning); compliance and good conduct lower the risk.
- **Everything:** history to 2025 unchanged (as M28's §41.8 target 1); a software company's game unchanged except where platform rules apply to its apps; turn time within M30's budget.

## Data needs (v4 research dossier, before each brief)

- **Platforms:** app-store fee history (Apple and Google, the 15% tiers from 2021, regulated changes from 2024); developer and app counts by store over time; share of mobile OS by region; notable removals and disputes; open-source milestones (Android, major open models).
- **Power:** regional wholesale prices (already in M17's data, extend); plant capex per kW and build times by type over 2010–2025; capacity factors; fuel prices; interconnection queue lengths by region; carbon prices by region (EU ETS, others) and their start dates; data-centre power demand history.
- **Equipment:** ASML's EUV and DUV tool generations, dates, prices, throughput and shipments; allocation constraints; export-control dates for tools (M22's data); rival lithography makers (Nikon, Canon, Chinese efforts).
- **Regulation:** EU Digital Markets Act designation and duty dates; major antitrust cases and remedies (Google, Apple, Microsoft, Meta) with dates and fines; app-store rulings; break-up proposals and their outcomes.

## Architecture (ADRs to write with the briefs)

- **ADR-0021, platforms and ecosystems:** the platform as an entity owned by a company (a facility-like record per device family and OS); developers and apps as populations and a market good; network effects as a state update in the market phase; how gatekeeper rules apply to other companies' products.
- **ADR-0022, power as an input everywhere:** power demand from every facility kind and data centre, supply from contracts, owned plants and the grid; where outages and carbon costs post; per-entity books for plants.
- **Streams** in ADR-0013 for platforms (developer choices, gatekeeper decisions), power (outages, carbon path), equipment (allocation, programme results) and regulation (investigations, rulings).

## Open until the briefs

- Which device families get their own OS and store (phones and tablets first; consoles, PCs, cars and headsets later).
- Whether an AI-model platform (a model API with developers on it) is a platform in M31's sense, or stays a product (default: a platform, since that's where the 2020s went).
- Whether power plants can be a subsidiary's business sold to third parties beyond the grid (default: yes, through M16's group).
