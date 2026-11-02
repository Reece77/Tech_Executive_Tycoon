"""The Org screen's structure guide (formulas.md 23.4, M10b): what departments, teams and
divisions do, with this company's live numbers: span of control and manager quality (13),
layer tax and cross-division factor (18.2), support coverage (18.4) and executive effects
(18.3). Seat effects are estimates from displayed ranges (18.8), as everywhere else."""

from __future__ import annotations

from collections import Counter

from tst.api.org_views import org_out
from tst.api.scaleup_views import scaleup_out
from tst.api.schemas.org import GuideSectionOut, StructureGuideOut
from tst.loader import LoadedData
from tst.sim.state import GameState

PCT = 100  # tunable-exempt: percent


def structure_guide(state: GameState, data: LoadedData) -> StructureGuideOut:
    b = data.balance
    org = org_out(state, state.player.id, data)
    scale = scaleup_out(state, data)
    units = [u for u in org.units if u.unit_id is not None]
    kinds = Counter(u.kind for u in units)
    over = [m for m in org.managers if m.over_span]
    labels = Counter(m.label for m in org.managers)
    sections = [
        GuideSectionOut(
            key="units",
            title="Departments and teams",
            text=(
                "Units group people under a leader. A team works on one product; a department "
                "holds teams. Members of a unit assigned to a product build, sell or market it "
                "by their role. Departments unlock at "
                f"{b.org.department_unlock_headcount} staff or once venture-backed."
            ),
            lines=[
                f"{org.headcount} staff in {kinds.get('department', 0)} departments and "
                f"{kinds.get('team', 0)} teams",
                "Departments are "
                + ("unlocked" if org.departments_unlocked else "not unlocked yet"),
            ],
        ),
        GuideSectionOut(
            key="span",
            title="Span of control and managers",
            text=(
                f"A manager handles {b.org.span_base} reports plus one for every "
                f"{b.org.span_per_leadership:g} points of leadership. Beyond that span, their "
                "reports lose output and morale. A good manager lifts their reports' morale; "
                "a poor one drags it down."
            ),
            lines=[
                f"{len(org.managers)} managers; {len(over)} over their span"
                + (f" ({', '.join(m.name for m in over[:3])})" if over else ""),
                *(f"{n} {label}" for label, n in sorted(labels.items())),
            ],
        ),
    ]
    if scale.in_play:
        deep = [d for d in scale.divisions if "layer tax" in d.effect_note]
        cross = scale.cross_division
        sections.append(
            GuideSectionOut(
                key="divisions",
                title="Divisions",
                text=(
                    "A division groups departments under a president. Central divisions share "
                    "corporate services; embedded ones run their own and work faster. Teams "
                    "three levels down pay a layer tax, and a product built across divisions "
                    "pays the cross-division factor."
                ),
                lines=[
                    f"{len(scale.divisions)} of {scale.max_divisions} divisions",
                    *(f"{d.name}: {d.effect_note}" for d in deep),
                    *(
                        f"{c.product_name}: output {c.output_effect_pct:+.1f}% across "
                        f"{', '.join(c.division_names)}. {c.fix}"
                        for c in cross
                    ),
                ],
            )
        )
        sections.append(
            GuideSectionOut(
                key="support",
                title="Support coverage",
                text=scale.support_rule,
                lines=[
                    f"{p.label}: {p.support_staff} of {p.needed} support staff; output "
                    f"{p.output_effect_pct:+.1f}%, morale {p.morale_effect:+.1f}"
                    for p in scale.support
                ],
            )
        )
        sections.append(
            GuideSectionOut(
                key="executives",
                title="Executives",
                text=(
                    "Each executive seat changes one part of the company; a vacant seat at "
                    "stage 3 costs a penalty. Effects are estimates from what you know."
                ),
                lines=[
                    f"{s.label}: {s.holder_name or 'vacant'}"
                    + (
                        f", {s.effect_label} {s.estimated_effect_pct:+.1f}% (est.)"
                        if s.estimated_effect_pct is not None
                        else ""
                    )
                    + (
                        f", {s.vacancy_penalty_pct:+.1f}% while vacant"
                        if s.holder_id is None and s.vacancy_penalty_pct is not None
                        else ""
                    )
                    for s in scale.seats
                ],
            )
        )
    return StructureGuideOut(sections=sections)
