"""Write the API's OpenAPI schema to a file without starting a server (ADR-0009).

Usage: uv run python scripts/export_openapi.py [OUTPUT]   (default: openapi.json)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tst.api.app import create_app


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(create_app().openapi(), fh, indent=2)
        fh.write("\n")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
