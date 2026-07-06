from app.scoring import normalize_metrics, recommendation, score_ipo


def test_dimension_weights_sum_to_10_and_missing_scores_zero():
    dimensions, score = score_ipo({})
    assert sum(item.weight for item in dimensions) == 10
    assert score == 0
    assert all(item.missing for item in dimensions if item.key != "greenshoe")
    assert next(item for item in dimensions if item.key == "greenshoe").missing == []


def test_recommendation_boundaries():
    assert recommendation(8) == "申购"
    assert recommendation(7.99) == "观望"
    assert recommendation(4) == "观望"
    assert recommendation(3.99) == "回避"


def test_ah_scoring_boundaries():
    base = {"has_cornerstone": True, "cornerstone_quality_good": True, "greenshoe": True,
            "subscription_multiple": 100, "is_ah": True, "sponsor_quality_good": True}
    expected = [(30, 7), (30.01, 8), (50, 8), (50.01, 9), (70, 9), (70.01, 10)]
    for premium, total in expected:
        _, score = score_ipo({**base, "ah_premium": premium})
        assert score == total


def test_subscription_boundaries_and_peer_valuation():
    base = {"has_cornerstone": False, "cornerstone_quality_good": True, "greenshoe": False,
            "is_ah": False, "peer_valuation_discount": 31, "sponsor_quality_good": False}
    expected = [(9.99, 3), (10, 4), (50, 5), (100, 6)]
    for multiple, total in expected:
        dimensions, score = score_ipo({**base, "subscription_multiple": multiple})
        assert score == total
        assert next(item for item in dimensions if item.key == "cornerstone_quality").score == 0


def test_boolean_metrics_are_normalized_before_scoring():
    dimensions, score = score_ipo({
        "has_cornerstone": "否",
        "cornerstone_quality_good": "是",
        "greenshoe": "无",
        "subscription_multiple": 0,
        "is_ah": False,
        "peer_valuation_discount": 0,
        "sponsor_quality_good": "有",
    })

    by_key = {item.key: item.score for item in dimensions}
    assert by_key["cornerstone_presence"] == 0
    assert by_key["cornerstone_quality"] == 0
    assert by_key["greenshoe"] == 0
    assert by_key["sponsor"] == 1
    assert score == 2


def test_cornerstone_presence_is_inferred_from_investors_or_ratio():
    metrics = normalize_metrics({
        "has_cornerstone": None,
        "cornerstone_investors": "GIC、富达",
        "cornerstone_ratio": "",
        "greenshoe": "15%",
    })

    assert metrics["has_cornerstone"] is True
    assert metrics["cornerstone_investors"] == ["GIC", "富达"]
    assert metrics["greenshoe"] is True


def test_missing_greenshoe_defaults_to_false():
    metrics = normalize_metrics({})

    assert metrics["greenshoe"] is False


def test_befar_has_no_greenshoe_and_scores_zero():
    from app.sample_data import SAMPLE_IPOS

    metrics = next(item["metrics"] for item in SAMPLE_IPOS if item["code"] == "06745.HK")
    dimensions, _ = score_ipo(metrics)
    by_key = {item.key: item.score for item in dimensions}

    assert normalize_metrics(metrics)["greenshoe"] is False
    assert by_key["greenshoe"] == 0
