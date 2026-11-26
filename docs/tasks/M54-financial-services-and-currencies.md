# M54: Financial services and currencies (v6, lane A)

**Goal:** the player's fintech can grow into a bank, a payments network or an insurer, each regulated, rate-sensitive and capable of failing. Every company with foreign sales lives with currency moves, and can hedge them.

**Formulas:** `docs/formulas.md` §64 (all), with §11.8, §16, §17, §18.6, §20, §40, §44, §48, §54 · **ADRs:** 0002, 0003, 0013 (streams `finserv` 74 and `fx` 75), 0020, **0025** (currencies) · **Research:** `docs/v6-research/finance-dossier.md` · **Depends on:** `m53-done` (on `main`) · **Lane:** A, alongside M55 (lane B) and M52 (lane C)

## Reece's decisions (2026-11-21, 2026-11-22)

- **Financial services at scale** in v6: banking, payments and insurance, with regulators, capital rules and stress tests.
- **Currencies and hedging** go into the first milestone that needs them: this one.
- Defaults for everything else.

## Lane

- Its own session, in its **own clone or worktree** (never a shared folder), on branch `m54-finance` from `main`.
- **Must not edit** M55's or M52's files. Merge `main` often.
- **CLAUDE.md §9's decision rules apply.**
- **M54 owns:**
  - new `backend/tst/sim/finserv/` (banks, deposits, loans, capital, stress tests, runs, payments networks, insurers);
  - new `backend/tst/sim/fx/` (rate indexes, translation, hedges);
  - `finance_services.yaml` and `fx_history.yaml` (new);
  - the bank, payments and insurance categories (new keys after `network_equipment`), and the bank and insurance regulator kinds' data;
  - the Bank, Payments, Insurance and Currency screens;
  - `tst/balance/m54.py` (new).
- **Shared files** (keep both sides on a merge): `categories.yaml`, `incumbents.yaml` (append; ids follow merge order, as M53's decision 8), `balance.yaml`, `regulation.yaml`, `accounts.yaml`, glossary, inbox templates, formulas §64, the data dictionary, ADR-0013, CHANGELOG.
- **No fixed merge order** with M55 and M52: the first ready merges first; the others then merge `main`, re-parent their migrations on the new head, and re-run every guard.
- §64.6 target 1 (history holds, and a company with no bank, network, insurer or foreign sales plays exactly as before) is the guard.

## Out of scope

Investment banking and trading desks; asset management; health insurance; crypto and stablecoins (a follow-up); central bank digital currencies; multi-currency cash accounts (ADR-0025, point 1).

## Sub-tasks (commit after each)

1. **Research and data:** `finance_services.yaml` and `fx_history.yaml` from the dossier, every value tagged S/D/R/A with its source; `finserv.*` and `fx.*` keys; streams `finserv` and `fx`; migration and data dictionary.
2. **Currencies first** (§64.4, ADR-0025): rate indexes, translation of regional prices and local costs, the FX gain and loss accounts, forwards. **Property tests:** books balance through translation and hedge settlement; a North-America-only company's state is identical to `main`'s (state hash, seeds 1–3, 240 months).
3. **Banking** (§64.1): charters and partner banks, deposits with a chosen beta, loans and losses through the cycle, securities and their market value, capital, stress tests, runs and failure. **Property test:** a bank's balance sheet balances every month; CET1 is computed exactly (integers or exact decimals).
4. **Payments** (§64.2): networks, issuers and acquirers; interchange caps by date; real-time rails; fraud.
5. **Insurance** (§64.3): lines, combined ratio, catastrophe years, float income, solvency.
6. **Rivals and regulation** (§64.5): the banks, networks, payments companies and insurers, pinned to history before 2026 as M53's operators were; bank and insurance regulators; a bank inside a tech group under review. **Hidden-value test:** no stress-test shock, run draw or catastrophe draw reaches the API or a prompt before it happens.
7. **Screens:**
   - **Bank** (balance sheet, net interest margin, deposit beta, capital ratio against the line, stress test results, uninsured share and run risk shown as a band);
   - **Payments** (volume by region, take rate, acceptance, fraud);
   - **Insurance** (premiums by line, combined ratio, float, solvency);
   - **Currency** (exposure by region, hedges and their settlement dates, a what-if of a 10% dollar move);
   - M29 unlocks; glossary entries (net interest margin, deposit beta, CET1, risk-weighted assets, interchange, combined ratio, float, forward, translation); Explain on a bank's profit and on an FX loss;
   - the CFO delegate (§40) can run the hedging programme within its limit.
8. **API, e2e, balance and close-out:**
   - **Playwright:** (a) charter a bank from a fintech and take deposits, (b) a rate rise squeezes a high-beta bank's margin on the Bank screen, (c) hedge 80% of Europe's revenue and see the settlement;
   - a practice save `pt-bank`: a fintech group in 2019 with cash for a charter;
   - **§64.6 targets** printed, tuning only `finserv.*` and `fx.*` (rule 1); re-run every earlier guard;
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `finance_services.yaml` and `fx_history.yaml` cite a source for every value; history to 2025 follows them.
- [ ] A company with no bank, network, insurer or foreign sales plays exactly as before; every earlier guard is unchanged on the combined code (or explained under rules 1–4).
- [ ] Money stays integer cents through translation, interest and hedges (the float-money guard covers `finserv/` and `fx/`).
- [ ] No run, stress or catastrophe draw reaches the API or a prompt before it happens (hidden-value test).
- [ ] §64.6 targets 2–5 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m54-done`.

## Decisions made

(filled in by the session)

## Follow-ups

(filled in by the session)
