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

1. **The research** (`backend/data/medical.yaml`, every value with its source or marked A; a test checks every line with a number). The dossier's *(verify)* figures:
   - **Confirmed:**
     - 510(k), De Novo and PMA review goals: 90, 150 and 180 FDA days; MDUFA V total-time goals of 128 and 290 calendar days.
     - Requests for more information on 63-68% of 510(k)s; about 3,000-3,300 clearances a year; 33-36 original PMAs a year (2023-24); about 12% of PMAs withdrawn or not approvable.
     - FDASIA's direct De Novo (July 2012); Dexcom G6's De Novo creating iCGM class II (27 Mar 2018); Apple Watch ECG and IRN De Novos (11 Sep 2018); Viz.ai (13 Feb 2018) and IDx-DR (11 Apr 2018); da Vinci's 510(k) (11 Jul 2000).
     - 1,016 AI-enabled devices by December 2024 (about 76% radiology, 96-97% by 510(k)); the PCCP final guidance (4 Dec 2024).
     - The MDR from 26 May 2021, and Reg. 2023/607's legacy dates (Dec 2027 for class III and implantable IIb, Dec 2028 for the rest); 51 MDR notified bodies; 13-18 months the most common time to an MDR certificate.
     - Rathi's pivotal median of 241 patients (IQR 147-415); the De Novo pivotal median of 112.5; the NCD's ~9-month clock, and the 5.7-year median and 44% rate to Medicare coverage for novel devices; TCET (12 Aug 2024).
     - The FDA's recall class mix (9/88/3%); Philips Respironics (June 2021 recall, April 2024 consent decree, USD 1.1B settlement).
     - Company revenues for 2010 and 2024; Intuitive's 2010 and 2024 installed base, procedures and recurring share.
   - **Estimates (secondary sources, marked est.):** actual MDUFA review totals (fda.gov could not be fetched from this session); the De Novo grant rate (~55-65%); the NSE share; the pivotal success rate (no published figure; 67% at standard quality, in the 60-75% planning range); the AI/SaMD market size.
   - **A:** quality-system costs, inspection outcome shares, recall rates per device line, field-action cost shares, notified-body fees, PMDA's and NMPA's approval rates, the reliance months, the coverage approval range by evidence, and clinicians' adoption curve.
2. **Market sizes follow the game's scale** (pending M35a's audit). The sub-categories' D0 are derived from real 2024 world revenue x `economy_scale.money` (0.0849, M34's figure), served at the incumbents' 65%, and taken back to 2010 by `growth_by_year`. The derivation is beside each category in categories.yaml, and a test holds 2010 and 2024 within 25% of real. Study costs per patient are real money, as salaries are; the audit may change both.
3. **Health regulators are M34's records with a kind.** `HealthRegulatorDef` (M34's `RegulatorDef` with `kind: health`) lives in regulation.yaml's new `health_regulators` list. This is one small, named change to M34's `config.py`. M34's competition code never reads the list, so its designations, cases and orders are unchanged. M41 uses M34's helpers through their interfaces (part shares, strictness by year, `6970_fines`). M38's `automotive` kind can follow the same pattern.
4. **Routes.** The class comes from the design's intended use (medical.yaml `uses`: the US class by date, the EU class under MDD and MDR). The US route is exempt, then 510(k) when a predicate exists (from the data's date, or once any company's device with that use is FDA-cleared), De Novo, or PMA for class III. EU: CE self-declared for class I, the MDD to April 2021, the MDR after. Japan and China have one route each. The other regions (and the rest of North America, Europe and East Asia) register by reliance on an FDA or CE clearance, in a drawn number of months.
5. **A product sells only where it is cleared.** The gate (formulas §50.8) multiplies new wins through M22's access map; existing customers keep buying. Rivals' devices are history's, cleared wherever they sell, with no filings, inspections or recalls (a follow-up).
6. **Razor and blade.** Consumables and service (`consumables_cents` a month per installed unit, account `4050_revenue_consumables`) post for every selling device, rivals' included. A surgical robot earns $57,400 a month per installed system, Intuitive's 2024 figure.
7. **Studies, coverage and adoption** (formulas §50.8). A study's design is chosen and shown; its result is drawn at readout. Evidence strength is the sum of successful studies' strengths (pivotal 0.6). Coverage reads evidence for its months and its chance. Clinicians' adoption is logistic from 3%.
8. **Quality** is a plant setting: low, standard or high, the default standard. A device's level is its company's worst assembly plant, a contract manufacturer's `standard`, or standard for software. A class I recall is a critical event with three answers (full recall, field correction, dispute) applied by `medical_step`.
9. **SaMD and change control plans.** A software device whose features pass its US clearance by `review.update_features` needs a new filing, unless it was filed with a PCCP (from December 2024's guidance); a PCCP adds two months to the review.
10. **History holds for the player and for every earlier company's money.**
    - The medical makers are twelve real incumbents appended to incumbents.yaml. Random startups, CPO pitches and angel backing skip family medical. A company without a medical design makes no medical draw (a test).
    - Golden snapshots are unchanged.
    - **M28's history fingerprint** (§41.8 target 1) is re-recorded for its `events` and `books` series only; prices, wafers and capacities are identical. The evidence, recorded before re-recording:
      - `tools/m41_history_diff.py` (M41's rivals' lines left out, and later companies' ids moved back by 12, the medical incumbents' count) shows every earlier company's books identical to main's fixture for all 16 years on seeds 1-2;
      - an events comparison against a main worktree shows every event identical on seeds 1-3, 2010-2025, except `rankings_published` and `rival_story`: the medical makers are large companies and take places in the Top 50 (Salesforce enters at #9, not #6).
    - Apple's consumer health features (the September 2018 De Novos) are a dated record shown on the Medical screen, not a product, so Apple's books to 2025 are unchanged.
11. **Stream `medical` (64)** through `tst/sim/medical/draws.py`; keys as ADR-0013's row, with the regulator index (not the region's) for review drift, as M34's decision 9.
12. **Accounts:** `4050_revenue_consumables`, `6980_recalls`, `6985_quality_regulatory`. Studies post to 6500, clinical education to 6400, consent decrees to 6970.
13. **Balance scripts** (`tst/balance/m41.py`, rule 2). Target 2 files each device 20 times per seed on the engine's filing and decision steps, filing a refusal again at once. The robotics entrant has 12 account executives, a contract manufacturer at 50 robots a month (my first script's 10 million-unit take-or-pay contract bankrupted it), filings at once with the FDA and the EU, coverage asked as soon as it is cleared, $50,000 a month of clinical education and surveillance, and answers a class I recall with a full recall.
14. **§50.6 targets** (`tools/m41_targets.py`, seeds 1-10), all met at the initial keys (no tuning):

    | # | Target | Result | Band |
    | --- | --- | --- | --- |
    | 1 | History holds | unit tests; golden unchanged; decision 10 | identical |
    | 2 | 510(k) median | 4.8 months | 4-12 |
    | 2 | De Novo median | 13.5 months | 8-18 |
    | 2 | PMA median (review) | 12.0 months | 12-36 |
    | 2 | EU class III: MDR longer than MDD | 10/10 seeds | at least 8 |
    | 3 | Evidence: earlier to coverage and 30% adoption | 60 months (median) | 24+ |
    | 4 | Quality: fewer class I recalls, high v low | 78% (46 to 10) | 60%+ |
    | 5 | Robotics entrant: year-8 recurring share | 48% (median) | 40%+ |
    | 6 | Turn time | `make check-timing` | within guards |

15. **Unlock** `medical` (M29 system 28): a medical product of the group's, or a device, chip or AI product at stage 3.

## Follow-ups

- **Rivals' filings, recalls and inspections** after 2025: rivals' devices are cleared as history had them and never recalled; a seeded rival recall or a new rival device's review would make the field livelier.
- **Breakthrough designation** (dates in medical.yaml): priority review and TCET's eligibility for designated devices only.
- **Hospital value-analysis contracts** as their own sales cycle (today the enterprise segment's sales capacity and adoption carry it).
- **Existing saves** do not gain the medical markets or rivals (as M12b's devices did not); a migration that adds markets mid-game would be a separate decision.
- **The economy-scale audit (M35a)** may move market sizes and study costs together.
