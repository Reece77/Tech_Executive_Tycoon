"""Read and validate backend/data YAML (ADR-0008). Lives outside tst.sim on purpose.

Callers load once at startup and pass `Balance` and `GameData` into the sim.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

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
from tst.sim.events.data import EventTemplate, EventTemplatesFile, template_problems
from tst.sim.facilities.config import ComponentsHistoryFile
from tst.sim.founder.models import PERSONAL_ACCOUNTS, PERSONAL_PREFIX
from tst.sim.ledger import ENGINE_ACCOUNTS
from tst.sim.markets_public.config import BanksFile
from tst.sim.modes.config import HistoricalScenario
from tst.sim.org.voice_data import VoicesFile
from tst.sim.research.data import ErasFile, TechFrontierFile

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
EVENTS_DIR = "events"  # M6: event templates, one file per category (formulas.md 16.4)
DATA_FILES = (
    ACCOUNTS_FILE,
    BANKS_FILE,
    BACKGROUNDS_FILE,
    BALANCE_FILE,
    CATEGORIES_FILE,
    CITIES_FILE,
    COMPONENTS_FILE,
    COMPUTE_INDEX_FILE,
    ENTRANTS_FILE,
    ERAS_FILE,
    VOICES_FILE,
    INBOX_FILE,
    INCUMBENTS_FILE,
    INVESTORS_FILE,
    INTERESTS_FILE,
    MACRO_HISTORY_FILE,
    NAMES_FILE,
    PERSONALITY_FILE,
    REGIONS_FILE,
    ROLES_FILE,
    SCENARIOS_FILE,
    SKILLS_FILE,
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


class _UniqueKeyLoader(yaml.SafeLoader):
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
        if kind.output_good not in balance.compute.goods and (
            kind.output_good != balance.hardware.output_good
        ):
            raise DataLoadError(
                f"{where}: output_good {kind.output_good!r} is not in compute.goods"
            )
        if bad := sorted(set(kind.staff_roles) - roles):
            raise DataLoadError(f"{where}: staff_roles {bad} are not in {ROLES_FILE}")
        if kind.staff_skill not in data.skill_keys:
            raise DataLoadError(f"{where}: staff_skill {kind.staff_skill!r} is not a skill")
    _check_hardware(balance, data, goods)
    key = balance.compute.capacity_category
    capacity = [c.key for c in data.categories if c.capacity_market]
    if capacity != [key]:
        raise DataLoadError(
            f"{CATEGORIES_FILE}: the one capacity_market category must be compute.capacity_category"
            f" {key!r}, found {capacity}"
        )


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
        if cat is None or not cat.sells_units or cat.family is not None:
            raise DataLoadError(f"{where}.bom.{key}: not a unit-sale category (chips excluded)")
        if bom.good not in goods:
            raise DataLoadError(f"{where}.bom.{key}: good {bom.good!r} not in {COMPONENTS_FILE}")
        if bom.chip_type not in ch.types:
            raise DataLoadError(
                f"{where}.bom.{key}: chip_type {bom.chip_type!r} not in chips.types"
            )
    for cat in data.categories:
        if cat.sells_units and cat.family is None and cat.key not in hw.bom:
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


def load_all(path: Path) -> LoadedData:
    """Load and cross-check every data file in `path`. Raises DataLoadError on any problem."""
    parsed: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for name in DATA_FILES:
        data, raw = _read(path / name)
        parsed[name] = data
        hashes[name] = file_hash(raw)

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
    eras = _validate(ErasFile, parsed[ERAS_FILE], ERAS_FILE)
    banks = _validate(BanksFile, parsed[BANKS_FILE], BANKS_FILE)
    voices = _validate(VoicesFile, parsed[VOICES_FILE], VOICES_FILE)
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
            "categories": categories.categories,
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
        },
        "seed data cross-check",
    )
    _check_against_balance(balance, game_data)
    traits = {t.key for t in game_data.personality}
    if bad := sorted({v.rule.trait for v in game_data.voices if v.rule} - traits):
        raise DataLoadError(f"{VOICES_FILE}: rules name unknown personality traits {bad}")
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
    return LoadedData(
        balance=balance,
        game_data=game_data,
        hashes=dict(sorted(hashes.items())),
        glossary=dict(glossary),
    )
