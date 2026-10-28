# M5: Rivals

**Goal:** the market fights back. The 2010 incumbents get people, ledgers and a personality, and decide every month whether to cut prices, push features, quality or brand, enter segments, cut costs or poach the player's best people; rival startups are founded, raise, launch and die; the player can poach from rivals; and a Competitors screen shows it all. One milestone: rules, API, CLI and screens.

**Spec sections:** §9, §10, §13 · **ADRs:** 0002, 0010, 0013, 0015, 0017, 0018 · **Formulas:** `docs/formulas.md` §15 (all) and its §12 rows · **Wireframes:** `docs/wireframes.md` (M5 screens) and `docs/wireframes/source/Competitors.dc.html`, `Rival.dc.html` · **Depends on:** M4c (`m4c-done`)

## Context

Until now the incumbents held fixed scores (ADR-0017), so a player could learn the market once and win it. M5 makes every rival an ordinary company run by the same rules as the player, with decisions from a utility AI in phase 2 (ADR-0010, ADR-0015). `docs/formulas.md` §15 is authoritative.

## Out of scope

M&A and acquisitions (v2; the acquirer personality is not used), rival fundraising beyond §15.4's simple rule, rival R&D trees (v2), events and storylines about rivals (M6), rival screens beyond the two wireframes.

## Sub-tasks (commit after each)

0. **Faster tests:** add `pytest-xdist` (approved, ADR-0001) to the dev dependencies; run the backend suite with `-n auto` in `make check` and `make check-fast`; make any test that shares files or ports parallel-safe. Record the before and after run times.
1. **Data and formula tests:** `incumbents.yaml` gains personality, builder skill, target margin and cash months (§15.1); a company-name pool in `names.yaml` for startups; all §12 M5 keys; every §15.8 worked example as a unit test.
2. **State and persistence:** rival workforce pools, key people (as persons with employment at the rival), rival ledgers, pushes and cooldowns, poach approaches, rival startups; migration; data dictionary. Older saves: incumbents get pools sized per §15.1 at their current revenue, key people generated, cash at the table's months of revenue.
3. **Rival economics:** pools sized from revenue, payroll, hosting and marketing in phase 6, revenue in phase 5, bankruptcy (§15.1); property tests: every rival ledger entry balances, pools never negative.
4. **Rival decisions** (§15.2, §15.3): utility, personality weights, cooldowns and pushes, action effects, `decision_log` with `source = "rival"`, replay by recomputation.
5. **Rival startups** (§15.4): founding, individuals and product development under §11, funding, bankruptcy, released people.
6. **Poaching** (§15.6): rival approaches with the counter window and phase 1 answer; the player's "Poach from a rival" channel with the leaving penalty and the quality hit.
7. **API and CLI:** rivals list and profile (personality, estimated headcount, products with public scores, cash label for incumbents ("deep pockets", "comfortable", "tight") and nothing for startups, recent moves, key people with the player's revealed ranges), market news, approaches (with a counter-offer preview showing the new chance band, not the probability), poach searches; `tst rivals`, `tst rival --id`, `tst news`, `tst poach --rival`. Extend the hidden-field test (no utilities, needs, noise, true attributes of key people, or acceptance probabilities).
8. **Screens:** Competitors (nav key 8, now live) and the rival profile per the wireframes; the approach item in the inbox with Counter (opens the raise dialog with the chance band) and Let them go; the Poach channel card on Recruitment; a News kind badge.
9. **Golden, balance and e2e:** regenerate golden snapshots (rival moves change markets; CHANGELOG note); print the §15.7 balance table and tune only `rivals.*` keys and personality weights until it holds; record values. Playwright: (a) open Competitors and a rival profile; (b) receive a scripted approach, counter it, and see the answer at Continue; (c) poach a rival's key person through the new channel.

## Acceptance criteria

- [ ] Every §15.8 worked example passes as a test.
- [ ] Incumbents act: a scripted share loss makes a cost leader cut its price and a premium rival start a push, and both show in Market news.
- [ ] Rival startups are founded, launch, raise and fail across 120 turns, within the cap of 8 alive.
- [ ] Rival approaches arrive, can be countered, and resolve per §15.6; the player can poach a rival's key person, and the rival's product loses quality over 6 months.
- [ ] All five §15.7 balance targets met (printed, values recorded).
- [ ] Replay reproduces a save with rival actions, a startup and a poach in each direction.
- [ ] No API response leaks a hidden field or a forbidden value.
- [ ] Backend tests run in parallel; the full `make check` time is recorded before and after.
- [ ] `make check` green; `make e2e` passes all flows; merged and tagged `m5-done` per CLAUDE.md §6.

## Manual check (Reece, after merge)

Play `funded_spinout` for 36 months. Note whether rivals feel like opponents (do their moves make sense, do they react to you), whether poaching approaches feel fair and counterable, and whether the Competitors screen tells you what you need.

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
