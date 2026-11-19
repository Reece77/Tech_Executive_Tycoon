# M44: Defence and government contracts (v5, lane K)

**Goal:** governments become customers. They buy the player's cloud, AI, satellites, chips and devices through tenders: multi-year contracts with clearances, sourcing rules and past performance. Bids and protests decide the awards. Defence work has a cost in brand, staff reactions and export controls, and brings political influence.

**Formulas:** `docs/formulas.md` §57 (all), with §28, §32.4, §32.5, §39, §40, §48, §54, §56 · **ADRs:** 0002, 0003, 0005, 0013 (stream `defence` 69) · **Research:** `docs/v5-research/defence-dossier.md` · **Depends on:** M40 (`m40-done`) · **Lane:** K, alongside M43 (lane L, measuring)

## Reece's decision (2026-11-15)

- **Defence and government contracts** in v5, before M43 closes it.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m44-defence` from `main`. Build from now. **Merge only after `m40-done`,** then merge `main`, re-parent the migration, re-record fixtures with reasons, and re-run every guard. M43 tunes and merges after you.
- **M44 owns:**
  - new `backend/tst/sim/government/` (budgets, tenders, bids, awards, protests, contracts, clearances, sourcing rules, reputation effects);
  - `government.yaml` (new);
  - defence primes as rivals;
  - the Government screen;
  - `tst/balance/m44.py` (new).
- **M44 must not edit:** M40's `space/` or M42's `pharma/` (read them through their interfaces); M43's balance scripts and keys.
- **Shared files:** `incumbents.yaml`, `balance.yaml` (add `government.*`), `docs/formulas.md` (notes in §57 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** A company that never bids must play exactly as before.

## Out of scope

Weapons systems; classified detail; selling to sanctioned states; automating bids (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `government.yaml` from the dossier (budgets by region and area, historical tenders and awards such as JEDI, JWCC and NSSL, sourcing rules and their dates, clearance times, protest statistics, defence primes), with every value cited;
   - `government.*` keys and stream `defence`;
   - migration and data dictionary.
2. **Governments and tenders** (§57.1).
3. **Bidding, awards, protests and delivery** (§57.2).
   - **Hidden-value test:** no rival bid or award draw reaches the API or a prompt.
   - **Property test:** books balance through cost-plus and fixed-price contracts.
4. **Clearances, export rules and sourcing** (§57.3): staff and facility clearances, controlled defence items, bill-of-materials checks against component bans and domestic content.
5. **Reputation and politics** (§57.4), and **rivals** (§57.5).
6. **Screens:**
   - a **Government** screen (tenders by region and area, requirements met, bids, awards, contracts, clearances);
   - M29 unlocks;
   - glossary entries (tender, IDIQ, cost-plus, past performance, protest, facility clearance, ITAR);
   - Explain on an award's score band.
7. **API, CLI, e2e, balance and close-out:**
   - `tst government`;
   - **Playwright:** (a) bid on a cloud tender and win or lose it with a score band, (b) a component ban disqualifies a device bid, (c) defence work triggers a staff reaction event;
   - **a practice save** `pt-defence`: a cloud, AI and satellites group in 2027 with cleared staff;
   - **§57.6 targets** printed and recorded, tuning only `government.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `government.yaml` cites a source for every value.
- [ ] A company that never bids plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No rival bid, award, clearance or seeded draw reaches the API or a prompt (hidden-value test).
- [ ] §57.6 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m44-done`.

## Decisions made

1. **Workspace and branch (2026-11-19).** This session's own clone, on `m44-defence` from main. PR #88 (docs-m44-m43) was merged with a merge commit once its check and e2e were green (rule 9), and main merged into the branch. M40's `space/`, M42's `pharma/` and M43's scripts and keys were not edited; M40's three space categories are named in government.yaml's `space` area and the loader accepts them missing until M40 merges.
2. **Research.** A research agent checked every *(verify)* item; its readings, corrections and what stays unverified are in `docs/v5-research/defence-dossier.md`'s new "Verification (M44)" section. The session's network could not open sipri.org, gao.gov or sec.gov, so SIPRI figures come from SIPRI's own April 2025 Milex workbook (a public mirror) and GAO's from its reports as quoted. Every number in government.yaml is `[value, "TAG:source"]`; the loader refuses an untagged value or an unknown source (`tag_problems`, `test_every_value_is_cited`). Counts and calendar fields on a named tender (`term_years`, `awards`, `from_year`) are structural, cited with the tender's value.
3. **Scale.** Budgets are real (2010 dollars, `cpi`); tenders are at the game's scale (`economy_scale.money`, 0.0849, §54), as M39's markets are.
4. **Rivals are bidders, not new companies.** The defence primes and newer entrants (25 in government.yaml: Lockheed Martin, RTX, Northrop Grumman, General Dynamics, Boeing Defense, L3Harris, BAE Systems, Palantir, Anduril, SpaceX, ULA, Blue Origin, York, Sierra Space, Thales, Airbus Defence and Space, Leonardo, Rheinmetall, MHI, Hanwha Aerospace, Elbit, HAL, Embraer Defense, CETC, CASC) bid from the data, and the hyperscalers, IBM, Intel, Microsoft, Dell and HPE bid as the game's companies (their merit is their best live product's quality). Their awards are published records with no books: their real revenue already includes government work in the incumbents' calibration, and a world where rivals booked awards would change every company's books for a player who never bids (57.6 target 1). Appending 25 incumbents would also have moved every later company id, as M38's and M39's did. M40's SpaceX, once merged, is matched by name (its awards name the game company).
5. **A company that never bids plays exactly as before.** Tenders and published awards are state no other system reads; nothing posts to the ledger, the inbox or a modifier for a company without bids, contracts or clearances. Evidence: `test_never_bidding_plays_exactly_as_before` (identical books and snapshots with and without government.yaml); 57.6 target 1 in `tst/balance/m44.py` (24 months from 2026); M22's software-company test (fixed to run without geopolitics data); golden snapshots unchanged; and M30's nine state-cache runs, re-run with M44's nine new GameState fields left out of the digest, identical to the recorded fixture in every one of their 360 months. With those fields the digest changes from turn 0, so M30's fixture and M45's dynasty fixture are re-recorded (CHANGELOG).
6. **Bids are the player's one-offs.** A bid is an action that takes effect at once (energy, the proposal's cost); no automation owner bids (automating bids is out of scope). Requirements are pass or fail and are checked at the bid (shown) and again at the award (they decide).
7. **Score bands.** The API shows the player's total and terms as 10-point bands and the lowest winner's band; exact scores and every rival bid stay in the engine. Explain's `bid_score` shows the player's banded terms with their weights.
8. **Protests** use GAO's effectiveness rate (relief, corrective action included) as the chance a protest succeeds, and re-compete once; JEDI's record protest holds it until its July 2021 cancellation.
9. **Clearances.** PAC publishes the fastest 90% of cases' days, not medians. The game's median is `median_of_p90` (0.75) x those days plus `sponsor_months` (3: sponsorship and forms before the investigation opens), so Top Secret runs about 16 months in 2018 and 9 in 2024, Secret about 9 and 6. "Never clear" adds discontinued cases to denials (5% and 8%), as 57.6 target 3 needs at least 5% where real DoD denials are about 0.2-2%.
10. **Sourcing reads M22's `made_in`** (plants' and contract makers' countries, chips' foundries'), so a Foxconn device assembled in Shenzhen is 100% China; a hardware product not in production this month cannot show domestic content. ITAR-style control hooks into M22's `sales.access` (one line beside the export rules) and only for a product that has delivered a defence contract in a controlled area.
11. **Reputation** uses existing hooks: brand on consumer lines, the founder's persona (`raise_trait`), influence (`with_influence`), objectors' morale through 23.2's event modifiers, and an engine-queued critical event (`defence_open_letter`, trigger `government`, `government_step`), as M39's incidents do.
12. **Unlock id** 34 (M42 takes 32, M40 33). The Government screen sits under Markets at `products/government`.
13. **Accounts** `4070_revenue_government`, `5300_contract_costs` (cost of revenue), `6990_bids_clearances`.

## Follow-ups

- Automating bids (an automation area with a capture owner), as the brief's out-of-scope note says.
- Rivals' government revenue: booking awards to the game's hyperscalers would need their revenue calibration split first.
- Component bans by named company (Huawei, ZTE parts in a bill of materials) rather than by country of manufacture; Section 889 part B (contractors' own use) and allied 5G bans.
- Re-check the R-tagged figures (RTX, Northrop, Boeing BDS, BAE, L-3 revenues; FY2010 GAO counts; FY2010 federal IT) against primary sources when sipri.org, gao.gov and sec.gov are reachable.
- Classified products as their own variants (a sovereign cloud region) and certifications such as FedRAMP as requirements.
