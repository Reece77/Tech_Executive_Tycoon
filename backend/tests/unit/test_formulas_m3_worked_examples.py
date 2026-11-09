"""docs/formulas.md 11.14 worked examples (noise off), plus the M3 data tables."""

from __future__ import annotations

import pytest

from tst.loader import LoadedData
from tst.sim.products import formulas as f

B2B = "b2b_saas"


def test_categories_match_formulas_tables(loaded: LoadedData) -> None:
    data = loaded.game_data
    assert [c.key for c in data.categories][:4] == [
        B2B,
        "dev_tools",
        "consumer_apps",
        "cybersecurity",
    ]
    assert [s.key for s in data.segments][:4] == ["consumer", "smb", "mid_market", "enterprise"]
    assert [s.key for s in data.segments][4:] == ["hyperscalers", "device_oems"]  # M12a, M12b
    b2b = data.category(B2B)
    assert b2b.market("smb").addressable == 400_000
    assert b2b.market("smb").reference_price_cents == 5000
    assert b2b.market("enterprise").hosting_cents == 40_000
    assert (b2b.growth, b2b.features_at_start, b2b.features_per_month) == (0.20, 60, 4.0)
    assert (b2b.scope, b2b.brand_constant) == (6, 60)
    for cat in data.categories:
        assert sum(cat.dev_weights.values()) == pytest.approx(1)
    sales = [s.key for s in data.segments if s.reach == "sales"]
    assert sales == ["mid_market", "enterprise", "hyperscalers", "device_oems"]  # M12a, M12b
    assert data.segment("smb").weights.price == 0.35


def test_every_role_has_a_product_function(loaded: LoadedData) -> None:
    by_function: dict[str, list[str]] = {}
    for role in loaded.game_data.roles:
        by_function.setdefault(role.product_function, []).append(role.key)
    assert sorted(by_function["builder"]) == sorted(
        [
            "software_engineer",
            "data_scientist",
            "devops_engineer",
            "security_engineer",
            "product_manager",
            "designer",
            "hardware_engineer",  # M12b
            "chip_designer",
            "manufacturing_engineer",
        ]
    )
    assert sorted(by_function["seller"]) == ["account_executive", "sales_representative"]
    assert by_function["marketer"] == ["marketer"]
    assert sorted(by_function["none"]) == [
        "finance_manager",
        "geologist",
        "mining_engineer",
        "operations_manager",
        "process_engineer",
        "recruiter",
    ]  # M18: geologist; M19: mining engineer; M20: process engineer


def test_incumbents_match_formulas_table(loaded: LoadedData) -> None:
    companies = loaded.game_data.incumbents
    assert [c.name for c in companies][:12] == [  # M8 appends five
        "Salesforce",
        "Oracle",
        "Zoho",
        "Atlassian",
        "Microsoft",
        "GitHub",
        "Facebook",
        "Zynga",
        "Evernote",
        "Symantec",
        "McAfee",
        "Check Point",
    ]
    sales_cloud = companies[0].products[0]
    assert (sales_cloud.quality, sales_cloud.features, sales_cloud.brand) == (70, 80, 80)
    assert sales_cloud.segments["smb"].price_cents == 6500
    # Starting shares were tuned for the incumbent equilibrium (M3a brief, Decisions made);
    # each segment keeps the 11.9 total.
    assert sales_cloud.segments["smb"].share_bp == 1000
    totals: dict[tuple[str, str], int] = {}
    for company in companies:
        for product in company.products:
            if product.regions is not None:  # M9's regional incumbents sell abroad only
                continue
            for seg, value in product.segments.items():
                key = (product.category, seg)
                totals[key] = totals.get(key, 0) + value.share_bp
    assert totals[("b2b_saas", "smb")] == 2500 and totals[("b2b_saas", "mid_market")] == 5500
    assert totals[("consumer_apps", "consumer")] == 4500
    assert max(totals.values()) <= 9000  # at most 90% served at the start (11.9)


def test_team_output_and_quality(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    b2b = loaded.game_data.category(B2B)
    team = [(12.0, None), (10.5, 58.0), (9.0, 54.0)]  # (d, morale); the founder has none
    m = [f.morale_factor(morale, pb) for _, morale in team]
    assert m == pytest.approx([1.0, 1.048, 1.024])
    o_i = [f.builder_output(d, mi, 1.0) for (d, _), mi in zip(team, m, strict=True)]
    assert o_i == pytest.approx([1.200, 1.100, 0.922], abs=5e-4)
    o = f.coord_factor(3, pb) * sum(o_i)
    assert o == pytest.approx(3.222, abs=5e-4)
    qcap = f.quality_cap([(oi, d) for oi, (d, _) in zip(o_i, team, strict=True)], pb)
    assert qcap is not None
    assert qcap / pb.qcap_per_skill == pytest.approx(10.63, abs=5e-3)
    assert pb.qcap_per_skill * round(qcap / pb.qcap_per_skill, 2) == pytest.approx(53.15)  # 53.2

    quality, points = pb.start_quality, 0.0
    after: dict[int, tuple[float, float]] = {}
    for turn in range(12):  # created in January 2010; phase 3 first runs in turn 0
        quality = f.next_quality(quality, o, b2b.scope, qcap, pb)
        points += o
        after[turn] = (quality, points)
    assert [round(after[t][0], 1) for t in (0, 5, 11)] == [13.5, 27.1, 37.4]
    assert [round(after[t][1], 1) for t in (5, 8, 11)] == [19.3, 29.0, 38.7]
    assert f.expected_features(b2b, 8) == 92
    score = f.feature_score(after[8][1], b2b, 8)
    assert score == pytest.approx(31.5, abs=0.05)
    assert round(after[8][0], 1) == 32.9
    assert after[8][0] >= pb.launch_min_quality and score >= pb.launch_min_feature


def test_appeal_and_share_smb(loaded: LoadedData) -> None:
    data, mb = loaded.game_data, loaded.balance.market
    smb = data.segment("smb")
    ref = data.category(B2B).market("smb").reference_price_cents
    rows = {
        "player": (40, 4000, 10, 40),
        "salesforce": (70, 6500, 80, 80),
        "zoho": (55, 2500, 40, 60),
    }
    scores = {k: f.price_score(ref, price) for k, (_, price, _, _) in rows.items()}
    assert scores["player"] == pytest.approx(62.5)
    assert scores["salesforce"] == pytest.approx(38.5, abs=0.05)
    assert scores["zoho"] == 100
    appeals = {
        k: f.appeal(smb.weights, q, scores[k], brand, feat)
        for k, (q, _, brand, feat) in rows.items()
    }
    assert appeals["player"] == pytest.approx(43.38, abs=0.006)
    assert appeals["salesforce"] == pytest.approx(62.96, abs=0.005)
    assert appeals["zoho"] == pytest.approx(69.75, abs=0.005)
    shares, outside = f.choice_shares(list(appeals.values()), smb.outside_option, mb)
    assert [round(s * 100, 2) for s in shares] == [10.71, 32.77, 44.55]
    assert round(outside * 100, 2) == 11.96

    best = max(appeals.values())
    churn_sf = f.churn_rate(smb.base_churn, best, appeals["salesforce"], 70, False, mb)
    churn_zoho = f.churn_rate(smb.base_churn, best, appeals["zoho"], 55, False, mb)
    assert churn_sf == pytest.approx(0.0341, abs=5e-5)
    assert churn_zoho == pytest.approx(0.03)
    d = 400_000
    customers_sf, customers_zoho = 0.15 * d, 0.10 * d
    unserved = d - customers_sf - customers_zoho
    in_play = customers_sf * churn_sf + customers_zoho * churn_zoho + smb.adoption * unserved
    assert round(customers_sf * churn_sf) == 2044
    assert round(customers_zoho * churn_zoho) == 1200
    assert round(smb.adoption * unserved) == 4500
    assert round(in_play) == 7744
    aware = f.awareness(10, mb)
    assert aware == pytest.approx(0.05)
    assert in_play * shares[0] * aware == pytest.approx(41.5, abs=0.05)
    own = f.churn_rate(smb.base_churn, best, appeals["player"], 40, False, mb)
    assert own == pytest.approx(0.0458, abs=5e-5)


def test_brand_from_budget_and_marketer(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    b2b = loaded.game_data.category(B2B)
    mu = f.contribution(12, f.morale_factor(50, pb))
    mk = f.marketing_points(1_000_000, mu, pb)  # $10,000 a month
    assert mk == pytest.approx(16)
    target = f.target_brand(mk, b2b.brand_constant)
    assert target == pytest.approx(21.05, abs=0.005)
    brand = 0.0
    for _ in range(12):
        brand = f.next_brand(brand, target, pb)
    assert round(brand, 1) == 15.1


def test_sales_capacity(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    m = f.morale_factor(60, pb)
    cap = f.seller_capacity(pb.seller_rate["mid_market"], [f.contribution(12, m)])
    assert cap == pytest.approx(2.544)
    assert round(cap, 2) == 2.54
    assert f.sell_skill(12, 12, 12) == 12


@pytest.mark.parametrize(
    ("builders", "expected"), [(1, 1.0), (5, 1.0), (6, 0.98), (15, 0.8), (40, 0.6)]
)
def test_coordination_cost(loaded: LoadedData, builders: int, expected: float) -> None:
    assert f.coord_factor(builders, loaded.balance.products) == pytest.approx(expected)


def test_quality_rules(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    # No team: rot 0.5 a month.
    assert f.next_quality(30, 0.0, 6, None, pb) == 29.5
    # A token team (below 0.25 sigma) also rots.
    assert f.next_quality(30, 1.0, 6, 60, pb) == 29.5
    # Above the cap: 1% a month, never below the cap.
    assert f.next_quality(60, 6, 6, 50, pb) == pytest.approx(59.4)
    assert f.next_quality(50.2, 6, 6, 50, pb) == 50
    assert f.pace(4.5, 6, pb) == "fast" and f.pace(2.5, 6, pb) == "steady"
    assert f.pace(2.3, 6, pb) == "slow"


def test_tag_effects(loaded: LoadedData) -> None:
    pb = loaded.balance.products
    assert f.tag_multiplier(("quiet_genius",), pb) == 1.25
    assert f.tag_multiplier(("politician", "mentor"), pb) == 1.0
    assert f.qcap_skill(18.5, True, pb) == 20
    assert f.qcap_skill(12, True, pb) == 15
    assert f.dev_noise_sd(0, pb) == 0.15
    assert f.dev_noise_sd(3, pb) == 0.40
