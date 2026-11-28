"""Create the M50b practice save (formulas.md 60.4-60.7; an e2e fixture tool). Never used by the game.

- `garage <save dir> <name>` (the practice save `pt-2000`): a garage start in January 2000
  (garage_bootstrap, seed 2000), two months before the NASDAQ peak: raise while the money
  is easy, then see whether the company survives the bust to 2004.

Usage: uv run --project backend python tools/e2e_m50b_save.py garage <save dir> <name>
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from tst.config import Settings
from tst.db.repository import create_save
from tst.loader import load_all

SEED: Final = 2000
COMPANY: Final = "Boo Street Labs"


def garage(save_dir: Path, name: str) -> Path:
    data = load_all(Settings().data_dir)
    return create_save(
        name,
        SEED,
        "garage_bootstrap",
        company_name=COMPANY,
        data=data,
        save_dir=save_dir,
        start_year=2000,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] != "garage":
        print(__doc__)
        return 2
    path = garage(Path(argv[1]), argv[2])
    print(f"Created {path.name}: {COMPANY}, Jan 2000")
    return 0


if __name__ == "__main__":
    import e2e_cache  # M59: CI keeps the saves it builds (tools/e2e_cache.py)

    sys.exit(e2e_cache.run(__file__, sys.argv[1:], lambda: main(sys.argv[1:])))
