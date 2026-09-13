"""智能助手质量架构（A11）—— 词典与品种闸门（阶段 4，S4）。

路由相关的"词典知识"收敛到本模块这一个事实源：

1. ``StockDirectory``：A 股名称→代码目录，从 ``stock_basic_info`` **全量**加载
   并带 TTL 缓存（默认 6h），替代散落各处的硬编码股票名单与每请求一次的
   Mongo regex 查询；
2. A 股代码提取（沪深主板/创业板/科创板），单一正则事实源；
3. 不支持品种（港股/美股）词表与检测：从 planned_analysis_service 物理收编，
   助手路由与规划分析共用同一套词表，两处不再各存一份。

注意：近期搜索快路径/数据预检查的**意图关键词规则**不在本模块——其去留
（保留规则 / 前置小模型 / 归还主 agent 工具选择）尚待路由埋点数据支撑后决策
（设计文档 D6），当前保持 service 内现状不动。

本模块不 import service（避免循环依赖）；db 以参数传入。
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────── A 股代码 ───────────────────────────

# 沪深主板/创业板/科创板（与重构前 service 的 _STOCK_CODE_RE 行为一致；
# 北交所代码不在预检查链路的既有覆盖范围内，本次不扩大行为面）
A_SHARE_CODE_RE = re.compile(r"\b(00|30|60|68)\d{4}\b")


def extract_a_share_code(text: str) -> Optional[str]:
    """从文本提取首个 6 位沪深 A 股代码。"""
    if not text:
        return None
    match = A_SHARE_CODE_RE.search(text)
    return match.group(0) if match else None


# ─────────────────────────── 不支持品种（港股/美股）───────────────────────────

# 港股关键词（市场词 + 代表性公司名；stock_basic_info 仅含 A 股，
# 港美股名单无全量数据表可接，保留为静态词表，收敛在本模块单处维护）
HK_STOCK_KEYWORDS: Tuple[str, ...] = (
    "港股", "恒生", "恒指", "H股", "h股", "港交所", "港币",
    "腾讯控股", "美团", "小米集团", "阿里巴巴-SW", "京东集团-SW",
)

# 美股关键词
US_STOCK_KEYWORDS: Tuple[str, ...] = (
    "美股", "纳斯达克", "标普", "道琼斯", "NYSE", "NASDAQ",
    "苹果公司", "特斯拉", "英伟达", "谷歌", "亚马逊", "微软",
    "中概股",
)

# 港股代码（xxxxx.HK）/ 美股 ticker
HK_CODE_PATTERN = re.compile(r"\b\d{5}\.HK\b", re.IGNORECASE)
US_TICKER_PATTERN = re.compile(
    r"(?<![A-Za-z])(AAPL|TSLA|NVDA|GOOGL|GOOG|AMZN|MSFT|META|NFLX|AMD|BABA|JD|PDD|NIO|XPEV|LI)"
    r"(?![A-Za-z])",
    re.IGNORECASE,
)

_HK_MESSAGE = (
    "🚫 **暂不支持港股分析**\n\n"
    "当前系统专注于 **A股市场**（沪深两市），港股分析功能尚在开发中。\n\n"
    "您可以尝试：\n"
    "- 分析 A 股个股（如「帮我分析比亚迪」）\n"
    "- 分析行业板块（如「新能源汽车板块怎么样」）"
)
_US_MESSAGE = (
    "🚫 **暂不支持美股分析**\n\n"
    "当前系统专注于 **A股市场**（沪深两市），美股分析功能尚在开发中。\n\n"
    "您可以尝试：\n"
    "- 分析 A 股个股（如「帮我分析宁德时代」）\n"
    "- 分析行业板块（如「半导体板块最近走势如何」）"
)
_US_CODE_MESSAGE = (
    "🚫 **暂不支持美股分析**\n\n"
    "检测到您输入了美股代码。当前系统专注于 **A股市场**（沪深两市）。\n\n"
    "您可以尝试输入 A 股代码（如 600519、000858）或股票名称进行分析。"
)
_HK_CODE_MESSAGE = (
    "🚫 **暂不支持港股分析**\n\n"
    "检测到您输入了港股代码。当前系统专注于 **A股市场**（沪深两市）。\n\n"
    "您可以尝试输入 A 股代码（如 600519、000858）或股票名称进行分析。"
)


def detect_unsupported_asset(question: str) -> Optional[str]:
    """检测问题是否涉及不支持的品种（港股/美股）；命中返回提示文案，否则 None。

    与 planned_analysis_service 历史行为逐分支保持一致（检测顺序：港股词 →
    美股词 → 美股 ticker → 港股代码）。
    """
    q = (question or "").strip()
    if not q:
        return None

    if any(keyword in q for keyword in HK_STOCK_KEYWORDS):
        return _HK_MESSAGE
    if any(keyword in q for keyword in US_STOCK_KEYWORDS):
        return _US_MESSAGE
    if US_TICKER_PATTERN.search(q):
        return _US_CODE_MESSAGE
    if HK_CODE_PATTERN.search(q):
        return _HK_CODE_MESSAGE
    return None


# ─────────────────────────── A 股名称目录（全量 + TTL）───────────────────────────

class StockDirectory:
    """stock_basic_info 全量名称→代码目录（进程内单例、TTL 过期懒刷新）。

    - 全量加载（约 1.6 万条），替代硬编码名单与每请求 regex 查库；
    - TTL 内零数据库访问；过期后下次调用触发一次刷新（asyncio.Lock 防击穿）；
    - 刷新失败时继续沿用上次成功缓存（若有），不因词典故障阻断路由。
    """

    def __init__(self, ttl_seconds: float = 6 * 3600, clock=time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._name_map: Dict[str, str] = {}
        # 名称按长度降序：子串匹配时优先长名（"赛力斯集团"不会被短名截胡）
        self._names_desc: List[Tuple[str, str]] = []
        self._loaded_at: Optional[float] = None
        self._lock = asyncio.Lock()

    def is_fresh(self) -> bool:
        return self._loaded_at is not None and (self._clock() - self._loaded_at) < self._ttl

    async def get_name_map(self, db, *, force: bool = False) -> Dict[str, str]:
        """返回 名称→代码 映射；TTL 过期或强制时刷新。"""
        if not force and self.is_fresh():
            return self._name_map
        async with self._lock:
            # 双检：等锁期间可能已被其他协程刷新
            if not force and self.is_fresh():
                return self._name_map
            previous = dict(self._name_map)
            mapping: Dict[str, str] = {}
            try:
                async for doc in db["stock_basic_info"].find(
                    {}, {"symbol": 1, "name": 1}
                ):
                    name = (doc.get("name") or "").strip()
                    symbol = (doc.get("symbol") or "").strip()
                    # 与历史加载逻辑一致：2~6 字名称；同名保留先出现的代码
                    if name and symbol and 2 <= len(name) <= 6 and name not in mapping:
                        mapping[name] = symbol
                self._name_map = mapping
                self._names_desc = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
                self._loaded_at = self._clock()
                logger.info("[智能助手·词典] 股票名称目录已刷新: %d 条", len(mapping))
            except Exception as exc:
                logger.warning("[智能助手·词典] 刷新股票名称目录失败，沿用旧缓存(%d 条): %s",
                               len(previous), exc)
                # 保留旧缓存；首次加载就失败时保持空映射
                if previous:
                    self._name_map = previous
                    self._names_desc = sorted(
                        previous.items(), key=lambda kv: len(kv[0]), reverse=True
                    )
                    self._loaded_at = self._clock()
            return self._name_map

    async def resolve_symbol(self, text: str, db) -> Optional[str]:
        """从自然语言文本解析 A 股代码：6 位代码优先，其次全量名称最长子串匹配。

        无硬编码名单兜底——全量目录已覆盖简称（赛力斯/茅台）与带后缀全名。
        """
        if not text:
            return None
        code = extract_a_share_code(text)
        if code:
            return code
        name_map = await self.get_name_map(db)
        if not name_map:
            return None
        # 精确命中优先（消息本身就是一个股票名）
        stripped = text.strip()
        if stripped in name_map:
            return name_map[stripped]
        # 长名优先的子串包含匹配
        for name, symbol in self._names_desc:
            if name in text:
                return symbol
        return None


# 模块级单例（service 与记忆链路共用同一个缓存）
stock_directory = StockDirectory()
