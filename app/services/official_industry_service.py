"""
官方行业数据服务

从官网提供的 JSON 获取 A 股行业分类，避免 AKShare 轮询查询导致封号。
数据格式：{"600519": "白酒", "000001": "银行", ...} 或 [{"code": "600519", "industry": "白酒"}, ...]
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 缓存：避免频繁请求官网
_industry_cache: Optional[Dict[str, str]] = None
_cache_time: Optional[datetime] = None
_CACHE_TTL_HOURS = 24


def get_official_industry_url() -> Optional[str]:
    """从配置获取官方行业数据 URL"""
    try:
        from app.core.config import settings
        url = getattr(settings, "OFFICIAL_INDUSTRY_DATA_URL", None)
        if url and str(url).strip():
            return str(url).strip()
    except Exception:
        pass
    import os
    return os.getenv("OFFICIAL_INDUSTRY_DATA_URL", "").strip() or None


async def fetch_industry_mapping() -> Dict[str, str]:
    """
    从官网 URL 获取股票代码 -> 行业 映射
    Returns: {"600519": "白酒", "000001": "银行", ...}
    """
    global _industry_cache, _cache_time
    url = get_official_industry_url()
    if not url:
        logger.debug("未配置 OFFICIAL_INDUSTRY_DATA_URL，跳过官方行业数据")
        return {}

    # 检查缓存
    if _industry_cache is not None and _cache_time is not None:
        if datetime.now() - _cache_time < timedelta(hours=_CACHE_TTL_HOURS):
            return _industry_cache

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"获取官方行业数据失败: {url}, {e}")
        if _industry_cache is not None:
            return _industry_cache
        return {}

    result: Dict[str, str] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            code = str(k).strip().zfill(6)
            if isinstance(v, str) and v.strip():
                result[code] = v.strip()
            elif isinstance(v, dict) and v.get("industry"):
                result[code] = str(v["industry"]).strip()
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                code = str(item.get("code", "")).strip().zfill(6)
                industry = item.get("industry") or item.get("industry_name")
                if code and industry:
                    result[code] = str(industry).strip()

    _industry_cache = result
    _cache_time = datetime.now()
    logger.info(f"✅ 官方行业数据加载成功: {len(result)} 只股票")
    return result


def get_industry_sync(code: str) -> Optional[str]:
    """同步获取单只股票行业（使用缓存，需先调用 fetch_industry_mapping）"""
    global _industry_cache
    if not _industry_cache:
        return None
    code6 = str(code).strip().zfill(6)
    return _industry_cache.get(code6)


async def get_industry(code: str) -> Optional[str]:
    """异步获取单只股票行业"""
    mapping = await fetch_industry_mapping()
    code6 = str(code).strip().zfill(6)
    return mapping.get(code6)


async def sync_industry_to_stock_basic_info(db=None) -> Dict[str, int]:
    """
    将官方行业数据批量更新到 stock_basic_info
    Returns: {"updated": N, "total": M}
    """
    if db is None:
        from app.core.database import get_mongo_db
        db = get_mongo_db()
    mapping = await fetch_industry_mapping()
    if not mapping:
        return {"updated": 0, "total": 0}
    coll = db["stock_basic_info"]
    updated = 0
    from pymongo import UpdateOne
    ops = []
    for code, industry in mapping.items():
        ops.append(UpdateOne(
            {"$or": [{"code": code}, {"symbol": code}]},
            {"$set": {"industry": industry, "industry_source": "official"}}
        ))
    if ops:
        result = await coll.bulk_write(ops, ordered=False)
        updated = result.modified_count
    logger.info(f"✅ 官方行业数据同步到 stock_basic_info: 更新 {updated} 条")
    return {"updated": updated, "total": len(mapping)}
