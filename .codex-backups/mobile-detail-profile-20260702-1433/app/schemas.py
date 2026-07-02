from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    reasons: list[str]
    missing: list[str] = []


class AdjustmentCreate(BaseModel):
    value: float = Field(ge=-10, le=10)
    reason: str = Field(min_length=10, max_length=200)
    operator: str = Field(default="本地用户", min_length=1, max_length=40)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("调整原因至少需要 10 个字符")
        return value


class Adjustment(BaseModel):
    id: int
    value: float
    reason: str
    operator: str
    created_at: datetime
    original_score: float
    final_score: float


class IPOBase(BaseModel):
    id: int
    name: str
    english_name: str
    code: str
    industry: str
    price_low: float
    price_high: float
    minimum_subscription_amount: float | None = None
    subscription_multiple: float | None = None
    deadline: date
    is_sample: bool
    original_score: float
    adjustment: float
    final_score: float
    recommendation: Literal["申购", "观望", "回避"]


class IPOList(BaseModel):
    items: list[IPOBase]
    total: int
    page: int
    page_size: int


class IPODetail(IPOBase):
    dimensions: list[DimensionScore]
    risks: list[str]
    metrics: dict[str, float | None]
    adjustments: list[Adjustment]


class ReportSummary(BaseModel):
    id: int
    report_date: date
    version: int
    created_at: datetime
    item_count: int
    buy_count: int
    hold_count: int
    avoid_count: int


class ReportDetail(ReportSummary):
    markdown: str
