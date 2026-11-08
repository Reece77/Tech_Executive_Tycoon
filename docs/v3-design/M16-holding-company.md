# M16 design draft: Holding company and subsidiaries (stage 5)

**Status: DESIGN DRAFT (2026-11-06).** Written ahead of the v2 retrospective so M16 can start without a gap. The brief and `docs/formulas.md` §31 are finalized against the code at `m15a-done` (as every brief has been). Builds on M14's kept brands (`parent_id`, own ledger, consolidation, cash sweep and funding, directives) and ADR-0020.

## The fantasy

The player stops running one company and starts running a **group**: an operating company per business (software, cloud, devices, chips, and in v3 mining and wafers), each with its own CEO, board, books and, if the player wants, outside shareholders. The player sits at the top as Chair of the holding company and steers through mandates, capital and people. Selling a stake, spinning a business off or listing a subsidiary become real choices with real trade-offs, not paperwork.

## 1. Becoming a holding company (stage 5)

- **Gate:** listed (stage 4) and either two or more subsidiaries (kept brands count) or group revenue of $2B or more a year.
- **Form a holding company** (a one-off action, energy 20, legal fees 0.1% of market cap): a new parent, "<Name> Holdings", takes the listing; the operating company and every kept brand become its subsidiaries. Shareholders swap one for one, so nobody's stake changes. The founder becomes the holding company's Chair; the operating company keeps its CEO (or the player appoints one).
- **Stage 5 screens:** a **Group** screen (an entity tree with ownership, mandate, CEO and KPIs per company), group-level consolidated statements with **segment reporting** by subsidiary, and the existing screens scoped to one company at a time through a company switcher.

## 2. Ownership and how it is accounted

| Stake held | Treatment | Accounts |
| --- | --- | --- |
| 50% or more (control) | Full consolidation; outside holders' share is **non-controlling interest** (NCI) | 3500 non-controlling interest; NCI's share of profit shown below net income |
| 20–50% (significant influence) | **Equity method**: the investment grows by the group's share of the company's profit, less dividends | 1820 investments in associates; 4900 share of associates' profit |
| Under 20% | **Financial investment** at fair value (market cap if listed, else the §28.1 value), marked each December | 1830 financial investments; 4910 fair-value gains and losses |

Intercompany balances and sales are eliminated on consolidation. Every treatment is tested by property tests (consolidated cash equals the sum of controlled companies' cash; NCI equals outside holders' share of net assets).

## 3. Subsidiaries as real companies

- **Cap table and board:** every subsidiary has its own cap table (parent, minority investors, an option pool for its staff) and a board (parent nominees, independents, a seat per 15% minority holder). A subsidiary with minorities must treat them fairly (§5).
- **CEO and mandate:** each subsidiary's CEO runs it under a **mandate** set by the parent (energy 3): growth, margin or cash return targets, a capex limit, and the categories and regions it may enter. The M13b pitch system lifts to group level: subsidiary CEOs pitch big moves to the holding company, judged against the mandate. Kept brands' directives become simple mandates.
- **Performance:** the subsidiary's board reviews its CEO each year against the mandate (§24's executive review); a missed mandate two years running prompts the board to propose a replacement.
- **Money:** dividends up the chain replace M14's sweep for companies with minorities (pro rata to every holder); 100%-owned subsidiaries keep the sweep and the parent's funding.

## 4. Capital actions

- **Sell a stake** in a subsidiary to investors (up to 49% keeps control): priced at its value with a private-company discount (`group.private_discount` 20%) unless listed.
- **Buy out minorities** at a premium (`group.buyout_premium` 25%).
- **Subsidiary IPO (carve-out):** list 10–40% of a subsidiary through M13's IPO chain; it gets its own share price, analysts and earnings, and the parent keeps control.
- **Spin-off:** give a subsidiary's shares to the holding company's shareholders; it becomes an independent listed rival (the player may keep up to 19.9%). Its people, products and facilities go with it.
- **Merge subsidiaries:** fold one into another, as M14's integration.
- **Minority stakes in others:** buy up to 49.9% of a listed rival on the market (price rises with the stake; a public disclosure event at 5%, 10% and 25%; at 30% the board must make an offer for the rest or stop), and **corporate venture** investments in startups' funding rounds (§15.4) for 5–25% stakes with information rights that reveal their key people and products as ranges.

## 5. Transfer prices and minorities

- Goods and services between group companies (chips to the devices subsidiary, compute from the cloud subsidiary, and in v3 wafers and minerals) move at a **transfer price** the holding company sets per flow: **cost**, **cost plus** a margin, or **market** (the market-good price).
- Inside 100%-owned companies it only moves profit around. Where a company has minorities, a price that favours the parent (more than `group.fairness_band` 10% from market) triggers a **minority complaint** event, then legal risk and a valuation discount for that subsidiary until it is corrected.
- (Tax by region arrives with M22's geopolitics; transfer prices are built to carry it.)

## 6. The conglomerate discount

A listed holding company trades at `group.conglomerate_discount` (10–25%, larger with more unrelated segments and less intra-group trade) below the sum of its parts, and the gap shrinks with intra-group synergy (internal supply, shared research). That gives spin-offs and carve-outs a real reason to exist, and rewards the vertical integration v3 is about. Analysts' notes name it.

## 7. Rivals

Incumbents with several businesses (for example Alphabet from 2015, Samsung's divisions) may be modelled as groups in v3 data, but rivals do not form holding companies, sell stakes or spin off in M16 (a follow-up).

## 8. Design for the rest of v3

- Facilities (mines, refineries, wafer plants, fabs) are owned by a subsidiary, so a mining or foundry business can be carved out or sold.
- M22's geopolitics will need **regional entities** (a subsidiary per bloc to comply with export rules and local ownership requirements); the entity model must allow a subsidiary to be registered in a region.
- Transfer prices carry M22's tax and tariff costs.

## 9. Targets (draft)

1. **Consolidation is right:** property tests on cash, NCI and eliminations; a group of three companies' consolidated statements equal hand-built ones in a worked example.
2. **Spin-offs and carve-outs pay sometimes:** with a 20% conglomerate discount, spinning off an unrelated subsidiary raises the founder's total value (stake in both) on 40–80% of seeds; spinning off a closely integrated one lowers it.
3. **Mandates matter:** a subsidiary under a growth mandate grows 20–60% faster than the same one under cash return, which returns 2–4× the cash.
4. **Minority fairness bites:** an unfair transfer price raises a complaint within 6 months on every seed.
5. **Nothing moves for a single company:** a game that never forms a holding company plays exactly as before.

## 10. Questions for Reece (defaults in brackets)

1. **Conglomerate discount:** include it [yes, 10–25%].
2. **Corporate venture investing** in startups' rounds: M16 or later [M16].
3. **Rivals as groups** (Alphabet, Samsung) that sell stakes and spin off: later [after M23].

## 11. Streams and accounts (draft)

Stream `group` (45), key: the company id or stable rival key (stake purchases' price impact, minority complaints, board reviews). Accounts 1820, 1830, 3500, 4900, 4910.
