"""Loading and syncing M54's records (formulas.md 64; migration 0068_m54). Every collection of
`GameState.finserv` lives in `finserv_record` and every collection of `GameState.fx` in
`fx_record`, one row a record (`kind` = the state's field), its fields in `data`; a changed
collection is rewritten whole. Nested records (a bank's securities lots, stress results and runs,
an insurer's licences, the world's catastrophes) are encoded field by field; the fx walk and the
translation marks are one row each (packed), since they change together."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, is_dataclass, replace
from typing import Any, Final

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from tst.db.models import FinservRecordRow, FxRecordRow
from tst.sim.finserv.models import (
    Bank,
    BankMonth,
    Catastrophe,
    FinservState,
    FinservWorld,
    InsuranceMonth,
    Insurer,
    Licence,
    Network,
    PaymentsMonth,
    RunRecord,
    SecurityLot,
    StressResult,
)
from tst.sim.fx.models import FxHedge, FxMonth, FxState, HedgeProgramme, PriceMark
from tst.sim.state import GameState

STRIDE: Final = 1_000_000  # tunable-exempt: row numbers kind_index x STRIDE + position
# nested tuples of records: (class, field) -> the record class
NESTED: Final[dict[tuple[type, str], type]] = {
    (Bank, "securities"): SecurityLot,
    (Bank, "stress"): StressResult,
    (Bank, "runs"): RunRecord,
    (Insurer, "licences"): Licence,
    (FinservWorld, "cats"): Catastrophe,
}
FINSERV: Final[dict[str, type]] = {
    "banks": Bank,
    "networks": Network,
    "insurers": Insurer,
    "bank_months": BankMonth,
    "payments_months": PaymentsMonth,
    "insurance_months": InsuranceMonth,
}
FX: Final[dict[str, type]] = {
    "hedges": FxHedge,
    "programmes": HedgeProgramme,
    "months": FxMonth,
}
WORLD: Final = "finserv_world"
MARKS: Final = "marks"
WALK: Final = "walk"


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return encode(value)
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    return value


def encode(record: Any) -> dict[str, Any]:
    return {f.name: _plain(getattr(record, f.name)) for f in fields(record)}


def _tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tuple(v) for v in value)
    return value


def decode[T](cls: Callable[..., T], data: dict[str, Any]) -> T:
    out: dict[str, Any] = {}
    for f in fields(cls):  # type: ignore[arg-type]
        if f.name not in data:
            continue
        v = data[f.name]
        nested = NESTED.get((cls, f.name))  # type: ignore[arg-type]
        out[f.name] = tuple(decode(nested, x) for x in v) if nested else _tuple(v)
    return cls(**out)


def _sync(
    session: Session,
    model: Any,
    order: tuple[str, ...],
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    for i, kind in enumerate(order):
        if before[kind] == after[kind]:
            continue
        session.execute(delete(model).where(model.kind == kind))
        items = after[kind]
        if items:
            session.execute(
                insert(model),
                [{"n": i * STRIDE + j, "kind": kind, "data": x} for j, x in enumerate(items)],
            )


def _finserv_rows(fs: FinservState) -> dict[str, Any]:
    out: dict[str, Any] = {k: [encode(x) for x in getattr(fs, k)] for k in FINSERV}
    out[WORLD] = [encode(fs.world)] if fs.world != FinservWorld() else []
    return out


def _fx_rows(fx: FxState) -> dict[str, Any]:
    out: dict[str, Any] = {k: [encode(x) for x in getattr(fx, k)] for k in FX}
    packed = [[m.product_id, m.region, m.segment, m.price_cents, m.turn] for m in fx.marks]
    out[MARKS] = [{"v": packed}] if packed else []
    out[WALK] = [{"region": r, "v": list(w)} for r, w in fx.walk]
    return out


def load_finserv(
    session: Session, state: GameState, has_table: Callable[[Session, Any], bool]
) -> GameState:
    """Every finance and currency record (0068_m54); a save from before M54 has none."""
    if not has_table(session, FinservRecordRow):
        return state
    found: dict[str, list[Any]] = {k: [] for k in FINSERV}
    world = FinservWorld()
    for row in session.scalars(select(FinservRecordRow).order_by(FinservRecordRow.n)):
        if row.kind == WORLD:
            world = decode(FinservWorld, row.data)
        elif row.kind in found:
            found[row.kind].append(decode(FINSERV[row.kind], row.data))
    fs = FinservState(
        **{k: tuple(v) for k, v in found.items()},
        world=world,
    )
    fx_found: dict[str, list[Any]] = {k: [] for k in FX}
    marks: tuple[PriceMark, ...] = ()
    walk: list[tuple[str, tuple[int, ...]]] = []
    for fx_row in session.scalars(select(FxRecordRow).order_by(FxRecordRow.n)):
        if fx_row.kind == MARKS:
            marks = tuple(
                PriceMark(int(a), str(b), str(c), int(d), int(e))
                for a, b, c, d, e in fx_row.data["v"]
            )
        elif fx_row.kind == WALK:
            walk.append((str(fx_row.data["region"]), tuple(int(x) for x in fx_row.data["v"])))
        elif fx_row.kind in fx_found:
            fx_found[fx_row.kind].append(decode(FX[fx_row.kind], fx_row.data))
    fx = FxState(
        marks=marks,
        walk=tuple(walk),
        **{k: tuple(v) for k, v in fx_found.items()},
    )
    return replace(state, finserv=fs, fx=fx)


def sync_finserv(
    session: Session, old: GameState, new: GameState, has_table: Callable[[Session, Any], bool]
) -> None:
    if not has_table(session, FinservRecordRow):
        return
    if old.finserv != new.finserv:
        _sync(
            session,
            FinservRecordRow,
            (*FINSERV, WORLD),
            _finserv_rows(old.finserv),
            _finserv_rows(new.finserv),
        )
    if old.fx != new.fx:
        _sync(session, FxRecordRow, (*FX, MARKS, WALK), _fx_rows(old.fx), _fx_rows(new.fx))
