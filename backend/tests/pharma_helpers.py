"""A game with pharmaceutical programmes of the player's (M42 tests), at any month without playing
to it: a new game moved to `turn`, with programmes or a marketed drug placed directly."""

from __future__ import annotations

from dataclasses import replace

from tst.loader import LoadedData
from tst.sim.pharma import data as pd
from tst.sim.pharma.models import Authorisation, Drug, Hta, Programme
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState

_BASES: dict[tuple[int, int], GameState] = {}


def base(loaded: LoadedData, seed: int = 1, turn: int = 0) -> GameState:
    if (id(loaded), seed) not in _BASES:
        found = loaded.game_data.scenario("ex_big_tech_founders")
        assert found is not None
        state, _ = new_game(
            save_name="pharma",
            master_seed=seed,
            scenario=found,
            difficulty="standard",
            company_name="Pharma Co",
            founder=DEFAULT_FOUNDER,
            balance=loaded.balance,
            data=loaded.game_data,
        )
        _BASES[(id(loaded), seed)] = state
    return replace(_BASES[(id(loaded), seed)], turn=turn)


def programme(state: GameState, **kw: object) -> Programme:
    fields: dict[str, object] = {
        "id": 1,
        "company_id": state.player.id,
        "name": "PX-1",
        "indication": "thrombosis",
        "area": "cardiovascular",
        "modality": "small_molecule",
        "stage": "phase2",
        "start_turn": state.turn,
        "due_turn": state.turn + 12,
        "efficacy": 0.6,
        "safety": 0.7,
    }
    fields.update(kw)
    return Programme(**fields)  # type: ignore[arg-type]


def marketed(
    loaded: LoadedData,
    turn: int,
    efficacy: float = 0.7,
    modality: str = "small_molecule",
    approved: int | None = None,
    seed: int = 1,
) -> GameState:
    """A drug approved everywhere at `approved` (default: two years before `turn`), covered."""
    d = loaded.game_data
    state = base(loaded, seed, turn)
    at = turn - 24 if approved is None else approved
    p = programme(
        state, stage="approved", status="marketed", efficacy=efficacy, obs_n=3,
        obs_eff=efficacy, obs_safety=0.7, modality=modality, patent_turn=at - 120,
        ind_turn=at - 96, filed_turn=at - 12, approved_turn=at, start_turn=at, due_turn=at,
    )  # fmt: skip
    rows = [Authorisation(p.id, r.key, r.region, at) for r in pd.regulators(d)]
    rows += [
        Authorisation(p.id, pd.RELY + region, region, at)
        for region in d.region_keys
        if pd.reliance_share(d, region) > 0
    ]
    ind = pd.indication(d, p.indication)
    hta = tuple(
        Hta(p.id, r.region, at, at, "covered", at) for r in pd.file(d).pricing.regions if r.hta
    )
    return replace(
        state,
        pharma_programmes=(p,),
        pharma_authorisations=tuple(rows),
        pharma_drugs=(Drug(p.id, round(ind.price_year * pd.CENTS), 1.0, at),),
        pharma_hta=hta,
    )
