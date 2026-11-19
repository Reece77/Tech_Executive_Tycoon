"""Requirements, sourcing rules and controlled items (docs/formulas.md 57.3).

A bid meets a tender's requirements, or it is disqualified with the reasons named (57.2:
requirements are pass or fail, "technically acceptable"):

- the product is the bidder's, live, and in one of the area's categories;
- the government takes bids from the bidder's bloc (`open_to`), and, for a defence tender, the
  bidder supplies no militaries of a bloc it `refuses` (57.4);
- a classified tender (Secret or Top Secret) needs `clearances.required[level]` staff cleared
  at its level or above and a cleared facility; a classified cloud tender a data centre in the
  government's country;
- **component bans** (Section 889-style, from their month): no share of the product made in a
  listed country (its plants' and contract makers' countries, M22's `made_in`);
- **domestic content** (Buy American-style, stepping up on its dates): at least the rule's
  share made in the government's domestic countries; a product not in production this month
  cannot show it;
- **trusted foundry** (defence chips): every chip made in a listed trusted country.

**Controlled items** (ITAR-style): a product that delivers a defence contract in a controlled
area keeps `itar_keep[bloc]` of each country's demand by the country's bloc, and none in
`controlled_countries` (22 CFR 126.1). A product never in defence work is never controlled.
"""

from __future__ import annotations

from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.geopolitics import world
from tst.sim.government.data import PCT, area_of, company_bloc, domestic_countries, file
from tst.sim.government.models import Tender
from tst.sim.products.models import Product
from tst.sim.state import CompanyState, GameState

LEVEL_RANK: Final = {"none": 0, "secret": 1, "top_secret": 2}
LEVEL_LABEL: Final = {"none": "none", "secret": "Secret", "top_secret": "Top Secret"}
HARDWARE_AREAS: Final = ("devices", "chips", "space")
CLOUD: Final = "cloud"
CHIPS: Final = "chips"
DATA_CENTRE_PREFIX: Final = "data_centre"
WHOLE: Final = 0.999  # tunable-exempt: "every chip" allows float rounding
EPS: Final = 1e-9  # tunable-exempt: float tolerance


def cleared_staff(state: GameState, company_id: int, level: str) -> int:
    """Staff cleared at `level` or above, still employed by the company."""
    need = LEVEL_RANK[level]
    staff = {e.person_id for e in state.staff(company_id)}
    return sum(
        1
        for c in state.clearances
        if c.company_id == company_id
        and c.status == "cleared"
        and LEVEL_RANK[c.level] >= need
        and c.person_id in staff
    )


def cleared_facility(state: GameState, company_id: int) -> bool:
    live = {f.id for f in state.facilities if f.company_id == company_id}
    return any(
        f.company_id == company_id and f.status == "cleared" and f.facility_id in live
        for f in state.facility_clearances
    )


def defence_blocs(state: GameState, company_id: int) -> tuple[str, ...]:
    record = state.defence_record(company_id)
    return record.blocs if record is not None else ()


def _made_in(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> dict[str, float]:
    if not world.enabled(data):
        return {}
    from tst.sim.geopolitics.tariffs import made_in

    return made_in(state, product, balance, data)


def requirements(
    state: GameState,
    company: CompanyState,
    product: Product | None,
    tender: Tender,
    balance: Balance,
    data: GameData,
) -> tuple[str, ...]:
    """The requirements the bid does not meet (empty: it qualifies)."""
    f = file(data)
    gov = f.government(tender.government)
    out: list[str] = []
    if product is None or product.company_id != company.id or product.status != "live":
        return ("the product is not one of the company's live products",)
    if area_of(product, data) != tender.area:
        return (f"{product.name} does not serve the {tender.area} area",)
    turn = state.turn
    if world.enabled(data):
        bloc = company_bloc(state, company, balance, data)
        if bloc not in gov.open_to:
            out.append(f"{gov.label} does not take bids from {bloc.replace('_', '-')} companies")
        if tender.buyer == "defence" and (set(defence_blocs(state, company.id)) & set(gov.refuses)):
            out.append(f"{gov.label} will not buy from a supplier to its rivals' militaries")
    if tender.clearance != "none":
        need = balance.government.clearances.required.get(tender.clearance, 0)
        have = cleared_staff(state, company.id, tender.clearance)
        if have < need:
            out.append(
                f"needs {need} staff cleared at {LEVEL_LABEL[tender.clearance]} ({have} now)"
            )
        if not cleared_facility(state, company.id):
            out.append("needs a cleared facility")
        if tender.area == CLOUD and world.enabled(data):
            sites = [
                x
                for x in state.facilities
                if x.company_id == company.id
                and x.kind.startswith(DATA_CENTRE_PREFIX)
                and world.facility_country(state, x, data) == gov.country
            ]
            if not sites:
                out.append(f"needs a data centre in {gov.label} for classified cloud")
    made: dict[str, float] | None = None
    if tender.area in HARDWARE_AREAS:
        made = _made_in(state, product, balance, data)
    for ban in f.bans:
        if tender.government in ban.governments and turn >= ban.start_turn and made:
            share = sum(v for c, v in made.items() if c in ban.countries)
            if share > EPS:
                out.append(f"{ban.label}: {share * PCT:.0f}% made in a banned country")
    for rule in f.domestic_content:
        if tender.government not in rule.governments or tender.area not in rule.areas:
            continue
        need_share = rule.share_at(turn)
        if need_share <= 0:
            continue
        if not made:
            out.append("not in production this month: domestic content cannot be shown")
            continue
        dom = sum(v for c, v in made.items() if c in domestic_countries(gov))
        if dom + EPS < need_share:
            out.append(
                f"domestic content {dom * PCT:.0f}% is below the required {need_share * PCT:.0f}%"
            )
    tf = f.trusted_foundry
    if (
        tender.area == CHIPS
        and tender.buyer == "defence"
        and tender.government in tf.governments
        and turn >= tf.start_turn
    ):
        trusted = sum(v for c, v in (made or {}).items() if c in tf.countries)
        if trusted < WHOLE:
            out.append("chips must come from a trusted foundry")
    return tuple(out)


def controlled(state: GameState, product_id: int) -> bool:
    return any(c.product_id == product_id for c in state.controlled_products)


def itar_keep(
    state: GameState, product: Product, country: str, balance: Balance, data: GameData
) -> float:
    """The share of `country`'s demand a controlled product keeps (1 if not controlled)."""
    if not state.controlled_products or not controlled(state, product.id):
        return 1.0
    f = file(data)
    if country in f.controlled_countries:
        return 0.0
    home = world.company_country(state, state.company(product.company_id), balance, data)
    if country == home:
        return 1.0
    bloc = world.bloc_of(data, country, state.turn)
    return balance.government.itar_keep.get(bloc, 1.0)
