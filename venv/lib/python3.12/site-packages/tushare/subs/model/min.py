from datetime import datetime
from typing import Optional

from pydantic.main import BaseModel


class TsMin(BaseModel):
    ts_code: str
    freq: str
    trade_time: datetime
    open: Optional[float]
    close: Optional[float]
    high: Optional[float]
    low: Optional[float]
    vol: Optional[int]
    amount: Optional[int]
    open_int: Optional[int]
