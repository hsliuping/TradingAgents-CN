"""
获取交易记录工具

从数据库获取交易记录（支持真实持仓和模拟交易）
"""

import logging
from typing import List, Dict, Any, Optional, Annotated
from bson import ObjectId
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    tool_id="get_trade_records",
    name="获取交易记录",
    description="从数据库获取交易记录，支持真实持仓(position_changes)和模拟交易(paper_trades)",
    category="trade_review",
    is_online=False
)
def get_trade_records(
    user_id: Annotated[str, "用户ID"],
    trade_ids: Annotated[List[str], "交易ID列表"],
    source: Annotated[str, "数据源: 'real'(真实持仓) 或 'paper'(模拟交易)"] = "real"
) -> Dict[str, Any]:
    """
    获取交易记录

    Args:
        user_id: 用户ID
        trade_ids: 交易ID列表
        source: 数据源 ('real' 或 'paper')

    Returns:
        包含交易记录列表的字典
    """
    try:
        from app.core.database import get_mongo_db
        import asyncio

        async def _fetch_records():
            db = get_mongo_db()
            records = []

            if source == "paper":
                # 从模拟交易集合获取
                collection = db["paper_trades"]
            else:
                # 从持仓操作集合获取
                collection = db["position_changes"]

            # 查询交易记录
            cursor = collection.find({
                "user_id": user_id,
                "_id": {"$in": [ObjectId(tid) if isinstance(tid, str) else tid for tid in trade_ids]}
            }).sort("created_at", 1)

            records = await cursor.to_list(None)
            return records

        # 在同步上下文中运行异步代码
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        records = loop.run_until_complete(_fetch_records())

        logger.info(f"✅ 获取交易记录成功: {len(records)} 条 (source={source})")

        return {
            "success": True,
            "data": records,
            "count": len(records),
            "source": source
        }

    except Exception as e:
        logger.error(f"❌ 获取交易记录失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": []
        }

