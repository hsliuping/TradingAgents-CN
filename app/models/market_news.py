"""
市场新闻数据库模型
支持AI分析、标签系统和词云生成
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class NewsCategory(str, Enum):
    """新闻分类"""
    MARKET_OVERVIEW = "market_overview"
    HOT_CONCEPT = "hot_concept"
    STOCK_ALERT = "stock_alert"
    FUND_MOVEMENT = "fund_movement"
    LIMIT_UP = "limit_up"


class SentimentType(str, Enum):
    """情感类型"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class NewsDocument(BaseModel):
    """新闻文档模型"""
    id: Optional[str] = None
    title: str
    content: str
    url: Optional[str] = None
    time: str
    dataTime: datetime
    source: str
    category: NewsCategory
    tags: List[Dict] = []
    keywords: List[str] = []
    stocks: List[Dict] = []
    subjects: List[str] = []
    sentiment: Optional[SentimentType] = None
    sentimentScore: float = 0.0
    hotnessScore: float = 0.0
    isRed: bool = False
    marketStatus: List[str] = []
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)


class WordCloudData(BaseModel):
    """词云数据"""
    word: str
    weight: float
    count: int
