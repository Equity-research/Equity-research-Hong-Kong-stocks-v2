from typing import Any

from app.config import load_rules
from app.schemas import DimensionScore


def _band_score(value: float, bands: list[dict[str, float]]) -> float:
    for band in bands:
        if "greater_than" in band and value > band["greater_than"]:
            return float(band["score"])
        if "min" in band and value >= band["min"]:
            return float(band["score"])
    return 0.0


def _boolean_dimension(key: str, rule: dict[str, Any], metrics: dict[str, Any]) -> DimensionScore:
    metric = rule["metric"]
    value = metrics.get(metric)
    missing = [] if value is not None else [rule["label"]]
    if rule.get("requires") and not metrics.get(rule["requires"]):
        score = 0.0
        reason = f'{rule["label"]}：无基石投资者，不计分'
    elif value is None:
        score = 0.0
        reason = f'{rule["label"]}：数据缺失，计 0 分'
    else:
        score = float(rule["weight"] if value else 0)
        reason = f'{rule["label"]}：{"符合" if value else "不符合"}，贡献 {score:g}/{rule["weight"]}'
    return DimensionScore(key=key, label=rule["label"], score=score, weight=rule["weight"],
                          reasons=[reason], missing=missing)


def score_ipo(metrics: dict[str, Any]) -> tuple[list[DimensionScore], float]:
    rules = load_rules()
    dimensions: list[DimensionScore] = []
    for key, rule in rules["dimensions"].items():
        if key in {"cornerstone_presence", "cornerstone_quality", "greenshoe", "sponsor"}:
            dimensions.append(_boolean_dimension(key, rule, metrics))
            continue

        if key == "subscription":
            value = metrics.get(rule["metric"])
            score = 0.0 if value is None else _band_score(float(value), rule["bands"])
            missing = [rule["label"]] if value is None else []
            reason = (f'{rule["label"]}：数据缺失，计 0 分' if value is None else
                      f'{rule["label"]}：{value:g} 倍，贡献 {score:g}/{rule["weight"]}')
        else:
            is_ah = bool(metrics.get("is_ah"))
            metric = rule["ah_metric"] if is_ah else rule["peer_metric"]
            bands = rule["ah_bands"] if is_ah else rule["peer_bands"]
            value = metrics.get(metric)
            score = 0.0 if value is None else _band_score(float(value), bands)
            missing = ["A/H 溢价" if is_ah else "相对同业估值折价"] if value is None else []
            basis = "A/H 溢价" if is_ah else "相对同业估值折价"
            reason = (f'{basis}：数据缺失，计 0 分' if value is None else
                      f'{basis}：{value:g}%，贡献 {score:g}/{rule["weight"]}')
        dimensions.append(DimensionScore(key=key, label=rule["label"], score=score,
                                         weight=rule["weight"], reasons=[reason], missing=missing))
    final = round(sum(item.score for item in dimensions), 1)
    return dimensions, final


def recommendation(score: float) -> str:
    rules = load_rules()["recommendations"]
    if score >= rules["buy"]["min"]:
        return rules["buy"]["label"]
    if score >= rules["hold"]["min"]:
        return rules["hold"]["label"]
    return rules["avoid"]["label"]
