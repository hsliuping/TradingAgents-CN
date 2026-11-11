"""能力查询同步适配层

DataFacade 能力查询为 async 接口；存量工具多为同步 def，
经本助手在同步上下文调用能力查询：
- 无运行中事件循环：直接 asyncio.run
- 已在事件循环内（嵌套场景）：线程池内开独立事件循环兜底，
  避免与外层循环冲突

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 8.2
"""

import asyncio
import concurrent.futures


def query_capability_sync(capability_id: str, **params):
    """同步上下文调用 DataFacade 能力查询。

    Args:
        capability_id: 能力 ID（如 'bond_china_yield'）
        **params: 能力标准查询参数

    Returns:
        标准化后的 DataFrame（契约与 CapabilityHandle.query 一致）
    """
    async def _run():
        from tradingagents.dataflows.capability.facade import get_data_facade

        handle = get_data_facade().get_capability(capability_id)
        return await handle.query(**params)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())

    # 已在事件循环内：独立线程跑新事件循环，避免与外层循环冲突
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(_run())).result()
