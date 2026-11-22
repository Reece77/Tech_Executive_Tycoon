"""M43r findings 1 and 2 (Codex review 9): a founder who dies in January.

1. Payroll (phase 6) pays the founder who was alive at the time; the personal book must credit
   that person's salary after tax, before the estate settles (phase 10), so the final salary
   passes to the heir with the rest of the estate (formulas.md 32.2, 52.4).
2. The foundation passes to the heir (45.6); the save must hold exactly the foundation the
   turn's state holds, under the heir's id, with the endowment conserved (ADR-0004).

Both through the full turn on a save, then a cold reload."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tst.db import repository
from tst.db.models import SaveMetaRow
from tst.db.repository import create_save, open_session, run_turn
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.data_models import Balance
from tst.sim.dynasty.config import MortalityRule
from tst.sim.family import answers, rules
from tst.sim.family.setup import FamilySpec
from tst.sim.founder import foundation, personal
from tst.sim.hiring.formulas import monthly_salary_cents
from tst.sim.money import exact
from tst.sim.people.founder import FounderSpec
from tst.sim.state import GameState, family_member, with_employment, with_family_member

JAN_2040 = 360
FOUNDER_SALARY = 18_000_000  # $180,000 a year
HEIR_SALARY = 9_600_000  # $96,000 a year: a different amount, so a mix-up shows
ENDOWED = 50_000_000_00  # $50m given to the foundation


def _certain_death(b: Balance) -> Balance:
    m = MortalityRule.model_validate(
        {"from_age": 75, "by_age": {75: 1.0}, "wealth": 1.0, "stress": [1, 1], "family_time": 1.0}
    )
    return b.model_copy(update={"dynasty": b.dynasty.model_copy(update={"mortality": m})})


def _edit(path: Path, change):  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        after = change(before)
        sync_state(session, before, after)
        meta = session.get(SaveMetaRow, 1)
        assert meta is not None
        meta.current_turn = after.turn
    repository._LAST.clear()


def _cold(path: Path) -> GameState:
    repository._LAST.clear()
    with open_session(path) as session:
        return load_state(session)


def _setup(loaded: LoadedData, tmp_path: Path) -> tuple[Path, int, int]:
    path = create_save(
        "estate",
        3,
        "funded_spinout",
        company_name="Family Co",
        data=loaded,
        save_dir=tmp_path,
        founder=FounderSpec(background="engineer", age=50),  # 80 in January 2040
        family=FamilySpec("children", (26, 22)),
        length="dynasty",
    )
    b, data = loaded.balance, loaded.game_data
    ids: dict[str, int] = {}

    def prepare(state: GameState) -> GameState:
        state = replace(state, turn=JAN_2040)
        old = state.founder_of(state.player.id)
        assert old is not None
        heir = min(
            (m.person_id for m in rules.children(state)),
            key=lambda pid: state.person(pid).birth_turn,
        )
        m = family_member(state, heir)
        assert m is not None
        state = with_family_member(state, replace(m, closeness=90.0))
        person = state.person(heir)
        role = next(
            r.key for r in data.roles if r.founder_fit and rules.roles_match(person, r.key, data)
        )
        state, _ = answers.offer_job(state, heir, 1, role, "senior", b, data)
        job = state.employment_of(heir)
        assert job is not None and job.company_id == state.player.id
        state = with_employment(state, replace(job, salary_cents=HEIR_SALARY))
        own = state.employment_of(old.id)
        assert own is not None
        state = with_employment(state, replace(own, salary_cents=FOUNDER_SALARY))
        state = personal.credit(state, old.id, 10**12, "secondary", "Test cash")
        state, _ = foundation.create(state, old.id, "", "education", None, b, data)
        state, _ = foundation.give(state, old.id, ENDOWED)
        ids["old"], ids["heir"] = old.id, heir
        return state

    _edit(path, prepare)
    return path, ids["old"], ids["heir"]


def _net(b: Balance, annual: int) -> int:
    month = monthly_salary_cents(annual)
    return month - round(exact(month) * exact(b.personal.tax_rate))


def test_a_january_death_credits_the_payroll_founder_and_settles_after_it(
    loaded: LoadedData, tmp_path: Path
) -> None:
    path, old, heir = _setup(loaded, tmp_path)
    b = _certain_death(loaded.balance)
    result = run_turn(path, replace(loaded, balance=b))
    state = result.new_state
    founder = state.founder_of(state.player.id)
    assert founder is not None and founder.id == heir  # the death happened and the heir took over
    month = [e for e in state.personal_book if e.turn == JAN_2040]
    salaries = [e for e in month if e.source == "salary"]
    # Payroll paid the founder alive in phase 6 at the founder's salary, so the book credits
    # that person exactly that salary after tax, and nobody else a salary this month.
    assert [(e.person_id, e.lines[0].amount) for e in salaries] == [(old, _net(b, FOUNDER_SALARY))]
    # The estate settled after that salary: it passed to the heir, nothing is left behind.
    first_estate = next(i for i, e in enumerate(month) if e.source == "estate")
    assert month.index(salaries[0]) < first_estate
    assert personal.cash_cents(state, old) == 0
    cold = _cold(path)
    assert cold.personal_book == state.personal_book
    assert personal.cash_cents(cold, old) == 0


def test_an_inherited_foundation_survives_a_cold_reload_once(
    loaded: LoadedData, tmp_path: Path
) -> None:
    path, old, heir = _setup(loaded, tmp_path)
    before = _cold(path)
    endowed = personal.endowment_cents(before, old)
    assert endowed == ENDOWED
    result = run_turn(path, replace(loaded, balance=_certain_death(loaded.balance)))
    warm = result.new_state
    assert [f.person_id for f in warm.foundations] == [heir]
    cold = _cold(path)
    assert cold.foundations == warm.foundations  # one foundation, the heir's
    assert personal.endowment_cents(cold, heir) + personal.endowment_cents(cold, old) == endowed - (
        sum(f.grants_cents for f in warm.foundations)
    )
    assert personal.endowment_cents(cold, old) == 0
