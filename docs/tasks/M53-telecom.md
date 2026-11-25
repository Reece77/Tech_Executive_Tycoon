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

1. **Workspace, branch and order (2026-11-24/25).** This session's own worktree (`../tst-m53-telecom`), branch `m53-telecom` from `main` at `0992683` once `docs/tasks/M53-telecom.md` was on `main` and `m50-done` existed (checked hourly from 13:22 UTC; the tag appeared at about 02:40 UTC on 25 November). M49 had merged already (`m49-done`, in `main`), so the brief's "merges after M49" held from the start. No M49 or M51 file was edited; shared files (categories, incumbents, balance, regulation, glossary, inbox templates, accounts, formulas §62, data dictionary, ADR-0013, CHANGELOG) keep both sides.
2. **Research.** As M40 found, this session could open only en.wikipedia.org (ITU, GSMA, the FCC, Ofcom, OECD, Dell'Oro and the operators' sites were refused by the proxy), so telecom.yaml's S figures are Wikipedia's (raw page text, quoted in comments), D derived from them, R recalled from a named source and A assumptions with their basis. The 2017 regional subscription totals are S-sums of LSBB's ITU country rows in the game's regions; other years D/R around them. No Wikipedia page gives ARPU, vendor RAN shares, rip-and-replace's cost estimates or most auction reserves: those are R or A. Corrections to the dossier are listed in telecom.yaml's header (Auction 97's net and gross; Auction 107's "over $81 billion" and Verizon's two figures; India 2022 and Germany 2019 totals R; the UK's 2018 total; the 2024 US order struck down). Follow-up: re-check the R and A rows against ITU, GSMA Intelligence, the regulators and the operators' filings when those hosts are reachable.
3. **Regions.** The game's regions follow platforms.yaml's `region_parts`: North America includes Mexico (so Telcel and Telmex are North American lines), Europe includes Russia and Turkey; the Middle East and Central Asia (about 229M and 78M mobile subscriptions around 2017) are in no game region and are left out.
4. **Scale.** `telecom.scale` 0.085 = `space.scale` (the economy scale), applied to subscriptions, sites, the national grid's sites and auction proceeds, at real prices in 2010 dollars.
5. **A category's own regional price index** (engine change). telecom ARPU differs far more by region than the regions table's 0.35-1.0 (India's mobile ARPU is about 1/15 of North America's), and one index for every category would put India's mobile revenue about 6x too high. `CategoryDef.price_index` (optional) replaces the table's index for that category only, in `price_ratio` (exact decimals), phase 5's appeal (`ReachContext.category_indexes`), a player's default regional price, a rival's regional entry and M43a's market value. Every other category reads exactly what it read before (the M28 fingerprint and every earlier series equal main's).
6. **Demand set by the data, as vehicles'.** The four categories have growth 0 and their addressable markets are set each month from telecom.yaml (decision 3's regions), then grown from 2026 by a seeded yearly rate a region; M43a's ceilings leave them alone. Network equipment's market is mobile subscriptions x 0.0011 site sets x scale (A), so equipment demand follows the regions' subscribers, not the regions table's size multipliers.
7. **Segments.** New `telecom_consumer` (1.5% churn a month, adoption 6%), `telecom_business` (1%) and `carriers` (2%; equipment by replacement_months 84): the consumer segment's 6% churn would empty telecom markets after 2025.
8. **Operators, lines and history.** Twenty-four operators and five vendors appended to incumbents.yaml (ids 107-134, after M40's space companies); a company in several regions has a line in each (one price a line). Lines are pinned before 2026 to their data (subscribers x scale x split, wholesale share, vendor share x region_mult less bans); Sprint closes in April 2020 and Vodafone India in September 2018 (Vodafone Idea opens then), Jio opens in September 2016. They hold, are never failed and are not ranked before 2026 (as M40's space companies, decision 17 there), and M28's fingerprint writes their lines to a new series `telecom`; the fingerprint's market-news filter keeps an item of another company whose name begins with a held one's ("Huawei Ascend", an entrant, against Huawei), a fix to the measure only. Docomo and SK Telecom are priced 1.5-1.6x East Asia's and Telcel and Telmex 0.8x North America's (A: a region is one market, and Japan's ARPU at 4x China's would empty them after 2025). Operators are private (no `listed_from`; a follow-up).
9. **Target 2b's measure.** The player's mobile line is still winning customers years after its 2016 launch, so its own share at 5G's arrival is no baseline (on seed 1 it rises from 2.4% to 5.6% with mid-band and to 3.4% without). "Loses at least 20% of its mobile share by the next generation" is read as: five years after 5G's arrival, the arm without mid-band holds at least 20% less of the market than the same network with it.
10. **Capacity.** A site carries each band once, at the best efficiency its radios reach there; a generation that needs mid-band (5G, 6G) reaches its own only on mid and high band and 4G's on low band (low-band 5G is 4G-like). The first version added every radio record's capacity (4G and 5G on the same sites counted twice) and gave 5G its mid-band efficiency on 600 MHz, so a player without mid-band lost nothing (target 2b 0%); fixed before tuning.
11. **Spectrum and licences.** Auctions are clock auctions resolved in their month; rivals' values are drawn then (stream telecom (1, auction id)) and never stored. A licence covers its area's population share of the region (a national licence in a multi-country region); its MHz count population-weighted. Renewal is automatic for a living company at `renewal_share`. China's spectrum is assigned administratively (no auctions for the player); Japan's comparative screening is treated as an auction (A).
12. **Bans.** A ban covers an area's share of the region x its scope; a vendor whose bans cover half a region is refused there; below that, its radios may be bought and owe replacement with the rest (the UK's ban touches 4.5% of Europe's networks). Rip-and-replace costs the radios x `ban.swap_mult` 1.3 (removal and integration, A against the UK's "at least GBP 2 billion", S). Sites owed and not replaced go dark. The US rip-and-replace programme's reimbursement is for providers with 2 million or fewer customers (S), so a national network gets none (`reimburse` 0).
13. **Acquired operators.** The player's own service lines need its networks; an operator the player acquires keeps its data network (no gate), a follow-up (modelling acquired networks).
14. **Facility opex** of the telecom kinds posts with phase 6's generic plant line ("Assembly plant operations", 5000), as charging networks' do; a label of its own is a follow-up.

## Follow-ups

(filled in by the agent)
