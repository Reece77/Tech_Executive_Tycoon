# M31: Platforms and ecosystems (v4, lane C)

**Goal:** platforms become the most valuable position in the game, and the hardest to win. The player can run its own app store and developer ecosystem, licence Android or build its own OS, pay or charge platform fees, be rejected or removed by a gatekeeper (Apple, Google and others), open-source a product, and fight standards wars. Network effects and lock-in make a leading platform hard to dislodge. History to 2025 is unchanged.

**Formulas:** `docs/formulas.md` §44 (all), with §11, §26, §28, §31, §40 · **ADRs:** 0002, 0003, 0005, 0013 (stream `platforms` 58), 0020, **0021 (new: platforms and ecosystems)** · **Research:** `docs/v4-research/platforms-dossier.md` · **Outline:** `docs/v4-outline.md` · **Depends on:** M27a (`m27a-done`), M28 (`m28-done`) · **Lane:** C, alongside M27b (lane A) and M30 (lane B)

## Reece's decisions (2026-11-13)

- **An own app store and developer ecosystem.**
- **Rivals' stores are competitors and gatekeepers.**
- **An AI-model API is a developer platform** (the outline's default).

## Lane

- Its own session and branch (`m31-platforms`) from `main`. First merge PR #52 (`docs-v4-outline`, docs only) if it is still open (rule 9).
- **M31 owns:**
  - new `backend/tst/sim/platforms/` (platforms, developers, catalogue, network effects, lock-in, fees, rules, gatekeeping, open source, standards);
  - `backend/data/platforms.yaml` (new, built from the dossier with a source on every value);
  - the `os` pseudo-category;
  - where products' demand reads platform effects (`tst/sim/products/` and `markets/` demand steps: a read of the platform state, and fee postings);
  - the Platforms screen and platform sections on the device and app product screens;
  - the removal event templates;
  - `tst/balance/m31.py` (new).
- **M31 must not edit:**
  - M27b's `automation/` (if a platform choice needs an area, note it for M27b or a follow-up);
  - M30's performance work (merge `main` often; M30 may touch your files in small, named commits);
  - `world/` beyond reading it.
- **Shared files:** `balance.yaml` (add `platforms.*`; change app categories' reference prices only as §44.4's calibration), `accounts.yaml` (add `4150_platform_fees` and `5150_platform_fees`), `docs/formulas.md` (notes in §44 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **CLAUDE.md §9's decision rules apply.** §44.9 target 1 (history holds) is the guard: if an earlier milestone's guard moves, apply rule 2. A calibration that can't keep 2010–2025 net revenue within 1% is a stop.

## Out of scope

Regulation's designations, investigations and break-ups (M34; M31 only follows the dated rules in the data). Consoles, PCs, cars and headsets as platforms (later data). Automating platform decisions (a follow-up for M27b's successor).

## Sub-tasks (commit after each)

1. **Research and data:**
   - Build `platforms.yaml` from the dossier: platforms, owners, dates, regional user shares by year, fee schedules, dated rules, developers by year, standards and open-source cases.
   - Check every *(verify)* figure against a source and cite it in a comment. A figure with no source found is left out and listed in Decisions made.
   - Add the `platforms.*` keys with comments (unit and intent), ADR-0021, stream `platforms`, the migration and the data dictionary.
   - **Test:** loader validation; regional shares sum to 1 where the data says they do.
2. **Platforms and users** (§44.1):
   - the platform and per-region records;
   - users from data to 2025 and from installed base after;
   - the player's devices on Android (with its licence fee) or an own OS;
   - the `os` pseudo-category;
   - switching a device line as a one-off.
   - **Test:** every platform's 2010–2025 shares equal the data.
3. **Developers and the catalogue** (§44.2) and **network effects and lock-in** (§44.3).
   - **Seeded test:** the same seed gives the same shares.
   - **Unit tests:** the attractiveness formula, multi-homing, the catalogue's effect on device features (capped) and the stay probability.
4. **Fees** (§44.4):
   - schedules and the effective-fee lookup;
   - `paid_share` per category;
   - postings for sellers and owners, intercompany in a group;
   - the history calibration of reference prices.
   - **Property test:** fee postings balance per entity.
   - **Guard test:** §44.9 target 1's net revenue within 1%.
5. **Rules and gatekeeping** (§44.5):
   - the owner's rules, and goodwill;
   - rival owners reviewing the player's products;
   - rejections, fee disputes and removals, with the removal critical event (comply, appeal, regulators);
   - the player reviewing rivals' apps.
   - **Hidden-value test:** no review chance or draw in the API or a prompt.
6. **Open source** (§44.6) and **standards wars** (§44.7), with the historical cases from the data.
7. **Rivals** (§44.8): rival owners' fees and rules from 2026, rival OEMs' licence choices, rival stores where the law allows.
8. **The screens:**
   - a **Platforms** screen: each platform's users, developer share, catalogue index, fees and rules by region, and the player's own platform settings;
   - platform sections on device products (which platform, catalogue effect) and app products (fees paid by platform and region, listing status);
   - removals in the inbox's Needs you tab;
   - M29 unlocks: Platforms at stage 3, or with a device or app-distributed product;
   - glossary entries (platform fee, catalogue, lock-in, side-loading, multi-homing) and Explain on the fee line and the catalogue effect.
9. **API, CLI, e2e, balance and close-out:**
   - **CLI:** `tst platforms` (platforms, users and fees by region).
   - **Playwright:** (a) launch an own OS on a device line and see its catalogue index; (b) a removal arrives as a critical event and complying restores the listing; (c) set the own store's fee and see developer share respond over a year.
   - **A practice save** `pt-platform`: a device maker in 2026 with 20% of its regions' users on Android, ready to launch its own OS and store.
   - **§44.9 targets** printed and recorded. Tune only `platforms.*` (rule 1). Re-run every earlier guard (v1–v6, M8, M10c, M13b, M21, M22, M23b, M27a, M28).
   - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] `platforms.yaml` cites a source for every value. Every 2010–2025 platform share, fee and rule follows it (tests).
- [ ] §44.9 target 1: app-category companies' net revenue to 2025 within 1% of `main` before M31, and every earlier guard unchanged.
- [ ] Fee postings balance per entity and eliminate within a group (property tests).
- [ ] No gatekeeper's chance or draw, and no rival's plan, reaches the API or a prompt (hidden-value test).
- [ ] §44.9 targets 2–7 printed and met, or carried with a recorded decision.
- [ ] `make check`, `make check-timing` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m31-done`.

## Manual check (Reece, after merge)

Load `pt-platform`. Launch your own OS and store on your phone line, set a 20% fee, and play to 2030. Watch your catalogue against Android's. Then publish a consumer app that competes with one of Apple's and see what its review does.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
