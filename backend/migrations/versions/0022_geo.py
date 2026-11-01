"""M9 cities, offices and regions (docs/formulas.md 19).

Side tables (migration 0013 loads company, person, org_unit and search through the current
models on older saves): `company_hq`, `person_city`, `office`, `unit_office`, `search_city`,
`regional_market`, `product_region` and `regional_segment`.

An existing save gets:
- San Francisco as the player's HQ (19.1);
- each person's home city: the first city of their region (19.1);
- every other region's market for each category and segment, with demand grown to its turn
  (19.5), North America being the home region;
- its v1 incumbents' presence in Europe at their starting shares of that demand, as at a new
  game (19.5). The six regional incumbents come only with new games, as M8's did.

Revision ID: 0022_geo
Revises: 0021_former_staff
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_geo"
down_revision: str | None = "0021_former_staff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOME = "north_america"  # an existing save's HQ is San Francisco (19.1)
HQ_CITY = "san_francisco"


def upgrade() -> None:
    op.create_table(
        "company_hq",
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), primary_key=True),
        sa.Column("city", sa.String(32), nullable=False),
    )
    op.create_table(
        "person_city",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), primary_key=True),
        sa.Column("city", sa.String(32), nullable=False),
    )
    op.create_table(
        "office",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("city", sa.String(32), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("opened_turn", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("closed_turn", sa.Integer(), nullable=True),
    )
    op.create_table(
        "unit_office",
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("org_unit.id"), primary_key=True),
        sa.Column("office_id", sa.Integer(), nullable=True),
    )
    op.create_table(
        "search_city",
        sa.Column("search_id", sa.Integer(), sa.ForeignKey("search.id"), primary_key=True),
        sa.Column("city", sa.String(32), nullable=False),
    )
    op.create_table(
        "regional_market",
        sa.Column("category", sa.String(32), primary_key=True),
        sa.Column("segment", sa.String(32), primary_key=True),
        sa.Column("region", sa.String(32), primary_key=True),
        sa.Column("addressable", sa.Float(), nullable=False),
    )
    op.create_table(
        "product_region",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id"), primary_key=True),
        sa.Column("region", sa.String(32), primary_key=True),
        sa.Column("launched_turn", sa.Integer(), nullable=False),
        sa.Column("live_turn", sa.Integer(), nullable=False),
    )
    op.create_table(
        "regional_segment",
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("product.id"), primary_key=True),
        sa.Column("region", sa.String(32), primary_key=True),
        sa.Column("segment", sa.String(32), primary_key=True),
        sa.Column("price_cents", sa.BigInteger(), nullable=True),
        sa.Column("customers", sa.Float(), nullable=False),
        sa.Column("capacity_limited", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("added_turn", sa.Integer(), nullable=False),
    )
    _seed_geo()
    op.execute("UPDATE save_meta SET schema_version = 22")


def _seed_geo() -> None:
    conn = op.get_bind()
    meta = conn.execute(sa.text("SELECT current_turn FROM save_meta")).first()
    if meta is None:
        return  # a brand-new save: new_game sets everything up
    from tst.config import Settings
    from tst.loader import load_all
    from tst.sim.data_models import incumbent_regions
    from tst.sim.geo.formulas import regional_price_cents
    from tst.sim.money import BP_DENOMINATOR
    from tst.sim.products.setup import regional_addressable_at

    data = load_all(Settings().data_dir).game_data
    turn = int(meta[0])
    player = conn.execute(sa.text("SELECT id FROM company WHERE is_player = 1")).first()
    if player is not None:
        conn.execute(
            sa.text("INSERT INTO company_hq (company_id, city) VALUES (:c, :city)"),
            {"c": int(player[0]), "city": HQ_CITY},
        )
    for person_id, region in conn.execute(sa.text("SELECT id, region FROM person")).all():
        conn.execute(
            sa.text("INSERT INTO person_city (person_id, city) VALUES (:p, :c)"),
            {"p": person_id, "c": data.region_city(region)},
        )
    demand: dict[tuple[str, str, str], float] = {}
    for cat in data.categories:
        for market in cat.markets:
            for region in data.region_keys:
                if region == HOME:
                    continue
                value = regional_addressable_at(data, cat.key, market.segment, region, HOME, turn)
                demand[(cat.key, market.segment, region)] = value
                conn.execute(
                    sa.text(
                        "INSERT INTO regional_market (category, segment, region, addressable) "
                        "VALUES (:c, :s, :r, :a)"
                    ),
                    {"c": cat.key, "s": market.segment, "r": region, "a": value},
                )
    products = {
        str(name): int(pid)
        for pid, name in conn.execute(
            sa.text(
                "SELECT product.id, product.name FROM product JOIN company "
                "ON company.id = product.company_id "
                "WHERE company.is_player = 0 AND product.status != 'retired'"
            )
        ).all()
    }
    for inc in data.incumbents:
        for spec in inc.products:
            product_id = products.get(spec.name)
            if spec.regions is not None or product_id is None:
                continue  # regional incumbents come with new games only
            for region in incumbent_regions(spec):
                if region == HOME:
                    continue
                conn.execute(
                    sa.text(
                        "INSERT INTO product_region (product_id, region, launched_turn, "
                        "live_turn) VALUES (:p, :r, :t, :t)"
                    ),
                    {"p": product_id, "r": region, "t": turn},
                )
                for seg, value in spec.segments.items():
                    conn.execute(
                        sa.text(
                            "INSERT INTO regional_segment (product_id, region, segment, "
                            "price_cents, customers, capacity_limited, added_turn) "
                            "VALUES (:p, :r, :s, :price, :c, 0, :t)"
                        ),
                        {
                            "p": product_id,
                            "r": region,
                            "s": seg,
                            "price": regional_price_cents(value.price_cents, region, HOME, data),
                            "c": demand[(spec.category, seg, region)]
                            * value.share_bp
                            / BP_DENOMINATOR,
                            "t": turn,
                        },
                    )


def downgrade() -> None:
    for table in (
        "regional_segment",
        "product_region",
        "regional_market",
        "search_city",
        "unit_office",
        "office",
        "person_city",
        "company_hq",
    ):
        op.drop_table(table)
    op.execute("UPDATE save_meta SET schema_version = 21")
