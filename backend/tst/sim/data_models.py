"""Pydantic schemas for balance and seed data (ADR-0008).

Model definitions only: this module never reads files. `tst.loader` parses the YAML and
validates it with these models. Unknown keys and out-of-range values fail validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# balance.yaml
# ---------------------------------------------------------------------------


class CompanyBalance(_Frozen):
    base_monthly_cost_cents: int = Field(ge=0)


class ScenarioBalance(_Frozen):
    starting_cash_cents: int = Field(ge=0)


class DifficultyBalance(_Frozen):
    starting_cash_mult_bp: int = Field(gt=0)


class BackupBalance(_Frozen):
    every_n_turns: int = Field(gt=0)
    keep_periodic: int = Field(gt=0)


class Balance(_Frozen):
    company: CompanyBalance
    scenario: dict[str, ScenarioBalance]
    difficulty: dict[str, DifficultyBalance]
    backup: BackupBalance


# ---------------------------------------------------------------------------
# Seed data files
# ---------------------------------------------------------------------------

type AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]


class Account(_Frozen):
    code: str = Field(pattern=r"^\d{4}_[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    type: AccountType


class Scenario(_Frozen):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    available_in: Literal["v1", "v3"]
    starting_equity_account: str  # credited when starting cash is posted on turn 0

    @property
    def selectable(self) -> bool:
        """Only v1 scenarios can be started in this release."""
        return self.available_in == "v1"


class GameData(_Frozen):
    accounts: tuple[Account, ...]
    scenarios: tuple[Scenario, ...]

    @model_validator(mode="after")
    def _check_references(self) -> GameData:
        codes = [a.code for a in self.accounts]
        if len(set(codes)) != len(codes):
            raise ValueError("accounts.yaml has duplicate account codes")
        ids = [s.id for s in self.scenarios]
        if len(set(ids)) != len(ids):
            raise ValueError("scenarios.yaml has duplicate scenario ids")
        equity = {a.code for a in self.accounts if a.type == "equity"}
        for scenario in self.scenarios:
            if scenario.starting_equity_account not in equity:
                raise ValueError(
                    f"scenario {scenario.id!r}: starting_equity_account "
                    f"{scenario.starting_equity_account!r} is not an equity account"
                )
        return self

    def scenario(self, scenario_id: str) -> Scenario | None:
        for scenario in self.scenarios:
            if scenario.id == scenario_id:
                return scenario
        return None

    def account_codes(self) -> frozenset[str]:
        return frozenset(a.code for a in self.accounts)
