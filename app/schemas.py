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


class GreyMarketQuote(BaseModel):
    ipo_id: int
    code: str
    price: float
    change_pct: float | None = None
    fetched_at: datetime
    source: str


class GreyMarketManualPrice(BaseModel):
    price: float = Field(gt=0)


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


class DataRefreshStart(BaseModel):
    job_id: str
    status: str


class DataRefreshStatus(BaseModel):
    job_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    report_date: date
    detail: str | None = None
    progress_current: int = 0
    progress_total: int = 0
    progress_percent: int = 0
    progress_label: str | None = None


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


class AShareSentimentHistoryPoint(BaseModel):
    record_date: date
    generated_at: datetime
    sentiment_score: int
    sentiment_label: str
    average_price: float
    average_change_pct: float
    stock_count: int
    up_count: int
    down_count: int
    flat_count: int


class USMarketNewsItem(BaseModel):
    title: str
    source: str
    url: str
    published_at: str | None = None
    title_zh: str | None = None
    source_zh: str | None = None
    article_title_zh: str | None = None
    article_summary_zh: str | None = None
    article_body_zh: str | None = None
    article_key_points_zh: list[str] | None = None
    original_url: str | None = None
    original_title: str | None = None
    original_body: str | None = None
    original_saved_at: str | None = None


class USMarketModule(BaseModel):
    key: str
    name: str
    focus: str
    sentiment_score: int
    trend: str
    analysis: str
    news: list[USMarketNewsItem]


class QQQHistoryPoint(BaseModel):
    date: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    change_pct: float | None = None


class USMarketQQQ(BaseModel):
    symbol: str
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    quote_time: str | None = None
    trend: str
    analysis: str
    history: list[QQQHistoryPoint]
    news: list[USMarketNewsItem]


class USMarketDashboard(BaseModel):
    record_date: date
    generated_at: datetime
    source: str
    cache_file: str
    modules: list[USMarketModule]
    qqq: USMarketQQQ
    highlights: list[str]
