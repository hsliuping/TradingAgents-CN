import asyncio
import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.services.dianjin_service import DianjinService


logger = logging.getLogger("webapi")
router = APIRouter(tags=["dianjin"])
service = DianjinService()


class DianjinRunRequest(BaseModel):
    min_pe: float = Field(0.1, description="最小 PE")
    max_pe: float = Field(20.0, description="最大 PE")
    min_dividend: float = Field(3.0, description="最小当前股息率")
    max_dividend: float = Field(15.0, description="最大当前股息率")
    min_market_cap: float = Field(50.0, description="最小流通市值，单位亿元")
    ratio_threshold: float = Field(0.88, description="股价/MA120 偏离度上限")
    min_pb: Optional[float] = Field(None, description="最小 PB")
    max_pb: Optional[float] = Field(None, description="最大 PB")
    dividend_mode: Literal["any", "all"] = Field("any", description="三年股息率模式")
    specific_stocks: str = Field("", description="指定股票代码，逗号分隔")
    kline_days: int = Field(1300, ge=200, le=3000, description="K 线抓取天数")
    limit_count: int = Field(0, ge=0, le=5000, description="限制股票数量，仅调试用")


class DianjinResultItem(BaseModel):
    code: str
    name: str
    price: float
    pe_ttm: float
    dividend_yield: float
    market_cap: float
    pb: float
    ma120_ratio: float
    three_year_dividend: List[float]
    three_year_dividend_pass: bool
    three_year_all_pass: bool


class DianjinRunStats(BaseModel):
    total_samples: int
    realtime_count: int
    first_filter_count: int
    ma120_pass_count: int
    final_count: int
    duration_ms: int


class DianjinRunResponse(BaseModel):
    items: List[DianjinResultItem]
    stats: DianjinRunStats
    years: List[int]


def _validate_request(req: DianjinRunRequest) -> None:
    if req.min_pe > req.max_pe:
        raise HTTPException(status_code=400, detail="PE 最小值不能大于最大值")
    if req.min_dividend > req.max_dividend:
        raise HTTPException(status_code=400, detail="股息率最小值不能大于最大值")
    if req.ratio_threshold <= 0:
        raise HTTPException(status_code=400, detail="股价/MA120 偏离度上限必须大于 0")

    only_one_pb = (req.min_pb is None) ^ (req.max_pb is None)
    if only_one_pb:
        raise HTTPException(status_code=400, detail="PB 最小值和最大值需要同时填写，或同时留空")
    if req.min_pb is not None and req.max_pb is not None and req.min_pb > req.max_pb:
        raise HTTPException(status_code=400, detail="PB 最小值不能大于最大值")


@router.post("/run", response_model=DianjinRunResponse)
async def run_dianjin(req: DianjinRunRequest, user: dict = Depends(get_current_user)):
    _validate_request(req)
    try:
        result = await asyncio.to_thread(service.run_strategy, req.model_dump())
        return DianjinRunResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[dianjin] 运行策略失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"点金术运行失败: {exc}")
