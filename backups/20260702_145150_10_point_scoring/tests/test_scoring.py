from app.scoring import recommendation, score_ipo


def test_dimension_weights_sum_to_100():
    dimensions, score = score_ipo({})
    assert sum(item.weight for item in dimensions) == 100
    assert score == 50
    assert all(item.missing for item in dimensions)


def test_recommendation_boundaries():
    assert recommendation(75) == "申购"
    assert recommendation(74.99) == "观望"
    assert recommendation(55) == "观望"
    assert recommendation(54.99) == "回避"

