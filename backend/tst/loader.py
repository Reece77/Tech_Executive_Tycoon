"""Read and validate backend/data YAML (ADR-0008). Lives outside tst.sim on purpose.

Callers load once at startup and pass `Balance` and `GameData` into the sim.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from tst.sim.data_models import (
    Account,
    BackgroundsFile,
    Balance,
    GameData,
    InboxTemplatesFile,
    InterestsFile,
    NamesFile,
    PersonalityFile,
    RegionsFile,
    RolesFile,
    Scenario,
    SkillsFile,
    TagsFile,
)
from tst.sim.ledger import ENGINE_ACCOUNTS

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
DATA_FILES = (
    ACCOUNTS_FILE,
    BACKGROUNDS_FILE,
    BALANCE_FILE,
    INBOX_FILE,
    INTERESTS_FILE,
    NAMES_FILE,
    PERSONALITY_FILE,
    REGIONS_FILE,
    ROLES_FILE,
    SCENARIOS_FILE,
    SKILLS_FILE,
    TAGS_FILE,
)


class DataLoadError(Exception):
    """Seed or balance data is missing or invalid. Raised at startup, never mid-game."""


@dataclass(frozen=True, slots=True)
class LoadedData:
    balance: Balance
    game_data: GameData
    hashes: dict[str, str]  # file name -> SHA-256 hex digest (line endings normalized)


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


def load_all(path: Path) -> LoadedData:
    """Load and cross-check every data file in `path`. Raises DataLoadError on any problem."""
    parsed: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for name in DATA_FILES:
        data, raw = _read(path / name)
        parsed[name] = data
        hashes[name] = file_hash(raw)

    balance = _validate(Balance, parsed[BALANCE_FILE], BALANCE_FILE)
    accounts = [
        _validate(Account, item, ACCOUNTS_FILE)
        for item in _list_of(parsed[ACCOUNTS_FILE], "accounts", ACCOUNTS_FILE)
    ]
    scenarios = [
        _validate(Scenario, item, SCENARIOS_FILE)
        for item in _list_of(parsed[SCENARIOS_FILE], "scenarios", SCENARIOS_FILE)
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
    game_data = _validate(
        GameData,
        {
            "accounts": accounts,
            "scenarios": scenarios,
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
            "inbox_templates": inbox.templates,
        },
        "seed data cross-check",
    )
    _check_against_balance(balance, game_data)

    scenario_ids = {s.id for s in game_data.scenarios}
    missing = sorted(scenario_ids - set(balance.scenario))
    if missing:
        raise DataLoadError(f"{BALANCE_FILE}: no scenario.<id> block for {missing}")
    orphans = sorted(set(balance.scenario) - scenario_ids)
    if orphans:
        raise DataLoadError(f"{BALANCE_FILE}: scenario blocks {orphans} are not in scenarios.yaml")
    unknown_accounts = sorted(set(ENGINE_ACCOUNTS) - game_data.account_codes())
    if unknown_accounts:
        raise DataLoadError(f"{ACCOUNTS_FILE}: engine accounts missing: {unknown_accounts}")

    return LoadedData(balance=balance, game_data=game_data, hashes=dict(sorted(hashes.items())))
