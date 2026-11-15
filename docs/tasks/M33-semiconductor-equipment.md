# M33: Semiconductor equipment (v4, lane B)

**Goal:** the EUV chokepoint becomes real. ASML is a company with capacity, generations (DUV immersion, low-NA and high-NA EUV), prices and an order queue where the player competes with TSMC, Samsung, Intel and others for slots, under export controls. Late in the game the player can fund its own lithography programme: a decade-long, very expensive bet with prototype tools that start worse and improve, which it can then use or sell.

**Formulas:** `docs/formulas.md` §47 (all), with §21, §38, §39, §41 · **ADRs:** 0002, 0003, 0013 (stream `equipment` 61), 0020 · **Research:** `docs/v4-research/equipment-dossier.md` · **Backlog:** `docs/ideas-backlog.md` ("Semiconductor equipment: lithography and EUV") · **Depends on:** M28r (`m28r-done`), M30 (`m30-done`) · **Lane:** B, alongside M32 (lane A) and M34 (lane C)

## Reece's decisions (2026-11-13)

- **The chokepoint first;** own tools as a late, very expensive research path.

## Lane

- Its own session and branch (`m33-equipment`) from `main`. **Merges second** (after M34, before M32).
- **M33 owns:** new `backend/tst/sim/equipment/` (tool generations, the queue, allocation, prices, the programme, tool sales); `equipment.yaml` (new); ASML, Nikon and Canon as chain companies (data and rules); the `euv_tools` market good's replacement by the queue in `fabs/` (where fab completion and conversion read tool deliveries); the lithography domain in the R&D tree data; the Equipment screen; `tst/balance/m33.py` (new).
- **M33 must not edit:** M32's `power/` (fab power costs are M32's line) or M34's regulation code; M31's platforms; M36's family code.
- **Shared files:** `balance.yaml` (add `equipment.*`), `chain_companies.yaml` (M32 adds power producers: keep both sides), `tech_frontier.yaml` (add the lithography domain), `docs/formulas.md` (notes in §47 only), CHANGELOG, data dictionary, ADR-0013.
- **CLAUDE.md §9's decision rules apply.** §47.5 target 1 (history holds) is the guard, with M21's §38.5 and M22's §39.4 targets re-run.

## Out of scope

Other equipment (deposition, etch, metrology) beyond a note in the data; masks and photoresists as goods (follow-up); automating tool orders (a follow-up for M27b's fabs area).

## Sub-tasks (commit after each)

1. **Research and data:** `equipment.yaml` from the dossier (generations, first shipments, prices, throughput, uptime, shipments a year to 2025, rival DUV makers), every value cited; `equipment.*` keys; stream `equipment`; migration and data dictionary.
2. **ASML and the generations** (§47.1): suppliers as chain companies, capacity from the data then their December rule.
3. **The queue** (§47.2): December orders, quarterly allocation by order and weight, prepayment as a one-off, prices with scarcity, fab completion and conversion waiting for tools. **Seeded test** of allocation; **test:** history's shipments to 2025.
4. **Controls on tools** (§47.3): M22's rules on the queue; servicing bans. **Test:** a banned buyer gets no deliveries.
5. **The lithography programme** (§47.4): the domain and its three generations, hidden success and overrun draws, prototype tools improving with use, own fabs equipped from them, sales to rival foundries, ASML's response. **Hidden-value test:** no success draw, overrun or allocation weight in the API or a prompt.
6. **Screens:** an **Equipment** screen (generations, prices, the player's orders and queue place as a range, deliveries, controls, the programme's progress), fab order and conversion screens showing tool waits, M29 unlocks (Equipment with a fab), glossary (EUV, high-NA, throughput, allocation) and Explain on a queue wait.
7. **API, CLI, e2e, balance and close-out:** `tst equipment`; Playwright: (a) order high-NA tools and see the queue range, (b) prepay to move up, (c) start the lithography programme and see its first stage; a practice save `pt-litho` (a stage-5 group in 2030 with two fabs and research capacity); **§47.5 targets** printed and recorded, tuning only `equipment.*` (rule 1); re-run every earlier guard (M21, M22, M23b, M28 especially); CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `equipment.yaml` cites a source for every value; shipments, prices, generations and dated controls to 2025 follow it (tests).
- [ ] Every earlier guard unchanged (M21 §38.5 and M22 §39.4 especially).
- [ ] No allocation weight, programme draw or overrun reaches the API or a prompt (hidden-value test).
- [ ] §47.5 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m33-done`.

## Manual check (Reece, after merge)

Load `pt-litho`. Order high-NA tools and look at your queue place, then prepay and look again. Start the lithography programme and leave it running for a decade.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
