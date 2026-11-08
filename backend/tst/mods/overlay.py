"""The overlay format and its merge (M25 section 3). Outside the sim; pure functions.

An overlay holds only changed values, in each data file's own shape:

    files:
      incumbents.yaml:
        companies:
          - name: Salesforce        # a list of records is matched by its identity field
            products:
              - name: Sales Cloud
                brand: 40

Mappings merge key by key. A list whose items are mappings with an identity field (`key`,
`id` or `name`, the first every item has) merges item by item: an overlay item names the
base item it changes, or is appended when no base item has its identity. Any other list,
and every scalar, is replaced whole. A change path is a list of segments: a mapping key, or
`@<field>=<value>` for the list item with that identity.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

IDENTITY_FIELDS = ("key", "id", "name")
SELECT = "@"


class OverlayError(ValueError):
    """An overlay or a change path that does not fit the data."""


def identity(items: list[Any]) -> str | None:
    """The field that identifies every item of a list of mappings, if there is one."""
    if not items or not all(isinstance(i, dict) for i in items):
        return None
    for name in IDENTITY_FIELDS:
        values = [i.get(name) for i in items]
        if all(v is not None for v in values) and len(set(map(str, values))) == len(values):
            return name
    return None


def merge(base: Any, overlay: Any) -> Any:
    """`base` with `overlay` merged in; neither input is changed."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = dict(base)
        for k, v in overlay.items():
            out[k] = merge(base[k], v) if k in base else copy.deepcopy(v)
        return out
    if isinstance(base, list) and isinstance(overlay, list):
        field = identity(base)
        if field is not None and all(isinstance(o, dict) and field in o for o in overlay):
            out_list = list(base)
            index = {str(item[field]): n for n, item in enumerate(base)}
            for o in overlay:
                n = index.get(str(o[field]))
                if n is None:
                    out_list.append(copy.deepcopy(o))
                else:
                    out_list[n] = merge(base[n], o)
            return out_list
    return copy.deepcopy(overlay)


def _select(segment: str) -> tuple[str, str] | None:
    if not segment.startswith(SELECT) or "=" not in segment:
        return None
    name, value = segment[1:].split("=", 1)
    return name, value


def value_at(data: Any, path: list[str]) -> Any:
    """The value at a change path, or OverlayError."""
    node = data
    for seg in path:
        sel = _select(seg)
        if sel is not None:
            if not isinstance(node, list):
                raise OverlayError(f"{seg}: not a list")
            name, value = sel
            found = [i for i in node if isinstance(i, dict) and str(i.get(name)) == value]
            if not found:
                raise OverlayError(f"{seg}: no such item")
            node = found[0]
        elif isinstance(node, dict) and seg in node:
            node = node[seg]
        else:
            raise OverlayError(f"{seg}: no such field")
    return node


def set_change(overlay: dict[str, Any], path: list[str], value: Any) -> dict[str, Any]:
    """`overlay` with one change set at `path` (which must name a value in the base data;
    the caller checks with value_at). Returns a new overlay."""
    if not path:
        raise OverlayError("an empty path")
    out = copy.deepcopy(overlay)
    node: Any = out
    for n, seg in enumerate(path):
        last = n == len(path) - 1
        sel = _select(seg)
        if sel is not None:
            name, ident = sel
            items = node
            found = next(
                (i for i in items if isinstance(i, dict) and str(i.get(name)) == ident), None
            )
            if found is None:
                found = {name: _typed(ident)}
                items.append(found)
            node = found
            if last:
                raise OverlayError("a path ends at a field, not a list item")
            continue
        if last:
            node[seg] = value
            break
        nxt = path[n + 1]
        node = node.setdefault(seg, [] if _select(nxt) is not None else {})
    return out


def _typed(text: str) -> Any:
    """An identity value from a path segment: an int stays an int."""
    return int(text) if text.lstrip("-").isdigit() else text


def canonical_hash(files: dict[str, Any]) -> str:
    """SHA-256 of merged data, independent of key order."""
    blob = json.dumps(files, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def changes_of(
    base: Any, overlay: Any, path: list[str] | None = None
) -> list[tuple[list[str], Any]]:
    """An overlay as change paths and values (the editor's list of edits)."""
    path = path or []
    if isinstance(overlay, dict) and isinstance(base, dict):
        out: list[tuple[list[str], Any]] = []
        for k, v in overlay.items():
            if k in base:
                out += changes_of(base[k], v, [*path, str(k)])
            else:
                out.append(([*path, str(k)], v))
        return out
    if isinstance(overlay, list) and isinstance(base, list):
        field = identity(base)
        if field is not None and all(isinstance(o, dict) and field in o for o in overlay):
            out = []
            for o in overlay:
                match = next((b for b in base if str(b.get(field)) == str(o[field])), None)
                seg = f"{SELECT}{field}={o[field]}"
                if match is None:
                    out.append(([*path, seg], o))
                    continue
                rest = {k: v for k, v in o.items() if k != field}
                out += changes_of(match, rest, [*path, seg])
            return out
    return [(path, overlay)]


def overlay_of(changes: list[tuple[str, list[str], Any]], base: dict[str, Any]) -> dict[str, Any]:
    """The overlay for (file, path, value) changes, each checked against the base data; a
    change equal to the base value is dropped (an overlay holds changed values only)."""
    files: dict[str, Any] = {}
    for file, path, value in changes:
        if file not in base:
            raise OverlayError(f"{file}: not an editable data file")
        try:
            current = value_at(base[file], path)
        except OverlayError as exc:
            raise OverlayError(f"{file}: {'.'.join(path)}: {exc}") from exc
        if current == value:
            continue
        files[file] = set_change(files.get(file, {}), path, value)
    return files
