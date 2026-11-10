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

| Milestone (draft) | What |
| --- | --- |
| **Automation everywhere** | an auto-manage switch for every area (hiring, products, pricing, research, supply and offtake, facilities, finance, group mandates, PR), run by the relevant executive or department with the player's guardrails; FM-style "delegate to staff" with reports and override; the inbox only surfaces what the player kept for themselves |
| **A living world** | rival miners, refiners and foundries as full companies; incumbents form groups, spin off and buy each other; Chinese chipmakers rise under the export rules; rivals use the same systems as the player |
| **Onboarding and the UI pulled together** | progressive unlocking (systems appear as the company reaches them), a guided first year, sensible defaults, one consistent dashboard, an inbox that triages, navigation for 40 screens |
| **A one-click launcher and performance at scale** | double-click to play (no PowerShell); a 2039 group with the full chain under a second a turn; save size |
| **Reece's 30-year campaign** | one game, 2010–2039: the real acceptance test for v1–v3; its notes shape v3.5's last fixes and v4 |

## Phase 3: v4, power, platforms and regulation

Regional power markets and owning power plants; platforms and ecosystems (app stores, developer ecosystems, lock-in, standards); regulation with teeth (unbundling, gatekeeper rules); and the **semiconductor equipment lane** (lithography and EUV) alongside. Details in `docs/ideas-backlog.md`.

## Phase 4: v5, the dynasty and new industries

The founder's life part 3 (family, heirs, succession, playing on as the next generation); electric vehicles, robotics, space and medical devices on the player's chain.

## Process

- **Codex review every 5–6 milestones**, with findings folded into the next balance or integration milestone rather than a separate fix milestone.
- **Every second playtest on a played save,** not only constructed ones.
- **Before scheduling anything, ask whether something can be removed or automated instead.**
- **Lanes:** up to three at once, with CLAUDE.md §9's decision rules; one named session merges each milestone.
