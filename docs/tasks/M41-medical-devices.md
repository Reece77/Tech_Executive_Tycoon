# M41: Medical devices (v5, lane D)

**Goal:** a regulated industry with real routes to market. The player can build medical devices (wearables and diagnostics, imaging, surgical robotics, implantables, and software and AI as medical devices) and take them through 510(k), De Novo or PMA in the US and the MDR in the EU. It runs clinical studies, wins reimbursement and clinician adoption, sells to hospitals, and lives with inspections and recalls. It builds on the player's devices, chips, AI models and plants, and on M34's regulator machinery.

**Formulas:** `docs/formulas.md` §50 (all), with §26, §28, §44, §48 · **ADRs:** 0002, 0003, 0005, 0013 (stream `medical` 64), 0020 · **Research:** `docs/v5-research/medical-devices-dossier.md` · **Outline:** `docs/v5-outline.md` · **Depends on:** M34 (merged) · **Lane:** D, a fourth lane alongside M35a, M35b and M38

## Reece's decisions (2026-11-14)

- **Realistic approval stages** for medical devices. Pharmaceuticals follow in M42 on the same machinery.
- **Market sizes and money follow the game's scale** (pending M35a's audit).
- **Reece reviews the clinical mechanics:** the pull request carries a one-page plain-language summary of the approval, evidence, reimbursement and recall rules for him to sanity-check (dossier note).

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m41-medical` from `main`.
- **Merges after `m35b-done` and after M38** (v4 closes first; M38 is the third lane). Then merge `main`, re-parent the migration, re-record the M30 fixture with the reason, and re-run every guard on the combined code.
- **M41 owns:**
  - new `backend/tst/sim/medical/` (sub-categories, classes, routes, submissions, studies, reimbursement, adoption, quality, recalls and surveillance);
  - `medical.yaml` (new);
  - health regulator kinds added to M34's regulator records (FDA, EU notified bodies, PMDA, NMPA), as data and kind-specific rules;
  - the medical screens;
  - `tst/balance/m41.py` (new).
- **M41 must not edit:** M35a's files; M35b's balance keys and scripts (including `regulation.*` keys); M38's `vehicles/`. Reuse M34's regulator code through its interfaces. If one needs a change, keep it small and named, and merge `main` often.
- **Shared files:** `categories.yaml` (append the medical sub-categories), `regulation.yaml` (add health regulators; M35b edits strictness: keep both sides), `chain_companies.yaml` or `incumbents.yaml` (rivals), `balance.yaml` (add `medical.*`), `docs/formulas.md` (notes in §50 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** §50.6 target 1 (history holds; a company without medical devices plays exactly as before) is the guard.

## Out of scope

Pharmaceuticals and biologics (M42); hospital operations; malpractice beyond recall lawsuits; automating medical decisions (a follow-up automation area).

## Sub-tasks (commit after each)

1. **Research and data:**
   - `medical.yaml` from the dossier (sub-category markets sized to the game, routes and review times by region, approval rates, the MDR's dates, study costs, coverage timelines, recall rates, rivals and shares), with every value cited;
   - `medical.*` keys and stream `medical`;
   - migration and data dictionary.
   - **Test:** loader validation.
2. **The category family** (§50.1): sub-categories, customers (hospital contracts with value analysis, clinicians, consumers), revenue models (units, consumables, subscriptions), rivals.
3. **Classes and routes** (§50.2): a design's class by region, routes (exempt, 510(k) with predicates, De Novo, PMA; CE under MDD and MDR), submissions with stages, review ranges and outcomes, SaMD and change-control plans.
   - **Test:** routes and review times to 2025 follow the data.
4. **Clinical evidence** (§50.3): study projects, enrolment, cost, readout draws, redesign.
   - **Hidden-value test:** no study draw before readout reaches the API or a prompt.
5. **Reimbursement and adoption** (§50.4).
6. **Quality, inspections, recalls and surveillance** (§50.5), with the class I recall as a critical event.
7. **Screens:**
   - a **Medical** screen (pipeline of designs, submissions by region with stages, studies, coverage, adoption, recalls);
   - product pages with class, route and evidence;
   - plant quality settings;
   - M29 unlocks (Medical once the player has a device, chip or AI product and stage 3);
   - glossary entries (510(k), De Novo, PMA, predicate, MDR, notified body, pivotal study, coverage, class I recall, SaMD);
   - Explain on a review range and a study's cost.
8. **API, CLI, e2e, balance and close-out:**
   - `tst medical`;
   - **Playwright:** (a) submit a wearable by 510(k) with a predicate and see the review range, (b) run a pivotal study for an implantable and file a PMA, (c) a class I recall arrives as a critical event;
   - **a practice save** `pt-medical`: a device and AI company in 2024 with a wearable and a radiology AI model, ready to enter medical devices;
   - **the one-page summary for Reece** in the pull request;
   - **§50.6 targets** printed and recorded, tuning only `medical.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `medical.yaml` cites a source for every value, and history to 2025 follows it (tests).
- [ ] A company without medical devices plays exactly as before, and every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] No study, review, inspection or recall draw reaches the API or a prompt before it happens (hidden-value test).
- [ ] §50.6 targets 2–6 printed and met, or carried with a recorded decision.
- [ ] The plain-language summary for Reece is in the pull request.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m41-done`.

## Manual check (Reece, after merge)

Load `pt-medical`. File the wearable by 510(k) and the radiology AI by De Novo, and see what each needs. Then start a surgical robot and watch the razor-and-blade model over a decade. Tell me where the clinical side rings false.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
