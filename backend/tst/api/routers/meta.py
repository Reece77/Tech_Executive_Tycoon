from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep
from tst.api.schemas.common import GlossaryOut
from tst.api.schemas.meta import (
    BackgroundOut,
    ChannelOut,
    FounderPreviewOut,
    FounderRulesOut,
    FounderSkillOut,
    HiringMetaOut,
    LabelOut,
    NewGameMetaOut,
    PresetOut,
    RoleOut,
    ScenarioOut,
    SkillMetaOut,
)
from tst.api.schemas.org import OrgMetaOut
from tst.api.schemas.products import ProductsMetaOut
from tst.api.schemas.saves import FounderIn
from tst.sim.actions.org import DEPARTMENT_STAGE, PROMOTION_LADDER
from tst.sim.data_models import DEFAULT_DIFFICULTY, DIFFICULTY_LEVELS
from tst.sim.hiring.formulas import energy_cost
from tst.sim.hiring.phases import ONE_BATCH
from tst.sim.org.models import PLAN_CHANNELS, UNIT_KINDS, WORK_POLICIES
from tst.sim.people.founder import preview_founder
from tst.sim.setup import MISSION_SIZE, starting_cash_cents

router = APIRouter(prefix="/api/meta", tags=["meta"])

CHANNEL_LABELS = {"network": "Network", "job_post": "Job post", "recruiter": "Recruiter"}


def _scenarios(data: DataDep) -> list[ScenarioOut]:
    return [
        ScenarioOut(
            id=s.id,
            name=s.name,
            description=s.description,
            available_in=s.available_in,
            selectable=s.selectable,
            starting_cash_cents=starting_cash_cents(data.balance, s.id, DEFAULT_DIFFICULTY),
            starting_cash_by_difficulty={
                d: starting_cash_cents(data.balance, s.id, d) for d in DIFFICULTY_LEVELS
            },
        )
        for s in data.game_data.scenarios
    ]


@router.get("/scenarios", response_model=list[ScenarioOut], operation_id="listScenarios")
def list_scenarios(data: DataDep) -> list[ScenarioOut]:
    return _scenarios(data)


@router.get("/new-game", response_model=NewGameMetaOut, operation_id="getNewGameMeta")
def new_game_meta(data: DataDep) -> NewGameMetaOut:
    """Everything the new-game setup screen needs (M1c)."""
    game, founder = data.game_data, data.balance.founder
    return NewGameMetaOut(
        scenarios=[s for s in _scenarios(data) if s.selectable],
        difficulties=list(DIFFICULTY_LEVELS),
        backgrounds=[
            BackgroundOut(
                key=b.key,
                label=b.label,
                description=b.description,
                available_in=b.available_in,
                selectable=b.selectable,
                bonuses=dict(b.bonuses),
                default_allocation=dict(b.default_allocation),
            )
            for b in game.backgrounds
        ],
        personality_presets=[
            PresetOut(key=p.key, label=p.label, description=p.description, values=dict(p.values))
            for p in game.personality_presets
        ],
        skills=[
            SkillMetaOut(key=s.key, label=s.label, short_label=s.short_label, group=s.group)
            for s in game.skills
        ],
        interests=[LabelOut(key=i.key, label=i.label) for i in game.interests],
        work_styles=[LabelOut(key=w.key, label=w.label) for w in game.work_styles],
        regions=[LabelOut(key=r.key, label=r.label) for r in game.regions],
        roles=[LabelOut(key=r.key, label=r.label) for r in game.roles],
        founder_rules=FounderRulesOut(
            skill_base=founder.skill_base,
            skill_points=founder.skill_points,
            skill_cap=founder.skill_cap,
            age_min=int(founder.age_range.lo),
            age_max=int(founder.age_range.hi),
            default_age=founder.default_age,
            default_region=founder.default_region,
            mission_size=MISSION_SIZE,
        ),
        cities=[
            LabelOut(key=c.key, label=f"{c.label} ({game.region(c.region).label})")
            for c in game.cities
        ],
        default_hq_city=data.balance.geo.default_hq_city,
    )


@router.get("/hiring", response_model=HiringMetaOut, operation_id="getHiringMeta")
def hiring_meta(data: DataDep) -> HiringMetaOut:
    """Channel costs, energy and offer limits for the Recruitment screen (M1c)."""
    hiring = data.balance.hiring
    channels = []
    for key, label in CHANNEL_LABELS.items():
        cfg = hiring.channel[key]
        channels.append(
            ChannelOut(
                key=key,
                label=label,
                energy=energy_cost(key, data.balance),
                monthly_cost_cents=hiring.job_post_cost_cents if key == "job_post" else 0,
                hire_fee_bp=hiring.recruiter_fee_bp if key == "recruiter" else 0,
                batch_min=int(cfg.size.lo),
                batch_max=int(cfg.size.hi),
                repeats=key not in ONE_BATCH,
                level_mix={k: int(v) for k, v in cfg.level_mix.items()},
            )
        )
    poach = data.balance.rivals.poach  # M5 (15.6): a rival's key people, one batch
    channels.append(
        ChannelOut(
            key="poach",
            label="Poach from a rival",
            energy=energy_cost("poach_search", data.balance),
            monthly_cost_cents=0,
            hire_fee_bp=0,
            batch_min=int(poach.candidates.lo),
            batch_max=int(poach.candidates.hi),
            repeats=False,
            level_mix={},
        )
    )
    morale = data.balance.morale
    return HiringMetaOut(
        channels=channels,
        roles=[
            RoleOut(
                key=r.key,
                label=r.label,
                primary_skills=list(r.primary),
                secondary_skills=list(r.secondary),
                product_function=r.product_function,
                summary=r.summary,
                why_hire=r.why_hire,
            )
            for r in data.game_data.roles
        ],
        interview_energy=energy_cost("interview", data.balance),
        reference_check_energy=energy_cost("reference_check", data.balance),
        offer_energy=energy_cost("offer", data.balance),
        max_offer_equity_bp=hiring.max_offer_equity_bp,
        lowball_ratio=hiring.lowball_ratio,
        candidate_shelf_turns=hiring.candidate_shelf_turns,
        fire_morale_penalty_min=int(
            min(abs(morale.fire_penalty), abs(morale.fire_penalty_culture_carrier))
        ),
        energy_per_month=data.balance.founder.energy_per_month,
    )


ORG_ACTION_ENERGY = (
    "create_unit",
    "dissolve_unit",
    "move_unit",
    "set_leader",
    "move_person",
    "set_policy",
    "give_raise",
    "promote",
    "hiring_plan",
    "appoint_executive",  # M8
    "remove_executive",
    "set_shared_services",
)


@router.get("/org", response_model=OrgMetaOut, operation_id="getOrgMeta")
def org_meta(data: DataDep) -> OrgMetaOut:
    """Energy costs, unlock rule and options for the org screens (formulas.md 6, 13)."""
    org, reorg = data.balance.org, data.balance.org.reorg
    return OrgMetaOut(
        energy_costs={key: energy_cost(key, data.balance) for key in ORG_ACTION_ENERGY}
        | {"set_authority": data.balance.exec_authority.change_energy},  # M10c (24.1)
        department_unlock_headcount=org.department_unlock_headcount,
        department_unlock_stage=DEPARTMENT_STAGE,
        unit_kinds=list(UNIT_KINDS),
        policies=list(WORK_POLICIES),
        plan_channels=list(PLAN_CHANNELS),
        max_ratio_bp=data.balance.delegates.max_ratio_bp,
        max_offer_equity_bp=data.balance.hiring.max_offer_equity_bp,
        delegate_energy_per_month=data.balance.delegates.energy_per_month,
        scout_energy=data.balance.delegates.scout_cost,
        raise_threshold_bp=org.raise_threshold_bp,
        raise_cooldown_turns=org.raise_cooldown_turns,
        raise_morale=org.raise_morale,
        pay_cut_morale=org.pay_cut_morale,
        promote_morale=org.promote_morale,
        reorg_morale={
            "move": reorg.move,
            "new_leader_members": reorg.new_leader_members,
            "replaced_leader": reorg.replaced_leader,
            "dissolve_members": reorg.dissolve_members,
        },
        promotion_levels=list(PROMOTION_LADDER),
    )


@router.post("/founder-preview", response_model=FounderPreviewOut, operation_id="previewFounder")
def founder_preview(body: FounderIn, data: DataDep) -> FounderPreviewOut:
    """Skill values, points left and every rule broken. Never current ability."""
    preview = preview_founder(body.to_spec(), data.game_data, data.balance)
    return FounderPreviewOut(
        skills=[
            FounderSkillOut(key=s.key, label=s.label, group=s.group, value=preview.skills[s.key])
            for s in data.game_data.skills
        ],
        points_spent=preview.points_spent,
        points_remaining=preview.points_remaining,
        errors=list(preview.problems),
    )


PRODUCT_ACTION_ENERGY = (
    "create_product",
    "set_price",
    "add_segment",
    "assign_unit",
    "unassign_unit",
    "set_marketing",
    "launch_product",
    "sunset_product",
    "cancel_product",
    "scout_search",
    "set_product_division",  # M8
)


@router.get("/products", response_model=ProductsMetaOut, operation_id="getProductsMeta")
def products_meta(data: DataDep) -> ProductsMetaOut:
    """Energy costs and launch thresholds for the product screens (formulas.md 6, 11.2)."""
    pb = data.balance.products
    return ProductsMetaOut(
        energy_costs={key: energy_cost(key, data.balance) for key in PRODUCT_ACTION_ENERGY},
        start_quality=pb.start_quality,
        launch_min_quality=pb.launch_min_quality,
        launch_min_feature=pb.launch_min_feature,
    )


@router.get("/glossary", response_model=GlossaryOut, operation_id="getGlossary")
def get_glossary(data: DataDep) -> GlossaryOut:
    """Definitions of every KPI label and table column header (M7b tooltips)."""
    return GlossaryOut(terms=data.glossary)
