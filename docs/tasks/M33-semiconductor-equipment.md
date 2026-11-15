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

1. **Shipments are ASML's "units recognised"** (its 20-F basis for every year 2010-2025), so one series runs throughout; shipped and recognised differ in a year (2023: 42 shipped, 53 recognised). Where a 20-F table was read only as a summary, or a figure comes from an aggregator (2025's 47 NXE + 3 EXE; Tom's Hardware reports 48 EUV shipped), the value is tagged R. nodes.yaml's M21 series (2017: 10, 2024: 44, 2025: 48) is left as it was: the queue reads equipment.yaml.
2. **Prices** are ASP = technology sales / units (20-F) at the ECB's annual EUR/USD rate (2019: EUR 107.7M = $120.5M, matching nodes.yaml's $120M c.2020); 2024's NXE ASP removes 2 EXE at EUR 350M (R). High-NA $380M (2024, R) and $400M (2025, R).
3. **Only EUV is queued.** DUV immersion is shown (shipments, prices, controls) but its cost stays in a fab's capex as before: DUV supply never bound the game's fabs, and queueing it would move M21's and M23b's guards.
4. **Allocation by place, not share** (47.2's "queue order x buyer weight"): the first build shared each quarter in proportion to weight x tools, and M21's test showed a 50-tool order from a new buyer outrunning TSMC. An order's place is its month moved up by the buyer's delivery history (`history_months` 12 at 20 tools in 5 years) and a prepayment (`prepay_months` 9), with a seeded ±0.5-month tie-break. Rivals' December orders top up to 1.1 x next year's capacity x their share.
5. **Target 2's measure:** a buyer's median wait is the median over its tools of the months from order to delivery, for a 25,000-start fab's 13 low-NA tools ordered in January, April, July, October and December of 2027-2032 (seeds 1-3). Months to the last tool: new 22, long-standing 12 (also within the bands).
6. **A fab's tool cost stays inside its capex**; from 2026 the order's price above or below list (scarcity, ASML's response) and a prepayment change the capex, and tools from stock reduce it, so 2010-2025 builds cost exactly what they did.
7. **The queue's dated rules end with the history**: the Netherlands' 2019 EUV practice (Reuters 2020), high-NA never licensed to China, January 2024's DUV revocation. From 2026 M22's rules on `euv_tools` (December 2024's ban, seeded tightening, détentes) carry the bans, so they can loosen.
8. **M21's balance script sites East Asian EUV fabs in Taiwan** (CLAUDE.md 9 rule 2): its fabs defaulted to China, where EUV tools have not shipped since July 2019; a sensible player builds in Taiwan. `m21.make_ready` (tools waived) cancels the fab's order. M21's unit and API tests quote those fabs in Taiwan likewise; the API now takes a fab's country and the Fabs screen has a Country picker (without one no player could site an EUV fab outside a region's default country).
9. **China's EUV-class capability:** a Chinese foundry reaches an EUV-only node only with EUV-class tools: ASML's (none while the bans hold) or its own, arriving in a seeded window January 2028 - December 2031 (Reuters 2025: chips targeted for 2028, 2030 more likely, widened a year). 41.5's lag number is unchanged, so M28's target 6 reads as before.
10. **The lithography domain's research skill** is hardware design 0.4, manufacturing 0.35, chip design 0.25: the brief's "research" weight is not a skill in skills.yaml (`ml_research` is AI's). Its baseline is 0: nobody in the game holds diffused lithography know-how.
11. **Programme scale** (equipment.yaml, A): litho_1 $8B over 48-72 months, 40 researchers, level 10; litho_2 $25B over 60-96, 120, level 25; litho_3 $40B over 60-96, 160, level 40; overrun 0-60% on the work (and so the cost); success 55% at reference funding and skill 10, ±25 points per unit of funding, ±15 per 10 skill points, within 15-90%. `programme.work_scale` (1.0) is the tuning key; the initial keys met target 3 (5 of 10 seeds), so nothing was tuned.
12. **Own tools' penalties as starts on offer:** a lower yield is read as fewer good starts (x (1 - cut / yield)), with lower uptime; lower throughput means more own tools per fab. So the cost per good die rises as 47.4 asks without touching M21's yield curve.
13. **Prepayment** on a fab's order goes into the fab's capex; on a stock order it is held in 1530 and becomes the tools' value at delivery, written off to 6900 if the order is lost to a rule (not refunded).
14. **ASML, Nikon and Canon** are chain_companies.yaml `equipment_makers` run by M33's rules, not the world's goods loop: they are not takeover targets or bidders (ASML's scale and the Dutch state's interest; and adding them to M28's groups would move its post-2026 draws). No books yet (a follow-up).
15. **The Equipment unlock** is M29 system 25 (a fab in the group), id taken before M32's; renumbered at merge if M34 took 25.
16. **Money scale (PM note 2026-11-15, M34's `economy_scale.money` = 0.1): not applied to M33.** The question was whether M33's real-world prices are on the same scale as the game's existing prices for the same things. They are. M21's fab capex is at real-world scale: nodes.yaml's CSET capital per wafer-per-year × 12 × `fab.capex_scale` 1.8 puts a 50k-start 5 nm fab at 50,000 × 12 × $15,694 × 1.8 = $16.9B, inside 38.5 target 2's real band of $15-25B. M21's own EUV tool price was already real too: nodes.yaml `euv.tool_cents` is $120M c.2020. M33's ASML ASPs (low-NA $196M in 2024; high-NA EUR 350M) follow the same money. A 50k fab's 25 low-NA tools come to about $5B, 29% of that fab's capex. That is the real tool share ASML's numbers imply, and the share `programme.tool_capex_share` (0.25) caps. Scaling only M33's tools by 0.1 would make them 3% of a fab, so they would stop meaning the same thing as M21's capex. So no factor is applied, game-scale and real figures are the same number, and nothing extra goes on screen. The programme's stage budgets ($8B, $25B, $40B) are also real ASML-scale R&D, and target 3 was met in-game at them (decision 11). Left to the PM: whether M21's fab economy as a whole (fab capex, wafer and die costs) should move to `economy_scale.money` along with company revenues. That would change how M21's target 2 is measured, so it is not decided here (a follow-up).

## Follow-ups

- ASML, Nikon and Canon's books (revenue from deliveries, R&D, capex) and company pages; ASML as a rival for M&A screens.
- Rival foundries' world expansions waiting on EUV deliveries (today the queue takes their orders but their capacity growth is the world's).
- Masks and photoresists as goods; deposition, etch and metrology tools (brief: out of scope).
- Automating tool orders and prepayments (M27b's fabs area).
- A DUV queue for a Chinese player under the 2023-2024 DUV rules.
- The M30 state-cache fixture is re-recorded with M33's state (rivals' order book exists from turn 0): see CHANGELOG.
- Money scale (decision 16): whether M21's fab economy (fab capex, wafer and die costs) and with it M33's tool prices move to `economy_scale.money` alongside company revenues — a PM call, since it changes how M21's target 2 is measured.
