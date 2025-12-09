"""
MCP 中国市场工具

使用 FastMCP 的 @mcp.tool() 装饰器定义中国市场概览工具。
提供中国A股市场的整体概览和特定分析功能。
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 全局 toolkit 配置
_toolkit_config: dict = {}


def set_toolkit_config(config: dict):
    """设置工具配置"""
    global _toolkit_config
    _toolkit_config = config or {}


def get_china_market_overview(
    date: Optional[str] = None,
    include_indices: bool = True,
    include_sectors: bool = True
) -> str:
    """
    中国A股市场概览工具 - 获取中国A股市场的整体概况。
    
    提供市场指数、板块表现、资金流向等宏观市场数据。
    适用于了解整体市场环境和趋势。
    
    Args:
        date: 查询日期，格式：YYYY-MM-DD（可选，默认为今天）
        include_indices: 是否包含主要指数数据（上证、深证、创业板等）
        include_sectors: 是否包含板块表现数据
    
    Returns:
        格式化的市场概览数据，包含指数、板块和资金流向信息
    """
    logger.info(f"🇨🇳 [MCP中国市场工具] 获取市场概览")
    start_time = datetime.now()

    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    result_sections = []

    # 获取主要指数数据
    if include_indices:
        try:
            import akshare as ak
            
            indices_data = []
            
            # 上证指数
            try:
                sh_index = ak.stock_zh_index_daily(symbol="sh000001")
                if not sh_index.empty:
                    latest = sh_index.iloc[-1]
                    indices_data.append(f"- **上证指数**: {latest.get('close', 'N/A')}")
            except Exception as e:
                logger.warning(f"获取上证指数失败: {e}")
            
            # 深证成指
            try:
                sz_index = ak.stock_zh_index_daily(symbol="sz399001")
                if not sz_index.empty:
                    latest = sz_index.iloc[-1]
                    indices_data.append(f"- **深证成指**: {latest.get('close', 'N/A')}")
            except Exception as e:
                logger.warning(f"获取深证成指失败: {e}")
            
            # 创业板指
            try:
                cy_index = ak.stock_zh_index_daily(symbol="sz399006")
                if not cy_index.empty:
                    latest = cy_index.iloc[-1]
                    indices_data.append(f"- **创业板指**: {latest.get('close', 'N/A')}")
            except Exception as e:
                logger.warning(f"获取创业板指失败: {e}")
            
            if indices_data:
                result_sections.append(f"## 主要指数\n\n" + "\n".join(indices_data))
            else:
                result_sections.append("## 主要指数\n\n⚠️ 指数数据暂时无法获取")
                
        except Exception as e:
            logger.error(f"❌ [MCP中国市场工具] 获取指数数据失败: {e}")
            result_sections.append(f"## 主要指数\n\n⚠️ 获取失败: {e}")

    # 获取板块表现
    if include_sectors:
        try:
            import akshare as ak
            
            # 获取行业板块涨跌幅
            try:
                sector_df = ak.stock_board_industry_name_em()
                if not sector_df.empty:
                    # 取涨幅前5和跌幅前5
                    top_sectors = sector_df.head(5)
                    bottom_sectors = sector_df.tail(5)
                    
                    sector_info = "## 板块表现\n\n"
                    sector_info += "### 涨幅前5\n"
                    for _, row in top_sectors.iterrows():
                        name = row.get('板块名称', 'N/A')
                        change = row.get('涨跌幅', 'N/A')
                        sector_info += f"- {name}: {change}%\n"
                    
                    sector_info += "\n### 跌幅前5\n"
                    for _, row in bottom_sectors.iterrows():
                        name = row.get('板块名称', 'N/A')
                        change = row.get('涨跌幅', 'N/A')
                        sector_info += f"- {name}: {change}%\n"
                    
                    result_sections.append(sector_info)
                else:
                    result_sections.append("## 板块表现\n\n⚠️ 板块数据暂时无法获取")
            except Exception as e:
                logger.warning(f"获取板块数据失败: {e}")
                result_sections.append(f"## 板块表现\n\n⚠️ 获取失败: {e}")
                
        except Exception as e:
            logger.error(f"❌ [MCP中国市场工具] 获取板块数据失败: {e}")
            result_sections.append(f"## 板块表现\n\n⚠️ 获取失败: {e}")

    # 计算执行时间
    execution_time = (datetime.now() - start_time).total_seconds()

    # 组合结果
    combined_result = f"""# 中国A股市场概览

**查询日期**: {date}
**执行时间**: {execution_time:.2f}秒

{chr(10).join(result_sections)}

---
*数据来源: AKShare*
"""

    logger.info(f"🇨🇳 [MCP中国市场工具] 数据获取完成，总长度: {len(combined_result)}")
    return combined_result
