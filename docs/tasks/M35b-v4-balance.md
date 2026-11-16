# M35b: v4 balance (v4, lane B; closes v4)

**Goal:** v4's systems (platforms, power, equipment and regulation) work together over 30 years. Their strategies are viable but not dominant, and each system's targets still hold on the combined code. The `m35b-done` tag closes v4.

**Formulas:** §44.9, §46.8, §47.5, §48.5, and the v3 targets (M23b's section) · **Depends on:** M32 (`m32-done`), M33, M34, M36p; merges **after M35a** · **Lane:** B, alongside M35a (lane A)

## Lane

- Its own session, in its **own clone or worktree**, on branch `m35b-balance` from `main`. Build strategies and measurement first. Tune and merge only after `m35a-done` exists: then merge `main` and re-run everything on the combined code.
- **M35b owns:** `tst/balance/` (new `v4.py` and strategy scripts), the balance keys of M31–M34 (`platforms.*`, `power.*`, `equipment.*`, `regulation.*`), `known_misses.py` entries for v4 targets, and `regulation.yaml` and `platforms.yaml` data for the follow-ups below.
- **M35b must not edit** M35a's files (see its brief).
- **CLAUDE.md §9's decision rules apply.** Long runs go to GitHub (rule 7).

## Sub-tasks (commit after each)

1. **v4 strategies** in `tst/balance/`:
   - **`platform_owner`:** a device maker that launches its own OS and store by 2014 and licenses it from 2018;
   - **`power_hyperscaler`:** a cloud company that builds its own plants behind its data centres from stage 4 and sites by power;
   - **`litho_bet`:** M23b's `full_integrator`, which also starts the lithography programme in 2028 at the 60th-percentile funding;
   - **`compliant_platform`:** `platform_owner`, but settling early and paying for influence.

   Each behaves as a sensible player would (rule 2's test).
2. **30-year runs on the combined code** (seeds 1–10, and the weekly on 1–30) for the four v4 strategies, with M23b's v3 strategies and `devices_regions` as comparisons. Dispatch on GitHub.
3. **The v4 targets** (printed):
   - **T1, viable, not dominant:** each v4 strategy's median year-30 ARR is between 0.9× and 1.4× its natural comparison:
     - `platform_owner` against `devices_regions`;
     - `power_hyperscaler` against a steady cloud company without plants;
     - `litho_bet` against `full_integrator`.
   - **T2, no strategy always wins:** no v4 strategy is top on more than 4 of 10 seeds among all strategies.
   - **T3, regulation bites platforms:** `platform_owner` meets at least one duty or fine by 2034 on at least 7 of 10 seeds, and `compliant_platform` pays at least 30% less in fines.
   - **T4, power binds:** `power_hyperscaler` reaches its 2032 capacity at least 1 year earlier than the steady cloud company in congested regions.
   - **T5, each system's targets still hold:** §44.9's 2–5, §46.8's 2–5, §47.5's 2–4 and §48.5's 2–5 re-measured on the combined code, and the v3 targets (I1–I3, S1, S2, F1, L1–L4).
   - **T6, the known misses:** each one closed, or reported with its numbers and owner. They are:
     - I1 (M28);
     - V3.ai and V5.cells / V5.cats (M28);
     - M28's target 2 (accepted at 12%);
     - M30's 439 ms (now M35a's).
4. **Follow-ups from M32–M34 that are balance or data:**
   - **Google Play's regulated rates** (M34): add them to `platforms.yaml` with sources. Re-record M28's §41.8 target 1 fingerprint for the fee series only, with the diff shown.
   - **Regulators' strictness after 2025:** a seeded drift moved by politics and §32.5 influence, within `regulation.*` bounds.
   - **Mergers review linked to regulators:** §28.7's antitrust review reads the regulator's strictness and an open investigation.
   - **The scripted phone line with a production contract that books no hardware sales** (M34): fix the script, or report the engine gap.
   - **Rival foundries' expansions waiting on EUV deliveries** (M33): rivals' new EUV capacity arrives only with their queue deliveries.
5. **Tune** only the keys this lane owns, as far as needed (rule 1), recording before and after values.
6. **Close-out:**
   - CHANGELOG;
   - a v4 section in the roadmap's status;
   - the M35 rows in the README index;
   - trigger the weekly on `main` after merging and report it.

## Acceptance criteria

- [ ] T1–T5 printed and met, or carried with a recorded decision; T6 reported in full.
- [ ] Every earlier guard on the combined code is unchanged, or explained under rules 1–4.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m35b-done`. **This tag closes v4.**

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
