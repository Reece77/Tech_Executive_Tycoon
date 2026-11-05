# ADR-0019: v2 scope decisions

- Status: Accepted
- Date: 2026-10-30
- Spec sections: §2, §3, §6, §8, §10, §17

## Context

The spec leaves v2's milestones "defined at v1 retrospective" (§17) and leaves several scope questions open. Reece answered them on 2026-10-29 and 2026-10-30, so the v2 roadmap (`docs/v2-roadmap.md`) could be drafted while v1 was finishing.

## Decision

1. **Order.** v2 starts with divisions, executive seats and new software markets (M8). Named cities and regions come next (M9), alongside capital and macro (M10).
2. **Facilities are simplified.** A facility (data centre, assembly plant, and later fabs, refineries and mines) has capacity, utilization, inputs, output quality, operating cost and staff, and is sourced by spot purchase, contract or ownership (spec §8). There are no Capitalism Lab unit layouts inside facilities.
3. **Cities.** ADR-0011's "named cities with offices in v2" comes in the milestone after divisions, so that hiring, wages and demand by region are in place before R&D, hardware and the IPO.
4. **CEO and Chair.** Appointing a CEO and stepping up to Chair (spec §3) is built with the IPO milestone.
5. **Personal stock trading** is v3 or later.
6. **Sandbox and the company score** are v2. They are planned for M15 unless the v1 retrospective moves them.
7. **R&D has era milestones** (2026-10-31): domain levels and projects underneath, plus named market-changing technologies that arrive on their historical date unless a company researches them first, accelerating that market and giving the first mover a head start.
8. **Factories are allowed from the start** (2026-10-31), alongside contract manufacturing. An early factory is likely unprofitable; spare capacity can be sold to other companies as contract manufacturing.
9. **Supply shocks follow history, then are seeded** (2026-10-31), like the macro layer (M10): component and GPU prices and allocation follow 2010–2025, then seeded shocks.
10. **The IPO is an event chain** (2026-10-31): hire banks, file, a 3–4 month roadshow of events with choices (pricing and how much to sell), then a listing day whose pop or flop follows macro and growth.
11. **Public life runs on earnings** (2026-10-31): the player sets quarterly guidance; beats and misses move the share price; analysts and activist investors react; a falling price raises board pressure and takeover risk.
12. **Chair and CEO** (2026-10-31): when the founder steps up to Chair, the appointed CEO (a person with stats) makes routine operating decisions each month, like a super-delegate. The founder keeps strategy (capital, M&A, executive appointments) and can override the CEO at an energy cost.
13. **Fabless chips sell to a market and to yourself** (2026-10-31): chips sell in a chip market to rivals' devices and servers, and go into the player's own devices and data centres at lower cost; foundry slots are bought from TSMC and others and are scarce in shortages.
14. **Parallel lanes.** v2 pairs milestones whose systems are separate and builds each pair in two Claude Code sessions, under the lane rules in `docs/v2-roadmap.md`.
15. **Future eras are seeded within public windows** (Reece, 2026-11-02): after 2025, eras have a published window (for example 2026–2028) and a scheduled month drawn from the seed and never shown; research can still pull one forward. M12b adds the first two (chiplets, edge AI); M15 extends the list to 2039.
16. **Acquisitions** (Reece, 2026-11-05): any company can be bought (startups, private incumbents, listed rivals by friendly offer or hostile tender); after each deal the player chooses to keep it as a brand or integrate it; antitrust uses a market-share test. Accepting a bid for the player's company ends the game with an exit.

## Consequences

- Each v2 brief names its lane, the folders it owns, its merge order and its reserved RNG stream ids.
- Facility formulas stay small enough to tune with the balance runner. Depth comes from sourcing choices and supply shocks rather than layout.
- CLAUDE.md §3's v2 list (divisions, IPO, hardware, R&D tree) becomes in scope only through the brief that names each system.

## Alternatives considered

- **Capitalism Lab unit layouts inside facilities:** much deeper, but would roughly double v2's work, and the game's identity is people and structure.
- **One global market until late v2:** simpler, but leaves the growth ceiling in place and puts hiring by city after the systems that depend on it.
- **CEO step-up with divisions:** possible, but stepping back fits public-company life better.
