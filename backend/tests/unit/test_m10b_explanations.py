"""M10b explanations (docs/formulas.md 23.4): the product team's strength against its two
lines, the two slipping messages, the sales capacity message with numbers, and a summary and
reason to hire for every role."""

from __future__ import annotations

from tests.helpers import fresh_game, with_product
from tst.api.product_views import capacity_note, team_strength
from tst.loader import LoadedData
from tst.sim.log import LogItem
from tst.sim.products.phases import _slipping, builders_to_add
from tst.sim.products.team import Builder, Contributor, Team

SCOPE = 6.0  # b2b_saas


def _team(*outputs: float, sellers: int = 0) -> Team:
    return Team(
        unit_ids=(None,),
        builders=tuple(Builder(i, 10.0, o, False, False) for i, o in enumerate(outputs, 2)),
        sellers=tuple(Contributor(100 + i, 1.0) for i in range(sellers)),
        marketers=(),
    )


def _params(item: LogItem) -> dict[str, object]:
    return dict(item.params)


def test_builders_to_add() -> None:
    assert builders_to_add(1.1, 1, 1.5) == 1
    assert builders_to_add(1.0, 2, 6.0) == 10  # 0.5 a builder, 5 more output
    assert builders_to_add(2.0, 1, 1.5) == 0
    assert builders_to_add(0.0, 0, 1.5) == 1


def test_team_strength_names_both_lines(loaded: LoadedData) -> None:
    product = with_product(fresh_game(loaded)).company_products(1)[0]
    slow = team_strength(product, _team(1.1), SCOPE, loaded.balance)
    assert slow is not None and (slow.maintains, slow.full_speed) == (1.5, SCOPE)
    assert slow.text == (
        f"Output about 1.1 (est.). Below 1.5 {product.name} slips; full speed at 6. "
        "Add about 1 builder to stop the slide."
    )
    nobody = team_strength(product, _team(), SCOPE, loaded.balance)
    assert nobody is not None and nobody.text.startswith(f"Nobody is working on {product.name}")
    fine = team_strength(product, _team(2.0, 2.0), SCOPE, loaded.balance)
    assert fine is not None and fine.text.endswith("About 1 more builder reach full speed.")


def test_the_two_slipping_messages(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    product = with_product(fresh_game(loaded)).company_products(1)[0]
    nobody = _slipping(3, product, _team(), 0.0, SCOPE, pb)
    assert nobody.template == "product_rotting"
    small = _slipping(3, product, _team(1.1), 1.1, SCOPE, pb)
    assert small.template == "product_understaffed"
    assert _params(small) == {
        "product": product.name,
        "output": "1.1",
        "needed": "1.5",
        "full_speed": "6",
        "builders": "1 builder",
    }
    templates = loaded.game_data.inbox_templates
    assert "too small to maintain it" in templates["product_understaffed"].body


def test_the_capacity_note_has_numbers(loaded: LoadedData) -> None:
    seg = loaded.game_data.segment("mid_market")
    team = _team(sellers=2)
    note = capacity_note(team, seg, True, loaded.balance)
    cap = team.capacity("mid_market", loaded.balance)
    assert note == (
        f"2 sellers win up to about {cap:,.0f} Mid-market customers a month (est.), fewer than "
        f"wanted to buy. Each extra seller adds about {cap / 2:,.0f}."
    )
    assert capacity_note(team, seg, False, loaded.balance) is None
    body = loaded.game_data.inbox_templates["sales_capacity_limited"].body
    assert "{sellers} win up to about {cap}" in body and "{per_seller}" in body


def test_every_role_says_what_it_does_and_why_hire(loaded: LoadedData) -> None:
    for role in loaded.game_data.roles:
        assert len(role.summary) > 40 and len(role.why_hire) > 30, role.key
        assert role.why_hire.startswith("Hire one"), role.key


def test_the_guide_at_stage_3_adds_divisions_support_and_seats(loaded: LoadedData) -> None:
    from dataclasses import replace

    from tst.api.guide_views import structure_guide
    from tst.sim.state import with_company

    state = fresh_game(loaded)
    state = with_company(state, replace(state.player, stage=3))
    keys = [s.key for s in structure_guide(state, loaded).sections]
    assert keys == ["units", "span", "divisions", "support", "executives"]


def test_the_shown_team_uses_what_the_company_sees(loaded: LoadedData) -> None:
    """ADR-0007: the numbers shown come from the displayed ranges' midpoints and noticed tags,
    not true skills; the founder knows their own."""
    from tests.helpers import make_person, with_employee
    from tst.sim.org.rules import org_view
    from tst.sim.people.reveal import revealed_range
    from tst.sim.products import formulas as f
    from tst.sim.products.estimates import shown_team
    from tst.sim.products.phases import team_of

    state = with_product(fresh_game(loaded))
    state = with_employee(loaded, state, make_person(loaded, 2), 9_000_000)
    product = state.company_products(1)[0]
    category = loaded.game_data.category(product.category)
    team = team_of(state, org_view(state, 1), product, loaded.balance, loaded.game_data)
    shown = shown_team(state, 1, team, category, loaded.balance)
    for b, seen in zip(team.builders, shown.builders, strict=True):
        person = state.person(b.person_id)
        reveal = state.reveal(1, b.person_id)
        if person.is_founder or reveal is None:
            assert seen == b
            continue
        mids = {k: sum(revealed_range(person, reveal, k)) / 2 for k in person.skills.as_dict()}
        pb = loaded.balance.products
        ratio = (
            f.dev_skill(mids, category.dev_weights)
            * f.tag_multiplier([t for t, _ in reveal.revealed_tags], pb)
        ) / (
            f.dev_skill(person.skills.as_dict(), category.dev_weights)
            * f.tag_multiplier(person.tags, pb)
        )
        assert abs(seen.output - b.output * ratio) < 1e-9
