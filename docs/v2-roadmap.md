# v2 roadmap: Scale-up

**Status: DRAFT (2026-10-30).** Written during M7 so v2 can start when v1 closes. It is finalized at the v1 retrospective, after Reece's 10-year playtest (spec §17: "M8 to M12: defined at v1 retrospective"). Scope decisions are recorded in ADR-0019.

## What v2 is for

The spec's v2 fantasy is a multi-division tech company in the public markets (§2). After M7a, v1 companies level off at about $45–57M ARR because they have only one market per category and nowhere to grow next. v2 gives them somewhere to grow:
- more markets: new categories and regions;
- better products: the R&D tree;
- products further up the supply chain: cloud, hardware and fabless chips;
- capital at scale: later rounds, debt, an IPO and M&A.

It also gives the 30-year campaign something to do after year 10.

## Milestones and lanes

v2 runs in two lanes where the systems are separate (Reece, 2026-10-29). Each lane gets its own Claude Code session, git worktree and branch.

| # | Milestone | Lane | Depends on | Size (compared with v1) |
| --- | --- | --- | --- | --- |
| M8 | **Divisions, executives and new markets.** Division units (stage 3) with a president, a division P&L and shared-service charges; executive seats (COO, CFO, CTO, CPO, CMO, CRO) with vacancy penalties and function bonuses; coordination cost; two new software categories, Fintech and AI models and inference (compute bought at a market price); the v2 API contracts the later lanes build on | single | v1 done | large (M5-sized) |
| M9 | **Cities and regions.** The seven regions as markets with their own demand by segment; named cities with offices (lease, capacity, cost); hiring pools and wages by city; launching a product in a region; rivals' regional presence; remote work across cities | A | M8 | large |
| M10 | **Capital and macro.** Series C and D, venture debt and bank loans with covenants, plus the macro layer (interest rates, venture climate, AI compute cycle, consumer confidence) replacing v1's yearly funding climate | B | M8 | medium |
| M11 | **R&D tree.** Domain levels 1–100 (software platform, AI, infrastructure, chip design, devices); research projects that cost researcher-months and money; levels raise products' quality ceilings; licensing in and out; rivals research; breakthroughs and dead ends as events. **Era milestones** (Reece, 2026-10-31): named, market-changing technologies (for example cloud-native, mobile-first, deep learning, transformers, large language models) that arrive on their historical date unless a company researches them first; the first to reach one pulls that market's acceleration forward and gets a head-start window | A | M9 | large |
| M12a | **Cloud and data centres.** Simplified facilities (capacity, utilization, inputs, output quality, operating cost, staff) with spot, contract or own sourcing: data centres and GPU procurement, owned compute for your own products, and the Cloud and GPU hosting category. Component and GPU prices with supply shocks that follow history to 2025 (the 2021 chip shortage, the 2023 GPU crunch), then seeded (Reece, 2026-10-31) | B | M10 | large |
| M12b | **Hardware and fabless chips.** Devices and servers built by a contract manufacturer per unit, or in your own assembly plant (Reece: both allowed; a factory is likely unprofitable early, and spare capacity can be sold to other companies as contract manufacturing); fabless chips with foundry slots bought from rival foundries | A | M11, M12a | large |
| M13 | **IPO and public company (stage 4).** Bankers and a roadshow event chain, share price from fundamentals plus sentiment, analysts, quarterly earnings and guidance, buybacks and dividends, activist investors; appointing a CEO and stepping up to Chair | B | M12a | large |
| M14 | **M&A.** Acquiring rivals and startups for cash (and for stock after an IPO); valuation, integration risk, culture clash and key-talent flight; technology and products that come with them | single | M12b, M13 | medium |
| M15 | **v2 balance and polish.** v2 strategies (research-heavy, acquirer, a partial vertical integrator), 30-year runs, v2 balance targets, History and tooltips for the new systems, Reece's playtests | single | all | medium |

**Order of work:** M8 alone → M9 alongside M10 → M11 alongside M12a → M12b alongside M13 → M14 alone → M15 alone. After the M9/M10 pair, three short single-lane milestones from Reece's playtest (2026-11-01) run before M11 and M12a: M10r (Codex review 2 fixes), M10b (feel fixes), M10c (executives with authority), M10d (balance checkpoint).

**Rough effort:** at v1's pace (a v1 milestone took Claude Code about one to two working sessions), v2 is roughly 10–14 sessions. Running two lanes takes off about a third of the calendar time, not the work. Reece's playtests set the real pace: after M9/M10, after M12 and after M15.

## Lane rules (for every paired milestone)

- **Files.** Each brief lists the folders its lane owns. Shared files (`balance.yaml`, `CHANGELOG.md`, `docs/formulas.md`, `docs/data-dictionary.md`) keep both sides on merge.
- **Migrations.** Each lane writes its own. The lane that merges second re-parents its unmerged migrations onto `main`'s new head before merging. A migration that isn't on `main` hasn't been applied to any save, so this doesn't break the "never edit an applied migration" rule.
- **Golden snapshots.** Only the lane that merges second regenerates them, with both lanes' reasons in CHANGELOG.
- **Balance.** The lane that merges second re-runs `make balance` and the guards on the combined code. If a target moves, it reports rather than tunes the other lane's keys.
- **Merge order** is fixed in each pair's briefs; usually the smaller milestone merges first (M10 before M9).
- **RNG streams.** New stream ids are reserved per lane in ADR-0013's table before work starts, so the two lanes can't collide.

## Decided for v2 (ADR-0019)

- **Facilities are simplified,** not Capitalism Lab's unit layouts (Reece, 2026-10-30).
- **Named cities come early,** in the milestone right after divisions (Reece).
- **CEO appointment and Chair step-up** come with the IPO milestone (Reece).
- **Personal stock trading** is v3 or later (Reece).
- **Sandbox mode and the company score** are in v2 (Reece, 2026-10-30), in M15 unless the retrospective moves them.
- **v2 starts with divisions and new markets** (Reece, 2026-10-30).

## Design settled ahead of the briefs

M12b and M13 have their design decisions recorded (ADR-0019 §8, §10–§13). Their full briefs and formulas are written when M11 and M12a (for M12b) and M10 (for M13) are built, as every brief has been, so they match the code as it stands. M14 and M15 wait for M12b and M13.

## Open until the v1 retrospective

- What Reece's 10-year playtest and the M7c agent report change, especially the speed of the early game and staff attrition.
- Whether Sandbox and the company score come earlier than M15.
- Exact stage gates for v2 (spec §3: stage 3 at Series B or $20M ARR, stage 4 at IPO).
- Which real companies join the rival roster for the new categories (for example Stripe, PayPal and Square for Fintech; Google and OpenAI from 2015 for AI; AWS for cloud; Apple, Dell and Foxconn for hardware; NVIDIA, AMD, Intel and TSMC for chips).
