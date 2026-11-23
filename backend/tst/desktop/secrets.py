"""The Anthropic API key in app data's `.env` (M58 sub-task 2).

Entered once in Settings, written to `<app data>/.env` (never to the install folder, so it is
never bundled and survives updates), loaded into the process environment at start, and never
returned by the API or written to a log: `RedactingFilter` masks anything that looks like a key
in every log record, as a second guard.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from collections.abc import MutableMapping
from pathlib import Path

KEY_NAME = "ANTHROPIC_API_KEY"
MAX_KEY_LENGTH = 400
# Anthropic keys start sk-ant-; anything key-shaped after "sk-" is masked too.
_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
MASK = "sk-***"


def read_env(path: Path) -> dict[str, str]:
    """KEY=value lines; blank lines and # comments ignored; quotes around a value dropped."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        out[name.strip()] = value
    return out


def write_env(path: Path, values: dict[str, str]) -> None:
    """Atomic write; the file is readable by its owner only where the platform allows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
    body = "".join(f"{k}={v}\n" for k, v in sorted(values.items()))
    tmp.write_text(body, encoding="utf-8")
    with contextlib.suppress(OSError):  # Windows ignores most mode bits
        os.chmod(tmp, 0o600)
    tmp.replace(path)


def clean_key(key: str) -> str:
    """The key as entered, trimmed; ValueError when it cannot be a key."""
    key = key.strip()
    if len(key) > MAX_KEY_LENGTH or any(c.isspace() or c in "\"'=#" for c in key):
        raise ValueError("that does not look like an API key")
    return key


def save_key(path: Path, key: str | None, environ: MutableMapping[str, str]) -> None:
    """Store the key (None or "" removes it) and apply it to this process."""
    values = read_env(path)
    if key:
        values[KEY_NAME] = clean_key(key)
        environ[KEY_NAME] = values[KEY_NAME]
    else:
        values.pop(KEY_NAME, None)
        environ.pop(KEY_NAME, None)
    write_env(path, values)


def load_into(path: Path, environ: MutableMapping[str, str]) -> bool:
    """Put the stored key into the environment (a key already set there wins). True if any."""
    key = read_env(path).get(KEY_NAME)
    if key and not environ.get(KEY_NAME):
        environ[KEY_NAME] = key
    return bool(environ.get(KEY_NAME))


def redact(text: str) -> str:
    return _KEY_RE.sub(MASK, text)


class RedactingFilter(logging.Filter):
    """Masks API keys in a record's message and arguments before any handler writes it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.msg = record.getMessage()
            record.args = None
        record.msg = redact(str(record.msg))
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True
