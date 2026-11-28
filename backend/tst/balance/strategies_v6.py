"""The v6 scripted strategies (M57 sub-task 4). Like the v1-v5 scripts they act only through
`Game.act`, so every rule applies, and they read only what a player sees (announced auctions and
their reserves, the build screens' rows, the bank's CET1 ratio and requirement, the leads on offer
as their shown ranges and fees), never a hidden draw. Their numbers describe the scripts, not the
game, so they live here rather than in balance.yaml.

- **telecom_operator** (62, M53): steady_regions and, from telecom's first month (`telecom.start`,
  2026), a mobile operator in its home region once it is stage 3 with cash to cover it: one bid
  at a time in each announced low- or mid-band auction there for an area and band it does not
  hold (as many blocks as cash covers twice over, up to the auction's cap, at a limit of 4x the
  reserve, which it pays only as far as rivals push the clock); with a licence, a mobile line at
  0.9x the reference price on a team of 20 and towers of the newest commercial generation on
  Ericsson radios in orders of 1,000 sites, one a year while cash covers one twice, to 75% of a
  national grid; a newer generation's radios on all its sites when one opens; once the mobile
  line is live, a fixed-broadband line (0.9x, a team of 20) and fibre in orders of 500,000 homes
  passed, one a year, to 5,000,000; devops crews for every tower, radio and fibre order.
- **bank_group** (64, M54): steady_regions and, from 2014 (`finserv.unlock_year`) once it is
  stage 3 with cash to cover it, a banking line at the reference price on a team of 8, its
  deposits held by a partner bank in the home region. After two years on the partner, and not
  before finance's first month (`finserv.start`, 2026), it applies for its own charter there once
  cash covers the fee, the opening capital and a quarter of the partner's deposits (the capital
  they will need and their growth while it waits), and puts in capital of 10% of those deposits
  while it applies. It sets the deposit beta to the middle of `bank.beta_range` and a
  conservative book (loans 40% of deposits, securities 50% at a two-year duration), and keeps
  CET1 between 1.1x and 1.5x its requirement: topped up to 1.25x from cash above a year of the
  company's costs, and capital above 1.5x brought back to the group.
- **media_studio** (65, M55): steady_regions and, from media's first month (`media.start`, 2026)
  once it is stage 3 with cash to cover it, a studio: every six months while fewer than four
  titles are in development it green-lights the next of a series, a film and a premium PC and
  console game at its kind's typical budget, licensed out, on a studio unit of six of its own,
  led by a free signed lead or else the open lead with the best shown creative and vision whose
  up-front share cash covers twice, signed for three years.
"""

from __future__ import annotations

from typing import Final

from tst.balance.game import PLAYER, Game
from tst.balance.strategies import Strategy, monthly_cost
from tst.balance.strategies_v2 import _unit, refill_energy, staff_unit, steady_regions
from tst.balance.strategies_v3 import _facilities, _mark, _product, _staff_plants, ready_for
from tst.sim.actions import AssignUnit, CreateProduct, SetPrice
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities import compute
from tst.sim.finserv import banks
from tst.sim.finserv.actions import ApplyCharter, BankCapital, PartnerBank, SetBank
from tst.sim.finserv.models import Bank
from tst.sim.media import talent, titles
from tst.sim.media.actions import GreenlightTitle, SignLead
from tst.sim.rng import RngFactory
from tst.sim.telecom import equipment as eq
from tst.sim.telecom import networks as nw
from tst.sim.telecom.actions import (
    AddRadios,
    BidSpectrum,
    BuildFibre,
    BuildTowers,
    generation_open,
)
from tst.sim.telecom.data import file as telecom_file

# --- A line on a team of its own ----------------------------------------------------------------


def _line(
    game: Game, spec: tuple[str, str, tuple[str, ...]], team: str, price: float = 1.0
) -> int | None:
    """Product `spec` (name, category, segments) at `price` x each segment's reference price,
    built by unit `team`; its id, or None if the rules refuse it."""
    name, category, segments = spec
    uid = _unit(game, team)
    if uid is None:
        return None
    pid = game.state.next_ids.product
    refill_energy(game)
    if not game.act(CreateProduct(game.founder_id, name, category, segments)):
        return None
    cat = game.loaded.game_data.category(category)
    for segment in segments:
        ref = cat.market(segment).reference_price_cents
        game.act(SetPrice(game.founder_id, pid, segment, round(ref * price)))
    game.act(AssignUnit(game.founder_id, pid, uid))
    _mark(game, category)
    return pid


def _live(game: Game, pid: int | None) -> bool:
    p = game.state.product(pid) if pid is not None else None
    return p is not None and p.status in ("live", "sunset")


def _home(game: Game) -> str:
    return compute.home_region_of(game.state, game.loaded.balance, game.loaded.game_data)


def _chunks(n: int, sizes: list[int]) -> list[int]:
    """`n` as orders of the kind's sizes, largest first (the last rounded up to the smallest)."""
    out = []
    left = n
    while left > 0:
        size = max((s for s in sizes if s <= left), default=min(sizes))
        out.append(size)
        left -= size
    return out


# --- telecom_operator ---------------------------------------------------------------------------

TELECOM_FROM: Final = ym_to_turn(2026, 1)  # telecom.start (checked in tests)
SPECTRUM_BANDS: Final = ("low", "mid")  # high band needs 25x the sites for the same coverage
BID_MULT: Final = (
    4.0  # a bid's limit a block x the reserve: well above what contested auctions clear at
)
MOBILE: Final = ("Volta Mobile", "mobile", ("telecom_consumer", "telecom_business"))
FIXED: Final = ("Volta Fibre", "fixed_broadband", ("telecom_consumer", "telecom_business"))
NETWORK_TEAM: Final = "Network team"  # builds the mobile and fixed lines
FIBRE_TEAM: Final = "Fibre team"
NETWORK_ROLE: Final = "devops_engineer"  # infrastructure weighs most in mobile's dev weights
NETWORK_STAFF: Final = 20  # in each line's team: the incumbents' lines are of quality 70-80
LINE_PRICE: Final = 0.9  # x the reference price, as the v5 lines (an entrant against incumbents)
CREW_ROLE: Final = "devops_engineer"  # the tower, radio and fibre kinds' staff role
GENERATIONS: Final = ("g6", "g5", "g4")  # newest first: towers carry the newest commercial one
VENDOR: Final = "ericsson"  # one vendor, banned nowhere in the scripts' regions
TOWER_ORDER: Final = 1_000  # sites an order
TOWER_TARGET: Final = 0.75  # of a national grid's sites: about 87% site coverage on low band
FIBRE_ORDER: Final = 500  # thousand homes passed an order
FIBRE_MAX: Final = 5_000  # thousand homes passed in all: about 40% of the home region's homes
BUILD_GAP: Final = 12  # months between a kind's orders


def _licences(game: Game, region: str) -> list[tuple[str, str]]:
    """The (area, band) of each licence the company holds in `region`."""
    return [
        (x.area, x.band)
        for x in game.state.telecom.licences
        if x.company_id == PLAYER and x.region == region and x.expires_turn > game.state.turn
    ]


def _bid(game: Game, region: str) -> None:
    """One bid at a time in an announced low- or mid-band auction in `region`: as many blocks as
    cash covers twice over at twice the reserve, up to the auction's cap."""
    state = game.state
    turn = state.turn
    open_ = [
        a
        for a in state.telecom.auctions
        if a.status == "announced" and a.turn > turn and a.region == region
    ]
    if any(a.bid_company_id == PLAYER and a.bid_blocks > 0 for a in open_):
        return
    held = set(_licences(game, region))
    f = telecom_file(game.loaded.game_data)
    cap_share = game.loaded.balance.telecom.auction.max_blocks_share
    for a in sorted(open_, key=lambda a: (a.turn, a.id)):
        area = f.region(a.region).area(a.area)
        if a.band not in SPECTRUM_BANDS or (a.area, a.band) in held or area is None:
            continue
        if area.method != "auction" or a.bid_company_id is not None:
            continue
        limit = round(a.reserve_cents * BID_MULT)
        cap = max(1, int(a.blocks * cap_share))
        blocks = min(cap, game.cash // (2 * limit))
        if blocks < 1 or not ready_for(game, blocks * limit):
            continue
        refill_energy(game)
        if game.act(BidSpectrum(game.founder_id, a.id, blocks, limit)):
            _mark(game, "bid")
            return


def _generation(game: Game) -> str | None:
    d = game.loaded.game_data
    return next((g for g in GENERATIONS if generation_open(game.state, g, d)), None)


def _site_cents(game: Game, generation: str) -> int:
    """A site's civil works and radios, as the build screen quotes them."""
    b, d = game.loaded.balance, game.loaded.game_data
    civil = eq.civil_exact(game.state, d)
    radio = eq.radio_exact(game.state, PLAYER, generation, VENDOR, b, d)
    return round(civil + radio)


def _towers(game: Game, region: str) -> None:
    """Towers to TOWER_TARGET of a national grid, an order a year; a newer generation's radios
    on its sites when one opens."""
    b, d = game.loaded.balance, game.loaded.game_data
    gen = _generation(game)
    if gen is None:
        return
    sites = nw.sites_in(game.state, PLAYER, region)
    full = telecom_file(d).region(region).sites_full * b.telecom.scale
    last = game.notes.get("towers_turn")
    due = last is None or game.state.turn - last >= BUILD_GAP
    cost = TOWER_ORDER * _site_cents(game, gen)
    if due and sites < TOWER_TARGET * full and ready_for(game, cost):
        refill_energy(game)
        if game.act(BuildTowers(game.founder_id, region, TOWER_ORDER, gen, VENDOR)):
            game.notes["towers_turn"] = game.state.turn
            _mark(game, "towers")
    # radios of a newer generation than the oldest towers carry, on the sites without them
    with_gen = sum(
        f.capacity
        for r in game.state.telecom.radios
        if r.company_id == PLAYER and r.region == region and r.generation == gen
        if (f := game.state.facility(r.facility_id)) is not None and f.status != "closed"
    )
    missing = sites - with_gen
    if missing <= 0 or f"radios:{gen}" in game.notes:
        return
    radio = eq.radio_exact(game.state, PLAYER, gen, VENDOR, b, d)
    if not ready_for(game, round(missing * radio)):
        return
    sizes = sorted(b.facility.kinds[b.telecom.radio_kind].sizes or b.facility.sizes)
    for size in _chunks(missing, sizes):
        refill_energy(game)
        game.act(AddRadios(game.founder_id, region, size, gen, VENDOR))
    game.notes[f"radios:{gen}"] = game.state.turn
    _mark(game, f"radios_{gen}")


def _fibre(game: Game, region: str) -> None:
    """A fixed-broadband line and fibre to FIBRE_MAX thousand homes, an order a year."""
    b = game.loaded.balance
    fid = _product(game, FIXED[1])
    if fid is None:
        fid = _line(game, FIXED, FIBRE_TEAM, LINE_PRICE)
        if fid is None:
            return
    staff_unit(game, FIBRE_TEAM, NETWORK_ROLE, NETWORK_STAFF)
    built = sum(f.capacity for f in _facilities(game, b.telecom.fibre_kind))
    last = game.notes.get("fibre_turn")
    if built >= FIBRE_MAX or (last is not None and game.state.turn - last < BUILD_GAP):
        return
    kind = b.facility.kinds[b.telecom.fibre_kind]
    if not ready_for(game, FIBRE_ORDER * kind.capex_per_unit_cents):
        return
    refill_energy(game)
    if game.act(BuildFibre(game.founder_id, region, FIBRE_ORDER)):
        game.notes["fibre_turn"] = game.state.turn
        _mark(game, "fibre")


def telecom_step(game: Game) -> None:
    """The operator in the home region from telecom's first month (module docstring)."""
    if game.state.turn < TELECOM_FROM:
        return
    b = game.loaded.balance
    region = _home(game)
    _bid(game, region)
    if not _licences(game, region):
        return
    _mark(game, "licence")
    pid = _product(game, MOBILE[1])
    if pid is None:
        pid = _line(game, MOBILE, NETWORK_TEAM, LINE_PRICE)
        if pid is None:
            return
    staff_unit(game, NETWORK_TEAM, NETWORK_ROLE, NETWORK_STAFF)
    _towers(game, region)
    for kind, label in (
        (b.telecom.tower_kind, "Tower crew"),
        (b.telecom.radio_kind, "Radio crew"),
        (b.telecom.fibre_kind, "Fibre crew"),
    ):
        _staff_plants(game, kind, CREW_ROLE, label)
    if _live(game, pid):
        _fibre(game, region)


def telecom_operator(game: Game) -> None:
    """steady_regions, then a mobile operator in its home region from 2026, and fibre."""
    steady_regions(game)
    telecom_step(game)


# --- bank_group ---------------------------------------------------------------------------------

BANK_FROM: Final = ym_to_turn(2014, 1)  # finserv.unlock_year (checked in tests)
BANK_LINE: Final = ("Volta Bank", "banking", ("bank_consumer", "bank_business"))
BANK_TEAM: Final = "Banking team"
BANK_ROLE: Final = "software_engineer"  # with finance, the banking line's heaviest dev weights
BANK_STAFF: Final = 8
BANK_CASH_CENTS: Final = 2_000_000_000  # $20M (x2, ready_for) before the banking line
PARTNER_MONTHS: Final = 24  # months on a partner bank before it applies for a charter ...
CHARTER_FROM: Final = ym_to_turn(
    2026, 1
)  # ... and not before finance's first month (finserv.start)
CAPITAL_SHARE: Final = 0.10  # opening capital, of the deposits it brings (M54's bank opens at 9%)
# cash before a charter, besides the fee and opening capital, as a share of the partner's
# deposits: the capital they need at 10%, and their growth while the application runs
CHARTER_COVER: Final = 0.25
CAPITAL_FLOOR: Final = 1.1  # CET1 kept at least this x the requirement ...
CAPITAL_TARGET: Final = 1.25  # ... topped up to (or brought back down to) this x ...
CAPITAL_RETURN: Final = 1.5  # ... and capital above this x comes back to the group
LOAN_TO_DEPOSIT: Final = 0.4  # a conservative book: loans (risk-weighted) under the default 0.7
SECURITIES_SHARE: Final = 0.5  # securities (0% risk weight) ...
DURATION: Final = 2.0  # ... of short duration, so a rate rise cannot start a run
KEEP_MONTHS: Final = 12  # months of the company's costs kept in cash before capital goes in


def _beta(game: Game) -> float:
    r = game.loaded.balance.finserv.bank.beta_range
    return (r.lo + r.hi) / 2


def _deposits(bank: Bank) -> int:
    return bank.consumer_deposits_cents + bank.business_deposits_cents


def _spare(game: Game) -> int:
    """Cash above KEEP_MONTHS of the company's costs."""
    return max(0, game.cash - KEEP_MONTHS * monthly_cost(game))


def _put(game: Game, bank: Bank, gap: int) -> None:
    amount = min(gap, _spare(game))
    if amount > 0:
        refill_energy(game)
        if game.act(BankCapital(game.founder_id, bank.id, amount)):
            _mark(game, "bank_capital")


def _capital(game: Game, bank_id: int) -> None:
    """Capital from the company's spare cash when CET1 falls below CAPITAL_FLOOR x the
    requirement (the bank screen's ratio and requirement), up to CAPITAL_TARGET x."""
    bank = game.state.finserv.bank(bank_id)
    if bank is None or bank.status != "chartered":
        return
    b, d = game.loaded.balance, game.loaded.game_data
    need = banks.requirement(bank, game.state.turn, d, b)
    ratio = banks.ratio(bank, d)
    target = round(CAPITAL_TARGET * need * banks.rwa_cents(bank, d))
    if ratio < CAPITAL_FLOOR * need:
        _put(game, bank, target - bank.equity_cents)
    elif ratio > CAPITAL_RETURN * need and not bank.restricted:
        floor = b.finserv.bank.charter_capital_cents
        back = min(bank.equity_cents - target, bank.reserves_cents, bank.equity_cents - floor)
        if back > 0:
            refill_energy(game)
            if game.act(BankCapital(game.founder_id, bank.id, -back)):
                _mark(game, "bank_dividend")


def bank_step(game: Game) -> None:
    """The banking line, its partner bank and then its own charter (module docstring)."""
    if game.state.turn < BANK_FROM:
        return
    bb = game.loaded.balance.finserv.bank
    pid = _product(game, BANK_LINE[1])
    if pid is None:
        if not ready_for(game, BANK_CASH_CENTS):
            return
        pid = _line(game, BANK_LINE, BANK_TEAM)
        if pid is None:
            return
    staff_unit(game, BANK_TEAM, BANK_ROLE, BANK_STAFF)
    region = _home(game)
    fs = game.state.finserv
    bank = fs.bank_in(PLAYER, region)
    if bank is None:
        refill_energy(game)
        if game.act(PartnerBank(game.founder_id, region)):
            game.notes["partner_turn"] = game.state.turn
            _mark(game, "partner")
        return
    own = next(
        (
            x
            for x in fs.banks
            if x.company_id == PLAYER
            and x.region == region
            and x.status in ("applying", "chartered")
        ),
        None,
    )
    partner = next(
        (
            x
            for x in fs.banks
            if x.company_id == PLAYER and x.region == region and x.status == "partner"
        ),
        None,
    )
    brings = round(CAPITAL_SHARE * _deposits(partner)) if partner is not None else 0
    if own is None:
        since = game.notes.get("partner_turn", game.state.turn)
        cover = round(CHARTER_COVER * _deposits(partner)) if partner is not None else 0
        need = bb.charter_fee_cents + bb.charter_capital_cents + cover
        if (
            _live(game, pid)
            and game.state.turn - since >= PARTNER_MONTHS
            and game.state.turn >= CHARTER_FROM
            and ready_for(game, need, cover=1.0)
        ):
            refill_energy(game)
            if game.act(ApplyCharter(game.founder_id, region)):
                _mark(game, "charter_applied")
        return
    if own.status == "applying" and own.equity_cents < brings:
        _put(game, own, brings - own.equity_cents)  # the capital its deposits will need
    if own.status == "chartered":
        _mark(game, "chartered")
    if "bank_set" not in game.notes:
        refill_energy(game)
        if game.act(
            SetBank(
                game.founder_id,
                own.id,
                _beta(game),
                LOAN_TO_DEPOSIT,
                SECURITIES_SHARE,
                DURATION,
            )
        ):
            game.notes["bank_set"] = game.state.turn
    _capital(game, own.id)


def bank_group(game: Game) -> None:
    """steady_regions, then a banking line on a partner bank from 2014 and its own charter."""
    steady_regions(game)
    bank_step(game)


# --- media_studio -------------------------------------------------------------------------------

MEDIA_FROM: Final = ym_to_turn(2026, 1)  # media.start (checked in tests)
STUDIO_CASH_CENTS: Final = 2_000_000_000  # $20M (x2, ready_for) before each green light
TITLE_GAP: Final = 6  # months between green lights
SLATE: Final = ("series", "film", "game")  # green-lit in turn
GAME_PLATFORMS: Final = ("pc", "console")  # a premium game's platforms
BUDGET_MULT: Final = 1.0  # x the kind's typical budget: a mid budget
MAX_IN_DEVELOPMENT: Final = 4  # titles in development at once
LEAD_YEARS: Final = 3  # an overall deal's years
STUDIO_TEAM: Final = "Studio"
STUDIO_ROLE: Final = "software_engineer"  # software engineering weighs most in the dev weights
STUDIO_STAFF: Final = 6


def _shown(game: Game) -> list[tuple[float, int, int, int]]:
    """The leads on offer as the studio screen shows them: (creative + vision centres, year, n,
    the deal's up-front cents for LEAD_YEARS)."""
    b, d = game.loaded.balance, game.loaded.game_data
    rng = RngFactory(game.state.save_meta.master_seed)
    out = []
    for o in game.state.media.offers:
        if o.status != "open":
            continue
        c = talent.candidate(o, rng, b, d)
        lo_c, hi_c = talent.shown_range(c.creative, c.creative_off, 0, b)
        lo_v, hi_v = talent.shown_range(c.vision, c.vision_off, 0, b)
        fee = talent.offer_fee_cents(c, b)
        upfront = round(fee * LEAD_YEARS * b.media.talent.upfront_share)
        out.append(((lo_c + hi_c + lo_v + hi_v) / 2, o.year, o.n, upfront))
    return out


def _free_lead(game: Game) -> int | None:
    busy = {t.lead_person_id for t in game.state.media.titles if t.stage == "development"}
    return next(
        (
            x.person_id
            for x in game.state.media.leads
            if x.company_id == PLAYER and x.person_id not in busy
        ),
        None,
    )


def _sign(game: Game) -> int | None:
    """The open lead with the best shown creative and vision whose up-front share cash covers
    twice; the person's id."""
    ranked = sorted(_shown(game), key=lambda x: (-x[0], x[1], x[2]))
    for _, year, n, upfront in ranked:
        if 2 * upfront > game.cash:
            continue
        before = {x.person_id for x in game.state.media.leads if x.company_id == PLAYER}
        refill_energy(game)
        if game.act(SignLead(game.founder_id, year, n, LEAD_YEARS)):
            new = [
                x.person_id
                for x in game.state.media.leads
                if x.company_id == PLAYER and x.person_id not in before
            ]
            _mark(game, "lead")
            return new[0] if new else None
    return None


def studio_step(game: Game) -> None:
    """A title every TITLE_GAP months from media's first month (module docstring)."""
    if game.state.turn < MEDIA_FROM:
        return
    mine = [t for t in game.state.media.titles if t.company_id == PLAYER]
    if mine:
        staff_unit(game, STUDIO_TEAM, STUDIO_ROLE, STUDIO_STAFF)
    if sum(1 for t in mine if t.stage == "development") >= MAX_IN_DEVELOPMENT:
        return
    last = game.notes.get("greenlight_turn")
    if last is not None and game.state.turn - last < TITLE_GAP:
        return
    if not ready_for(game, STUDIO_CASH_CENTS):
        return
    b = game.loaded.balance
    kind = SLATE[len(mine) % len(SLATE)]
    budget = round(titles.typical_budget_cents(b.media.kind(kind), b) * BUDGET_MULT)
    if not ready_for(game, budget):
        return
    uid = staff_unit(game, STUDIO_TEAM, STUDIO_ROLE, STUDIO_STAFF)
    lead = _free_lead(game) or _sign(game)
    refill_energy(game)
    platforms = GAME_PLATFORMS if kind == titles.GAME else ()
    name = f"Volta {kind.title()} {len(mine) + 1}"
    if game.act(
        GreenlightTitle(
            game.founder_id,
            name,
            kind,
            budget,
            lead_person_id=lead,
            unit_id=uid,
            platforms=platforms,
        )
    ):
        game.notes["greenlight_turn"] = game.state.turn
        _mark(game, "title")


def media_studio(game: Game) -> None:
    """steady_regions, then a studio licensing its titles out from 2026."""
    steady_regions(game)
    studio_step(game)


V6: Final[dict[str, Strategy]] = {
    "telecom_operator": telecom_operator,
    "bank_group": bank_group,
    "media_studio": media_studio,
}
