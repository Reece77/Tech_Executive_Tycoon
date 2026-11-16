# Roadmap after v3

**Status: AGREED (Reece, 2026-11-09).** The product manager's plan from v3's close to v5. Detailed plans live in `docs/v2-roadmap.md` (done), `docs/v3-outline.md` (v3) and `docs/ideas-backlog.md` (everything not yet scheduled).

## Where the game stands (2026-11-09)

v1, v2 and v3 are built: a founder-to-conglomerate game with people, products, research, cloud, hardware, chips, capital markets, acquisitions, a holding company, a mineral chain from exploration to fabs, geopolitics, the founder's personal life and investing, and quality-of-life tools. The engineering is healthy: deterministic, exact money, five outside reviews' fixes, and CI guarding `main` with `check` and `e2e`.

**Three product risks, which matter more than new content:**
1. **The world is shallower than the player.** Foundries, refiners and miners are data-driven; rivals don't form groups; rivals weren't under export controls (fixed in M23a). Capitalism Lab works because rivals play the same game.
2. **Nobody has played the full game.** Every playtest so far used constructed saves; balance has been tuned against scripts.
3. **Complexity has outgrown the experience.** About 40 screens, many new concepts, and a PowerShell setup to start the game.

## Decisions (Reece, 2026-11-09)

- **v3.5 comes before v4.**
- **Automate anything:** every area gets an "auto-manage" switch, Football Manager-style, so the player plays at whatever depth they like. "That is what makes FM fun."
- **Reece plays one full 30-year campaign** (2010–2039, with Continue until) after M23, before v4 is built.

## Phase 1: close v3

| Step | What |
| --- | --- |
| Playtest 5 and Codex review 5 | in parallel, now |
| **M23a, v3 integration** (lane A) | fabs, mines and refineries supply the whole group; rivals under export controls; choosing a facility's country; tariffs in transfer prices; Codex review 5's fixes; Reece's playtest 5 notes |
| **M23b, v3 balance** (lane B) | 30-year runs across the full chain; carried known misses (V3.ai, V5's launch cells, M16's T3 and T4); new strategies (a full vertical integrator); carried follow-ups |
| v3 retrospective | including what to cut or simplify |

## Phase 2: v3.5, "a game you can actually play"

**Reece's decisions (2026-11-11):** every area can be automated, but one-off decisions need his approval; each delegate has a money limit; a monthly digest; delegates can be bad, so staff matter.

| Milestone | Lane | What | Brief |
| --- | --- | --- | --- |
| **M27a, automation everywhere** | A | areas and owners (seat holders, the CEO, area leads, subsidiary CEOs); money limits and one-offs that always need approval; quality from true skills and a workload in energy; routine events; the monthly digest; the Automation screen (formulas §40) | `docs/tasks/M27a-automation-everywhere.md` |
| **M27b, automation for the chain** | A, after M27a | device production, supply, exploration, mines and refineries, fabs, government affairs, corporate development (§40.7) | `docs/tasks/M27b-automation-for-the-chain.md` (revised 2026-11-14) |
| **M28, a living world** | B, merges last | chain companies as companies, supply-driven prices from 2026, rival groups and bids, China's catch-up, regional cycles, World news and company pages (§41) | `docs/tasks/M28-a-living-world.md` |
| **M29, onboarding, navigation and the launcher** | C, merges first | double-click launcher, progressive unlocking, guided first year, What next, inbox tabs, grouped navigation and a command palette (§42) | `docs/tasks/M29-onboarding-navigation-and-launcher.md` |
| **M30, performance at scale** | after M28 | faster 2039 turns, Holiday, saves and screens with identical results | `docs/tasks/M30-performance-at-scale.md` |
| **Reece's 30-year campaign** | — | one game, 2010–2039, started after `m23b-done` on `main`; saves upgrade as v3.5 merges, and its notes shape v3.5's last fixes and v4 | campaign log page |

M27a, M28 and M29 start together once `m23b-done` exists; Codex review 6 (all of v3) runs alongside them.

**Status (2026-11-14):** M29, M27a and M28 merged. M28r (an M21 guard after M28), M27b, M30 and v4's M31 run next, in parallel.

**Product manager rulings (2026-11-14):** M28's §41.8 target 2 ("markets respond", band 15–40%) read a 12% median drop, because rivals respond by building less and the price recovers by 2032–33. Accepted as met in spirit and recorded; the band stays for v4's power and platform work to revisit.

## Phase 3: v4, power, platforms and regulation

**Reece's decisions (2026-11-13, "defaults"):** an own app store and developer ecosystem, with rivals' stores as competitors and gatekeepers; power contracts and owned plants (from stage 4); break-ups possible but rare, visible and warned years ahead; EUV first as a chokepoint, own tools as a late, very expensive research path. Outline: `docs/v4-outline.md`.

| Milestone | Lane | Starts |
| --- | --- | --- |
| M31, platforms and ecosystems | C | after `m27a-done` (about 2026-11-17) |
| M32, power and owned plants | A, merges last | now (brief `docs/tasks/M32-power-and-owned-plants.md`, formulas §46) |
| M33, semiconductor equipment (EUV) | B, merges second | now (brief `docs/tasks/M33-semiconductor-equipment.md`, formulas §47) |
| M34, regulation with teeth | C, merges first | now (brief `docs/tasks/M34-regulation-with-teeth.md`, formulas §48) |
| M35a, v4 polish and engineering | A, merges first | now (brief `docs/tasks/M35a-v4-polish-and-engineering.md`) |
| M35b, v4 balance | B, closes v4 | now; tunes after `m35a-done` (brief `docs/tasks/M35b-v4-balance.md`) |

## Phase 4: v5, the dynasty and new industries

**Reece's decisions (2026-11-14, "defaults", plus pharmaceuticals):** play the heir, with the old founder as board adviser; an optional dynasty mode to 2069; electric vehicles and robotics first, then space, medical devices and pharmaceuticals; realistic approval stages. Outline: `docs/v5-outline.md`.

| Milestone | Starts |
| --- | --- |
| M36, family and succession | now, as a fourth lane (brief `docs/tasks/M36-family-and-succession.md`, formulas §45) |
| M37, dynasty mode (the second 30 years) | after v4 |
| M38, electric vehicles | now, lane C beside M35; merges after `m35b-done` (brief `docs/tasks/M38-electric-vehicles.md`, formulas §49) |
| M39, robotics | after M32 |
| M40, space and satellites | after M32 |
| M41, medical devices | now, lane D; merges after `m35b-done` and M38 (brief `docs/tasks/M41-medical-devices.md`, formulas §50) |
| M42, pharmaceuticals | after M41 |
| M43, v5 balance and polish | last; closes v5 |

## Process

- **Codex review every 5–6 milestones**, with findings folded into the next balance or integration milestone rather than a separate fix milestone.
- **Every second playtest on a played save,** not only constructed ones.
- **Before scheduling anything, ask whether something can be removed or automated instead.**
- **Lanes:** up to three at once, with CLAUDE.md §9's decision rules; one named session merges each milestone.
