"""
助理操作工具模块（Assistant Ops）

提供分析触发、报告查询、定时任务管理、股票关注列表管理等操作类工具，
使智能助理从"数据教练"升级为"全能操作员"。

工具通过 @register_tool 装饰器自动注册到 ToolRegistry。
用户身份通过 core.tools.context 的 contextvars 机制获取。
"""

# 导入各子模块，触发 @register_tool 自动注册
import logging

from core.tools.implementations.assistant_ops import analysis_trigger  # noqa: F401
from core.tools.implementations.assistant_ops import report_query  # noqa: F401
from core.tools.implementations.assistant_ops import schedule_manager  # noqa: F401
from core.tools.implementations.assistant_ops import watchlist_manager  # noqa: F401
from core.tools.implementations.assistant_ops import favorite_manager  # noqa: F401
from core.tools.implementations.assistant_ops import position_analysis  # noqa: F401
from core.tools.implementations.assistant_ops import trade_review_ops  # noqa: F401
try:
    from core.tools.implementations.assistant_ops import trading_plan  # noqa: F401
except ImportError:  # 社区版：交易计划工具依赖交易系统（Pro），文件随删除清单剔除
    logging.getLogger(__name__).warning("交易计划工具未加载（社区版无交易系统服务）")
from core.tools.implementations.assistant_ops import risk_alerts  # noqa: F401
from core.tools.implementations.assistant_ops import topic_manager  # noqa: F401
from core.tools.implementations.assistant_ops import recent_search  # noqa: F401
from core.tools.implementations.assistant_ops import agent_executor  # noqa: F401
from core.tools.implementations.assistant_ops import stock_sync_ops  # noqa: F401
# v3.0 在线搜索工具：必须显式导入，否则京东云编译后 .py 被删、ToolLoader 动态发现失效
from core.tools.implementations.assistant_ops import web_search  # noqa: F401
from core.tools.implementations.assistant_ops import fetch_url  # noqa: F401
from .gain_alerts import set_stop_gain_alert, list_stop_gain_alerts, clear_stop_gain_alert
# 使用问答机器人专用工具（v3.0 新增）：仅在 assistant_role="usage_helper" 时加载
from core.tools.implementations.assistant_ops import user_state  # noqa: F401
from core.tools.implementations.assistant_ops import system_status  # noqa: F401
from core.tools.implementations.assistant_ops import user_activity  # noqa: F401
from core.tools.implementations.assistant_ops import manual_reader  # noqa: F401
from core.tools.implementations.assistant_ops import data_sync_status  # noqa: F401
from core.tools.implementations.assistant_ops import paper_trading_status  # noqa: F401
from core.tools.implementations.assistant_ops import token_usage  # noqa: F401
from core.tools.implementations.assistant_ops import running_tasks  # noqa: F401
# 通用表格 Excel 导出：确定性渲染（零 LLM 调用），对话数据 → xlsx 交付物
from core.tools.implementations.assistant_ops import export_table_excel_tool  # noqa: F401
