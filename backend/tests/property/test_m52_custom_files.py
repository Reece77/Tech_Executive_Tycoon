"""M52 sub-task 1's property test (ADR-0026, formulas.md 66.2): any valid custom spec
round-trips (write, read, canonicalise) to the same hash, and any field set outside its
`editor.*` range is refused."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tst import scenario_files as sf
from tst.loader import load_all
from tst.sim.modes import custom
from tst.sim.modes.custom_config import CustomScenario, Range

LOADED = load_all(DATA_DIR)
B, D = LOADED.balance, LOADED.game_data
ED = B.editor
INCUMBENTS = sorted(c.name for c in D.incumbents)
CATEGORIES = sorted(set(custom.editable_categories(B, D)) - custom.computed_markets(B))
BASES = [custom.from_historical(h) for h in D.historical] + [
    custom.blank(y, B, D) for y in (2008, 2010, 2026)
]


def _in(r: Range) -> st.SearchStrategy[float]:
    return st.floats(r.lo, r.hi, allow_nan=False)


@st.composite
def specs(draw: st.DrawFn) -> CustomScenario:
    base = draw(st.sampled_from(BASES))
    rivals = draw(
        st.dictionaries(
            st.sampled_from(INCUMBENTS),
            st.fixed_dictionaries(
                {
                    "present": st.booleans(),
                    "cash_mult": _in(ED.rival_cash_mult_range),
                    "quality_delta": _in(ED.rival_quality_range),
                }
            ),
            max_size=4,
        )
    )
    markets = draw(
        st.dictionaries(
            st.sampled_from(CATEGORIES),
            st.fixed_dictionaries(
                {
                    "market_mult": _in(ED.market_mult_range),
                    "growth_delta": _in(ED.growth_delta_range),
                }
            ),
            max_size=4,
        )
    )
    added = draw(st.lists(st.sampled_from(CATEGORIES), max_size=3, unique=True))
    world: dict[str, object] = {"eras": draw(st.sampled_from(["historical", "seeded"]))}
    if base.year >= ED.macro_from_year:
        world["confidence"] = draw(_in(ED.confidence))
        world["policy_rate_pct"] = draw(_in(ED.policy_rate_pct))
    raw = base.model_dump(mode="json")
    raw["cash_dollars"] = draw(st.integers(int(ED.cash_dollars.lo), int(ED.cash_dollars.hi)))
    raw["label"] = draw(
        st.text(min_size=1, max_size=40).filter(lambda t: t.strip() != "" and t.isprintable())
    )
    raw["overrides"] = {
        "company": {"name": draw(st.text(min_size=1, max_size=30).filter(str.isprintable))},
        "rivals": rivals,
        "markets": markets,
        "added_rivals": [{"category": c, "count": draw(st.integers(1, 5))} for c in added],
        "world": world,
        "rules": {
            "challenges": draw(
                st.lists(st.sampled_from(["bootstrapped", "hard_rivals"]), unique=True)
            )
        },
    }
    return CustomScenario.model_validate(raw)


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(specs())
def test_a_valid_spec_round_trips_to_the_same_hash(spec: CustomScenario) -> None:
    assert custom.refusals(spec, B, D) == []
    with tempfile.TemporaryDirectory() as tmp:
        sf.write(Path(tmp), spec, B, D, overwrite=False)
        back = sf.read(Path(tmp), spec.key, B, D)
        assert sf.sha256(back) == sf.sha256(spec)
        again = sf.parse(sf.canonical(back))
        assert sf.canonical(again) == sf.canonical(spec)


# (field label, how to set a value on a valid spec's raw dict, its range)
def _set_cash(raw: dict, v: float) -> None:
    raw["cash_dollars"] = int(v)


def _set_rival_cash(raw: dict, v: float) -> None:
    raw["overrides"]["rivals"] = {INCUMBENTS[0]: {"cash_mult": v}}


def _set_rival_quality(raw: dict, v: float) -> None:
    raw["overrides"]["rivals"] = {INCUMBENTS[0]: {"quality_delta": v}}


def _set_market(raw: dict, v: float) -> None:
    raw["overrides"]["markets"] = {CATEGORIES[0]: {"market_mult": v}}


def _set_growth(raw: dict, v: float) -> None:
    raw["overrides"]["markets"] = {CATEGORIES[0]: {"growth_delta": v}}


def _set_year(raw: dict, v: float) -> None:
    raw["year"] = int(v)


def _set_quality(raw: dict, v: float) -> None:
    raw["products"] = [{**raw["products"][0], "quality": v}]


def _set_lead(raw: dict, v: float) -> None:
    raw["research"] = [{"domain": "ai", "lead": v}]


def _set_added(raw: dict, v: float) -> None:
    raw["overrides"]["added_rivals"] = [{"category": CATEGORIES[0], "count": int(v)}]


FIELDS = [
    (_set_cash, ED.cash_dollars, True),
    (_set_rival_cash, ED.rival_cash_mult_range, False),
    (_set_rival_quality, ED.rival_quality_range, False),
    (_set_market, ED.market_mult_range, False),
    (_set_growth, ED.growth_delta_range, False),
    (_set_year, ED.start_years, True),
    (_set_lead, ED.research_lead, False),
    (_set_added, ED.added_rivals, True),
]


@settings(max_examples=80, deadline=None)
@given(
    st.sampled_from(range(len(FIELDS))),
    st.booleans(),
    st.floats(1e-6, 1e6, allow_nan=False),
)
def test_a_field_outside_its_range_is_refused(which: int, above: bool, by: float) -> None:
    setter, r, integer = FIELDS[which]
    value = r.hi + by if above else r.lo - by
    if integer:
        value = float(int(r.hi) + max(1, int(by))) if above else float(int(r.lo) - max(1, int(by)))
    if value < 0 and setter in (_set_cash, _set_added, _set_lead):
        value = r.hi + max(1.0, by)  # a negative count or amount is refused by the schema too
    raw = custom.from_historical(D.historical_scenario("ai_lab")).model_dump(mode="json")  # type: ignore[arg-type]
    raw["overrides"] = {}
    setter(raw, value)
    try:
        spec = sf.from_dict(raw)
    except sf.InvalidCustomScenarioError:
        return  # refused by the schema
    assert custom.refusals(spec, B, D), (setter.__name__, value)


@settings(max_examples=40, deadline=None)
@given(st.text(min_size=1, max_size=20).filter(lambda t: not t.isprintable()))
def test_a_control_character_in_a_name_is_refused(name: str) -> None:
    raw = custom.blank(2010, B, D).model_dump(mode="json")
    raw["overrides"] = {"company": {"name": name}}
    try:
        sf.from_dict(raw)
    except sf.InvalidCustomScenarioError as exc:
        assert "printable" in str(exc)
    else:
        raise AssertionError(repr(name))
