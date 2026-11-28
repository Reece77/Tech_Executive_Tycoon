"""The editor and custom scenarios (M52, formulas.md 66.1-66.2, ADR-0026): the Editor screen's
options, opening a start, checking, the scenario files (list, read, create, update, delete,
import, export), the preview and the background difficulty estimate. The files live in
`<saves>/scenarios/` (tst.scenario_files); nothing here reads or writes a save."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, status

from tst import scenario_files as sf
from tst import scenario_preview as pv
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.saves import ERRORS
from tst.api.schemas.editor import (
    CategoryOptionOut,
    CustomCardOut,
    CustomCheckOut,
    CustomImportIn,
    DifficultyOut,
    EditorOut,
    ExportOut,
    IncumbentOptionOut,
    NodeOptionOut,
    OptionOut,
    PreviewOut,
    RangeOut,
    RoleOptionOut,
    StartOptionOut,
)
from tst.loader import LoadedData
from tst.profile import results as kept
from tst.sim.calendar import format_turn, ym_to_turn
from tst.sim.errors import InvalidCustomScenarioError, NotFoundError
from tst.sim.modes import challenges, custom
from tst.sim.modes.custom_config import CustomScenario, Range

router = APIRouter(tags=["editor"])

BLANK_YEARS = (2008, 2010)  # 66.1: a blank start in M50's start years


def _ranges(loaded: LoadedData) -> dict[str, RangeOut]:
    ed = loaded.balance.editor
    out = {}
    for name in type(ed).model_fields:
        value = getattr(ed, name)
        if isinstance(value, Range):
            out[name] = RangeOut(lo=value.lo, hi=value.hi)
    return out


@router.get("/api/editor", response_model=EditorOut, operation_id="getEditor")
def get_editor(data: DataDep) -> EditorOut:
    """Every option the Editor screen offers: ranges, starts and the loaded data's lists (M54's
    and M55's categories and incumbents included, as data)."""
    from tst.sim.facilities.config import month_to_turn

    d, b = data.game_data, data.balance
    computed = custom.computed_markets(b)
    editable = set(custom.editable_categories(b, d))
    starts = [
        StartOptionOut(key=f"blank_{y}", label=f"A blank start, {y}", year=y) for y in BLANK_YEARS
    ]
    starts += [StartOptionOut(key=h.key, label=h.label, year=h.year) for h in d.historical]
    nodes = []
    if d.nodes is not None:
        for n in d.nodes.nodes:
            first = min(month_to_turn(m) for m in n.first.values())
            nodes.append(NodeOptionOut(key=n.key, label=n.label, first_year=2010 + first // 12))
    return EditorOut(
        ranges=_ranges(data),
        macro_from_year=b.editor.macro_from_year,
        starts=starts,
        backgrounds=[OptionOut(key=s.id, label=s.name) for s in d.scenarios if s.selectable],
        roles=[
            RoleOptionOut(key=r.key, label=r.label, levels=list(r.salary_band_mid_cents))
            for r in d.roles
        ],
        categories=[
            CategoryOptionOut(
                key=c.key,
                label=c.label,
                segments=list(c.segment_keys),
                market_editable=c.key not in computed,
            )
            for c in d.categories
            if c.key in editable
        ],
        incumbents=[
            IncumbentOptionOut(name=c.name, categories=sorted({p.category for p in c.products}))
            for c in d.incumbents
        ],
        domains=[OptionOut(key=x.key, label=x.label) for x in (d.tech.domains if d.tech else ())],
        lenders=[OptionOut(key=x.key, label=x.name) for x in d.lenders],
        nodes=nodes,
        regions=[OptionOut(key=r.key, label=r.label) for r in d.regions],
        cities=[OptionOut(key=c.key, label=c.label) for c in d.cities],
        commodities=[
            OptionOut(key=g.key, label=g.label)
            for g in (d.commodities.goods if d.commodities is not None else ())
        ],
        challenges=[OptionOut(key=r, label=challenges.LABELS[r][0]) for r in challenges.RULES],
        goal_kinds={k: list(v) for k, v in custom.GOAL_FIELDS.items()},
        lengths=["standard", "dynasty", "endless"],
    )


@router.get(
    "/api/editor/open/{start}",
    response_model=CustomScenario,
    responses=ERRORS,
    operation_id="openEditorStart",
)
def open_start(start: str, data: DataDep) -> CustomScenario:
    """A start to edit: `blank_<year>` or any scenarios.yaml entry (M51's included), with no
    overrides."""
    d, b = data.game_data, data.balance
    if start.startswith("blank_") and start[6:].isdigit():
        year = int(start[6:])
        if not b.editor.start_years.holds(year):
            raise InvalidCustomScenarioError(
                f"a start year is {b.editor.start_years.text()}, not {year}"
            )
        return custom.blank(year, b, d)
    h = d.historical_scenario(start)
    if h is None:
        raise NotFoundError(f"no scenario {start!r}")
    return custom.from_historical(h)


@router.post(
    "/api/editor/check", response_model=CustomCheckOut, responses=ERRORS, operation_id="checkCustom"
)
def check_custom(body: CustomScenario, data: DataDep) -> CustomCheckOut:
    """Every reason the editor refuses the spec (66.1), without saving it."""
    reasons = custom.refusals(body, data.balance, data.game_data)
    return CustomCheckOut(
        valid=not reasons, reasons=reasons, sha256=None if reasons else sf.sha256(body)
    )


# --- The files --------------------------------------------------------------------------------


def card(spec: CustomScenario, stored: dict[str, dict[str, dict[str, object]]]) -> CustomCardOut:
    from tst.api.routers.scenarios import result_out

    records = stored.get(kept.result_key(custom.custom_key(spec.key), sf.sha256(spec)), {})
    return CustomCardOut(
        slug=spec.key,
        label=spec.label,
        description=spec.description,
        year=spec.year,
        goal=spec.goal.text if spec.goal is not None else None,
        deadline_label=format_turn(ym_to_turn(*spec.deadline)) if spec.deadline else None,
        opened_from=spec.opened_from,
        sha256=sf.sha256(spec),
        played=len(records),
        best=result_out(kept.best(records)),
    )


def custom_cards(settings: SettingsDep, data: LoadedData) -> list[CustomCardOut]:
    """The Custom section (66.2): each custom scenario with its best result, from the custom
    results file (kept apart from M51's)."""
    save_dir = settings.resolved_save_dir()
    stored = kept.load(save_dir, custom=True)
    return [card(s, stored) for s in sf.list_specs(save_dir, data.balance, data.game_data)]


@router.get("/api/scenarios/custom", response_model=list[CustomCardOut], operation_id="listCustom")
def list_custom(settings: SettingsDep, data: DataDep) -> list[CustomCardOut]:
    return custom_cards(settings, data)


@router.get(
    "/api/scenarios/custom/{slug}",
    response_model=CustomScenario,
    responses=ERRORS,
    operation_id="getCustom",
)
def get_custom(slug: str, settings: SettingsDep, data: DataDep) -> CustomScenario:
    return sf.read(settings.resolved_save_dir(), slug, data.balance, data.game_data)


@router.post(
    "/api/scenarios/custom",
    response_model=CustomScenario,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    operation_id="createCustom",
)
def create_custom(body: CustomScenario, settings: SettingsDep, data: DataDep) -> CustomScenario:
    """Save (or save as) a new custom scenario; 409 if the name exists, 400 with every reason
    if refused."""
    return sf.write(
        settings.resolved_save_dir(), body, data.balance, data.game_data, overwrite=False
    )


@router.put(
    "/api/scenarios/custom/{slug}",
    response_model=CustomScenario,
    responses=ERRORS,
    operation_id="updateCustom",
)
def update_custom(
    slug: str, body: CustomScenario, settings: SettingsDep, data: DataDep
) -> CustomScenario:
    """Save over an existing custom scenario (its name is the route's)."""
    save_dir = settings.resolved_save_dir()
    sf.read(save_dir, slug, data.balance, data.game_data)  # 404 when it does not exist
    spec = body.model_copy(update={"key": sf.check_slug(slug)})
    return sf.write(save_dir, spec, data.balance, data.game_data, overwrite=True)


@router.delete(
    "/api/scenarios/custom/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
    operation_id="deleteCustom",
)
def delete_custom(slug: str, settings: SettingsDep) -> None:
    """Delete the file; games started from it keep their own copy (ADR-0026 point 4)."""
    sf.delete(settings.resolved_save_dir(), slug)


@router.post(
    "/api/scenarios/custom-import",
    response_model=CustomScenario,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    operation_id="importCustom",
)
def import_custom(body: CustomImportIn, settings: SettingsDep, data: DataDep) -> CustomScenario:
    """A shared file validated and saved; refused with every reason, nothing written."""
    return sf.import_text(
        settings.resolved_save_dir(),
        body.text,
        data.balance,
        data.game_data,
        slug=body.slug,
        overwrite=body.overwrite,
    )


@router.get(
    "/api/scenarios/custom/{slug}/export",
    response_model=ExportOut,
    responses=ERRORS,
    operation_id="exportCustom",
)
def export_custom(slug: str, settings: SettingsDep, data: DataDep) -> ExportOut:
    text = sf.export_text(settings.resolved_save_dir(), slug, data.balance, data.game_data)
    return ExportOut(filename=f"{slug}{sf.SUFFIX}", text=text)


# --- Preview and difficulty -------------------------------------------------------------------


@router.post(
    "/api/editor/preview", response_model=PreviewOut, responses=ERRORS, operation_id="previewCustom"
)
def preview_custom(body: CustomScenario, data: DataDep) -> PreviewOut:
    """The start month's summary (66.1): the world built to the start in memory (no turn is
    played, nothing is saved)."""
    spec = sf.validate(body, data.balance, data.game_data)
    return PreviewOut.model_validate(asdict(pv.preview(data, spec)))


def _job_out(job: pv.Job, data: LoadedData) -> DifficultyOut:
    return DifficultyOut(
        job_id=job.id,
        status=job.status,
        seeds=list(job.seeds),
        results=[asdict(r) for r in job.results],
        wins=job.wins,
        difficulty=job.difficulty(data),
        error=job.error,
    )


@router.post(
    "/api/editor/difficulty",
    response_model=DifficultyOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERRORS,
    operation_id="startDifficulty",
)
def start_difficulty(body: CustomScenario, data: DataDep) -> DifficultyOut:
    """Start (or rejoin) the difficulty estimate in the background (66.1)."""
    spec = sf.validate(body, data.balance, data.game_data)
    return _job_out(pv.start_job(data, spec), data)


@router.get(
    "/api/editor/difficulty/{job_id}",
    response_model=DifficultyOut,
    responses=ERRORS,
    operation_id="getDifficulty",
)
def get_difficulty(job_id: str, data: DataDep) -> DifficultyOut:
    job = pv.job(job_id)
    if job is None:
        raise NotFoundError(f"no difficulty estimate {job_id!r}")
    return _job_out(job, data)
