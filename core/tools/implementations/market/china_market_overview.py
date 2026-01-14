"""
中国市场概览工具 (Tushare版)
替代旧版的 get_china_market_overview_legacy
"""
import logging
import pandas as pd
from typing import Annotated, Dict, Any, Optional
from langchain_core.tools import tool
from datetime import datetime

from core.tools.base import register_tool
from tradingagents.dataflows.providers.china.tushare import TushareProvider

logger = logging.getLogger(__name__)

@tool
@register_tool(
    tool_id="get_china_market_overview",
    name="中国市场概览 (Tushare)",
    description="获取中国股市主要指数行情概览（上证、深证、创业板、科创50）",
    category="market",
    is_online=True,
    auto_register=True
)
def get_china_market_overview(
    curr_date: Annotated[str, "当前日期，格式 yyyy-mm-dd"]
) -> str:
    """
    获取中国股市整体概览，包括主要指数的行情。
    涵盖上证指数、深证成指、创业板指、科创50等主要指数。
    
    Args:
        curr_date (str): 当前日期，格式 yyyy-mm-dd
        
    Returns:
        str: 包含主要指数行情的市场概览报告
    """
    logger.info(f"📊 [中国市场概览] 开始获取数据, 日期: {curr_date}")
    
    try:
        # 初始化 Tushare Provider
        provider = TushareProvider()
        if not provider.connect_sync():
            return "❌ 无法连接到 Tushare 数据源，请检查 API Token 配置。"
            
        api = provider.api
        
        # 定义主要指数代码
        indices = {
            "000001.SH": "上证指数",
            "399001.SZ": "深证成指",
            "399006.SZ": "创业板指",
            "000688.SH": "科创50"
        }
        
        results = []
        
        # 获取指数日线数据
        # 注意：Tushare index_daily 接口
        # 🔑 记录实际使用的日期，以便在报告中说明
        actual_dates = []
        
        for code, name in indices.items():
            try:
                # 🔑 获取指定日期的数据，如果当天没有（如周末），向前找最近的一天
                # 使用 end_date 参数，limit=1 会返回指定日期之前最近的一条数据
                curr_date_clean = curr_date.replace('-', '')
                df = api.index_daily(ts_code=code, end_date=curr_date_clean, limit=1)
                
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    trade_date = row['trade_date']
                    close = row['close']
                    change = row['change']
                    pct_chg = row['pct_chg']
                    vol = row['vol']
                    amount = row['amount']
                    
                    # 格式化日期
                    trade_date_str = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
                    actual_dates.append(trade_date_str)
                    
                    # 🔑 如果实际日期与请求日期不一致，在报告中说明
                    date_note = ""
                    if trade_date_str != curr_date:
                        date_note = f" (注：{curr_date} 无数据，使用最近交易日 {trade_date_str})"
                    
                    # 格式化涨跌幅符号
                    sign = "+" if change > 0 else ""
                    
                    item = f"""### {name} ({code})
- **日期**: {trade_date_str}{date_note}
- **收盘**: {close:.2f}
- **涨跌**: {sign}{change:.2f} ({sign}{pct_chg:.2f}%)
- **成交量**: {vol/10000:.2f} 万手
- **成交额**: {amount/100000:.2f} 亿元
"""
                    results.append(item)
                else:
                    results.append(f"### {name} ({code})\n- 暂无数据（请求日期：{curr_date}）")
                    
            except Exception as e:
                logger.error(f"❌ 获取指数 {name} 失败: {e}")
                results.append(f"### {name} ({code})\n- 获取失败: {e}")
        
        # 🔑 如果所有指数的实际日期都一致，使用实际日期；否则使用请求日期
        if actual_dates and len(set(actual_dates)) == 1:
            actual_date = actual_dates[0]
            date_note = f"（请求日期：{curr_date}，实际使用：{actual_date}）" if actual_date != curr_date else ""
        else:
            actual_date = curr_date
            date_note = ""
        
        # 组合报告
        report = f"""# 中国市场概览
**分析基准日期**: {curr_date}{date_note}

## 📉 主要指数表现
{chr(10).join(results)}

---
*数据来源: Tushare Pro*
"""
        logger.info(f"✅ [中国市场概览] 获取成功")
        return report
        
    except Exception as e:
        error_msg = f"中国市场概览获取失败: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg
