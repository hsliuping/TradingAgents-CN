"""短周期分析缓存索引（M6，设计文档 §3.4）

语义边界（务必与结论快照区分）：
- 缓存 = 同一数据基准下的**分析结果副本**，TTL 内直接复用，不重跑 LLM
- 快照 = 历史版本的**对比基线**，只在真正重跑时产生
- 因此缓存命中不写结论快照、不计新分析次数、不出演化对照（M6.3）

集合 `analysis_cache_index`，键为用户 + 股票 + 档位 + 数据基准日 + 参数指纹，
同一键只保留最新一条（覆盖式写入），TTL 过期靠惰性覆盖，不做主动清理。
"""

import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

# 缓存索引集合（主库）
ANALYSIS_CACHE_COLLECTION = "analysis_cache_index"

# 仅单股 / ETF 分析参与缓存：交易复盘、持仓分析等不是「同股同档可复用」的语义
CACHEABLE_TASK_TYPES = frozenset({"stock_analysis", "etf_analysis"})

# 参数指纹成分：影响分析输出的输入项（分析师集合/偏好/自定义提示词/调试模板/模型等）
_FINGERPRINT_KEYS = (
    "selected_analysts",
    "preference_type",
    "custom_prompt",
    "debug_template_id",
    "debug_mode",
    "quick_analysis_model",
    "deep_analysis_model",
    "max_debate_rounds",
    "lookback_days",
)

# 不入缓存 payload 的运行时对象：AgentContext / LangChain 消息不可序列化且无复用价值；
# 上期结论块是本次分析的输入，下次分析会重新按最新快照组装，不应被缓存固化
_PAYLOAD_EXCLUDED_KEYS = ("context", "messages", "prev_conclusion_block")

# 缓存键字段（读写两侧共用，保证 key 完全一致）
_CACHE_KEY_FIELDS = ("user_id", "ticker", "depth", "data_as_of", "param_fingerprint")


def normalize_data_as_of(value: Any) -> str:
    """把分析日期/数据基准日归一化为 YYYY-MM-DD（未知返回空串）。"""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value or "").strip()
    if len(text) >= 10 and text[:4].isdigit() and text[4] == "-":
        return text[:10]
    return ""


def build_param_fingerprint(inputs: Dict[str, Any]) -> str:
    """计算参数指纹：只取影响输出的输入项，保证同一输入得到同一哈希。

    - 分析师集合按集合语义排序（顺序不影响产出）后参与哈希
    - 其余项取原值字符串化；缺失项按空值参与，保证键稳定
    """
    if not isinstance(inputs, dict):
        inputs = {}

    normalized: Dict[str, Any] = {}
    for key in _FINGERPRINT_KEYS:
        value = inputs.get(key)
        if key == "selected_analysts":
            if isinstance(value, (list, tuple, set)):
                normalized[key] = sorted(str(item).strip().lower() for item in value)
            elif isinstance(value, str) and value.strip():
                normalized[key] = [item.strip().lower() for item in value.split(",") if item.strip()]
            else:
                normalized[key] = []
        elif value is None:
            normalized[key] = ""
        elif isinstance(value, (list, tuple, set)):
            normalized[key] = sorted(str(item) for item in value)
        else:
            normalized[key] = str(value).strip()

    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def is_cache_eligible(task_type: Any, task_params: Optional[Dict[str, Any]], user_id: Optional[str]) -> bool:
    """判断本次任务是否参与短周期缓存（读或写）。

    不参与的情形：非单股/ETF 任务、匿名（无 user_id，键不成立）、断点续跑
    （管「同一次分析中断恢复」，与缓存入口不同）、debug 模式（排查需每次真跑）。

    注意：force_refresh 不在这里拦——它只跳过「读」（强制真跑），
    跑完仍覆盖写索引（M6.2），否则旧缓存会一直残留、TTL 内无法被新结果替换。
    """
    raw_type = getattr(task_type, "value", task_type)
    type_text = str(raw_type or "").strip().lower()
    if type_text not in CACHEABLE_TASK_TYPES:
        return False
    if not str(user_id or "").strip():
        return False

    params = task_params or {}
    if bool(params.get("resume")):
        return False
    if bool(params.get("debug_mode")):
        return False
    return True


def build_cache_key(
    user_id: str,
    ticker: str,
    depth: str,
    data_as_of: str,
    param_fingerprint: str,
) -> Dict[str, Any]:
    """构造缓存索引键（与写入侧字段一一对应）。"""
    return {
        "user_id": str(user_id or "").strip(),
        "ticker": str(ticker or "").strip().upper(),
        "depth": str(depth or "").strip(),
        "data_as_of": str(data_as_of or "").strip(),
        "param_fingerprint": str(param_fingerprint or "").strip(),
    }


async def find_cache_hit(
    db: Any,
    *,
    user_id: str,
    ticker: str,
    depth: str,
    data_as_of: str,
    param_fingerprint: str,
    ttl_min: int,
) -> Optional[Dict[str, Any]]:
    """按键查缓存；同键记录且在 TTL 内才算命中，返回 payload 与缓存元信息。"""
    try:
        ttl = int(ttl_min)
    except (TypeError, ValueError):
        return None
    if ttl <= 0:
        return None

    key = build_cache_key(user_id, ticker, depth, data_as_of, param_fingerprint)
    doc = await db[ANALYSIS_CACHE_COLLECTION].find_one(key, sort=[("created_at", -1)])
    if not doc:
        return None

    created_at = doc.get("created_at")
    if not isinstance(created_at, datetime):
        return None
    if created_at.tzinfo is None:
        # 历史记录可能没带时区，按当前时区解释，避免比较时报 naive/aware 冲突
        created_at = created_at.replace(tzinfo=now_tz().tzinfo)
    if now_tz() - created_at >= timedelta(minutes=ttl):
        return None

    result = doc.get("result")
    if not isinstance(result, dict) or not result:
        return None

    cache_meta = doc.get("cache_meta")
    if not isinstance(cache_meta, dict):
        cache_meta = {}
    cache_meta = {
        **cache_meta,
        "generated_at": cache_meta.get("generated_at") or created_at.isoformat(),
        "data_as_of": cache_meta.get("data_as_of") or key["data_as_of"],
        "depth": cache_meta.get("depth") or key["depth"],
        "ttl_min": ttl,
        "cached_at": created_at.isoformat(),
    }
    return {"result": result, "cache_meta": cache_meta}


async def save_cache_entry(
    db: Any,
    *,
    user_id: str,
    ticker: str,
    stock_name: str,
    depth: str,
    data_as_of: str,
    param_fingerprint: str,
    ttl_min: int,
    run_id: str,
    result: Dict[str, Any],
) -> bool:
    """写入/覆盖缓存索引（同键只留最新一条；TTL 过期靠覆盖，不做主动清理）。"""
    try:
        ttl = int(ttl_min)
    except (TypeError, ValueError):
        return False
    if ttl <= 0 or not isinstance(result, dict) or not result:
        return False

    payload = _sanitize_payload(result)
    if not payload:
        return False

    key = build_cache_key(user_id, ticker, depth, data_as_of, param_fingerprint)
    now = now_tz()
    doc = {
        **key,
        "stock_name": str(stock_name or ""),
        "ttl_min": ttl,
        "run_id": str(run_id or ""),
        "created_at": now,
        "expires_at": now + timedelta(minutes=ttl),
        "cache_meta": {
            "generated_at": now.isoformat(),
            "data_as_of": key["data_as_of"],
            "depth": key["depth"],
            "run_id": str(run_id or ""),
            "ttl_min": ttl,
        },
        "result": payload,
    }
    await db[ANALYSIS_CACHE_COLLECTION].replace_one(key, doc, upsert=True)
    return True


def build_cache_notice(cache_meta: Dict[str, Any]) -> str:
    """构造报告头部的缓存命中标注（命中即复用，不冒充新分析）。"""
    generated = _format_generated_at((cache_meta or {}).get("generated_at"))
    data_as_of = str((cache_meta or {}).get("data_as_of") or "未知")
    return (
        f"缓存命中：分析于 {generated}，数据基准日 {data_as_of}，"
        "TTL 内直接复用；如需重跑请用强制刷新。"
    )


def _format_generated_at(value: Any) -> str:
    """缓存生成时间的展示格式（YYYY-MM-DD HH:MM，无法解析时原样返回）。"""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value or "").strip()
    if not text:
        return "未知"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.strftime("%Y-%m-%d %H:%M")


def _sanitize_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """剔除不可序列化/无复用价值的运行时对象，保证可安全入库。"""
    slim = {key: value for key, value in result.items() if key not in _PAYLOAD_EXCLUDED_KEYS}
    try:
        return json.loads(json.dumps(slim, ensure_ascii=False, default=str))
    except (TypeError, ValueError) as e:
        logger.warning(f"⚠️ 分析缓存 payload 序列化失败，本次不缓存: {e}")
        return {}
