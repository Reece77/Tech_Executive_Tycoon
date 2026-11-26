# ADR-0025: Currencies and hedging

**Status:** accepted (2026-11-25, product manager, from Reece's v6 decisions of 2026-11-21 and the backlog's currencies item) · **Milestone:** M54 · **Formulas:** §64.4

## Context

Every amount in the game is integer US cents (ADR-0003), and regional prices are US prices times a regional index (§19, M53's per-category `price_index`). Real groups earn in many currencies, and the dollar's moves change their reported revenue, costs and debts. Several data files hold fixed exchange rates for one purpose each (`regulation.fx`, `power.yaml`'s `fx`). v6 adds currencies as a system without breaking ADR-0003 or history.

## Decision

1. **The unit stays the US cent.** Every ledger amount, price and state field is integer US cents, as before. There are no multi-currency accounts.
2. **Each game region has a currency** (`fx_history.yaml`): north_america USD, europe EUR (GBP and CHF folded in by weight; A), east_asia a basket of CNY, JPY and KRW by GDP weight, south_asia INR, latin_america a basket of BRL and MXN. A region's **rate index** is its basket's US dollars per local unit this month divided by its January 2010 value (exact decimals, `Decimal` or rational, never float in money).
3. **Prices are set in local terms.** A regional price the player or a rival sets is fixed in local money, and its US-cent value each month is the price at setting × (index now / index at setting), rounded half-even to cents. Costs paid in a region (staff, facilities, power, local suppliers) move the same way. Revenue and costs are **translated**, not converted: no currency is held.
4. **History holds.** Before `fx.applies_from` (January 2026) rivals' pinned lines and their history are unchanged: their data are already in reported dollars. The player's regional lines translate from the start. A company that sells and spends only in North America plays exactly as before (the guard).
5. **Hedging** is a contract (`FxHedge`): a region, a notional in local terms, a term of 1–12 months and a forward index = spot index × (1 + home rate) / (1 + region rate) for the term, plus a spread. At settlement the gain or loss (notional × (forward − spot)) posts to an FX gain or loss line. Hedge accounting is not modelled: gains and losses go through the income statement in their month.
6. **Rates after 2025** are seeded: each region's index follows a mean-reverting walk around its real-rate drift (stream `fx`, keyed by region and month), with rare jumps (`fx.jump_*`).
7. **The fixed `fx` tables** in regulation and power keep their roles (converting dated fines and carbon prices); M54 does not rewrite them.

## Consequences

- The ledger, cash and every guard keep integer cents; the float-money guard covers the new code.
- A new account pair: FX gain and FX loss (non-operating), and the balance sheet's hedge assets and liabilities at fair value.
- Stream `fx` (75) in ADR-0013.
- Translation runs in the month's existing revenue and cost phases (one multiply per regional line), so turn time grows little.
