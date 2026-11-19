# Economy-scale audit (M35a, sub-task 5)

Report only: no rule, formula or balance value changes with this document. Reece decides after his campaign. Written 2026-11-16 on `main` as of M36r.

**Tags.** **R** a repository figure (file and key cited). **W** an approximate public real-world figure, recalled and not re-verified for this audit; treat as ±10–20% unless stated. **E** an estimate computed here from repository data (method given; no simulation was run for this audit). All game money is in cents in the data; figures below are in dollars.

## 1. Findings in brief

1. The game runs **two money economies**. Unit prices and costs (salaries, rent, a SaaS seat, a phone, a wafer, a fab, a tool, a plant, a tonne of copper) are at real scale. **Tech-market volumes** (customers, users, units) and the **product lines** each incumbent sells are not, so tech revenues, and every value derived from them (valuations, acquisition prices, fines, regulatory turnover), sit at about **a tenth of real**: `economy_scale.money` = 0.0849 (R).
2. The heavy-industry chain (commodities, mines, refineries, wafers, foundry slots, power) is real scale on **both** sides: it pays real costs and sells into markets sized to real world supply. It is internally consistent.
3. The mismatch is at the seam: a leading-edge fab costs about 9–11× more **relative to the largest tech companies' revenue** than it does in reality, and once built it earns about as much as a fifth of the game's Apple.
4. Part of the 0.0849 is inflation: game revenue is in constant 2010 dollars, real 2025 revenue is nominal. In constant dollars the scale is about **0.125** (about 1/8).
5. Recommendation (§7): keep the two economies (option A), label them, and plan a tech-demand rescale (option C) only if the campaign shows the seam spoils play. Do not scale heavy industry down (option B).

## 2. The scale of each money domain

| Domain | Game figure | Basis (source) | Real comparator | Scale vs real |
| --- | --- | --- | --- | --- |
| **Company revenues** | Apple $39.6B, Microsoft with Azure $35.9B, Facebook $6.4B in 2025 | R: `balance.yaml` `economy_scale.money` 0.0849 = mean of 0.0952, 0.1275, 0.0319; `tools/m34_economy_scale.py` (do-nothing games, seeds 1–3, booked revenue accounts 4000–4899 less intercompany, turns 180–191) | W (in R comments): Apple $416.2B (FY to Sep 2025), Microsoft $281.7B (FY to Jun 2025), Meta $200.97B (2025) | **0.085** nominal; **0.125** in 2010 dollars (§3) |
| Salaries | Software engineer mid-point $65k junior, $90k mid, $115k senior, $190k exec (San Francisco = 1.0, 2010 dollars, never inflated) | R: `roles.yaml` `software_engineer.salary_band_mid_cents`; `cities.yaml` `salary_multiplier_bp` | W: US software engineer about $120–150k in 2010–2020 (senior in San Francisco at the top) | **≈1.0** in 2010; ≈0.65–0.75 of 2025 nominal pay |
| Office rent | $600 a head a month × city `rent_index` (lease × 0.75); tools and travel $1,500 a head | R: `balance.yaml` `payroll.office_cost_per_head_cents` 60000, `office.lease_discount` 0.75, `costs.tools_per_head_cents` 150000 | W: San Francisco class A about $35–45 a sq ft a year in 2010 × about 200 sq ft a head ≈ $600–750 a month | **≈1.0** |
| Software prices | B2B SaaS seat $50 / $800 / $8,000 a month (SMB / mid / enterprise); Salesforce $65 / $900 / $9,000 | R: `categories.yaml` `b2b_saas.markets`, `incumbents.yaml` | W: Salesforce list prices 2010 about $65–250 **a user** a month; a game price is **a customer's** | **≈1.0** a seat; ≈0.2–1.0 a customer (a game SMB customer pays about one seat) |
| Cloud and compute | 1 CU = $1,000 a month on spot; general data centre $24,000 a CU capex, $250 a month opex | R: `balance.yaml` `compute.goods.compute_general.spot_cents` 100000, `facility.kinds.data_centre_general` | Abstract unit. Market size (§4): the cloud category's 2010 addressable is about real public IaaS | **≈1.0** (market); unit economics abstract, tuned by M12a |
| Fab capex | 5 nm, 50,000 starts: $16.9B before overrun, $16.9–21.2B measured | R: `nodes.yaml` `n5.capital_cents` 1569400 × 12 × 50,000 × `balance.yaml` `fab.capex_scale` 1.8; `balance-targets.md` M21 T2 | W: a 3 nm fab about $20B; TSMC Arizona Fab 1 $12B (R: v3 dossier) | **1.0** (nominal, CSET 2020 dollars) |
| Wafer prices | 16 nm $3,984, 7 nm $9,346, 5 nm $16,988, 3 nm $20,000, 2 nm $30,000 | R: `nodes.yaml` `wafer_cents` | W: same sources (CSET 2020, 2024–25 reports) | **1.0** (nominal) |
| Tool prices | Low-NA EUV $120.5M (2019) to $236.8M (2025); high-NA $380–400M | R: `equipment.yaml` EUV `price_cents` (ASML 20-F sales ÷ units × ECB rate); `nodes.yaml` `euv.tool_cents` | W: EUV about $180–200M (2023–24); high-NA about EUR 350M | **1.0** (nominal) |
| Plant capex | Gas CC $1,019/kW (2010); 1 GW nuclear $10–15B with overrun; × `capex_premium` 1.2 | R: `power.yaml` plant `capex` (deflated to 2010 dollars with `cpi`); `balance.yaml` `power.capex_premium`; M32 brief decision 16 | W: Lazard / NREL ATB | **1.0** (2010 dollars) |
| Grid and PPA prices | Grid $68/MWh × region index (2010, North America); PPA = forward × (1 − 0.005 × years, at most 0.08) | R: `balance.yaml` `refining.power_cents_per_mwh` 6800, `power.ppa`; ADR-0022 | W: EIA US industrial 6.77 ¢/kWh (2010) | **1.0** (2010 dollars) |
| Commodity prices | Copper 341.7 ¢/lb (2010), 440 (2025); every good history to 2025 | R: `commodities_history.yaml`; world supply in `chain_companies.yaml` `world_supply` | W: LME, USGS | **1.0** (nominal); volumes also real |
| Mines and refineries | Mine capex from the feasibility study ($25,000 a t/yr copper intensity); refinery capex a t/yr | R: `balance.yaml` `facility.kinds.*.capex_per_unit_cents`; §35.2 | W: dossier 6 | **1.0** |
| Acquisitions and valuations | Any company: ARR × multiple (bounds 1–30); listed rivals × sentiment; acqui-hire $150k a builder; diligence at least $50k | R: `balance.yaml` `public.multiple`, `finance.multiple_*`, `mna.min_value_per_builder_cents`; §28.1 | W: Apple market cap about $3.5–4T (late 2025) | **≈0.085** (follows revenue); game Apple about $200B at m ≈ 5 (E) |
| Chain-company valuations | A year's EBITDA × 7, less net debt | R: `balance.yaml` `world.ev_multiple` 7.0 | W: mining and materials EV/EBITDA 5–9 | **1.0** (their EBITDA is real scale) |
| Fines | 0.5–4% of global trailing-year turnover; thresholds and the $1B investigation floor × 0.0849 ($85M) | R: `balance.yaml` `regulation.fine.share`, `regulation.investigation.min_revenue_cents`, `economy_scale`; §48.1 | W: EU fines EUR 0.5–4.3B (2017–2025, in `regulation.yaml`) | **≈0.085** (a share of game turnover); lobbying $5M real (`regulation.lobby_cents`) |
| Estate | US exemption $5M (2010) to $15M (2026), 40% above it; trust set-up $500k; schooling $124k–348k; dynasty unit $1B | R: `balance.yaml` `estate_tax.north_america`, `family.trust_setup_cents`, `family.dynasty_unit_dollars` | W: IRS, OBBBA | **1.0** rules against **≈0.085** wealth (founder wealth is shares at game valuations) |
| Starting capital | $50k / $400k / $1.5M; v3 $5M; historical scenarios $1.5–40M; × difficulty 0.6–1.5 | R: `balance.yaml` `scenario.*.starting_cash_cents`, `scenarios.yaml` `cash_dollars`; §8a | W: savings, angel and seed rounds of 2010 | **1.0** |
| Funding and IPO gates | IPO at $80M ARR; Series C $80M, D $200M | R: `balance.yaml` `ipo.min_arr_cents`; balance-targets M10d notes | W: 2010s SaaS IPOs at about $100M+ ARR | **1.0** gates against game-scale revenue (tuned in M7a–M15a, so not a defect) |

## 3. The dollar basis

The game says its money is constant 2010 dollars with no inflation (R: `ipo.min_arr_cents` comment; `power.yaml` header). That holds for salaries, rents, software prices, the grid and plant capex, which M32 deflates with `power.yaml` `cpi` (2010 218.056, 2025 322.0: ×1.477). It does **not** hold for M17 commodity history, M21 wafer and fab capital, or M33 tool prices, which are nominal (CSET's 2020 dollars, ASML's 20-F in each year's dollars, LME nominal prices). Consequences:

- `economy_scale.money` compares 2010-dollar game revenue with nominal 2025 revenue, so it bundles about 1/1.48 of inflation: 0.0849 × 1.477 ≈ **0.125** in constant dollars. It is still the right factor for M34's use, because the thresholds it scales are nominal.
- By 2020–2025, nominal heavy-industry prices are about 1.2–1.48× dearer against 2010-dollar revenue and pay than a constant-dollar economy would make them. This is small next to the 8–12× volume gap, and changing it would move pre-2026 prices (§41.8 target 1), so it is noted, not proposed.

## 4. Why tech revenues come out at about a tenth of real

The unit prices are real (§2). The shortfall is in **how many** customers, users and units each market holds, **which** lines of business exist, and, for advertising, **revenue per user**.

**2010 market sizes (E):** turn-0 addressable demand × reference price × 12 (units markets: ÷ replacement months), over the seven regions (`categories.yaml` `regions`: size × price index, sum 2.24× North America). Served revenue is lower (incumbents' shares sum to at most 90%).

| Category (R: `categories.yaml`) | Game, 2010 | Real 2010 comparator (W) | Game ÷ real |
| --- | --- | --- | --- |
| B2B SaaS | $2.25B | SaaS about $10B; CRM about $9B | ≈0.2 |
| Developer tools | $0.83B | dev tools and ALM a few $B (low confidence) | ≈0.1–0.2 |
| Consumer apps | $0.54B | Facebook alone $1.97B, Zynga about $0.6B | <0.2 of two firms |
| Cybersecurity | $2.74B | security software about $16.5B | ≈0.17 |
| Fintech | $2.62B | PayPal $3.4B + Intuit $3.5B + Fiserv $4.1B (whole companies) | <0.25 |
| Cloud and GPU hosting | $6.71B | public IaaS a few $B (AWS about $0.5–1B) | **≈1 or above** |
| Devices | $8.23B | smartphones about $100B, PCs about $200B | ≈0.03 |
| Servers | $2.01B | about $49B (IDC) | ≈0.04 |
| Chips: mobile SoCs | $0.89B | Qualcomm's chip unit alone about $7B | ≈0.1 |
| Chips: server CPUs | $0.42B | Intel's data-centre group about $8.7B | ≈0.05 |
| Chips: AI accelerators | $0.18B | NVIDIA Tesla about $0.1B | ≈1–2 |
| Contract manufacturing | $0.70B | Foxconn alone about $95B | <0.01 (a spare-capacity market by design) |

**The three companies behind 0.0849:**

| Company | What it sells in the game (R: `incumbents.yaml`) | 2025, game ÷ real (R) | Main reasons (W for the real split) |
| --- | --- | --- | --- |
| Apple | iPhone only (devices: consumer $650, SMB $700) | 0.095 | Services (about $109B), Mac, iPad and wearables (together about half of real revenue) have no category; the devices market's unit volume is about 190M a year in 2025 (E, base growth, eras excluded) against about 1.2B phones, 260M PCs and 150M tablets; the unit price is about real |
| Microsoft + Azure | Team Foundation Server (developer tools) and Windows Azure (cloud) | 0.128 | Windows, Office and Microsoft 365, LinkedIn, Xbox and search have no category. Cloud is the one market near real scale, so this is the highest ratio |
| Meta | Facebook (consumer apps, $0.35 a user a month) | 0.032 | Revenue per user: $0.35 a month in 2010 dollars against about $4.8 a month in 2025 (W: $201B over about 3.5B daily people); advertising is not modelled as a market |

**Whole businesses absent:** search and advertising (Alphabet has only Google Cloud, an entrant: R `entrants.yaml`), e-commerce (Amazon is only AWS), operating-system and office licences, games, payments networks. Any real company whose core is one of these books a small fraction in the game.

**What is not the main cause:** unit prices (real a seat or a unit, §2; B2B prices a customer may be low by up to a few times, since a game customer pays about one seat); regions (seven, with Europe and East Asia shrunk to 0.55 and 0.45 of North America's demand in M10d, R `categories.yaml`; the shrink cost about 25% of foreign demand, not 90%); user tests (`economy_scale.users` 1.0, shares).

**Earlier evidence (R: `balance-targets.md`):** "funded companies plateau at about $45–57M ARR (v1 has one market per product line)" (M7a); "an AI-models company is about $7M ARR in 2020" (V3.ai); "subscriptions are 100% of the group's 2039 revenue and cost of goods 0.2–0.3%" (I1, M28).

## 5. What the mismatch does to play

The heavy-industry chain is consistent with itself: costs are real, and its outputs sell into real-scale markets (commodity spot and offtake at history prices; foundry slots against real world wafer capacity, `chain_companies.yaml` `world_supply`; surplus power to the grid). The tech economy is consistent with itself at about 1/10. The two meet where a tech company pays for, finances, owns or is compared with heavy industry.

**Worked example 1: a leading-edge fab against the largest companies.**

| | Fab capex | Revenue compared | Fab ÷ a year's revenue |
| --- | --- | --- | --- |
| Game | 5 nm 50k-start: $16.9–21.2B (R: M21 T2) | Apple 2025: $39.6B (R) | **43–54%** |
| Real | 3 nm fab about $20B (W) | Apple FY2025 $416.2B (R comment) | 4.8% |
| Real | same | TSMC 2023 $69.3B (W) | 29% |
| Real | same | NVIDIA FY2025 $130.5B (W) | 15% |

Relative to a top company's revenue, the fab is **9–11× dearer** in the game. A game-scale "Apple" spends more than a year's operating cash flow on one fab; real Apple could fund several a year.

**Worked example 2: an EUV tool and a nuclear unit against Microsoft.** One low-NA tool in 2025, $236.8M (R: `equipment.yaml`), is 0.66% of game Microsoft + Azure ($35.9B) against about 0.08% of real Microsoft (8×). A 1 GW nuclear unit, $10–15B (R: M32 decision 16), is 28–42% of game Microsoft's year against about 4–5% of real Microsoft's (and well under real Microsoft's FY2025 capex of about $88B including leases, W).

**Worked example 3: what the fab then earns (E).** Sold out as slots: 600,000 starts a year × $16,988 × `fab.slot.discount` 0.9 × `fab.slot.take` 0.85 ≈ **$7.8B a year** before the yield and reliability factors, about a fifth of game Apple's revenue and more than any game software incumbent. A foundry rival such as TSMC (17.4M wafers a year by 2025, R `nodes.yaml` capacity) books real-scale revenue from 2026 and is valued at 7× real-scale EBITDA, so it is worth more than the game's Apple (E: several hundred $B against about $200B), where real TSMC is about a third of Apple.

**Effects on play:**

- **The entry ticket is about 10× steeper** for a tech company moving down the chain: its cash, ARR-multiple valuation, rounds and loans are game scale; the fab, tools, plants and mines are real scale. Integration arrives later and rarer than in reality.
- **Once built, the chain dominates the group.** One fab or a few mines outweigh the software side in revenue, turnover and value, so a "tech conglomerate" becomes a commodity and foundry group with a software arm. M34's turnover thresholds (× 0.0849) are crossed by one fab's slot revenue.
- **Own supply barely moves margins.** The group's own chip, device and compute needs are game scale, a small share of one fab's output, so an own fab's 23–24% cheaper chip cannot move group margin (R: I1, M28 row).
- **Acquisitions are inconsistent across the seam.** Tech firms are priced at about a tenth of real (ARR × multiple); chain companies at real EV/EBITDA.
- **Estate rules are about 10× more generous** relative to wealth for estates near the exemption. For a billionaire founder the effect is negligible, since 40% applies to almost all of the estate either way.
- **Data centres are mostly unaffected.** Cloud demand is near real scale, and data-centre costs were tuned against spot in M12a.

## 6. Options

| | A. Two economies, labelled | B. Scale heavy industry down | C. Scale tech demand up |
| --- | --- | --- | --- |
| **What** | Keep both. Keep `economy_scale` for real-world thresholds (M34). Label every money screen "game economy" or "real prices" and show the game-equivalent beside heavy-industry quotes (fab capex as years of the player's revenue). | Multiply fab capex, wafer prices, tools, plant capex, grid and PPA prices, commodities and mine and refinery capex by about 0.085. | Raise customer, user and unit counts by category (about 3–30×, §4 table), raise consumer revenue per user, and add the missing big lines (search and ads, OS and office licences, e-commerce) as categories or incumbent products, so `economy_scale.money` moves toward 0.5–1. |
| **§41.8 target 1** (prices, capacities and dated events before 2026 identical) | Holds | **Fails**: every price before 2026 changes. Re-stating it as "identical × 0.085" changes how an earlier target is measured (CLAUDE.md §9: Reece's call). | Holds for prices, capacities and dated events (demand only). Target 7 (a software company's books identical before 2026) and the M28 state cache move: regenerate with a CHANGELOG reason. |
| **Earlier targets** | None move | M21 T2 ($15–25B → about $1.3–2.1B), M32 and M33 decisions 16 reversed; M20 margins (8%, wafers 14%) and M19 AISC ($1.5–3.0/lb) collapse because staff keep real salaries, unless salaries scale too, which moves every v1 target; the grid price feeds data centres, so v2 books and golden snapshots move | Every revenue-based band since M3: M3a ARR $0.5–4M, T5 bankruptcy and T8 ARR, rounds and the $80M IPO gate, M10d's region ratios, M13 P/S, M14 deal sizes, M16 and M23b group targets, `economy_scale` re-derived; golden snapshots regenerate. Shares-based tests (antitrust, platforms) hold. |
| **Cost** | Small: interface and docs | Large, and it breaks the real-data provenance of v3–v4 | Very large: a v5 balance milestone |
| **Fixes the seam?** | No; makes it visible | Yes for costs, but makes chain revenues game scale too, so the chain becomes small and the labour mismatch moves inside it | Yes, at the root: tech revenues, valuations and fines reach the chain's scale |

A fourth idea, applying C only from January 2026 so history holds, creates an unexplained jump in every market in one month; it is not recommended.

## 7. Recommendation

**Choose A now; hold C as the planned fix; reject B.** The two economies are each consistent, and real prices are valuable data provenance across v3 and v4. Labelling the seam costs little and moves no target. If Reece's campaign shows the integrator path is out of reach or pointless, for example a group at the game's Apple scale cannot finance a leading-edge fab by about 2030, or own supply never moves margins, schedule C as its own balance milestone, with every revenue band re-measured and the golden snapshots regenerated, keeping §41.8 target 1 intact. B should not be taken: labour is shared and real, so scaling the chain's money alone breaks its margins, and it rewrites history's prices.

## 8. Limits of this audit

- No game was run for this audit. In-game revenues are known only for Apple, Microsoft with Azure, and Facebook in 2025 (M34's tool). Game revenues of NVIDIA, Intel, AWS, TSMC (books only from 2026), Salesforce and the others over 2010–2025 are not recorded anywhere in the repository; `tools/m34_economy_scale.py` could be extended to print them.
- The 2010 and 2025 market sizes in §4 are addressable demand at reference prices with base growth only (era boosts and adoption excluded), not served revenue. The 2025 unit volumes are indicative.
- Real-world comparators marked W are from memory, not re-verified; 2010 sizes for developer tools, public IaaS and fintech are low confidence.
- The split of game Apple's $39.6B between device sales and platform fees (M31) was not established.
- Whether a game-scale player can actually finance a 5 nm fab (debt limits, chain-company leverage rules applied to the player) was not tested.

## 9. M43a note (2026-11-17)

M43a (formulas §54) gave every market a ceiling tied to its region's GDP and recalibrated 2025 on **served revenue** (Reece's ruling). What changed for this audit:

- **The runaway is closed.** The AI-models market's served revenue is about $270B real-dollar equivalent in 2025 (was $1.2-1.6T) and the largest money value in a dynasty run to 2069 is 1.48e16 cents (was 6.07e18). Technology served revenue peaks at 11.6% of world GDP (2039).
- **The two economies remain.** Tech revenues stay at `economy_scale.money` 0.0849 of real (the game's served sizes sit at 0.6-1.8x published once divided by it; servers moved up 7x, so game Dell and HP now book real-scale-equivalent server revenue). Heavy industry is untouched. The seam of §5 is unchanged: a leading-edge fab is still 9-11x dearer against the largest tech revenues than in reality.
- **Option C is still needed** if the integrator path should be affordable at real proportions: M43a made market sizes believable at the game's scale, it did not raise that scale. `economy_scale.money` was not re-derived (M34's key; Microsoft's Azure book moves with cloud's ceiling, so a re-derivation would now read lower than 0.0849; not measured).
