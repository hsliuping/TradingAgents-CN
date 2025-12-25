"""
构建交易信息工具

从交易记录构建完整的交易信息对象
"""

import logging
from typing import List, Dict, Any, Optional, Annotated
from datetime import datetime
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    tool_id="build_trade_info",
    name="构建交易信息",
    description="从交易记录构建完整的交易信息对象，包含统计数据和时间信息",
    category="trade_review",
    is_online=False
)
def build_trade_info(
    trade_records: Annotated[List[Dict[str, Any]], "交易记录列表"],
    code: Annotated[Optional[str], "股票代码（可选）"] = None
) -> Dict[str, Any]:
    """
    构建交易信息
    
    Args:
        trade_records: 交易记录列表
        code: 股票代码
    
    Returns:
        包含交易信息的字典
    """
    try:
        if not trade_records:
            return {
                "success": False,
                "error": "交易记录为空",
                "data": None
            }

        # 打印输入的交易记录（调试用）
        logger.info(f"📊 [build_trade_info] 收到 {len(trade_records)} 笔交易记录")
        for i, record in enumerate(trade_records):
            logger.info(f"  记录 {i+1}: side={record.get('side')}, qty={record.get('quantity')}, "
                       f"price={record.get('price')}, pnl={record.get('pnl')}, "
                       f"timestamp={record.get('timestamp')}")

        # 提取基本信息
        first_trade = trade_records[0]
        stock_code = code or first_trade.get("code", "")
        stock_name = first_trade.get("name") or first_trade.get("stock_name")  # 尝试获取股票名称
        market = first_trade.get("market", "CN")

        logger.info(f"📊 [build_trade_info] 股票信息: code={stock_code}, name={stock_name}, market={market}")

        # 统计数据
        total_buy_qty = 0
        total_buy_amount = 0.0
        total_sell_qty = 0
        total_sell_amount = 0.0
        total_pnl = 0.0
        timestamps = []

        trades = []
        for record in trade_records:
            side = record.get("side", "")
            qty = record.get("quantity", 0)
            price = record.get("price", 0.0)
            amount = qty * price
            pnl = record.get("pnl", 0.0)
            timestamp = record.get("timestamp", "")
            
            trades.append({
                "side": side,
                "quantity": qty,
                "price": price,
                "amount": amount,
                "pnl": pnl,
                "timestamp": timestamp
            })
            
            if timestamp:
                timestamps.append(timestamp)
            
            if side == "buy":
                total_buy_qty += qty
                total_buy_amount += amount
            else:
                total_sell_qty += qty
                total_sell_amount += amount
                total_pnl += pnl
                logger.info(f"  累加卖出 pnl: {pnl}, 累计 total_pnl: {total_pnl}")

        # 计算统计数据
        avg_buy_price = total_buy_amount / total_buy_qty if total_buy_qty > 0 else 0.0
        avg_sell_price = total_sell_amount / total_sell_qty if total_sell_qty > 0 else 0.0
        pnl_pct = (total_pnl / total_buy_amount * 100) if total_buy_amount > 0 else 0.0

        logger.info(f"📊 [build_trade_info] 统计结果:")
        logger.info(f"  - total_buy_amount: {total_buy_amount}")
        logger.info(f"  - total_sell_amount: {total_sell_amount}")
        logger.info(f"  - total_pnl: {total_pnl}")
        logger.info(f"  - pnl_pct: {pnl_pct}%")
        
        # 计算持仓天数
        timestamps.sort()
        first_buy_date = timestamps[0] if timestamps else None
        last_sell_date = timestamps[-1] if timestamps else None
        holding_days = 0
        
        if first_buy_date and last_sell_date:
            try:
                first_dt = datetime.fromisoformat(first_buy_date.replace('Z', '+00:00').split('+')[0])
                last_dt = datetime.fromisoformat(last_sell_date.replace('Z', '+00:00').split('+')[0])
                holding_days = (last_dt - first_dt).days
            except Exception:
                pass
        
        trade_info = {
            "code": stock_code,
            "name": stock_name,  # 添加股票名称
            "market": market,
            "trades": trades,
            "total_buy_quantity": total_buy_qty,
            "total_buy_amount": round(total_buy_amount, 2),
            "avg_buy_price": round(avg_buy_price, 4),
            "total_sell_quantity": total_sell_qty,
            "total_sell_amount": round(total_sell_amount, 2),
            "avg_sell_price": round(avg_sell_price, 4),
            "realized_pnl": round(total_pnl, 2),
            "realized_pnl_pct": round(pnl_pct, 2),
            "first_buy_date": first_buy_date,
            "last_sell_date": last_sell_date,
            "holding_days": holding_days
        }
        
        logger.info(f"✅ 构建交易信息成功: {stock_code}, {len(trades)} 笔交易")
        
        return {
            "success": True,
            "data": trade_info
        }
    
    except Exception as e:
        logger.error(f"❌ 构建交易信息失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": None
        }

