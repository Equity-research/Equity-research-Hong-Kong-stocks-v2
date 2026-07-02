from app.config import load_rules
from app.schemas import DimensionScore


def _normalize(value: float, minimum: float, maximum: float, higher_is_better: bool) -> float:
    ratio = max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    return ratio if higher_is_better else 1 - ratio


def score_ipo(metrics: dict[str, float | None]) -> tuple[list[DimensionScore], float]:
    rules = load_rules()
    dimensions: list[DimensionScore] = []
    for key, dimension in rules["dimensions"].items():
        total = 0.0
        reasons: list[str] = []
        missing: list[str] = []
        for metric_key, indicator in dimension["indicators"].items():
            value = metrics.get(metric_key)
            if value is None:
                missing.append(indicator["label"])
                normalized = 0.5
                reasons.append(f'{indicator["label"]}：缺失，按中性值计分')
            else:
                normalized = _normalize(value, indicator["min"], indicator["max"], indicator["higher_is_better"])
                reasons.append(f'{indicator["label"]}：{value:g}，贡献 {normalized * indicator["weight"]:.1f}/{indicator["weight"]}')
            total += normalized * indicator["weight"]
        dimensions.append(DimensionScore(key=key, label=dimension["label"], score=round(total, 1),
                                         weight=dimension["weight"], reasons=reasons, missing=missing))
    final = round(sum(item.score for item in dimensions), 1)
    return dimensions, final


def recommendation(score: float) -> str:
    if score >= 75:
        return "申购"
    if score >= 55:
        return "观望"
    return "回避"

