from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    reasons: list[str]
    missing: list[str] = []


class AdjustmentCreate(BaseModel):
    value: float = Field(ge=-1, le=1)
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


class AllotmentDifficulty(BaseModel):
    label: str
    companies: list[str]
    note: str | None = None


class ReportInsights(BaseModel):
    fundamental_valuation_ranking: list[list[str]] = []
    allotment_difficulty: list[AllotmentDifficulty] = []


class IPOList(BaseModel):
    items: list[IPOBase]
    total: int
    page: int
    page_size: int
    insights: ReportInsights = ReportInsights()


class IPODetail(IPOBase):
    dimensions: list[DimensionScore]
    risks: list[str]
    metrics: dict[str, Any]
    adjustments: list[Adjustment]
    issuance_shares: float | None = None
    lot_size: int | None = None
    greenshoe: bool | None = None
    cornerstone_investors: list[str] = []
    cornerstone_ratio: float | None = None
    sponsors: list[str] = []
    company_quality: list[str] = []


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


class AShareHotWord(BaseModel):
    word: str
    count: int
    sentiment: Literal["positive", "neutral", "negative"]
    weight: int


class AShareMarketSample(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float
    change: float
    volume: float
    amount: float


class AShareHotSector(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float
    turnover_rate: float
    amount: float
    main_inflow: float
    leading_stock: str
    leading_stock_code: str
    leading_stock_change_pct: float


class AShareSentiment(BaseModel):
    record_date: date
    generated_at: datetime
    average_price: float
    average_change_pct: float
    stock_count: int
    up_count: int
    down_count: int
    flat_count: int
    sentiment_score: int
    sentiment_label: str
    market_source: str
    hot_word_sources: list[str]
    sector_source: str
    market_file: str
    hot_words_file: str
    hot_sectors_file: str
    hot_words: list[AShareHotWord]
    hot_sectors: list[AShareHotSector]
    market_sample: list[AShareMarketSample]
