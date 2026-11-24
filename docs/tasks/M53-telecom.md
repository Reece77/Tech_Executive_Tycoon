# M53: Telecom (v6, lane B)

**Goal:** the player can build networks. Mobile and fixed broadband are businesses, with towers, fibre and subsea cables as facilities, spectrum won at auction, and equipment from Ericsson, Nokia, Huawei or the player's own chips. Bans force rip-and-replace. The player meets Verizon, Vodafone, China Mobile and Jio as rivals, and satellite links (M40) as partners or competitors.

**Formulas:** `docs/formulas.md` §62 (all), with §22, §39, §46, §48, §54, §56 · **ADRs:** 0002, 0003, 0013 (stream `telecom` 73), 0020 · **Research:** `docs/v6-research/telecom-dossier.md` · **Depends on:** M50 (`m50-done`) · **Lane:** B, alongside M49 (lane A) and M51 (lane C)

## Reece's decision (2026-11-22)

- **Telecom first** among v6's new industries.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m53-telecom` from `main`.
- **Must not edit** M49's or M51's's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M53 owns:**
  - new `backend/tst/sim/telecom/` (subscribers, networks, generations, spectrum auctions, equipment, bans, operators);
  - `telecom.yaml` (new);
  - the `telecom` categories and the `network_equipment` hardware category;
  - tower, fibre and subsea-cable facility kinds;
  - the telecom regulator kind's data;
  - the Telecom screens;
  - `tst/balance/m53.py` (new).
- **Merges after M49.** Then merge `main` and re-run every guard.
- §62.5 target 1 (history holds, and a company without telecom plays exactly as before) is the guard.

## Out of scope

Retail stores; TV bundles; satellite operators beyond M40's.

## Sub-tasks (commit after each)

1. **Research and data:** `telecom.yaml` from the dossier, with every value cited, at the game's scale; `telecom.*` keys and stream `telecom`; migration and data dictionary.
2. **Networks and generations** (§62.1). **Property test:** books balance through builds and wholesale sales.
3. **Spectrum auctions** (§62.2). **Hidden-value test:** no rival bid or draw reaches the API or a prompt.
4. **Equipment and bans** (§62.3), including rip-and-replace with deadlines.
5. **Rivals and regulation** (§62.4).
6. **Screens:**
   - a **Telecom** screen (subscribers, coverage map by region and generation, capacity and quality, spectrum holdings, equipment by supplier, auctions);
   - M29 unlocks;
   - glossary entries (spectrum, band, coverage obligation, rip-and-replace, ARPU);
   - Explain on a network's payback.
7. **API, e2e, balance and close-out:**
   - **Playwright:** (a) win a mid-band auction, (b) build 5G in a region and see coverage grow, (c) a ban forces replacing Huawei equipment;
   - a practice save `pt-telecom`: a devices and chips group in 2018 with cash for a network;
   - **§62.5 targets** printed, tuning only `telecom.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `telecom.yaml` cites a source for every value; history to 2025 follows it.
- [ ] A company without telecom plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No rival bid or draw reaches the API or a prompt (hidden-value test).
- [ ] §62.5 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m53-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
