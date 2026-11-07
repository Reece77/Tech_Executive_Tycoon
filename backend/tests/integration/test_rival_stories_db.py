"""Rival CEO pieces (M15b addendum 12) through the text writer: the LLM's words replace the
inbox item's template body; with the LLM off (template adapter) the template stays."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from tst.db.events import write_pending
from tst.db.models import InboxItemRow, LLMTextRow
from tst.db.repository import create_save, open_session, write_session
from tst.llm.base import Completion, TextPrompt
from tst.llm.offline import MockLLMAdapter, TemplateAdapter
from tst.loader import LoadedData

TEMPLATE = 'Asked about the founder, they said: "They talk. We ship."'


class _Writes(MockLLMAdapter):
    def generate_text(self, prompt: TextPrompt) -> Completion:
        self.calls.append(prompt)
        return Completion("[mock] " + prompt.fallback)


def _save(tmp_path: Path, loaded: LoadedData) -> Path:
    path = create_save(
        "stories",
        5,
        "ex_big_tech_founders",
        company_name="Story Co",
        data=loaded,
        save_dir=tmp_path / "saves",
    )
    with write_session(path) as session:
        session.add(
            InboxItemRow(
                turn=0,
                company_id=1,
                template="rival_story",
                title="CEO answers founder",
                body=TEMPLATE,
                link_kind="rival",
                link_id=2,
            )
        )
        session.add(
            LLMTextRow(company_id=1, turn=0, kind="rival_story", ref_id=2, status="pending")
        )
    return path


def _body(path: Path) -> tuple[str, str]:
    with open_session(path) as session:
        row = session.scalars(select(InboxItemRow).where(InboxItemRow.template == "rival_story"))
        text = session.scalars(select(LLMTextRow).where(LLMTextRow.kind == "rival_story"))
        return row.one().body, text.one().source


def test_the_llm_rewords_the_piece(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    adapter = _Writes()
    write_pending(path, loaded, adapter=adapter)
    body, source = _body(path)
    assert body == "[mock] " + TEMPLATE and source == "mock"
    prompt = next(p for p in adapter.calls if p.kind == "rival_story")
    assert TEMPLATE in prompt.user  # engine facts only: the template's own words


def test_template_when_the_llm_is_off(tmp_path: Path, loaded: LoadedData) -> None:
    path = _save(tmp_path, loaded)
    write_pending(path, loaded, adapter=TemplateAdapter())
    assert _body(path) == (TEMPLATE, "template")
