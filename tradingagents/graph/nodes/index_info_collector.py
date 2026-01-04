import logging
from typing import Dict, Any
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")

def index_info_collector_node(state):
    code = state.get("company_of_interest")
    market_type = state.get("market_type", "A股")
    if not code:
        return {}
    
    logger.info(f"🔍 [IndexInfoCollector] Collecting info for: {code} (market: {market_type})")
    
    try:
        from tradingagents.utils.index_resolver import IndexResolver
        import asyncio
        
        # LangGraph 的同步节点中，如果需要调用异步代码，必须使用 asyncio.run
        # 但如果当前已经有 loop 在运行（例如整个 graph 是在 async 上下文中运行的），
        # asyncio.run 会报错。
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # 如果已经在 loop 中，我们需要使用 create_task 或类似机制，但这里是同步节点，不能 await。
            # 这通常意味着设计上的冲突。
            # 解决方案：使用 nest_asyncio 或者 将任务提交给线程池执行并等待结果。
            import nest_asyncio
            nest_asyncio.apply()
            resolved = loop.run_until_complete(IndexResolver.resolve(code, market_type))
        else:
            resolved = asyncio.run(IndexResolver.resolve(code, market_type))
        
        updates = {}
        
        # 如果解析出了不同的 symbol，更新 state
        new_symbol = resolved.get("symbol")
        if new_symbol and new_symbol != code:
            logger.info(f"✅ [IndexInfoCollector] Updating symbol: {code} -> {new_symbol}")
            updates["company_of_interest"] = new_symbol
        
        # 保存完整的指数信息到 state
        if resolved:
            logger.info(f"✅ [IndexInfoCollector] Info collected: {resolved.get('name')} ({resolved.get('source_type')})")
            updates["index_info"] = resolved
            
        return updates
            
    except Exception as e:
        logger.error(f"❌ [IndexInfoCollector] Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return {}
