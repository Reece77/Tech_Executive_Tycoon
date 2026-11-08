"""M25 sub-task 4: the overlay format. Identity-keyed lists merge item by item, mappings
key by key, everything else replaces; change paths round-trip through overlays."""

from __future__ import annotations

from pathlib import Path

import pytest

from tst.config import Settings
from tst.loader import DataLoadError, LoadedData, load_all
from tst.mods.overlay import (
    OverlayError,
    canonical_hash,
    changes_of,
    identity,
    merge,
    overlay_of,
    value_at,
)

BASE = {
    "companies": [
        {"name": "Salesforce", "products": [{"name": "Sales Cloud", "brand": 80, "q": 70}]},
        {"name": "Oracle", "products": [{"name": "CRM", "brand": 60}]},
    ],
    "growth": {"smb": 0.1, "enterprise": 0.05},
    "tags": ["a", "b"],
}


def test_merge_by_identity_and_key() -> None:
    overlay = {
        "companies": [{"name": "Salesforce", "products": [{"name": "Sales Cloud", "brand": 40}]}],
        "growth": {"smb": 0.2},
        "tags": ["c"],
    }
    out = merge(BASE, overlay)
    assert out["companies"][0]["products"][0] == {"name": "Sales Cloud", "brand": 40, "q": 70}
    assert out["companies"][1] == BASE["companies"][1]
    assert out["growth"] == {"smb": 0.2, "enterprise": 0.05}
    assert out["tags"] == ["c"]  # a list of scalars is replaced whole
    assert BASE["companies"][0]["products"][0]["brand"] == 80  # inputs unchanged


def test_a_new_identity_is_appended() -> None:
    out = merge(BASE, {"companies": [{"name": "Zoho", "products": []}]})
    assert [c["name"] for c in out["companies"]] == ["Salesforce", "Oracle", "Zoho"]


def test_identity_needs_unique_values() -> None:
    assert identity([{"key": "a"}, {"key": "b"}]) == "key"
    assert identity([{"name": "a"}, {"name": "a"}]) is None
    assert identity([1, 2]) is None


def test_changes_round_trip() -> None:
    path = ["companies", "@name=Salesforce", "products", "@name=Sales Cloud", "brand"]
    assert value_at(BASE, path) == 80
    overlay = overlay_of([("f", path, 40), ("f", ["growth", "smb"], 0.1)], {"f": BASE})
    assert overlay == {
        "f": {
            "companies": [
                {"name": "Salesforce", "products": [{"name": "Sales Cloud", "brand": 40}]}
            ]
        }
    }  # the unchanged growth is dropped
    assert changes_of(BASE, overlay["f"]) == [(path, 40)]
    with pytest.raises(OverlayError):
        overlay_of([("f", ["companies", "@name=Nobody", "brand"], 1)], {"f": BASE})


def test_hash_ignores_key_order() -> None:
    assert canonical_hash({"a": 1, "b": [1, 2]}) == canonical_hash({"b": [1, 2], "a": 1})


def test_no_overlay_loads_exactly_the_base(loaded: LoadedData) -> None:
    again = load_all(Settings().data_dir)
    assert again.mod_name is None and again.mod_hash is None and again.mod_overlay is None
    assert again.hashes == loaded.hashes and again.balance == loaded.balance
    empty = load_all(Settings().data_dir, {}, "empty")
    assert empty.balance == loaded.balance and empty.game_data == loaded.game_data
    assert empty.hashes == loaded.hashes and empty.mod_hash is not None


def test_an_invalid_overlay_fails_with_the_loaders_message() -> None:
    with pytest.raises(DataLoadError, match="balance.yaml"):
        load_all(Settings().data_dir, {"balance.yaml": {"backup": {"every_n_turns": "x"}}}, "bad")
    with pytest.raises(DataLoadError, match="unknown data files"):
        load_all(Settings().data_dir, {"nope.yaml": {}}, "bad")


def test_data_dir_exists() -> None:
    assert Path(Settings().data_dir, "balance.yaml").is_file()
