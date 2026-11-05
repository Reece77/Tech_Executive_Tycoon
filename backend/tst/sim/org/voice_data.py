"""Executives' report voices as data (docs/formulas.md 27.2, M13b; exec_voices.yaml)."""

from __future__ import annotations

import string

from pydantic import BaseModel, ConfigDict, Field, model_validator

PLACEHOLDERS = ("did", "pitch", "worry", "numbers", "quarter")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class VoiceRule(_Frozen):
    trait: str
    at_least: float | None = Field(default=None, ge=1, le=20)  # tunable-exempt: 1-20 scale
    at_most: float | None = Field(default=None, ge=1, le=20)  # tunable-exempt: 1-20 scale

    @model_validator(mode="after")
    def _check(self) -> VoiceRule:
        if (self.at_least is None) == (self.at_most is None):
            raise ValueError("a voice rule has exactly one of at_least or at_most")
        return self

    def matches(self, value: float) -> bool:
        if self.at_least is not None:
            return value >= self.at_least
        return self.at_most is not None and value <= self.at_most


class Voice(_Frozen):
    key: str
    rule: VoiceRule | None = None
    opener: str
    did: str
    nothing_done: str
    pitch: str
    no_pitch: str
    worry: str
    calm: str
    numbers: str


class VoicesFile(_Frozen):
    voices: tuple[Voice, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> VoicesFile:
        keys = [v.key for v in self.voices]
        if len(set(keys)) != len(keys):
            raise ValueError("exec_voices.yaml: voice keys must be unique")
        if self.voices[-1].rule is not None or any(v.rule is None for v in self.voices[:-1]):
            raise ValueError("exec_voices.yaml: only the last voice has no rule")
        for v in self.voices:
            for name in ("opener", "did", "pitch", "worry", "numbers"):
                text = getattr(v, name)
                for word in _fields(text):
                    if word not in PLACEHOLDERS:
                        raise ValueError(f"voice {v.key}.{name}: unknown placeholder {word!r}")
        return self


def _fields(text: str) -> list[str]:
    return [f for _, f, _, _ in string.Formatter().parse(text) if f]
