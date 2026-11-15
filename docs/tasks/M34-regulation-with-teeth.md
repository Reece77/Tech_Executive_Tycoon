# M34: Regulation with teeth (v4, lane C)

**Goal:** size brings scrutiny. Regulators by region designate gatekeepers, impose duties (side-loading, alternative payments, interoperability, no self-preferencing, fee caps), open investigations with visible stages, fine up to 10% of turnover and, rarely and with years of warning, order a break-up or unbundling. Rivals face the same rules and their real 2010–2025 histories. Compliance, settling and influence lower the risk.

**Formulas:** `docs/formulas.md` §48 (all), with §28.7, §29, §31, §32.4, §32.5, §44 · **ADRs:** 0002, 0003, 0005, 0013 (stream `regulation` 62), 0021 · **Research:** `docs/v4-research/regulation-dossier.md` · **Depends on:** M31 (`m31-done`) · **Lane:** C, alongside M32 (lane A) and M33 (lane B)

## Reece's decisions (2026-11-13)

- **Break-ups possible but rare, visible and warned years ahead;** most outcomes are lesser remedies.

## Lane

- Its own session and branch (`m34-regulation`) from `main`. **Merges first** of the three (it changes the fewest costs).
- **M34 owns:** new `backend/tst/sim/regulation/` (regulators, designations, duties, investigations, remedies, structural orders); `regulation.yaml` (new); where M31's platform rules and fee schedules read duties (`platforms/` rules: a forced setting and fee-rule rows); the antitrust review in `mna/` where it joins regulators; the Regulation screen and investigation events; `tst/balance/m34.py` (new).
- **M34 must not edit:** M32's `power/`, M33's `equipment/`, M36's family code. M31's platform model beyond the rule and fee hooks ADR-0021 names.
- **Shared files:** `balance.yaml` (add `regulation.*`), `accounts.yaml` (add `6970_fines`), `docs/formulas.md` (notes in §48 only), CHANGELOG, data dictionary, ADR-0013.
- **CLAUDE.md §9's decision rules apply.** §48.5 target 1 (history holds) is the guard, with M31's §44.9 targets re-run (fee schedules to 2025 must still follow history).

## Out of scope

Health regulators (M41 and M42 reuse this machinery with new kinds); data-privacy fines (GDPR) beyond a note (follow-up); export controls (M22's).

## Sub-tasks (commit after each)

1. **Research and data:** `regulation.yaml` from the dossier (regulators, strictness, thresholds, duties and dates, historical cases with fines, rulings and remedies for rivals), every value cited; `regulation.*` keys; stream `regulation`; migration and data dictionary.
2. **Regulators and designations** (§48.1): December tests, the year-ahead warning, rivals' historical designations.
3. **Duties** (§48.2): forced platform settings and fee-rule rows, compliance costs, non-compliance. **Test:** a designated platform's duties change its rules on their dates.
4. **Investigations** (§48.3): openings (seeded), visible stages, settle, contest and lobby, fines (`6970_fines`), behavioural remedies; rivals' cases to 2025 from the data. **Hidden-value test:** no investigation chance or draw in the API or a prompt.
5. **Break-ups and unbundling** (§48.4): the preconditions, warning signs at least 3 years ahead, the order, spin-off or sale within 24 months (§31, §28), appeals. **Property test:** a structural order never arrives without its preconditions and 3 years of warnings.
6. **Screens:** a **Regulation** screen (regulators by region, designations and thresholds, duties, investigations with stages, fines, warnings), investigation items in Needs you, M29 unlocks (Regulation at the first warning or investigation), glossary (gatekeeper, statement of objections, behavioural and structural remedy) and Explain on a fine and on designation thresholds.
7. **API, CLI, e2e, balance and close-out:** `tst regulation`; Playwright: (a) a designation warning arrives a year ahead, (b) settle an investigation with a commitment, (c) a scripted structural order after ignored warnings offers spin-off or sale; a practice save `pt-regulated` (a dominant platform owner in 2029 under an EU investigation); **§48.5 targets** printed and recorded, tuning only `regulation.*` (rule 1); re-run every earlier guard (M31 especially); CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `regulation.yaml` cites a source for every value; rules, designations, fines and rulings to 2025 follow it (tests).
- [ ] Every earlier guard unchanged (M31 §44.9 especially).
- [ ] A structural order never arrives without its preconditions and at least 3 years of warnings (property test).
- [ ] No investigation chance or draw reaches the API or a prompt (hidden-value test).
- [ ] §48.5 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m34-done`.

## Manual check (Reece, after merge)

Load `pt-regulated`. Read the investigation's stages, then either settle or contest. Turn self-preferencing back on and watch the warnings build.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
