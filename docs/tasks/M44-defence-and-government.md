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

(filled in by the agent)

## Follow-ups

(filled in by the agent)
