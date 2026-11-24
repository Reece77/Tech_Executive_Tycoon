"""A copy of backend/data with balance.yaml keys overridden, for M46's CI sweeps (never the game).

with overridden_data(["products.marketer_lift=0.03,products.marketer_lift_cap=0.3"]) as root:
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parent.parent / "backend"


@contextmanager
def overridden_data(settings: list[str]) -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree(BACKEND / "data", root / "data")
        path = root / "data" / "balance.yaml"
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for setting in (s for arg in settings for s in arg.split(",") if s):
            key, value = setting.split("=", 1)
            *parents, leaf = key.split(".")
            node = doc
            for p in parents:
                node = node[p]
            if leaf not in node:
                raise SystemExit(f"unknown balance key {key}")
            node[leaf] = yaml.safe_load(value)
            print(f"override {key} = {node[leaf]!r}", flush=True)
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        yield root
