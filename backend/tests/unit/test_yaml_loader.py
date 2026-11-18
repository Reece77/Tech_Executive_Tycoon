"""The data loader's YAML parser (tst.loader.safe_load and its duplicate-key loader): libyaml's
C parser where PyYAML has it, giving the same documents as the pure-Python SafeLoader for every
data file, and still refusing a duplicate key. Saving a mod validates every data file, so the
parser's speed is what the editor's save waits for (e2e m25 (c))."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tst import loader

DATA = Path(__file__).resolve().parents[2] / "data"
FILES = sorted(p for p in DATA.rglob("*.yaml"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(DATA)))
def test_the_fast_parser_reads_every_data_file_as_the_pure_one(path: Path) -> None:
    raw = path.read_bytes()
    assert loader.safe_load(raw) == yaml.load(raw, Loader=yaml.SafeLoader)
    assert yaml.load(raw, Loader=loader._UniqueKeyLoader) == yaml.load(raw, Loader=yaml.SafeLoader)


def test_duplicate_keys_are_still_refused() -> None:
    with pytest.raises(yaml.constructor.ConstructorError, match="duplicate key"):
        yaml.load(b"a: 1\na: 2\n", Loader=loader._UniqueKeyLoader)


def test_the_c_parser_is_used_where_pyyaml_has_it() -> None:
    if hasattr(yaml, "CSafeLoader"):
        assert issubclass(loader._UniqueKeyLoader, yaml.CSafeLoader)
