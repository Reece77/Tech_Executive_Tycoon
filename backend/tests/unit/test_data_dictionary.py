"""M15r (Codex review 4 finding 10): docs/data-dictionary.md keeps one table per heading for
every table migrations 0030 onward create, and each table's columns, types, nullability and
primary keys match the ORM (and so the migrations: test_migration_matches_models). Tables
documented in a JSON `data` summary (0034, 0035) are checked by name."""

from __future__ import annotations

import re
from pathlib import Path

from tst.db.models import Base

ROOT = Path(__file__).resolve().parents[3]
DICTIONARY = ROOT / "docs" / "data-dictionary.md"
MIGRATIONS = ROOT / "backend" / "migrations" / "versions"
FROM = 30  # tunable-exempt: the first migration this guard covers (review 4's audit range)


def created_tables() -> list[str]:
    out = []
    for path in sorted(MIGRATIONS.glob("00*.py")):
        if int(path.name[:4]) >= FROM:
            out += re.findall(r'op\.create_table\(\s*"(\w+)"', path.read_text())
    return out


def sections() -> dict[str, list[str]]:
    """`### name` heading -> the lines up to the next heading."""
    out: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in DICTIONARY.read_text().splitlines():
        if line.startswith("#"):
            match = re.match(r"### `?(\w+)`?", line)
            current = out.setdefault(match.group(1), []) if match else None
        elif current is not None:
            current.append(line)
    return out


HEADER = "| Column | Type | Null | Meaning |"


def rows(lines: list[str]) -> list[list[str]] | None:
    """The column table's rows; None when the section's table is not in the standard
    four-column form."""
    table = [ln for ln in lines if ln.startswith("|")]
    if not table:
        return []
    if table[0].strip() not in (HEADER, HEADER.replace("Meaning", "Description")):
        return None
    out = [[c.strip() for c in ln.strip("|").split("|")] for ln in table[2:]]
    return None if any(len(r) != 4 for r in out) else out


def _type(text: str) -> str:
    return text.split()[0].split("(")[0].upper()


def test_every_new_table_is_documented_once_and_matches_the_orm() -> None:
    docs = sections()
    summary = DICTIONARY.read_text()
    problems = []
    for name in created_tables():
        table = Base.metadata.tables[name]
        if name not in docs:
            if f"| `{name}` |" not in summary:
                problems.append(f"{name}: no section")
            continue
        found = rows(docs[name])
        if found is None:
            problems.append(f"{name}: not a Column | Type | Null | Meaning table")
            continue
        documented = {r[0].strip("`"): r for r in found}
        if len(documented) != len(found):
            problems.append(f"{name}: a column twice")
        columns = {c.name: c for c in table.columns}
        if set(documented) != set(columns):
            problems.append(
                f"{name}: missing {sorted(set(columns) - set(documented))}, "
                f"extra {sorted(set(documented) - set(columns))}"
            )
            continue
        text = "\n".join(docs[name])
        for col_name, col in columns.items():
            row = documented[col_name]
            if _type(row[1]) != str(col.type).split("(")[0].upper():
                problems.append(f"{name}.{col_name}: type {row[1]} vs {col.type}")
            if (row[2] == "yes") != bool(col.nullable):
                problems.append(f"{name}.{col_name}: null {row[2]} vs {col.nullable}")
            if (
                col.primary_key
                and "primary key" not in (row[3] + text).lower()
                and " PK" not in row[1]
            ):
                problems.append(f"{name}.{col_name}: primary key not documented")
    assert problems == []
