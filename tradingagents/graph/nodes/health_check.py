import asyncio
import logging
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor

from tradingagents.graph.data_probes import DataSourceProbe
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

def health_check_node(state: AgentState) -> Dict[str, Any]:
    """
    数据源健康检查节点
    
    在 Workflow 早期执行，探测所有关键数据源的可用性。
    探测结果将存入 state["data_source_status"]，供后续 Agent 决策使用。
    """
    logger.info("🩺 [Health Check] 开始数据源健康检查...")
    
    # 1. 获取上下文信息
    index_info = state.get("index_info", {})
    # 优先使用 index_info 中的 symbol，否则使用 company_of_interest
    index_code = index_info.get("symbol", state.get("company_of_interest", "000001.SH"))
    market_type = state.get("market_type", "A股")
    
    # 2. 执行探测
    # 为了兼容 LangGraph 可能的执行环境（Sync/Async混用），我们使用独立线程运行 Event Loop
    # 这样可以避免 "RuntimeError: This event loop is already running"
    
    def run_probes_in_thread():
        return asyncio.run(DataSourceProbe.run_all_probes(index_code, market_type))
        
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_probes_in_thread)
            probe_results = future.result()
            
    except Exception as e:
        logger.error(f"❌ [Health Check] 探测过程发生异常: {e}")
        # 降级：假设所有都可用（或者都不可用？），为了不阻断流程，假设可用但记录错误
        # 或者保守起见，假设 API 不可用但 Cache 可用？
        # 这里我们返回一个空的 status，后续 Agent 如果发现 key 不存在，可以回退到默认行为
        probe_results = {
            "status": {},
            "details": {"error": str(e)}
        }

    # 3. 更新状态
    status = probe_results.get("status", {})
    details = probe_results.get("details", {})
    
    available_sources = [k for k, v in status.items() if v]
    logger.info(f"🩺 [Health Check] 检查完成，可用源: {available_sources}")
    
    return {
        "data_source_status": status,
        "data_source_details": details
    }
