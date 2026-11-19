"""Read and validate backend/data YAML (ADR-0008). Lives outside tst.sim on purpose.

Callers load once at startup and pass `Balance` and `GameData` into the sim.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from tst.advisor.config import ADVISOR_FILE, DEFAULT_ADVISOR, AdvisorConfig
from tst.mods.overlay import canonical_hash, merge
from tst.profile.data import ACHIEVEMENTS_FILE, AchievementDef, AchievementsFile
from tst.sim.commodities.config import (
    CommoditiesFile,
    CommoditiesHistoryFile,
    PowerHistoryFile,
    SuppliersFile,
)
from tst.sim.data_models import (
    INSTRUMENTS,
    MENTOR_TAG,
    ORG_TAGS,
    Account,
    BackgroundsFile,
    Balance,
    CategoriesFile,
    CitiesFile,
    ComputeIndexFile,
    EntrantsFile,
    GameData,
    InboxTemplatesFile,
    IncumbentsFile,
    InterestsFile,
    InvestorsFile,
    MacroHistory,
    NamesFile,
    PersonalityFile,
    RegionsFile,
    RolesFile,
    Scenario,
    SkillsFile,
    TagsFile,
)
from tst.sim.dynasty.frontier import with_slowdown
from tst.sim.dynasty.markets import with_maturity
from tst.sim.dynasty.nodes import with_successors
from tst.sim.equipment.config import EquipmentFile
from tst.sim.events.data import EventTemplate, EventTemplatesFile, template_problems
from tst.sim.exploration.config import GeologyFile
from tst.sim.fabs import nodes as nd
from tst.sim.fabs.config import NodesFile
from tst.sim.facilities.config import ComponentsHistoryFile
from tst.sim.founder.models import PERSONAL_ACCOUNTS, PERSONAL_PREFIX
from tst.sim.geopolitics.config import (
    BLOCS,
    CountriesFile,
    ExportControlsFile,
    TariffSchedule,
    TariffsFile,
)
from tst.sim.ledger import ENGINE_ACCOUNTS
from tst.sim.markets.longrun import with_long_run
from tst.sim.markets_public.config import BanksFile
from tst.sim.medical.config import MedicalFile
from tst.sim.mining.config import NationalizationHistory
from tst.sim.modes.config import HistoricalScenario
from tst.sim.org.voice_data import VoicesFile
from tst.sim.platforms.config import PlatformsFile
from tst.sim.power.config import PowerFile
from tst.sim.regulation.config import RegulationFile
from tst.sim.research.data import ErasFile, TechFrontierFile
from tst.sim.robotics.config import HUMANOID_SEGMENTS, INDUSTRIAL_SEGMENTS, RoboticsFile
from tst.sim.vehicles.config import LEVELS, VehiclesFile
from tst.sim.world.config import ChainCompaniesFile

POLY_TOLERANCE = 1e-9  # tunable-exempt: float tolerance
SHARE_TOLERANCE = 1e-6  # tunable-exempt: shares that split 1
FIRST_HISTORY_YEAR = 2010  # tunable-exempt: the game's first year
LAST_HISTORY_YEAR = 2025  # tunable-exempt: history holds to December 2025
CENTS_PER_DOLLAR = 100  # tunable-exempt: unit conversion
CELL_PRICE_TOLERANCE = (
    0.06  # tunable-exempt: battery_cells history is vehicles.yaml's to 0.1 dollar
)
BALANCE_FILE = "balance.yaml"
SCENARIOS_FILE = "scenarios.yaml"
ACCOUNTS_FILE = "accounts.yaml"
SKILLS_FILE = "skills.yaml"
PERSONALITY_FILE = "personality.yaml"
INTERESTS_FILE = "interests.yaml"
REGIONS_FILE = "regions.yaml"
ROLES_FILE = "roles.yaml"
TAGS_FILE = "tags.yaml"
BACKGROUNDS_FILE = "backgrounds.yaml"
NAMES_FILE = "names.yaml"
INBOX_FILE = "inbox_templates.yaml"
CATEGORIES_FILE = "categories.yaml"
INCUMBENTS_FILE = "incumbents.yaml"
INVESTORS_FILE = "investors.yaml"
MACRO_HISTORY_FILE = "macro_history.yaml"  # M10 (formulas.md 20.1); folds in climate.yaml
COMPUTE_INDEX_FILE = "compute_index.yaml"  # M8 (formulas.md 18.6)
ENTRANTS_FILE = "entrants.yaml"  # M8 (formulas.md 18.7)
CITIES_FILE = "cities.yaml"  # M9 (formulas.md 19.1)
COMPONENTS_FILE = "components_history.yaml"  # M12a (formulas.md 22.4)
TECH_FILE = "tech_frontier.yaml"  # M11 (formulas.md 21.1-21.3)
ERAS_FILE = "eras.yaml"  # M11 (formulas.md 21.4)
BANKS_FILE = "banks.yaml"  # M13 (formulas.md 25.2)
VOICES_FILE = "exec_voices.yaml"  # M13b (formulas.md 27.2)
COMMODITIES_FILE = "commodities.yaml"  # M17 (formulas.md 33.1)
COMMODITY_HISTORY_FILE = "commodities_history.yaml"  # M17 (formulas.md 33.1)
POWER_HISTORY_FILE = "power_history.yaml"  # M17 (formulas.md 33.5)
SUPPLIERS_FILE = "suppliers.yaml"  # M17 (formulas.md 33.4)
GEOLOGY_FILE = "geology.yaml"  # M18 (formulas.md 34.1)
NATIONALIZATION_FILE = "nationalization_history.yaml"  # M19 (formulas.md 35.4)
NODES_FILE = "nodes.yaml"  # M21 (formulas.md 38.1, 38.3)
COUNTRIES_FILE = "countries.yaml"  # M22 (formulas.md 39.1)
CONTROLS_FILE = "export_controls.yaml"  # M22 (39.2)
TARIFFS_FILE = "tariffs.yaml"  # M22 (39.3)
CHAIN_FILE = "chain_companies.yaml"  # M28 (formulas.md 41.1)
PLATFORMS_FILE = "platforms.yaml"  # M31 (formulas.md 44)
POWER_FILE = "power.yaml"  # M32 (formulas.md 46)
REGULATION_FILE = "regulation.yaml"  # M34 (formulas.md 48)
MEDICAL_FILE = "medical.yaml"  # M41 (formulas.md 50)
EQUIPMENT_FILE = "equipment.yaml"  # M33 (formulas.md 47)
VEHICLES_FILE = "vehicles.yaml"  # M38 (formulas.md 49)
ROBOTICS_FILE = "robotics.yaml"  # M39 (formulas.md 53)
EVENTS_DIR = "events"  # M6: event templates, one file per category (formulas.md 16.4)
DATA_FILES = (
    ACCOUNTS_FILE,
    BANKS_FILE,
    BACKGROUNDS_FILE,
    BALANCE_FILE,
    CATEGORIES_FILE,
    CHAIN_FILE,
    CITIES_FILE,
    COMMODITIES_FILE,
    COMMODITY_HISTORY_FILE,
    COMPONENTS_FILE,
    COMPUTE_INDEX_FILE,
    ENTRANTS_FILE,
    EQUIPMENT_FILE,
    ERAS_FILE,
    VOICES_FILE,
    GEOLOGY_FILE,
    INBOX_FILE,
    INCUMBENTS_FILE,
    INVESTORS_FILE,
    PLATFORMS_FILE,
    POWER_FILE,
    VEHICLES_FILE,
    ROBOTICS_FILE,
    REGULATION_FILE,
    MEDICAL_FILE,
    INTERESTS_FILE,
    MACRO_HISTORY_FILE,
    NATIONALIZATION_FILE,
    COUNTRIES_FILE,
    CONTROLS_FILE,
    TARIFFS_FILE,
    NAMES_FILE,
    NODES_FILE,
    PERSONALITY_FILE,
    POWER_HISTORY_FILE,
    REGIONS_FILE,
    ROLES_FILE,
    SCENARIOS_FILE,
    SKILLS_FILE,
    SUPPLIERS_FILE,
    TAGS_FILE,
    TECH_FILE,
)


class DataLoadError(Exception):
    """Seed or balance data is missing or invalid. Raised at startup, never mid-game."""


GLOSSARY_FILE = "glossary.yaml"  # UI definitions (M7b): not game data, so not hashed
GLOSSARY_TEXT_MAX = 320  # characters: one or two sentences in plain words


class GlossaryFile(BaseModel):
    """Term id -> definition for every KPI label and table column header (M7b)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    terms: dict[str, str]

    @model_validator(mode="after")
    def _check(self) -> GlossaryFile:
        for key, text in self.terms.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)?", key):
                raise ValueError(f"term {key!r}: lower-case words joined by _ (one optional .)")
            if not text.strip() or len(text) > GLOSSARY_TEXT_MAX:
                raise ValueError(f"term {key!r}: 1 to {GLOSSARY_TEXT_MAX} characters")
        return self


@dataclass(frozen=True, slots=True)
class LoadedData:
    balance: Balance
    game_data: GameData
    hashes: dict[str, str]  # file name -> SHA-256 hex digest (line endings normalized)
    glossary: dict[str, str] = field(default_factory=dict)  # M7b tooltips
    advisor: AdvisorConfig = DEFAULT_ADVISOR  # M25: the Explain panel and Ask why (unhashed)
    achievements: tuple[AchievementDef, ...] = ()  # M25: the profile's (unhashed)
    # M25 (section 3): the data-editor mod merged in, the hash of the merged data files and a
    # copy of the overlay; all None for the base data, which then loads exactly as before.
    mod_name: str | None = None
    mod_hash: str | None = None
    mod_overlay: dict[str, Any] | None = None


# libyaml's parser where PyYAML has it (its wheels do on every platform CI runs): the same
# documents as the pure-Python SafeLoader, about 10x faster (tests/unit/test_yaml_loader.py).
# Saving a mod validates every data file, and the pure parser had grown to most of that time.
_SAFE: type[yaml.SafeLoader] = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(text: str | bytes) -> Any:
    """yaml.safe_load with the C parser where available (identical results)."""
    return yaml.load(text, Loader=_SAFE)


class _UniqueKeyLoader(_SAFE):
    """SafeLoader that rejects duplicate mapping keys instead of silently keeping the last."""


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def file_hash(raw: bytes) -> str:
    """SHA-256 of a data file with CRLF normalized, so a Windows checkout hashes the same."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _read(path: Path) -> tuple[Any, bytes]:
    if not path.is_file():
        raise DataLoadError(f"{path.name}: file not found at {path}")
    raw = path.read_bytes()
    try:
        return yaml.load(raw, Loader=_UniqueKeyLoader), raw
    except yaml.YAMLError as exc:
        raise DataLoadError(f"{path.name}: invalid YAML: {exc}") from exc


def _validate[M: BaseModel](model: type[M], data: Any, file: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise DataLoadError(f"{file}: {details}") from exc


def _list_of(data: Any, key: str, file: str) -> list[Any]:
    if not isinstance(data, dict) or set(data) != {key}:
        raise DataLoadError(f"{file}: expected a single top-level key {key!r}")
    items = data[key]
    if not isinstance(items, list):
        raise DataLoadError(f"{file}: {key!r} must be a list")
    return items


def _check_against_balance(balance: Balance, data: GameData) -> None:
    """Checks that need both balance.yaml and the seed files."""
    regions = set(data.region_keys)
    if set(balance.people.region_weights) != regions:
        raise DataLoadError(
            f"{BALANCE_FILE}: people.region_weights must cover exactly {sorted(regions)}"
        )
    if balance.founder.default_region not in regions:
        raise DataLoadError(
            f"{BALANCE_FILE}: founder.default_region {balance.founder.default_region!r} "
            "is not in regions.yaml"
        )
    if data.cities and not data.has_city(balance.geo.default_hq_city):
        raise DataLoadError(
            f"{BALANCE_FILE}: geo.default_hq_city {balance.geo.default_hq_city!r} "
            "is not in cities.yaml"
        )
    tag_keys = {t.key for t in data.tags}
    missing_tags = sorted({*ORG_TAGS, MENTOR_TAG, *balance.relationships.tag_push} - tag_keys)
    if missing_tags:
        raise DataLoadError(f"{TAGS_FILE}: org rules need tags {missing_tags} (formulas.md 13)")
    sales = sorted(s.key for s in data.segments if s.reach == "sales")
    if sorted(balance.products.seller_rate) != sales:
        raise DataLoadError(
            f"{BALANCE_FILE}: products.seller_rate must cover exactly the sales segments {sales}"
        )
    missing_product_tags = sorted(set(balance.products.tag) - tag_keys)
    if missing_product_tags:
        raise DataLoadError(f"{TAGS_FILE}: product rules need tags {missing_product_tags} (11.10)")
    segment_keys = {s.key for s in data.segments}
    unknown_segments = sorted(set(balance.macro.confidence_segments) - segment_keys)
    if unknown_segments:  # M10 (20.1)
        raise DataLoadError(
            f"{BALANCE_FILE}: macro.confidence_segments {unknown_segments} are not segments"
        )
    for instrument in INSTRUMENTS:  # M10 (20.3): someone must lend each instrument
        if not any(lender.instrument == instrument for lender in data.lenders):
            raise DataLoadError(f"{INVESTORS_FILE}: no lender offers {instrument}")
    for scenario in data.scenarios:
        total = scenario.cap_table.total
        if total != balance.finance.initial_fd_shares:
            raise DataLoadError(
                f"{SCENARIOS_FILE}: {scenario.id!r} cap_table holds {total} shares, expected "
                f"finance.initial_fd_shares = {balance.finance.initial_fd_shares}"
            )
    if balance.board.director_role not in {r.key for r in data.roles}:
        raise DataLoadError(
            f"{BALANCE_FILE}: board.director_role {balance.board.director_role!r} "
            "is not in roles.yaml"
        )
    skills = set(data.skill_keys)  # M8 (formulas.md 18.3)
    for key, seat in balance.exec_seats.seats.items():
        if bad := sorted(set(seat.weights) - skills):
            raise DataLoadError(f"{BALANCE_FILE}: exec_seats.seats.{key} unknown skills {bad}")
    missing_mix = sorted({c.key for c in data.categories} - set(balance.rivals.function_mix))
    if missing_mix:
        raise DataLoadError(f"{BALANCE_FILE}: rivals.function_mix misses categories {missing_mix}")
    rv = balance.rivals  # M5 (formulas.md 15)
    roles = {r.key for r in data.roles}
    bad_roles = sorted(set(rv.function_roles.values()) - roles)
    if bad_roles:
        raise DataLoadError(f"{BALANCE_FILE}: rivals.function_roles {bad_roles} not in roles.yaml")
    cats = {c.key for c in data.categories}
    if set(rv.function_mix) != cats:
        raise DataLoadError(
            f"{BALANCE_FILE}: rivals.function_mix must cover exactly {sorted(cats)}"
        )
    for inc in data.incumbents:
        if inc.personality not in rv.weights:
            raise DataLoadError(
                f"{INCUMBENTS_FILE}: {inc.name!r} personality {inc.personality!r} is not one of "
                f"{sorted(rv.weights)}"
            )
    _check_facilities(balance, data)
    _check_conglomerate(balance, data)
    _check_family(balance, data)
    founder = balance.founder
    for bg in data.backgrounds:
        spent = sum(bg.default_allocation.values())
        if spent != founder.skill_points:
            raise DataLoadError(
                f"{BACKGROUNDS_FILE}: {bg.key!r} default_allocation spends {spent} points, "
                f"expected founder.skill_points = {founder.skill_points}"
            )
        if any(points < 0 for points in bg.default_allocation.values()):
            raise DataLoadError(f"{BACKGROUNDS_FILE}: {bg.key!r} allocates negative points")
        for skill in data.skill_keys:
            value = (
                founder.skill_base + bg.default_allocation.get(skill, 0) + bg.bonuses.get(skill, 0)
            )
            if value > founder.skill_cap:
                raise DataLoadError(
                    f"{BACKGROUNDS_FILE}: {bg.key!r} puts {skill} at {value}, "
                    f"above founder.skill_cap = {founder.skill_cap}"
                )


def _check_family(balance: Balance, data: GameData) -> None:
    """M36 (45.3, 45.6): estate tax for every region; the education and mentoring skills."""
    regions = set(data.region_keys)
    if set(balance.estate_tax) != regions:
        raise DataLoadError(f"{BALANCE_FILE}: estate_tax must cover exactly {sorted(regions)}")
    fb = balance.family
    named = {*fb.mentor_skills, *fb.education.mba_skills}
    for skills in fb.education.degree_skills.values():
        named.update(skills)
    unknown = sorted(named - set(data.skill_keys))
    if unknown:
        raise DataLoadError(f"{BALANCE_FILE}: family skills {unknown} are not in skills.yaml")


def _check_conglomerate(balance: Balance, data: GameData) -> None:
    """M43: every product category and facility kind is reported in an industry, and every
    account an industry lists is a revenue account."""
    where = f"{BALANCE_FILE}: conglomerate.industries"
    industries = balance.conglomerate.industries
    categories = {c for i in industries for c in i.categories}
    if missing := sorted({c.key for c in data.categories} - categories):
        raise DataLoadError(f"{where}: categories {missing} are in no industry")
    kinds = {k for i in industries for k in i.facility_kinds}
    if missing := sorted(set(balance.facility.kinds) - kinds):
        raise DataLoadError(f"{where}: facility kinds {missing} are in no industry")
    revenue = {a.code for a in data.accounts if a.type == "revenue"}
    if bad := sorted({a for i in industries for a in i.accounts} - revenue):
        raise DataLoadError(f"{where}: accounts {bad} are not revenue accounts")


def _check_facilities(balance: Balance, data: GameData) -> None:
    """M12a (formulas.md 22): facility kinds name known goods, roles and skills; the
    capacity market exists and is marked as one."""
    goods = {g.key for g in data.components.goods} if data.components else set()
    roles = {r.key for r in data.roles}
    for key, kind in balance.facility.kinds.items():
        where = f"{BALANCE_FILE}: facility.kinds.{key}"
        if kind.input_good not in goods:
            raise DataLoadError(
                f"{where}: input_good {kind.input_good!r} is not in {COMPONENTS_FILE}"
            )
        refined = {r.output_good for r in balance.refining.recipes.values() if r.kind == key}
        if (
            kind.generic
            and kind.output_good not in balance.compute.goods
            and kind.output_good != balance.hardware.output_good
            and kind.output_good not in refined  # M20: a refinery makes its recipe's good
            and key not in vehicle_kinds(balance)  # M38: cells and charging are 49's
            and key != balance.robotics.depot_kind  # M39: a depot serves robotaxis (53.3)
        ):
            raise DataLoadError(
                f"{where}: output_good {kind.output_good!r} is not in compute.goods"
            )
        if bad := sorted(set(kind.staff_roles) - roles):
            raise DataLoadError(f"{where}: staff_roles {bad} are not in {ROLES_FILE}")
        if kind.staff_skill not in data.skill_keys:
            raise DataLoadError(f"{where}: staff_skill {kind.staff_skill!r} is not a skill")
    _check_hardware(balance, data, goods)
    _check_commodities(balance, data)
    if problems := refining_problems(balance, data, goods, roles):
        raise DataLoadError(f"{BALANCE_FILE}: refining: " + "; ".join(problems))
    key = balance.compute.capacity_category
    capacity = [c.key for c in data.categories if c.capacity_market]
    if capacity != [key]:
        raise DataLoadError(
            f"{CATEGORIES_FILE}: the one capacity_market category must be compute.capacity_category"
            f" {key!r}, found {capacity}"
        )


def refining_problems(
    balance: Balance, data: GameData, components: set[str], roles: set[str]
) -> list[str]:
    """M20 (formulas.md 36): recipes run known refinery kinds on known goods; derived goods
    are priced off commodities; curbs name regions; the process domain exists."""
    rb = balance.refining
    problems: list[str] = []
    commodities = {g.key for g in data.commodities.goods} if data.commodities else set()
    known = commodities | set(rb.goods)
    for key, spec in rb.goods.items():
        if spec.source not in commodities:
            problems.append(f"goods.{key}: source {spec.source!r} is not a commodity")
        if spec.allocation_from is not None and spec.allocation_from not in components:
            problems.append(f"goods.{key}: allocation_from {spec.allocation_from!r} is unknown")
        poly = spec.priced_by == "divisor" and spec.source == "polysilicon"
        if poly and abs(spec.value - balance.commodity.semi_poly_multiple) > POLY_TOLERANCE:
            problems.append(f"goods.{key}: the divisor must be commodity.semi_poly_multiple")
    for key, r in rb.recipes.items():
        if r.kind not in balance.facility.kinds:
            problems.append(f"recipes.{key}: kind {r.kind!r} is not in facility.kinds")
        if r.output_good not in known:
            problems.append(f"recipes.{key}: output_good {r.output_good!r} is unknown")
        if r.input_good is not None and r.input_good not in known:
            problems.append(f"recipes.{key}: input_good {r.input_good!r} is unknown")
    for kind in rb.kinds:
        if (
            kind in balance.facility.kinds
            and not set(balance.facility.kinds[kind].staff_roles) <= roles
        ):
            problems.append(f"facility.kinds.{kind}: staff roles are unknown")
    regions = set(data.region_keys)
    if bad := sorted(set(rb.curb.monthly) - regions):
        problems.append(f"curb.monthly: unknown regions {bad}")
    if bad := sorted({c.region for c in rb.curb.history} - regions):
        problems.append(f"curb.history: unknown regions {bad}")
    if data.tech is not None and rb.domain not in {d.key for d in data.tech.domains}:
        problems.append(f"domain {rb.domain!r} is not in tech_frontier.yaml")
    return problems


def _check_commodities(balance: Balance, data: GameData) -> None:
    """M17 (formulas.md 33): the commodity files agree on the goods, in the same order; the
    mixes, volatilities and suppliers name known goods; power covers every region, in
    regions.yaml order; power is paid by known facility kinds."""
    if data.commodities is None or data.commodity_history is None:
        return
    keys = [g.key for g in data.commodities.goods]
    if [g.key for g in data.commodity_history.goods] != keys:
        raise DataLoadError(
            f"{COMMODITY_HISTORY_FILE}: goods must be {COMMODITIES_FILE}'s, in the same order"
        )
    cb = balance.commodity
    if sorted(cb.vol) != sorted(keys):
        raise DataLoadError(f"{BALANCE_FILE}: commodity.vol must cover exactly {keys}")
    components = {g.key for g in data.components.goods} if data.components else set()
    for good, mix in cb.mixes.items():
        if good not in components:
            raise DataLoadError(
                f"{BALANCE_FILE}: commodity.mixes.{good} is not in {COMPONENTS_FILE}"
            )
        if bad := sorted(set(mix.weights) - set(keys)):
            raise DataLoadError(f"{BALANCE_FILE}: commodity.mixes.{good} names {bad}")
    if data.power_history is not None:
        if [r.key for r in data.power_history.regions] != list(data.region_keys):
            raise DataLoadError(
                f"{POWER_HISTORY_FILE}: regions must be {REGIONS_FILE}'s, in the same order"
            )
        base = data.power_history.region(balance.power.base_region)
        if any(v != 1.0 for v, _ in base.years.values()):
            raise DataLoadError(f"{POWER_HISTORY_FILE}: the base region must be 1.0 every year")
    if bad := sorted(set(balance.power.paid_by) - set(balance.facility.kinds)):
        raise DataLoadError(f"{BALANCE_FILE}: power.paid_by names unknown kinds {bad}")
    if data.suppliers is not None:
        regions = set(data.region_keys)
        for s in data.suppliers.suppliers:
            if s.region not in regions:
                raise DataLoadError(f"{SUPPLIERS_FILE}: {s.key!r} region {s.region!r}")
            if bad := sorted(set(s.goods) - set(keys)):
                raise DataLoadError(f"{SUPPLIERS_FILE}: {s.key!r} sells unknown goods {bad}")
        for good in keys:
            if not any(good in s.goods for s in data.suppliers.suppliers):
                raise DataLoadError(f"{SUPPLIERS_FILE}: no supplier sells {good!r}")


def _check_hardware(balance: Balance, data: GameData, goods: set[str]) -> None:
    """M12b (formulas.md 26): hardware and chips name known goods, categories, chip types,
    cities and segments."""
    hw, ch = balance.hardware, balance.chips
    categories = {c.key: c for c in data.categories}
    where = f"{BALANCE_FILE}: hardware"
    if hw.plant_kind not in balance.facility.kinds:
        raise DataLoadError(f"{where}.plant_kind {hw.plant_kind!r} is not a facility kind")
    if balance.facility.kinds[hw.plant_kind].output_good != hw.output_good:
        raise DataLoadError(f"{where}.plant_kind must make hardware.output_good")
    market = categories.get(hw.capacity_category)
    if market is None or not market.assembly_market:
        raise DataLoadError(f"{where}.capacity_category must be an assembly_market category")
    if [c.key for c in data.categories if c.assembly_market] != [hw.capacity_category]:
        raise DataLoadError(f"{CATEGORIES_FILE}: one assembly_market category, {where}'s")
    for key, bom in hw.bom.items():
        cat = categories.get(key)
        if cat is None or not cat.sells_units or cat.family == "chips":
            raise DataLoadError(f"{where}.bom.{key}: not a unit-sale category (chips excluded)")
        if bom.good not in goods:
            raise DataLoadError(f"{where}.bom.{key}: good {bom.good!r} not in {COMPONENTS_FILE}")
        if bom.chip_type not in ch.types:
            raise DataLoadError(
                f"{where}.bom.{key}: chip_type {bom.chip_type!r} not in chips.types"
            )
    for cat in data.categories:
        if cat.sells_units and cat.family != "chips" and cat.key not in hw.bom:
            raise DataLoadError(f"{where}.bom: no bill of materials for {cat.key!r}")
        if cat.chip_type is not None and cat.chip_type not in ch.types:
            raise DataLoadError(f"{CATEGORIES_FILE}: {cat.key!r} chip_type not in chips.types")
        for seg, follows in (cat.growth_follows or {}).items():
            if bad := sorted(set(follows) - set(categories)):
                raise DataLoadError(f"{CATEGORIES_FILE}: {cat.key}.growth_follows.{seg} {bad}")
    if data.cities and hw.contract.cheap_city not in {c.key for c in data.cities}:
        raise DataLoadError(f"{where}.contract.cheap_city is not in {CITIES_FILE}")
    if ch.good not in goods:
        raise DataLoadError(f"{BALANCE_FILE}: chips.good {ch.good!r} not in {COMPONENTS_FILE}")
    chip_types = {c.chip_type for c in data.categories if c.chip_type is not None}
    if chip_types != set(ch.types):
        raise DataLoadError(f"{BALANCE_FILE}: chips.types must each have one chip category")
    for c in data.categories:
        if c.family == "chips" and ch.price_segment not in c.segment_keys:
            raise DataLoadError(f"{CATEGORIES_FILE}: {c.key!r} lacks chips.price_segment")


def geology_problems(balance: Balance, data: GameData) -> list[str]:
    """M18 (34.1): geology.yaml's regions are regions.yaml's, and the geologist role exists."""
    problems: list[str] = []
    if data.geology is None:
        return problems
    regions = set(data.region_keys)
    if set(data.geology.regions) != regions:
        problems.append(
            f"regions must be exactly regions.yaml's: missing "
            f"{sorted(regions - set(data.geology.regions))}, unknown "
            f"{sorted(set(data.geology.regions) - regions)}"
        )
    if balance.exploration.geologist_role not in {r.key for r in data.roles}:
        problems.append(
            f"exploration.geologist_role {balance.exploration.geologist_role!r} not in roles.yaml"
        )
    return problems


SPECIAL_DESTINATIONS: Final = ("all", "affiliates")  # export_controls.yaml `to` words (39.2)


def power_problems(balance: Balance, data: GameData) -> list[str]:
    """M32 (46): power.yaml covers every region in regions.yaml's order, names known countries
    and facility kinds, and balance power.* covers every plant type and region."""
    pf = data.power
    if pf is None:
        return []
    problems: list[str] = []
    if [r.key for r in pf.regions] != list(data.region_keys):
        problems.append(f"regions must be {REGIONS_FILE}'s, in the same order")
    if set(pf.others) != set(data.region_keys):
        problems.append("others must name every region")
    if bad := sorted(set(pf.draws) - set(balance.facility.kinds)):
        problems.append(f"draws name unknown facility kinds {bad}")
    if bad := sorted(set(balance.power.paid_by) - set(pf.draws)):
        problems.append(f"power.paid_by kinds {bad} need a draw")
    countries = {c.key for c in data.countries.countries} if data.countries else None
    if countries is not None:
        for p in pf.producers:
            if p.country not in countries:
                problems.append(f"producer {p.key}: unknown country {p.country!r}")
        for key, o in pf.others.items():
            if o.country not in countries:
                problems.append(f"others.{key}: unknown country {o.country!r}")
    if data.chain_companies is not None:
        taken = {c.key for c in data.chain_companies.companies}
        if clash := sorted(taken & {p.key for p in pf.producers}):
            problems.append(f"producer keys clash with {CHAIN_FILE}: {clash}")
    pb = balance.power
    types = {t.key for t in pf.plant_types}
    for name, table in (
        ("plants.overrun", pb.plants.overrun),
        ("plants.overrun_delay", pb.plants.overrun_delay),
        ("plants.learning", pb.plants.learning),
        ("plants.outages_a_year", pb.plants.outages_a_year),
        ("plants.outage_months", pb.plants.outage_months),
        ("plants.firm_share", pb.plants.firm_share),
        ("plants.load_share", pb.plants.load_share),
    ):
        if set(table) != types:
            problems.append(f"power.{name} must cover exactly {sorted(types)}")
    regions = set(data.region_keys)
    for name, rtable in (
        ("carbon.drift", pb.carbon.drift),
        ("carbon.start_rate", pb.carbon.start_rate),
        ("carbon.decarbonise", pb.carbon.decarbonise),
    ):
        if set(rtable) != regions:
            problems.append(f"power.{name} must cover exactly the regions")
    if pb.ppa.years.lo < 1:
        problems.append("power.ppa.years must be at least 1")
    return problems


def equipment_problems(balance: Balance, data: GameData) -> list[str]:
    """M33 (47): equipment.yaml's nodes, countries and suppliers are known; the programme's
    domain is a tech_frontier.yaml domain; `equipment.start` is the month after the history."""
    ef = data.equipment
    if ef is None:
        return []
    problems: list[str] = []
    if data.nodes is not None:
        known = set(data.nodes.node_keys())
        for g in ef.generations:
            if bad := sorted(set(g.nodes) - known):
                problems.append(f"generation {g.key}: unknown nodes {bad}")
    if data.countries is not None:
        countries = {c.key for c in data.countries.countries}
        named = {*ef.buyer_countries.values(), *(s.country for s in ef.suppliers)}
        named |= {c for rule in ef.controls for c in rule.to}
        if bad := sorted(named - countries):
            problems.append(f"unknown countries {bad}")
    if data.chain_companies is not None:
        makers = {s.key for s in ef.suppliers}
        if bad := sorted({m.key for m in data.chain_companies.equipment_makers} - makers):
            problems.append(f"chain_companies.yaml equipment_makers: not suppliers {bad}")
    if data.tech is not None and balance.equipment.programme.domain not in {
        d.key for d in data.tech.domains
    }:
        problems.append(f"programme domain {balance.equipment.programme.domain!r} is not a domain")
    if balance.equipment.start_turn != nd.HISTORY_END + 1:
        problems.append("equipment.start must be the month after the history (2026-01)")
    return problems


def platforms_problems(balance: Balance, data: GameData) -> list[str]:
    """M31 (44): platforms.yaml names known regions, categories and owners; every region has a
    share row for every year of the history; balance's app categories and segments exist."""
    pf = data.platforms
    if pf is None:
        return []
    problems: list[str] = []
    regions = set(data.region_keys)
    categories = {c.key: c for c in (*data.categories, *data.pseudo_categories)}
    owners = {c.name for c in data.incumbents}
    first, last = 2010, 2010 + pf.history_end_turn // 12
    for p in pf.platforms:
        if p.owner is not None and p.owner not in owners:
            problems.append(f"platform {p.key}: owner {p.owner!r} is not in incumbents.yaml")
        if p.regions and set(p.regions) - regions:
            problems.append(f"platform {p.key}: unknown regions")
        if set(p.first_party) - set(categories):
            problems.append(f"platform {p.key}: first_party names unknown categories")
    if set(pf.user_shares) != regions:
        problems.append(f"user_shares must list exactly the regions {sorted(regions)}")
    for region, years in pf.user_shares.items():
        if missing := sorted(set(range(first, last + 1)) - set(years)):
            problems.append(f"user_shares {region}: missing years {missing}")
    for rule in pf.fee_rules:
        if rule.region is not None and rule.region not in regions:
            problems.append(f"fee rule {rule.platform} {rule.from_}: unknown region")
    if set(pf.region_parts) - regions:
        problems.append("region_parts names unknown regions")
    for s in pf.standards:
        if s.category not in categories:
            problems.append(f"standard {s.key}: unknown category")
    pb = balance.platforms
    for key, app in pb.app_categories.items():
        if key not in categories:
            problems.append(f"platforms.app_categories: unknown category {key!r}")
        elif set(app.segments) - set(categories[key].segment_keys):
            problems.append(f"platforms.app_categories.{key}: unknown segments")
    if "os" not in categories or not categories["os"].pseudo:
        problems.append("categories.yaml needs the `os` pseudo-category")
    if pb.start_turn != pf.history_end_turn + 1:
        problems.append("platforms.start must be the month after platforms.yaml's history_end")
    return problems


def regulation_problems(balance: Balance, data: GameData) -> list[str]:
    """M34 (48): regulation.yaml names known regions, parts, companies, platforms and
    currencies; its history ends with platforms.yaml's; `regulation.start` is the month after."""
    rf = data.regulation
    if rf is None:
        return []
    problems: list[str] = []
    regions = set(data.region_keys)
    owners = {c.name for c in data.incumbents}
    parts = data.platforms.region_parts if data.platforms is not None else {}
    keys = {p.key for p in data.platforms.platforms} if data.platforms is not None else set()
    for r in rf.regulators:
        if r.region not in regions:
            problems.append(f"regulator {r.key}: unknown region {r.region!r}")
        elif r.part is not None and r.part not in parts.get(r.region, {}):
            problems.append(f"regulator {r.key}: unknown part {r.part!r} of {r.region}")
    for g in rf.regimes:
        if g.currency not in balance.regulation.fx:
            problems.append(f"regime {g.key}: currency {g.currency} has no regulation.fx rate")
    for d in rf.designations:
        if d.company is not None and d.company not in owners:
            problems.append(f"designation of {d.label}: {d.company!r} is not in incumbents.yaml")
        if d.platform is not None and d.platform not in keys:
            problems.append(f"designation of {d.label}: unknown platform {d.platform!r}")
    for c in rf.cases:
        if c.company is not None and c.company not in owners:
            problems.append(f"case {c.key}: {c.company!r} is not in incumbents.yaml")
        if c.currency not in balance.regulation.fx:
            problems.append(f"case {c.key}: currency {c.currency} has no regulation.fx rate")
    if data.platforms is not None and rf.history_end_turn != data.platforms.history_end_turn:
        problems.append("history_end must be platforms.yaml's")
    if balance.regulation.start_turn != rf.history_end_turn + 1:
        problems.append("regulation.start must be the month after regulation.yaml's history_end")
    return problems


def medical_problems(balance: Balance, data: GameData) -> list[str]:
    """M41 (50): medical.yaml's sub-categories are categories.yaml's family medical; routes,
    reliance and coverage name known health regulators and regions; history ends with the
    regulators' (regulation.yaml)."""
    mf = data.medical
    if mf is None:
        return []
    problems: list[str] = []
    rf = data.regulation
    health = {r.key: r for r in rf.health_regulators} if rf is not None else {}
    regions = set(data.region_keys)
    parts = data.platforms.region_parts if data.platforms is not None else {}
    for r in health.values():
        if r.region not in regions:
            problems.append(f"health regulator {r.key}: unknown region {r.region}")
        if r.part is not None and r.part not in parts.get(r.region, {}):
            problems.append(f"health regulator {r.key}: unknown part {r.part} of {r.region}")
    medical = {c.key for c in data.categories if c.medical}
    if missing := sorted(medical - {s.key for s in mf.subcategories}):
        problems.append(f"no sub-category for medical categories {missing}")
    for s in mf.subcategories:
        if s.key not in medical:
            problems.append(f"sub-category {s.key} is not a family medical category")
    for route in mf.routes:
        if route.regulator not in health:
            problems.append(f"route {route.key}: unknown health regulator {route.regulator}")
    for rel in mf.reliance:
        if rel.region not in regions:
            problems.append(f"reliance: unknown region {rel.region}")
        if bad := sorted(set(rel.relies_on) - set(health)):
            problems.append(f"reliance {rel.region}: unknown regulators {bad}")
    for cov in mf.coverage:
        if cov.region != "other" and cov.region not in regions:
            problems.append(f"coverage: unknown region {cov.region}")
    if rf is not None and mf.history_end != rf.history_end:
        problems.append("medical.yaml history_end must be regulation.yaml's")
    return problems


def world_problems(balance: Balance, data: GameData) -> list[str]:
    """M28 (41.1): every chain company is a supplier selling a commodity in December 2025 or a
    foundry, sits in a known country, and no good's named shares exceed 1 in any month."""
    from tst.sim.world.config import FOUNDRY_GOOD
    from tst.sim.world.data import named_shares

    chain = data.chain_companies
    if chain is None:
        return []
    problems: list[str] = []
    if data.suppliers is None or data.nodes is None or data.commodities is None:
        return ["needs suppliers.yaml, nodes.yaml and commodities.yaml"]
    if data.countries is None:
        return ["needs countries.yaml"]
    goods = {g.key for g in data.commodities.goods}
    foundries = {f.key for f in data.nodes.foundries}
    suppliers = {s.key for s in data.suppliers.suppliers}
    countries = {c.key for c in data.countries.countries}
    if bad := sorted(set(chain.world_supply) ^ goods):
        problems.append(f"world_supply must name exactly the commodities: {bad}")
    every = goods | {FOUNDRY_GOOD}
    for name, table in (
        ("demand_growth", chain.demand_growth),
        ("build_months", chain.build_months),
        ("others", chain.others),
    ):
        if bad := sorted(set(table) ^ every):
            problems.append(f"{name} must name every commodity and {FOUNDRY_GOOD}: {bad}")
    if bad := sorted(c.key for c in chain.companies if c.key not in suppliers | foundries):
        problems.append(f"companies that are neither suppliers nor foundries: {bad}")
    if bad := sorted(foundries - {c.key for c in chain.companies}):
        problems.append(f"foundries without an entry: {bad}")
    for c in chain.companies:
        country = c.country or data.countries.sites.get(c.key)
        if country is None or country not in countries:
            problems.append(f"{c.key}: no known country")
    if bad := sorted({o.country for o in chain.others.values()} - countries):
        problems.append(f"others in unknown countries: {bad}")
    from tst.sim.world.data import specs

    rivals = {c.name for c in data.incumbents} | {e.name for e in data.entrants}
    if bad := sorted(s.name for s in specs(data) if s.name in rivals):
        problems.append(f"chain companies named as rivals: {bad} (give them a name)")
    if bad := sorted(set(balance.world.groups.security_goods) - goods):
        problems.append(f"world.groups.security_goods not commodities: {bad}")
    for good in sorted(goods):
        for turn in range(0, balance.world.start_turn):
            if sum(named_shares(data, good, turn).values()) > 1.0 + 1e-9:
                problems.append(f"{good}: named shares above 1 in turn {turn}")
                break
    return problems


def geopolitics_problems(balance: Balance, data: GameData) -> list[str]:
    """M22 (formulas.md 39): countries cover every region and city; rules and tariffs name
    known actors, goods and destinations; controlled commodities exist."""
    if data.countries is None or data.controls is None or data.tariffs is None:
        return []
    gb = balance.geopolitics
    problems: list[str] = []
    countries = data.countries
    keys = {c.key for c in countries.countries}
    regions = set(data.region_keys)
    if bad := sorted({c.region for c in countries.countries} - regions):
        problems.append(f"countries in unknown regions {bad}")
    if missing := sorted(regions - {c.region for c in countries.countries}):
        problems.append(f"regions without countries {missing}")
    for city in data.cities:
        if city.country is None:
            problems.append(f"city {city.key}: no country")
        elif city.country not in keys:
            problems.append(f"city {city.key}: unknown country {city.country!r}")
        elif countries.country(city.country).region != city.region:
            problems.append(f"city {city.key}: {city.country} is not in {city.region}")
    sites = set(balance.hardware.contract.manufacturers) | set(balance.chips.contract.foundries)
    if data.suppliers is not None:
        sites |= {s.key for s in data.suppliers.suppliers}
    if bad := sorted(set(countries.sites) - sites):
        problems.append(f"sites: unknown suppliers {bad}")
    actors = keys | set(BLOCS)
    destinations = actors | set(SPECIAL_DESTINATIONS)
    commodities = {g.key for g in data.commodities.goods} if data.commodities else set()
    for key, good in gb.goods.items():
        if good.kind == "commodity" and good.commodity not in commodities:
            problems.append(f"goods.{key}: commodity {good.commodity!r} is unknown")
        if bad := sorted(set(good.chip_types) - set(balance.chips.types)):
            problems.append(f"goods.{key}: unknown chip types {bad}")
    for rule in (*data.controls.rules, *data.controls.seeded):
        if rule.actor not in actors:
            problems.append(f"rule {rule.key}: unknown actor {rule.actor!r}")
        if bad := sorted(set(rule.goods) - set(gb.goods)):
            problems.append(f"rule {rule.key}: unknown goods {bad}")
        if bad := sorted(set(rule.countries) - destinations):
            problems.append(f"rule {rule.key}: unknown destinations {bad}")
    categories = {c.key for c in data.categories}
    for tariff_good, cats in gb.tariff_goods.items():
        if bad := sorted(set(cats) - categories):
            problems.append(f"tariff_goods.{tariff_good}: unknown categories {bad}")
    for t in data.tariffs.schedules:
        if t.origin not in actors or t.market not in actors:
            problems.append(f"tariff {t.key}: unknown origin or market")
        if bad := sorted(set(t.goods) - set(gb.tariff_goods)):
            problems.append(f"tariff {t.key}: unknown goods {bad}")
    if bad := sorted(set(gb.local_partner.categories) - categories):
        problems.append(f"local_partner: unknown categories {bad}")
    if bad := sorted(set(gb.local_partner.countries) - keys):
        problems.append(f"local_partner: unknown countries {bad}")
    if bad := sorted(set(gb.actor_regions) - set(BLOCS)) + sorted(
        set(gb.actor_regions.values()) - regions
    ):
        problems.append(f"actor_regions: unknown {bad}")
    if data.commodities is not None:
        for g in data.commodities.goods:
            if countries.by_name(g.top_country) is None:
                problems.append(f"commodity {g.key}: top_country {g.top_country!r} is unknown")
    return problems


def mining_problems(balance: Balance, data: GameData) -> list[str]:
    """M19 (35): mining's commodities, skills and roles exist, and every history event names
    a region and an explorable commodity."""
    problems: list[str] = []
    mb = balance.mining
    if data.geology is not None:
        known = {c.key for c in data.geology.commodities}
        if bad := sorted(set(mb.strategic) ^ known):
            problems.append(f"mining.strategic must name geology.yaml's commodities: {bad}")
        for e in data.nationalization.events if data.nationalization else ():
            if e.commodity is not None and e.commodity not in known:
                problems.append(f"{e.title}: unknown commodity {e.commodity!r}")
    regions = set(data.region_keys)
    for e in data.nationalization.events if data.nationalization else ():
        if e.region not in regions:
            problems.append(f"{e.title}: unknown region {e.region!r}")
    if bad := sorted(set(mb.staff_skills) - set(data.skill_keys)):
        problems.append(f"mining.staff_skills {bad} are not skills")
    if "mine" in balance.facility.kinds:
        roles = {r.key for r in data.roles}
        if bad := sorted(set(balance.facility.kinds["mine"].staff_roles) - roles):
            problems.append(f"facility.kinds.mine staff_roles {bad} are not roles")
    return problems


def fab_problems(balance: Balance, data: GameData) -> list[str]:
    """M21 (38): rival foundries sit in known regions and back known contract foundries; the
    fab kind's roles exist; the materials name known goods; the EUV tools good exists."""
    problems: list[str] = []
    if data.nodes is None:
        return problems
    regions = set(data.region_keys)
    foundries = set(balance.chips.contract.foundries)
    for f in data.nodes.foundries:
        if f.region not in regions:
            problems.append(f"foundry {f.key!r}: unknown region {f.region!r}")
        if f.contract not in foundries:
            problems.append(f"foundry {f.key!r}: {f.contract!r} is not in chips.contract.foundries")
    fm = balance.fab.materials
    if fm.substrate_good not in balance.refining.goods:
        problems.append(
            f"fab.materials.substrate_good {fm.substrate_good!r} is not a refining good"
        )
    if data.commodities is not None:
        known = {c.key for c in data.commodities.goods}
        if bad := sorted(set(fm.mix) - known):
            problems.append(f"fab.materials.mix: unknown commodities {bad}")
    if "fab" in balance.facility.kinds:
        roles = {r.key for r in data.roles}
        if bad := sorted(set(balance.facility.kinds["fab"].staff_roles) - roles):
            problems.append(f"facility.kinds.fab staff_roles {bad} are not roles")
    if data.components is not None and EUV_GOOD not in {g.key for g in data.components.goods}:
        problems.append(f"{COMPONENTS_FILE} has no {EUV_GOOD!r} good")
    return problems


EUV_GOOD = "euv_tools"  # M21 (38.2): components_history.yaml key of EUV tools


def research_problems(balance: Balance, data: GameData) -> list[str]:
    """M11 (21): domains' skills, categories, eras' domains and boosts, and personalities
    all name things the other files define."""
    problems: list[str] = []
    if data.tech is None:
        return problems
    skills = set(data.skill_keys)
    domains = {d.key for d in data.tech.domains}
    categories = {c.key for c in data.categories}
    for d in data.tech.domains:
        if bad := sorted(set(d.research_skill) - skills):
            problems.append(f"domain {d.key!r}: unknown skills {bad}")
    if bad := sorted(set(data.tech.tech_weights) - categories):
        problems.append(f"tech_weights: unknown categories {bad}")
    for era in data.eras.eras:
        if era.domain not in domains:
            problems.append(f"era {era.key!r}: unknown domain {era.domain!r}")
        for b in era.boosts:
            if b.category not in categories:
                problems.append(f"era {era.key!r}: unknown category {b.category!r}")
            elif b.segments and (
                bad := sorted(set(b.segments) - set(data.category(b.category).segment_keys))
            ):
                problems.append(f"era {era.key!r}: {b.category} has no segments {bad}")
    if bad := sorted(set(data.eras.base_growth) - categories):
        problems.append(f"base_growth: unknown categories {bad}")
    if bad := sorted(set(balance.rivals.weights) - set(balance.rnd.rival.weights)):
        problems.append(f"rnd.rival.weights: no weight for {bad}")
    return problems


def automation_problems(balance: Balance, data: GameData) -> list[str]:
    """M27a (40): every area names known roles, skills, KPIs and a rule the engine has."""
    from tst.sim.automation.config import KPIS, RULES

    problems: list[str] = []
    roles = {r.key for r in data.roles}
    skills = set(data.skill_keys)
    for key, area in balance.automation.areas.items():
        if bad := sorted(set(area.roles) - roles):
            problems.append(f"automation area {key!r}: unknown roles {bad}")
        if bad := sorted(set(area.weights) - skills):
            problems.append(f"automation area {key!r}: unknown skills {bad}")
        if bad := sorted(set(area.kpis) - KPIS):
            problems.append(f"automation area {key!r}: unknown KPIs {bad}")
        if area.rule not in RULES:
            problems.append(f"automation area {key!r}: no rule {area.rule!r}")
    return problems


def load_all(
    path: Path, overlay: dict[str, Any] | None = None, mod_name: str | None = None
) -> LoadedData:
    """Load and cross-check every data file in `path`. Raises DataLoadError on any problem.

    `overlay` (M25, a mod's `files`): changed values merged into the named data files before
    any validation, so a mod is checked exactly as the base files are. Without one the
    files load as before; `hashes` are always the base files' own."""
    parsed: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for name in DATA_FILES:
        data, raw = _read(path / name)
        parsed[name] = data
        hashes[name] = file_hash(raw)
    mod_hash = None
    if overlay is not None:
        if unknown := sorted(set(overlay) - set(DATA_FILES)):
            raise DataLoadError(f"mod {mod_name!r}: unknown data files {unknown}")
        for name, changes in overlay.items():
            parsed[name] = merge(parsed[name], changes)
        mod_hash = canonical_hash({name: parsed[name] for name in DATA_FILES})

    event_templates: list[EventTemplate] = []
    for file in sorted((path / EVENTS_DIR).glob("*.yaml")):
        name = f"{EVENTS_DIR}/{file.name}"
        data, raw = _read(file)
        hashes[name] = file_hash(raw)
        event_templates += _validate(EventTemplatesFile, data, name).templates
    if problems := template_problems(tuple(event_templates)):
        raise DataLoadError(f"{EVENTS_DIR}/*.yaml: " + "; ".join(problems))

    balance = _validate(Balance, parsed[BALANCE_FILE], BALANCE_FILE)
    chart = dict(parsed[ACCOUNTS_FILE] or {})
    personal_chart = chart.pop("personal_accounts", None) or []  # M24 (32.2)
    accounts = [
        _validate(Account, item, ACCOUNTS_FILE)
        for item in _list_of(chart, "accounts", ACCOUNTS_FILE)
    ]
    personal_accounts = [  # M24 (32.2): the founder's own chart, apart from the companies'
        _validate(Account, item, ACCOUNTS_FILE) for item in personal_chart
    ]
    if extra := set(parsed[SCENARIOS_FILE] or {}) - {"scenarios", "historical"}:
        raise DataLoadError(
            f"{SCENARIOS_FILE}: expected a single top-level key 'scenarios' (with 'historical' "
            f"beside it, M15b); unknown keys {sorted(extra)}"
        )
    scenarios = [
        _validate(Scenario, item, SCENARIOS_FILE)
        for item in _list_of(
            {"scenarios": (parsed[SCENARIOS_FILE] or {}).get("scenarios")},  # beside `historical`
            "scenarios",
            SCENARIOS_FILE,
        )
    ]
    historical = [  # M15b (30.3)
        _validate(HistoricalScenario, item, SCENARIOS_FILE)
        for item in (parsed[SCENARIOS_FILE] or {}).get("historical", [])
    ]
    skills = _validate(SkillsFile, parsed[SKILLS_FILE], SKILLS_FILE)
    personality = _validate(PersonalityFile, parsed[PERSONALITY_FILE], PERSONALITY_FILE)
    interests = _validate(InterestsFile, parsed[INTERESTS_FILE], INTERESTS_FILE)
    regions = _validate(RegionsFile, parsed[REGIONS_FILE], REGIONS_FILE)
    roles = _validate(RolesFile, parsed[ROLES_FILE], ROLES_FILE)
    tags = _validate(TagsFile, parsed[TAGS_FILE], TAGS_FILE)
    backgrounds = _validate(BackgroundsFile, parsed[BACKGROUNDS_FILE], BACKGROUNDS_FILE)
    names = _validate(NamesFile, parsed[NAMES_FILE], NAMES_FILE)
    inbox = _validate(InboxTemplatesFile, parsed[INBOX_FILE], INBOX_FILE)
    categories = _validate(CategoriesFile, parsed[CATEGORIES_FILE], CATEGORIES_FILE)
    incumbents = _validate(IncumbentsFile, parsed[INCUMBENTS_FILE], INCUMBENTS_FILE)
    investors = _validate(InvestorsFile, parsed[INVESTORS_FILE], INVESTORS_FILE)
    macro_history = _validate(MacroHistory, parsed[MACRO_HISTORY_FILE], MACRO_HISTORY_FILE)
    compute_index = _validate(ComputeIndexFile, parsed[COMPUTE_INDEX_FILE], COMPUTE_INDEX_FILE)
    entrants = _validate(EntrantsFile, parsed[ENTRANTS_FILE], ENTRANTS_FILE)
    cities = _validate(CitiesFile, parsed[CITIES_FILE], CITIES_FILE)
    components = _validate(ComponentsHistoryFile, parsed[COMPONENTS_FILE], COMPONENTS_FILE)
    tech = _validate(TechFrontierFile, parsed[TECH_FILE], TECH_FILE)
    tech = with_slowdown(tech, balance.dynasty)  # M37 (52.2): the 2040s on
    eras = _validate(ErasFile, parsed[ERAS_FILE], ERAS_FILE)
    # M43a (54.1): growth after 2030 decays toward the economy's plus a premium
    grown, eras = with_long_run(
        categories.categories, eras, balance.markets, balance.dynasty.start_year - 1
    )
    categories = categories.model_copy(update={"categories": grown})
    # M37 (52.2): category growth decays toward a mature rate from 2040
    grown, eras = with_maturity(categories.categories, eras, balance.dynasty)
    categories = categories.model_copy(update={"categories": grown})
    banks = _validate(BanksFile, parsed[BANKS_FILE], BANKS_FILE)
    voices = _validate(VoicesFile, parsed[VOICES_FILE], VOICES_FILE)
    commodities = _validate(CommoditiesFile, parsed[COMMODITIES_FILE], COMMODITIES_FILE)
    commodity_history = _validate(
        CommoditiesHistoryFile, parsed[COMMODITY_HISTORY_FILE], COMMODITY_HISTORY_FILE
    )
    power_history = _validate(PowerHistoryFile, parsed[POWER_HISTORY_FILE], POWER_HISTORY_FILE)
    suppliers = _validate(SuppliersFile, parsed[SUPPLIERS_FILE], SUPPLIERS_FILE)
    geology = _validate(GeologyFile, parsed[GEOLOGY_FILE], GEOLOGY_FILE)
    nationalization = _validate(
        NationalizationHistory, parsed[NATIONALIZATION_FILE], NATIONALIZATION_FILE
    )
    nodes = _validate(NodesFile, parsed[NODES_FILE], NODES_FILE)
    nodes = with_successors(nodes, balance.dynasty)  # M37 (52.2): successors' windows
    countries = _validate(CountriesFile, parsed[COUNTRIES_FILE], COUNTRIES_FILE)
    controls = _validate(ExportControlsFile, parsed[CONTROLS_FILE], CONTROLS_FILE)
    tariffs = _validate(TariffsFile, parsed[TARIFFS_FILE], TARIFFS_FILE)
    chain = _validate(ChainCompaniesFile, parsed[CHAIN_FILE], CHAIN_FILE)
    platforms = _validate(PlatformsFile, parsed[PLATFORMS_FILE], PLATFORMS_FILE)
    power = _validate(PowerFile, parsed[POWER_FILE], POWER_FILE)
    regulation = _validate(RegulationFile, parsed[REGULATION_FILE], REGULATION_FILE)
    equipment = _validate(EquipmentFile, parsed[EQUIPMENT_FILE], EQUIPMENT_FILE)
    vehicles = _validate(VehiclesFile, parsed[VEHICLES_FILE], VEHICLES_FILE)
    robotics = _validate(RoboticsFile, parsed[ROBOTICS_FILE], ROBOTICS_FILE)
    tariffs = with_vehicle_tariffs(tariffs, vehicles)  # M38 (49.5): cars join 39.3's schedules
    medical = _validate(MedicalFile, parsed[MEDICAL_FILE], MEDICAL_FILE)
    game_data = _validate(
        GameData,
        {
            "accounts": accounts,
            "personal_accounts": personal_accounts,
            "scenarios": scenarios,
            "historical": historical,
            "skills": skills.skills,
            "personality": personality.personality,
            "hidden": personality.hidden,
            "work_styles": personality.work_styles,
            "interests": interests.interests,
            "regions": regions.regions,
            "roles": roles.roles,
            "tags": tags.tags,
            "backgrounds": backgrounds.backgrounds,
            "personality_presets": backgrounds.personality_presets,
            "names": names.names,
            "startup_names": names.companies,
            "inbox_templates": inbox.templates,
            "segments": categories.segments,
            "categories": tuple(c for c in categories.categories if not c.pseudo),
            "pseudo_categories": tuple(c for c in categories.categories if c.pseudo),
            "incumbents": incumbents.companies,
            "investors": investors.firms,
            "lenders": investors.lenders,
            "macro_history": macro_history,
            "compute_index": compute_index,
            "entrants": entrants.entrants,
            "cities": cities.cities,
            "region_growth": cities.region_growth,
            "home_city_region": cities.home_city_region,
            "region_markets": categories.regions,
            "components": components,
            "event_templates": tuple(event_templates),
            "tech": tech,
            "eras": eras,
            "banks": banks.banks,
            "voices": voices.voices,
            "commodities": commodities,
            "commodity_history": commodity_history,
            "power_history": power_history,
            "suppliers": suppliers,
            "geology": geology,
            "nationalization": nationalization,
            "nodes": nodes,
            "countries": countries,
            "places": countries.plain(),
            "controls": controls,
            "tariffs": tariffs,
            "chain_companies": chain,
            "platforms": platforms,
            "power": power,
            "regulation": regulation,
            "equipment": equipment,
            "vehicles": vehicles,
            "medical": medical,
            "robotics": robotics,
        },
        "seed data cross-check",
    )
    _check_against_balance(balance, game_data)
    traits = {t.key for t in game_data.personality}
    if bad := sorted({v.rule.trait for v in game_data.voices if v.rule} - traits):
        raise DataLoadError(f"{VOICES_FILE}: rules name unknown personality traits {bad}")
    if problems := geology_problems(balance, game_data):
        raise DataLoadError(f"{GEOLOGY_FILE}: " + "; ".join(problems))
    if problems := mining_problems(balance, game_data):
        raise DataLoadError(
            f"{NATIONALIZATION_FILE}, {BALANCE_FILE} mining: " + "; ".join(problems)
        )
    if problems := fab_problems(balance, game_data):
        raise DataLoadError(f"{NODES_FILE}, {BALANCE_FILE} fab: " + "; ".join(problems))
    if problems := power_problems(balance, game_data):
        raise DataLoadError(f"{POWER_FILE}, {BALANCE_FILE} power: " + "; ".join(problems))
    if problems := world_problems(balance, game_data):
        raise DataLoadError(f"{CHAIN_FILE}, {BALANCE_FILE} world: " + "; ".join(problems))
    if problems := platforms_problems(balance, game_data):
        raise DataLoadError(f"{PLATFORMS_FILE}, {BALANCE_FILE} platforms: " + "; ".join(problems))
    if problems := regulation_problems(balance, game_data):
        raise DataLoadError(f"{REGULATION_FILE}, {BALANCE_FILE} regulation: " + "; ".join(problems))
    if problems := medical_problems(balance, game_data):
        raise DataLoadError(f"{MEDICAL_FILE}, {REGULATION_FILE} health: " + "; ".join(problems))
    if problems := equipment_problems(balance, game_data):
        raise DataLoadError(f"{EQUIPMENT_FILE}, {BALANCE_FILE} equipment: " + "; ".join(problems))
    if problems := vehicles_problems(balance, game_data):
        raise DataLoadError(f"{VEHICLES_FILE}, {BALANCE_FILE} vehicles: " + "; ".join(problems))
    if problems := robotics_problems(balance, game_data):
        raise DataLoadError(f"{ROBOTICS_FILE}, {BALANCE_FILE} robotics: " + "; ".join(problems))
    if problems := geopolitics_problems(balance, game_data):
        raise DataLoadError(
            f"{COUNTRIES_FILE}, {CONTROLS_FILE}, {TARIFFS_FILE}, {BALANCE_FILE} geopolitics: "
            + "; ".join(problems)
        )
    if problems := automation_problems(balance, game_data):
        raise DataLoadError("balance.yaml automation: " + "; ".join(problems))
    if problems := research_problems(balance, game_data):
        raise DataLoadError(f"{TECH_FILE}, {ERAS_FILE}: " + "; ".join(problems))

    scenario_ids = {s.id for s in game_data.scenarios}
    missing = sorted(scenario_ids - set(balance.scenario))
    if missing:
        raise DataLoadError(f"{BALANCE_FILE}: no scenario.<id> block for {missing}")
    orphans = sorted(set(balance.scenario) - scenario_ids)
    if orphans:
        raise DataLoadError(f"{BALANCE_FILE}: scenario blocks {orphans} are not in scenarios.yaml")
    personal = {a.code for a in game_data.personal_accounts}
    if personal != set(PERSONAL_ACCOUNTS):
        raise DataLoadError(f"{ACCOUNTS_FILE}: personal_accounts must be {list(PERSONAL_ACCOUNTS)}")
    if mixed := sorted(c for c in game_data.account_codes() if c.startswith(PERSONAL_PREFIX)):
        raise DataLoadError(f"{ACCOUNTS_FILE}: company accounts may not use 9xxx codes: {mixed}")
    unknown_accounts = sorted(set(ENGINE_ACCOUNTS) - game_data.account_codes())
    if unknown_accounts:
        raise DataLoadError(f"{ACCOUNTS_FILE}: engine accounts missing: {unknown_accounts}")

    glossary = _validate(GlossaryFile, _read(path / GLOSSARY_FILE)[0], GLOSSARY_FILE).terms
    advisor = _validate(AdvisorConfig, _read(path / ADVISOR_FILE)[0], ADVISOR_FILE)  # M25
    achievements = _validate(
        AchievementsFile, _read(path / ACHIEVEMENTS_FILE)[0], ACHIEVEMENTS_FILE
    ).achievements
    return LoadedData(
        balance=balance,
        game_data=game_data,
        hashes=dict(sorted(hashes.items())),
        glossary=dict(glossary),
        advisor=advisor,
        achievements=achievements,
        mod_name=mod_name if overlay is not None else None,
        mod_hash=mod_hash,
        mod_overlay=overlay,
    )


def with_vehicle_tariffs(tariffs: TariffsFile, vehicles: VehiclesFile) -> TariffsFile:
    """M38 (49.5): vehicles.yaml's tariffs on imported cars, appended to tariffs.yaml's schedules
    for the `vehicles` good (39.3), so one file cites every vehicles figure."""
    extra = tuple(
        TariffSchedule(
            key=t.key,
            title=t.title,
            origin=t.origin,
            market=t.market,
            goods=("vehicles",),
            steps=t.steps,
            tag=t.tag,
        )
        for t in vehicles.tariffs
    )
    return TariffsFile(schedules=(*tariffs.schedules, *extra))


def vehicles_problems(balance: Balance, data: GameData) -> list[str]:
    """M38 (49): vehicles.yaml covers every region, names known incumbents, countries, cell makers,
    commodities and levels; its cell prices agree with commodities_history.yaml's battery_cells."""
    v = data.vehicles
    vb = balance.vehicles
    out: list[str] = []
    if v is None:
        return ["vehicles.yaml is required"]
    if [r.key for r in v.regions] != list(data.region_keys):
        out.append("regions must list every regions.yaml region in its order")
    category = next((c for c in data.categories if c.key == vb.category), None)
    if category is None or not category.sells_units:
        out.append(f"vehicles.category {vb.category!r} must be a unit-sale category")
    else:
        for m in category.markets:
            if vb.replacement_months.get(m.segment) != m.replacement_months:
                out.append(f"replacement_months for {m.segment} differ from categories.yaml")
    segs = set(category.segment_keys) if category is not None else set()
    for r in v.regions:
        if set(r.segments) != segs or abs(sum(r.segments.values()) - 1) > 1e-6:
            out.append(f"{r.key}: segments must split 1 over {sorted(segs)}")
        if any(not 0 <= x <= 1 for x in r.ev_share.values()):
            out.append(f"{r.key}: ev_share must be in 0-1")
        if max(r.ev_share) < LAST_HISTORY_YEAR:
            out.append(f"{r.key}: ev_share must reach {LAST_HISTORY_YEAR}")
    names = {c.name for c in data.incumbents}
    makers = {m.key for m in v.cell_makers}
    countries = {c.key for c in data.countries.countries} if data.countries is not None else set()
    for rival in v.rivals:
        if rival.company not in names:
            out.append(f"rival {rival.company!r} is not in incumbents.yaml")
        if rival.cells not in makers:
            out.append(f"rival {rival.company!r}: unknown cell maker {rival.cells!r}")
        if countries and rival.origin not in countries:
            out.append(f"rival {rival.company!r}: unknown country {rival.origin!r}")
        if bad := set(rival.share_points) - set(data.region_keys):
            out.append(f"rival {rival.company!r}: unknown regions {sorted(bad)}")
    for region in data.region_keys:
        for year in range(FIRST_HISTORY_YEAR, LAST_HISTORY_YEAR + 1):
            total = sum(r.share_at(region, year) for r in v.rivals)
            if total > 1 + 1e-9:
                out.append(f"{region} {year}: rivals' shares sum to {total:.3f} > 1")
    vehicle_incumbents = {
        c.name for c in data.incumbents for p in c.products if p.category == vb.category
    }
    if missing := sorted(vehicle_incumbents - {r.company for r in v.rivals}):
        out.append(f"vehicle incumbents without vehicles.yaml history: {missing}")
    goods = {g.key for g in data.commodities.goods} if data.commodities is not None else set()
    for chem in v.battery.chemistries.values():
        if bad := set(chem.inputs) - goods:
            out.append(f"chemistry {chem.label!r}: unknown commodities {sorted(bad)}")
    if vb.cell_good not in goods:
        out.append(f"vehicles.cell_good {vb.cell_good!r} is not a commodity")
    elif data.commodity_history is not None:
        hist = next((g for g in data.commodity_history.goods if g.key == vb.cell_good), None)
        if hist is None:
            out.append(f"commodities_history.yaml has no {vb.cell_good}")
        else:
            for year, (value, _tag) in hist.years.items():
                want = v.battery.pack_at(year) * v.battery.cell_share_at(year) / CENTS_PER_DOLLAR
                if abs(value - want) > CELL_PRICE_TOLERANCE:
                    out.append(f"{vb.cell_good} {year}: {value} != vehicles.yaml's {want:.1f}")
    for subsidy in v.subsidies:
        if subsidy.region not in data.region_keys:
            out.append(f"subsidy {subsidy.key!r}: unknown region {subsidy.region!r}")
        if countries and subsidy.country not in countries:
            out.append(f"subsidy {subsidy.key!r}: unknown country {subsidy.country!r}")
    for g in v.regulators:
        if g.region not in data.region_keys:
            out.append(f"regulator {g.key!r}: unknown region {g.region!r}")
    if [k for k in LEVELS if k in vb.levels] != list(vb.levels):
        out.append(f"vehicles.levels must be {list(LEVELS)} in order")
    if vb.plant.kind not in balance.facility.kinds or vb.cell_plant.kind not in (
        balance.facility.kinds
    ):
        out.append("vehicles.plant and cell_plant kinds must be facility.kinds")
    if vb.charging.kind not in balance.facility.kinds:
        out.append("vehicles.charging.kind must be a facility kind")
    if data.tech is not None and vb.domain not in {d.key for d in data.tech.domains}:
        out.append(f"vehicles.domain {vb.domain!r} is not a tech_frontier.yaml domain")
    if vb.category not in balance.hardware.bom:
        out.append("hardware.bom needs the vehicles category")
    return out


def vehicle_kinds(balance: Balance) -> tuple[str, ...]:
    """M38 (49.2, 49.5): the facility kinds whose output tst.sim.vehicles runs on the generic
    lifecycle (cell plants and charging networks)."""
    return (balance.vehicles.cell_plant.kind, balance.vehicles.charging.kind)


def robotics_problems(balance: Balance, data: GameData) -> list[str]:
    """M39 (53): robotics.yaml covers every region in order, splits installations over the
    industrial segments, reaches 2025, names known incumbents, countries, eras, cities and
    operators; balance.yaml's robotics keys agree with categories.yaml."""
    r = data.robotics
    rb = balance.robotics
    out: list[str] = []
    if r is None:
        return ["robotics.yaml is required"]
    if [x.key for x in r.regions] != list(data.region_keys):
        out.append("regions must list every regions.yaml region in its order")
    cats = {c.key: c for c in (*data.categories, *data.pseudo_categories)}
    ind, hum, mob = cats.get(rb.industrial), cats.get(rb.humanoid), cats.get(rb.mobility)
    if ind is None or not ind.sells_units:
        out.append(f"robotics.industrial {rb.industrial!r} must be a unit-sale category")
    elif tuple(ind.segment_keys) != INDUSTRIAL_SEGMENTS:
        out.append(f"{rb.industrial} must sell to {list(INDUSTRIAL_SEGMENTS)}")
    else:
        for m in ind.markets:
            if rb.replacement_months.get(m.segment) != m.replacement_months:
                out.append(f"replacement_months for {m.segment} differ from categories.yaml")
            if rb.units_per_customer.get(m.segment) != m.units_per_customer:
                out.append(f"units_per_customer for {m.segment} differ from categories.yaml")
    if hum is None or not hum.sells_units or tuple(hum.segment_keys) != HUMANOID_SEGMENTS:
        out.append(
            f"robotics.humanoid {rb.humanoid!r} must sell units to {list(HUMANOID_SEGMENTS)}"
        )
    if mob is None or not mob.pseudo:
        out.append(f"robotics.mobility {rb.mobility!r} must be a pseudo-category")
    for key in (rb.industrial, rb.humanoid):
        if key not in balance.hardware.bom:
            out.append(f"hardware.bom needs {key}")
    if rb.depot_kind not in balance.facility.kinds:
        out.append(f"robotics.depot_kind {rb.depot_kind!r} is not a facility kind")
    for kind in rb.automation.plant_kinds:
        if kind not in balance.facility.kinds:
            out.append(f"automation.plant_kinds: unknown facility kind {kind!r}")
        if kind not in rb.automation.workers_per_unit or kind not in rb.automation.labour_share:
            out.append(f"automation: {kind} needs workers_per_unit and labour_share")
    for row in r.regions:
        if set(row.segments) != set(INDUSTRIAL_SEGMENTS) or (
            abs(sum(row.segments.values()) - 1) > SHARE_TOLERANCE
        ):
            out.append(f"{row.key}: segments must split 1 over {list(INDUSTRIAL_SEGMENTS)}")
        if max(row.installations) < LAST_HISTORY_YEAR:
            out.append(f"{row.key}: installations must reach {LAST_HISTORY_YEAR}")
    names = {c.name for c in data.incumbents}
    countries = {c.key for c in data.countries.countries} if data.countries is not None else set()
    for maker in r.makers:
        if maker.company not in names:
            out.append(f"maker {maker.company!r} is not in incumbents.yaml")
        if countries and maker.origin not in countries:
            out.append(f"maker {maker.company!r}: unknown country {maker.origin!r}")
        if bad := set(maker.share_points) - set(data.region_keys):
            out.append(f"maker {maker.company!r}: unknown regions {sorted(bad)}")
    for key in data.region_keys:
        for year in range(FIRST_HISTORY_YEAR, LAST_HISTORY_YEAR + 1):
            total = sum(maker.share_at(key, year) for maker in r.makers)
            if total > 1 + POLY_TOLERANCE:
                out.append(f"makers' shares in {key} {year} sum over 1 ({total:.3f})")
    for hm in r.humanoids.makers:
        if hm.company not in names:
            out.append(f"humanoid maker {hm.company!r} is not in incumbents.yaml")
    for a in r.humanoids.announcements:
        if r.humanoid_maker(a.company) is None:
            out.append(f"announcement by unknown humanoid maker {a.company!r}")
    if r.humanoids.era not in {e.key for e in data.eras.eras}:
        out.append(f"humanoids.era {r.humanoids.era!r} is not in eras.yaml")
    if set(r.humanoids.workers) != set(data.region_keys):
        out.append("humanoids.workers must cover every region")
    city_keys = {c.key for c in r.robotaxi.cities}
    for c in r.robotaxi.cities:
        if c.region not in data.region_keys:
            out.append(f"city {c.key}: unknown region {c.region!r}")
        if countries and c.country not in countries:
            out.append(f"city {c.key}: unknown country {c.country!r}")
    for op in r.robotaxi.operators:
        if op.company is not None and op.company not in names:
            out.append(f"operator {op.key}: {op.company!r} is not in incumbents.yaml")
        for svc in op.services:
            if svc.city not in city_keys:
                out.append(f"operator {op.key}: unknown city {svc.city!r}")
    ops = {op.key for op in r.robotaxi.operators}
    for inc in r.robotaxi.incidents:
        if inc.operator not in ops or inc.city not in city_keys:
            out.append(f"incident {inc.label!r}: unknown operator or city")
    for size in rb.robotaxi.zone_sizes:
        if size not in ("small", "medium", "large"):
            out.append(f"robotaxi.zone_sizes: unknown size {size!r}")
    return out
