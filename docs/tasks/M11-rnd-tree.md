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

## Design for v3 (ADR-0020)

Leads, projects and licences belong to a `company_id`; use `player_companies(state)` wherever "the player" is meant. Keep domains as data, so v3 can add process and materials domains (fabs and refining) without code changes.

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

Engineering and design gaps the spec left open (also in `docs/formulas.md` 21.10):

- **Baseline and thresholds.** Baselines accrue monthly (`per_year / 12`); an era's threshold reads the baseline at the end of its historical month, so both 21.9 era examples hold exactly (43.5; 24 in January 2016).
- **Base growth lives in `eras.yaml`.** The lane rule keeps `categories.yaml` untouched, so `eras.yaml` `base_growth` replaces its growth (for demand, startups' founding rate and the API) for AI models, consumer apps, developer tools and fintech; AI's M8 `growth_by_year` is no longer read. The non-AI categories needed this too: with the 21.4 boosts on unchanged growth, consumer apps' January 2020 demand would be 39% above before M11 (target 1 allows 10%). Their base growth is lowered until the era's boost has run (consumer apps and developer tools to 2020, fintech to 2021), then returns to `categories.yaml`'s rate. Zero trust (2020) and AI agents (2025) arrive after the tuned decade and add growth. Boosts reach every region.
- **The hook's signature.** `tech_factor(state, company_id, category, balance, data)` in `tst.sim.research.levels` (the sim takes balance and data as arguments everywhere); `lead(state, company_id, domain)` there is M12a's stable read. The package `__init__` stays empty of imports because `data_models` imports `research.data`.
- **Researchers** are a unit's direct members in builder roles (and the founder); seat, structure, tag and unit event-modifier factors apply as for builders. A unit with an active project cannot be assigned to a product and the reverse; the company root cannot research.
- **Budget** NULL = full funding; setting a budget is free (`rnd.budget_energy` 0), like a marketing budget.
- **Licensing.** The licensee can reach at most the licensor's lead minus the margin; the price uses the licensee's ARR and is nominal (no inflation in the game); licensing in is R&D (6500) for the buyer and licence revenue (4100) for the seller. Rivals accept any licence out; royalties post in phase 5 on the licensee's booked revenue in the domain's categories. Rival-initiated licensing from the player is not built (follow-up).
- **Rivals' research** is one action at a time, a unit-less project for 6 months; candidates come after v1's and M9's so their noise draws are unchanged; personality weights sit in `rnd.rival.weights` (only `rnd.*` may be added). The builder pool's +10% is returned when the action ends.
- **What the API shows.** A rival's lead range is offset by a seeded draw (stream `lead_reveal`, lane A's reserved id 25, now in ADR-0013) so its midpoint is not the true lead; licence limits on the screen come from the range's low end; refusals for too many points name no number. Projects show estimated lead gained a month from displayed skills, not `output` (the 11.13 hidden-name guard flags it).
- **Research triggers' strengths** are in `events.trigger` (it must list every trigger), not `rnd.*`.
- **Existing saves** get past eras recorded as arrived on schedule (migration `0028_research`).
- **`player_companies(state)`** added to `tst.sim.state` (ADR-0020).
- **Tuning (2026-11-02), `rnd.*` only:**
  - `rnd.rival.era_bonus` 0.3 to **0.15**: at 0.3, incumbents researching near era dates moved T2 from steady 6 to steady 7 of 10 (a guard that passes on main); off entirely it returns to 6, at 0.2 it is steady 5, frugal 5.
  - `rnd.rival.need_span` 15 to **30**: rivals chased each other's noise-started research into early eras on 60% of do-nothing seeds (target 3b, at most 15%).
  - `rnd.rate` 0.25 to **0.4**, `rnd.cap_per_point` 0.004 to **0.010**, `rnd.feature_per_point` 0.002 to **0.005** (target 2: at 21.2's values research raised quality 6-12 points but median ARR only 1.03-1.04x).
  - `rnd.license.price_per_point_cents` $150,000 to **$24,000** (target 5: at $150,000 licensing 15 points cost 2.3x researching them).
  - The 21.9 worked examples test the formulas at 21.9's keys and also at the tuned ones.
- **Target 2's measure.** The fork is steady's first month at stage 2's ARR gate ($1M): steady reaches stage 2 by its seed round at month 4-6 with no revenue, and a six-person unit then bankrupts it on every seed. The unit is kept at six (a researcher who leaves is replaced). "Net of the research cost" subtracts 12 x the final month's budget and the researchers' employment cost; the ratio is of medians (m8 and m10c's convention).
- **Target 3b** runs do-nothing games for 200 months (to the AI agents era); "rivals pull an era more than 6 months early" counts any era a rival caused more than 6 months early.

## Values (2026-11-02)

| Target | Value | Band | Result |
| --- | --- | --- | --- |
| 21.8 target 1: AI demand January 2024 | 350x January 2010 (M8 359x) | +-10% | pass |
| 21.8 target 1: other categories, January 2020 | 1.000 (b2b, dev tools, consumer apps, cybersecurity), 0.944 (fintech) | +-10% | pass |
| 21.8 target 2: research / steady median ARR net; quality | 1.11 (gross 1.13); +18.7 points | >= 1.10; >= 5 | pass |
| 21.8 target 3: AI lab brings Transformers before 2017 | 10/10 (months 54-58, about 2.5 years early) | >= 5 | pass |
| 21.8 target 3: rivals pull an era > 6 months early, do-nothing | 0% | <= 15% | pass |
| 21.8 target 4: a lead of 30 after 46 months | 14.95 | 14-16 | pass |
| 21.8 target 5: licensing 15 points / researching them | 0.67 | <= 0.7 | pass |

## Follow-ups

- **Research may be too strong for M15.** With the tuned keys a six-person software-platform unit lifts steady's quality by about 19 points and its lead runs past 50; check a research-heavy strategy against T2 in M15 and revisit `rnd.cap_per_point` and `rnd.rate` there.
- **21.2 and 21.5's numbers in the spec** (0.004, 0.002, 0.25, $150,000) differ from the tuned keys; update the spec text when the design doc is next exported.
- **Rivals licensing in from the player** ("or the player, for rivals", 21.5) is not built: rivals never ask. Add a rival `license_in` action if the playtest wants it.
- **Rival startups never research** (21.6, out of scope); M12b's chip and device domains research now but feed nothing.
- **The `output` hidden-name guard** blocks showing a project's output (21.7 allows it); the screen shows estimated lead gained a month instead. Decide whether research output should be visible.
- **Long-run growth.** After 2030 every era's boost has ended; AI models grow 25% a year from 2030 as before. A 30-year campaign may want later eras (M15).
