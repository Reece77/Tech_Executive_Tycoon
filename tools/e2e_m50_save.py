"""Create the M50 practice save (formulas.md 60; an e2e fixture tool). Never used by the game.

- `garage <save dir> <name>` (the practice save `pt-2008`): a garage start in January 2008
  (garage_bootstrap, seed 2008), the financial crisis ahead: try to raise a seed round in late
  2008, and see whether the company survives to 2010.

Usage: uv run --project backend python tools/e2e_m50_save.py garage <save dir> <name>
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from tst.config import Settings
from tst.db.repository import create_save
from tst.loader import load_all

SEED: Final = 2008
COMPANY: Final = "Lehman Street Labs"


def garage(save_dir: Path, name: str) -> Path:
    data = load_all(Settings().data_dir)
    return create_save(
        name,
        SEED,
        "garage_bootstrap",
        company_name=COMPANY,
        data=data,
        save_dir=save_dir,
        start_year=2008,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] != "garage":
        print(__doc__)
        return 2
    path = garage(Path(argv[1]), argv[2])
    print(f"Created {path.name}: {COMPANY}, Jan 2008")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
