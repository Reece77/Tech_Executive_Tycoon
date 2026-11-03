"""M12b: hardware, devices and fabless chips (formulas.md 26): contract-manufacturing and
wafer contracts (`production_contract`), each unit-sale product's month of production
(`production_month`), and assembly plants' yield and use on `facility`. Existing saves start
with none. M12b's eras that a save is already past arrive on schedule: historical ones at
their month, future ones at their seeded month (stream era_window, 26.4).

Revision ID: 0031_hardware
Revises: 0030_public_company
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_hardware"
down_revision: str | None = "0030_public_company"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "production_contract",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("supplier", sa.String(32), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Float(), nullable=False),
        sa.Column("signed_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=False),
        sa.Column("city", sa.String(32), nullable=True),
        sa.Column("delivered", sa.Float(), nullable=False),
        sa.Column("used", sa.Float(), nullable=False),
        sa.Column("charged_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_table(
        "production_month",
        sa.Column("turn", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("capacity", sa.Float(), nullable=False),
        sa.Column("units", sa.Float(), nullable=False),
        sa.Column("plant_units", sa.Float(), nullable=False),
        sa.Column("contract_units", sa.Float(), nullable=False),
        sa.Column("own_chips", sa.Float(), nullable=False),
        sa.Column("bought_chips", sa.Float(), nullable=False),
        sa.Column("internal_units", sa.Float(), nullable=False),
        sa.Column("bom_cents", sa.BigInteger(), nullable=False),
        sa.Column("chip_cents", sa.BigInteger(), nullable=False),
        sa.Column("assembly_cents", sa.BigInteger(), nullable=False),
        sa.Column("lost_units", sa.Float(), nullable=False),
    )
    with op.batch_alter_table("facility") as batch:
        batch.add_column(sa.Column("yield_rate", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("run_units", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("sold_units", sa.Float(), nullable=False, server_default="0"))
    _past_eras()
    op.execute("UPDATE save_meta SET schema_version = 31")


def _past_eras() -> None:
    """Eras a save is past but has not recorded (M12b's), arrived on schedule."""
    conn = op.get_bind()
    meta = conn.execute(sa.text("SELECT current_turn, master_seed FROM save_meta")).first()
    if meta is None:
        return
    from tst.config import Settings
    from tst.loader import load_all
    from tst.sim.research.levels import scheduled_turn
    from tst.sim.rng import RngFactory

    data = load_all(Settings().data_dir).game_data
    known = {r[0] for r in conn.execute(sa.text("SELECT key FROM era_arrival"))}
    rng = RngFactory(int(meta[1]))
    for index, era in enumerate(data.eras.eras):
        turn = scheduled_turn(era, index, rng)
        if era.key not in known and turn < int(meta[0]):
            conn.execute(
                sa.text(
                    "INSERT INTO era_arrival (key, turn, company_id, months_early) "
                    "VALUES (:k, :t, NULL, 0)"
                ),
                {"k": era.key, "t": turn},
            )


def downgrade() -> None:
    op.execute("UPDATE save_meta SET schema_version = 30")
    with op.batch_alter_table("facility") as batch:
        batch.drop_column("sold_units")
        batch.drop_column("run_units")
        batch.drop_column("yield_rate")
    op.drop_table("production_month")
    op.drop_table("production_contract")
