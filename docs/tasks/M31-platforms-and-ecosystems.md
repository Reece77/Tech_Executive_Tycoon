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

1. **Fees post from January 2026** (`platforms.fees_from: "2026-01"`). §44.4 posts fees in 2010–2025 with a reference-price calibration, but M28's §41.8 target 1 fingerprint hashes every ledger entry of every company to December 2025, so any history fee line fails that guard by construction (rules 1–4 cannot fix a hash). I put the choice to Reece; the question was declined, so I took the option that leaves every earlier guard unchanged (the acceptance criteria). Shares, fee schedules and rules still follow the data to 2025 as state, and every demand effect also starts in 2026. The §44.4 calibration has nothing to offset and is not applied. Setting `fees_from: "2010-01"` gives §44.4 as written; it then needs the calibration and a re-recorded M28 books fingerprint. **Reece to confirm.**
2. **Shares are StatCounter's** yearly mobile OS usage share (web traffic), the dossier's measure, fetched as CSV for 17 regions and countries (2010–2025). Game regions come from StatCounter regions: North America, Europe, South America, Africa and Oceania as they are. East Asia blends China, Japan and South Korea, and South and Southeast Asia blends India and Indonesia, both by 2020 population (World Bank; fixed weights, A). China's Android goes to Android (China); feature phones, bada, consoles and the rest go to `other`. Each row is normalised to 1. HarmonyOS is not separated by StatCounter (it counts inside Android in China), so Counterpoint's sales shares were left out.
3. **Dossier figures corrected or left out.** Corrected:
   - Google Play peaked at about 3.6M apps (March 2018), not 3.5M.
   - The App Store had 1.96M apps at the end of 2024.
   - The US contempt ruling (30 April 2025) was upheld on 11 December 2025, with a cost-based rate allowed later; none had been set by December 2025, so the data keeps 0%.

   Left out (no source found):
   - "About 20M developers in 2015": developers come from Evans Data's points (2013, 2019, 2022, 2024) and hold the 2013 value before it.
   - The fee rates of Chinese stores, BlackBerry World, the Nokia Store and the Windows Phone Store: 30% (A).
   - Google's EU DMA alternative billing rate, and its compliance terms after Epic v. Google (October 2025).
   - Apple's Core Technology Fee and the 2025–2026 EU terms.
   - The last BlackBerry 10 device.

   Developers' regional split uses categories.yaml's market sizes (A). Region parts (Korea in East Asia, the US in North America, the EU in Europe) are population shares; `platforms.alternative_share` (20%, A) of a regulated country's sales take its path.
4. **Owners outside the game** (Google, BlackBerry, Nokia and China's stores) set fees and review apps but book nothing; their fees leave the game. Apple and Microsoft book `4150`.
5. **Users after 2025** = the in-game device lines on a platform plus its share of the rest of the market. The rest replaces at the devices' pace with lock-in and chooses by users × catalogue tilt; in January 2026 the rest is set so users equal December 2025's data (formulas §44.11). Lock-in therefore acts in this users flow, not as a per-customer choice inside the device market. ThinkPad counts as an Android line. Developer shares to 2025 are computed from the data's users and fees, with no draw.
6. **An own OS may be built and launched before 2026**, but platform effects start in January 2026.
7. **Smaller choices:**
   - The `os` pseudo-category is kept out of `GameData.categories`, so no market, rival or loop sees it; `data.category("os")` still finds it.
   - Platform actions' energy lives in `platforms.energy`, because `founder.energy_cost` is a fixed set.
   - A developer platform competes with the rest of its category; its catalogue index is measured against a half-share steady state.
   - A rejected update costs a month of features; a fee dispute charges a month's fees on that platform again; regulators answer in 6 months.
   - Seeded standards contests have no sponsors, so no standards licence is charged (none after 2025).
   - Rival stores take real alternative stores' names.
   - Android's licence is $10 a unit from 2026 (`android_licence_cents`, A: the EU reports of up to $40 a device from 2018 were not verified).
8. **Unlock.** Platforms opens at stage 3, with a device line (from development), or with a *live* app sold through stores. Counting apps still in development would open the screen in month 1 for every software start, against M29's progressive unlocking.
9. **Tuning (rule 1, `platforms.*` only):**
   - `reach_exp` 1.0 → 0.5 and `fee_exp` 1.0 → 3.0, for target 2. At α = 1 a challenger with 5% of users cannot pass about 8% of developers, so the strong case could never tip; a sweep of α ∈ {0.5, 0.6, 0.7} × β ∈ {1, 2, 3} on seeds 1–10 found only (0.5, 3.0) meeting both halves.
   - `review.removed_loss` 0.15 → 0.30 (my own first value), for target 4.
10. **The practice save** `pt-platform` plays 2010–2025 with the engine (a do-nothing Kestrel), then adds the phone line, taking its 20% from the other Android lines so Android's users stay history's. Its first version jumped a new game to 2026; iOS then fell 16 points in 3 months because 2010's in-game customers met 2025's shares.

## Follow-ups

- **Fees in history** (decision 1): if Reece wants §44.4 as written, set `fees_from: "2010-01"`, apply the reference-price calibration, and re-record M28's books fingerprint with a recorded reason. The other fingerprint series are unaffected.
- **M34:**
  - regulated paths for Google Play (the EU DMA, Epic v. Google from October 2025) and Apple's 2025–2026 EU and Japan terms, as `platform_fee_rule` data once rates are sourced;
  - designations read platform users and developer shares;
  - "go to regulators" already marks the regions with rules.
- **HarmonyOS** as its own platform in China (needs a usage series by year, not Counterpoint's sales shares).
- **Lock-in inside the device market:** reserve a platform's churned customers for devices on the same platform. It is now in the users flow only.
- **Developer platforms against named rivals'** (OpenAI's and Anthropic's APIs, the clouds' marketplaces), instead of "the rest of the category".
- **Automating platform decisions:** M27b's successor; no automation area was added.
- **Product-screen platform actions** (switching a line, steering) live on the Platforms screen; the product section links there.
- **Standards licences** for a sponsored winning format after 2025.
- **Consoles, PCs, cars and headsets** as device platforms (later data).
