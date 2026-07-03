import re
from typing import Any

from app.config import load_rules
from app.schemas import DimensionScore


TRUE_VALUES = {"1", "true", "t", "yes", "y", "有", "是", "设有", "存在"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "无", "否", "没有", "未设", "不设", "暂无", "不适用", "na", "n/a", "-"}


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return None
        compact = re.sub(r"[\s　：:，,。.;；（）()]+", "", text)
        if compact in TRUE_VALUES:
            return True
        if compact in FALSE_VALUES:
            return False
        if compact.endswith("%"):
            try:
                return float(compact.rstrip("%")) > 0
            except ValueError:
                pass
        if compact.startswith(("无", "否", "未", "不设", "没有", "暂无")):
            return False
        if compact.startswith(("有", "是", "设有")):
            return True
    return None


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        return float(match.group()) if match else None
    return None


def _to_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        if _to_bool(value) is False:
            return []
        return [item.strip() for item in re.split(r"[、,，;/；\n]+", value) if item.strip()]
    return []


def normalize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metrics)
    investors = _to_list(normalized.get("cornerstone_investors"))
    ratio = _to_float(normalized.get("cornerstone_ratio"))
    normalized["cornerstone_investors"] = investors
    normalized["cornerstone_ratio"] = ratio

    for key in ("greenshoe", "has_cornerstone", "cornerstone_quality_good", "sponsor_quality_good", "is_ah"):
        parsed = _to_bool(normalized.get(key))
        normalized[key] = parsed

    if normalized["greenshoe"] is None:
        for alias in ("over_allotment_option", "over_allotment", "over_allocation_option"):
            parsed = _to_bool(normalized.get(alias))
            if parsed is not None:
                normalized["greenshoe"] = parsed
                break

    inferred_cornerstone = bool(investors) or (ratio is not None and ratio > 0)
    if normalized["has_cornerstone"] is None and inferred_cornerstone:
        normalized["has_cornerstone"] = True
    if normalized["has_cornerstone"] is False:
        normalized["cornerstone_quality_good"] = False
    return normalized


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
    metrics = normalize_metrics(metrics)
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
