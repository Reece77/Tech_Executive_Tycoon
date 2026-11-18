# M42: Pharmaceuticals (v5, lane H)

**Goal:** the hardest science business in the game. The player discovers molecules (with its own AI models, if it has them) and takes them through preclinical work and Phase I–III trials, at historical odds and costs. It submits them through the health regulators M41 built, prices them by region, and lives through the generics cliff when exclusivity ends. Biologics plants, licensing and partnering, and twelve big-pharma rivals round it out.

**Formulas:** `docs/formulas.md` §55 (all), with §21, §28, §48, §50, §54 · **ADRs:** 0002, 0003, 0005, 0013 (stream `pharma` 67), 0020 · **Research:** `docs/v5-research/pharma-dossier.md` · **Depends on:** M41 (`m41-done`), M43a's market sizes for calibration · **Lane:** H, alongside M43a (lane G) and M40 (lane I)

## Reece's decisions

- **Pharmaceuticals, as realistic as medical devices** (2026-11-14).
- **M41's clinical mechanics approved as built** (2026-11-17), and M42 reuses them.
- **Reece reviews the clinical mechanics:** a one-page plain-language summary of the trial, approval, pricing and cliff rules goes in the pull request.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m42-pharma` from `main`.
- **Merges after M43a** (which changes market sizes). Then merge `main`, re-parent the migration, re-record fixtures with reasons, and re-run every guard.
- **M42 owns:**
  - new `backend/tst/sim/pharma/` (programmes, stages, readouts, AI discovery, submissions, exclusivity, demand, pricing, generics, plants, licensing);
  - `pharma.yaml` (new);
  - the pharma categories and the `drug_discovery` domain;
  - pharma-specific kinds in M41's regulator data;
  - the Pharma screens;
  - `tst/balance/m42.py` (new).
- **M42 must not edit:**
  - M43a's market-growth code and keys (size pharma's markets through M43a's mechanism once it lands, and merge `main` often);
  - M40's `space/`;
  - M41's `medical/` beyond reusing it through its interfaces.
- **Shared files:** `categories.yaml`, `regulation.yaml`, `chain_companies.yaml` and `incumbents.yaml`, `balance.yaml` (add `pharma.*`), `docs/formulas.md` (notes in §55 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** A company without pharma must play exactly as before.

## Out of scope

Vaccines' public-health deals beyond ordinary pricing; diagnostics (M41's); pharmacy retail; automating pharma decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `pharma.yaml` from the dossier (transition rates by area and stage, durations, costs per patient, exclusivity terms, generic erosion, pricing rules and the IRA's dates, patient populations by indication and region, rivals' portfolios, pipelines and expiries, contract manufacturers), with every value cited;
   - `pharma.*` keys and stream `pharma`;
   - migration and data dictionary.
2. **Molecules and the pipeline** (§55.1): programmes with hidden efficacy and safety, stages, costs, readouts, and the `drug_discovery` domain.
   - **Hidden-value test:** no true efficacy, safety or pending readout reaches the API or a prompt.
3. **AI-driven discovery** (§55.2).
4. **Approval and exclusivity** (§55.3) through M41's regulators.
5. **Revenue, pricing and the cliff** (§55.4).
   - **Property test:** books balance through approval, pricing changes and loss of exclusivity.
6. **Manufacturing, licensing and rivals** (§55.5).
7. **Screens:**
   - a **Pharma** screen (pipeline by stage and area, readouts, submissions, exclusivity clock, revenue by drug);
   - programme pages;
   - plant pages;
   - M29 unlocks;
   - glossary entries (Phase I/II/III, NDA/BLA, LOE, biosimilar, orphan, priority review);
   - Explain on a programme's chance to approval and its expected value (rNPV).
8. **API, CLI, e2e, balance and close-out:**
   - `tst pharma`;
   - **Playwright:** (a) start a programme with AI discovery and see its preclinical stage shortened, (b) a Phase II readout fails and the programme can be redesigned or stopped, (c) loss of exclusivity cuts a drug's revenue;
   - **a practice save** `pt-pharma`: an AI and devices company in 2026 with an ML research team and $5B cash;
   - **the one-page summary for Reece** in the pull request;
   - **§55.6 targets** printed and recorded, tuning only `pharma.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `pharma.yaml` cites a source for every value.
- [ ] A company without pharma plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No true efficacy, safety, pending readout or seeded rule reaches the API or a prompt (hidden-value test).
- [ ] §55.6 targets 2–6 printed and met, or carried with a recorded decision.
- [ ] The summary for Reece is in the pull request.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m42-done`.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
