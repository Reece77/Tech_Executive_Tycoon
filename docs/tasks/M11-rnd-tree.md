# M11: R&D tree and era milestones (lane A)

**Goal:** technology becomes something a company can push. Research units raise domain levels above the world's baseline, which lifts their products' quality caps and features. Leads decay unless they're maintained, can be licensed, and leak when researchers leave. Named era milestones (mobile-first, deep learning, transformers, large language models and others) arrive on their historical dates and accelerate their markets. A company that researches far enough ahead can pull one forward and take a head-start window.

**Spec sections:** §7.3 (technology tree), §9 · **ADRs:** 0002, 0005, 0007, 0013 (streams `research` 23, `rival_research` 24, reserved), 0019 (§7 era milestones) · **Formulas:** `docs/formulas.md` §21 (all), with §11.3–§11.5, §15 and §18 · **Wireframes:** `docs/wireframes.md` (M11 screens) and `docs/wireframes/source/Research.dc.html` · **Roadmap:** `docs/v2-roadmap.md` (lane rules) · **Depends on:** M10d (`m10d-done`)

## Lane

- **Lane A.** It runs at the same time as M12a (lane B) in its own session and branch (`m11-rnd-tree`).
- **Merge order: M11 merges first.** M12a then merges `main`, re-parents its migrations and regenerates golden snapshots.
- **M11 owns:**
  - new `backend/tst/sim/research/` (levels, projects, eras, licensing, rival research);
  - `backend/data/tech_frontier.yaml`, `eras.yaml` and the research event templates;
  - the AI `growth_by_year` replacement (base growth plus era boosts) in the market code;
  - the rivals' `research` action;
  - screens: a new **Research** screen, the era timeline on Market, and the tech factor in the product's quality breakdown.
- **M11 must not edit:** compute, hosting, facilities, `accounts.yaml` or the Cloud hosting category. Those belong to M12a.
- **Shared files:**
  - `balance.yaml`: add only `rnd.*`;
  - `categories.yaml`: none (domain weights live in `tech_frontier.yaml`);
  - `docs/formulas.md`: notes in §21 only;
  - `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **Shared hook:** `research.tech_factor(state, company_id, category)`, called once in the product quality cap and feature gain, and once in rivals' quality target. M12a's Cloud hosting features read `research.lead(state, company_id, "infrastructure")`; expose that function and keep its signature stable.

## Out of scope

Chip and device products (M12b; their domains research now but feed nothing until then). Patents and lawsuits. Research for rival startups. Government grants.

## Sub-tasks (commit after each)

1. **Data and formula tests:**
   - `tech_frontier.yaml` (baselines, category weights, research skills, budgets), `eras.yaml` (the §21.4 table with thresholds and boosts), `rnd.*` keys;
   - research event templates (`research_breakthrough`, `research_dead_end`, era-arrival news);
   - every §21.9 worked example as a unit test;
   - stream rows moved into ADR-0013's main table.
2. **Levels and the tech factor** (§21.1, §21.2):
   - baselines, leads and decay; the factor on the quality cap and features for products and rivals;
   - **test:** a company with no research has a factor of exactly 1, and golden snapshots are unchanged by this sub-task.
3. **Projects** (§21.3):
   - the start and stop actions; unit assignment that excludes products; output, budget and progress;
   - breakthroughs and dead ends on stream `research` as event triggers;
   - migration and data dictionary;
   - **tests:** progress, underfunding, a seeded breakthrough test, and that one unit can't be on a product and a project at once.
4. **Era milestones** (§21.4):
   - arrival by date or by threshold; the baseline +5; boosts in the market code;
   - the AI growth curve refitted as base growth plus three era boosts;
   - the first-mover window; History entries and news;
   - **tests:** historical arrival on every seed with no research; early arrival when a lead reaches the threshold; the window's effects and expiry; the §21.8 target 1 demand check.
5. **Licensing and leaks; rivals research** (§21.5, §21.6): licence in and out with royalties, the leak on a researcher's departure, the rival `research` action on stream `rival_research`. Tests for each.
6. **API, CLI and screens** (per the wireframes):
   - **Research screen:** domain levels with baseline and lead, projects (team, output, budget, progress, months to the next threshold), licences, and rivals' levels as ranges.
   - **Market:** the era timeline (arrived and coming, with thresholds and who caused each).
   - **Product quality breakdown:** the tech factor.
   - **Supporting work:** glossary entries and driver breakdowns for the new numbers; History entries.
   - **CLI:** `tst research`, `tst project --unit --domain`, `tst license --from --domain --points`.
   - **Hidden values:** extend the hidden-value test to rivals' exact leads.
7. **Balance, golden snapshots and e2e:**
   - The §21.8 targets, printed and recorded. Tune only `rnd.*`, era boosts and `tech_frontier.yaml`.
   - Golden snapshots regenerated if the refitted AI curve or rivals' research moves them, with the reason in CHANGELOG.
   - **Playwright:**
     - (a) assign a unit to an AI project and see the lead grow;
     - (b) a scripted lead past the Transformers threshold triggers the era early, with the news and the first-mover note;
     - (c) license in from a rival and see the level change.
   - **Close-out:** CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Every §21.9 worked example passes as a test.
- [ ] A company that never researches has a tech factor of exactly 1; with eras on their historical dates, demand matches §21.8 target 1.
- [ ] Projects, decay, breakthroughs, dead ends, licensing, leaks and rival research work as specified.
- [ ] Eras arrive on time or early by threshold; the first-mover window applies and expires.
- [ ] No API response shows a rival's exact lead (planted-value test).
- [ ] §21.8 targets 2–5 met (printed, values recorded); earlier targets unchanged.
- [ ] `make check` green (recorded xfails unchanged); `make e2e` passes; merged first in the pair per CLAUDE.md §6 with the trailer `Milestone-Tag: m11-done`.

## Manual check (Reece, after merge)

Start an AI-focused game. Build a research unit early, push for Transformers, and see whether pulling it forward feels like a real advantage.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
