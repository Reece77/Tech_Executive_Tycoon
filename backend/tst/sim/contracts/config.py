"""balance.yaml `contracts` (M23a, playtest 5): breaking contracts, counterparties' memory and
foundry contracts. Definitions only, so `tst.sim.data_models` can import it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Range(_Frozen):
    """A closed range [lo, hi]; written as a two-item list in YAML."""

    lo: float
    hi: float

    @model_validator(mode="before")
    @classmethod
    def _from_list(cls, value: object) -> object:
        if isinstance(value, list | tuple) and len(value) == 2:  # tunable-exempt: a pair
            return {"lo": value[0], "hi": value[1]}
        return value


class FoundryContractBalance(_Frozen):
    months: Range  # whole months a foundry contract may run
    max_price: float = Field(gt=0)  # the highest price a designer signs at, x the node's slot price
    customer_share: float = Field(gt=0, le=1)  # most of a fab's capacity one designer contracts
    max_share: float = Field(gt=0, le=1)  # most of a fab's capacity under contract
    take_or_pay: float = Field(ge=0, le=1)
    energy: int = Field(ge=0)


class ContractsBalance(_Frozen):
    break_penalty: float = Field(ge=0)  # on top of the discounted take-or-pay of the months left
    terminate_energy: int = Field(ge=0)
    mine_take_or_pay: float = Field(ge=0, le=1)  # a mine's sale contract's minimum (none before)
    relationship_hit: float = Field(ge=0, le=1)  # a counterparty's score falls this at a break
    relationship_recovery: float = Field(ge=0)  # and recovers this a month, towards 1
    relationship_premium: float = Field(ge=0)  # a new deal's price x (1 + this x (1 - score))
    relationship_floor: float = Field(ge=0, le=1)  # below this score it signs nothing new
    foundry: FoundryContractBalance
