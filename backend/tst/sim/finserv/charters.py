"""A bank's or insurer's charter moves with its line (M57r-A, review 10 item 17).

- **Integration** (28.5) folds an acquired rival's lines into the player's company. A rival's
  finance line has no charter record (its books are abstract), so a banking line arrives as a
  partner-bank programme (64.1: deposits held at a partner, no capital) in each region it serves
  where the acquirer has no bank, and an insurance line with active licences there (the acquirer
  capitalises the insurer, as for any licence: until then it is not solvent and writes nothing
  new). The player may then apply for its own charter.
- **An ordered sale** (48.3) of the player's banking or insurance line to a buyer takes the
  company's banks or insurer with it once no other line of the kind is left: the books leave the
  company (the difference to 4930, as a failure's do) and the records go.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.finserv import banks, insurance
from tst.sim.finserv.models import Bank, Insurer, Licence
from tst.sim.ledger import DISPOSAL, LedgerEntry, LedgerLine
from tst.sim.products.models import SELLING, Product
from tst.sim.state import GameState


def _regions(state: GameState, product: Product, home: str) -> list[str]:
    out = [home] if any(s.customers > 0 for s in state.segments_of(product.id)) else []
    out += [r.region for r in state.regional_segments_of(product.id) if r.customers > 0]
    return sorted(set(out))


def on_integrate(
    state: GameState, acquirer: int, products: list[Product], balance: Balance, data: GameData
) -> GameState:
    """Module docstring: the acquirer's partner banks and licences for the lines it folds in."""
    fb = balance.finserv
    home = home_region_of(state, balance, data)
    for p in products:
        if p.category == fb.banking_category:
            for region in _regions(state, p, home):
                if state.finserv.bank_in(acquirer, region) is not None:
                    continue
                bank = Bank(
                    id=state.finserv.next_id(),
                    company_id=acquirer,
                    region=region,
                    status="partner",
                    applied_turn=state.turn,
                    beta=fb.bank.default_beta,
                )
                fs = state.finserv
                state = replace(state, finserv=replace(fs, banks=(*fs.banks, bank)))
        elif p.category == fb.insurance_category:
            fs = state.finserv
            ins = fs.insurer_of(acquirer) or Insurer(id=fs.next_id(), company_id=acquirer)
            have = {x.region for x in ins.licences}
            new = tuple(
                Licence(region, "active", state.turn, state.turn)
                for region in _regions(state, p, home)
                if region not in have
            )
            if not new and fs.insurer_of(acquirer) is not None:
                continue
            ins = replace(ins, licences=(*ins.licences, *new))
            others = tuple(i for i in fs.insurers if i.company_id != acquirer)
            state = replace(state, finserv=replace(fs, insurers=(*others, ins)))
    return state


def _left(state: GameState, company_id: int, category: str) -> bool:
    return any(
        p.category == category and p.status in SELLING for p in state.company_products(company_id)
    )


def on_sale(
    state: GameState, seller: int, products: list[Product], balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """Module docstring: after the lines have moved to the buyer."""
    fb = balance.finserv
    kinds = {p.category for p in products}
    entries: list[LedgerEntry] = []
    fs = state.finserv
    if fb.banking_category in kinds and not _left(state, seller, fb.banking_category):
        kept = []
        for b in fs.banks:
            if b.company_id != seller or b.status == "failed":
                kept.append(b)
                continue
            if b.status == "chartered" or b.assets_cents or b.deposits_cents:
                lines = [
                    LedgerLine(banks.DEPOSITS, b.deposits_cents),
                    LedgerLine(banks.RESERVES, -b.reserves_cents),
                    LedgerLine(banks.LOANS, -b.loans_cents),
                    LedgerLine(banks.SECURITIES, -b.securities_cents),
                    LedgerLine(DISPOSAL, b.assets_cents - b.deposits_cents),
                ]
                rows = tuple(x for x in lines if x.amount)
                if rows:
                    entries.append(LedgerEntry(state.turn, seller, "Bank sold with its line", rows))
        fs = replace(fs, banks=tuple(kept))
    ins = fs.insurer_of(seller)
    if (
        ins is not None
        and fb.insurance_category in kinds
        and not _left(state, seller, fb.insurance_category)
    ):
        lines = [
            LedgerLine(insurance.RESERVES, ins.reserves_cents),
            LedgerLine(insurance.INVESTMENTS, -ins.investments_cents),
            LedgerLine(DISPOSAL, ins.investments_cents - ins.reserves_cents),
        ]
        rows = tuple(x for x in lines if x.amount)
        if rows:
            entries.append(LedgerEntry(state.turn, seller, "Insurer sold with its line", rows))
        fs = replace(fs, insurers=tuple(i for i in fs.insurers if i.company_id != seller))
    return replace(state, finserv=fs), entries
