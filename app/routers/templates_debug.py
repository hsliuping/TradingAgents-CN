from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.routers.auth_db import get_current_user
from app.core.permissions import require_pro
from app.services.license_service import LicenseInfo
from tradingagents.agents.utils.agent_context import AgentContext

router = APIRouter(prefix="/api/templates/debug", tags=["templates-debug"])

@router.get("/agents")
async def list_debug_agents():
    """获取所有可用于调试的agents"""
    import logging
    logger = logging.getLogger("webapi")

    try:
        logger.info("开始获取调试agents列表...")
        # v1.0 硬编码的agent类型
        v1_agents = [
            {"id": "market", "name": "市场分析师", "version": "v1.0", "category": "analyst"},
            {"id": "fundamentals", "name": "基本面分析师", "version": "v1.0", "category": "analyst"},
            {"id": "news", "name": "新闻分析师", "version": "v1.0", "category": "analyst"},
            {"id": "social", "name": "社交媒体分析师", "version": "v1.0", "category": "analyst"},
            {"id": "index_analyst", "name": "指数分析师", "version": "v1.0", "category": "analyst"},
            {"id": "sector_analyst", "name": "行业分析师", "version": "v1.0", "category": "analyst"},
        ]

        # v2.0 注册的agents
        v2_agents = []
        try:
            from core.agents import get_registry
            registry = get_registry()

            for metadata in registry.list_all():
                try:
                    # 包含分析师、管理者、交易员类别的agents
                    category_value = getattr(metadata.category, 'value', str(metadata.category))
                    if category_value in ["analyst", "manager", "trader"]:
                        v2_agents.append({
                            "id": metadata.id,
                            "name": metadata.name,
                            "version": "v2.0",
                            "category": category_value,
                            "description": getattr(metadata, 'description', '')
                        })
                except Exception as e:
                    logger.warning(f"处理agent metadata失败: {metadata.id if hasattr(metadata, 'id') else 'unknown'}, 错误: {e}")
                    continue
        except Exception as e:
            logger.warning(f"获取v2.0 agents失败: {e}")
            # 如果获取v2.0 agents失败，继续使用空列表

        # 合并并返回
        all_agents = v1_agents + v2_agents
        logger.info(f"成功获取调试agents: v1.0={len(v1_agents)}个, v2.0={len(v2_agents)}个, 总计={len(all_agents)}个")
        return {"success": True, "data": all_agents}

    except Exception as e:
        logger.error(f"获取调试agents失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DebugLLM(BaseModel):
    provider: str = Field(...)
    model: str = Field(...)
    temperature: float = Field(0.2)  # 股票分析推荐值：0.2-0.3（快速分析），0.1-0.2（深度分析）
    max_tokens: int = Field(2000)
    backend_url: Optional[str] = None
    api_key: Optional[str] = None

class DebugStock(BaseModel):
    symbol: str = Field(...)
    market_type: Optional[str] = None
    analysis_date: Optional[str] = None

class AnalystDebugRequest(BaseModel):
    analyst_type: str = Field(...)
    agent_version: Optional[str] = None
    template_id: Optional[str] = None
    use_current: bool = Field(True)
    llm: DebugLLM
    stock: DebugStock
    dataopts: Optional[Dict[str, Any]] = None
    prompt_overrides: Optional[Dict[str, Any]] = None

@router.post("/analyst")
async def debug_analyst(
    req: AnalystDebugRequest,
    user: dict = Depends(get_current_user),
    license: LicenseInfo = Depends(require_pro)  # 高级学员专属功能
):
    try:
        import logging
        logger = logging.getLogger("webapi")

        # 基本参数校验
        # 只有大盘分析师不需要股票代码，其他分析师都需要
        # 板块分析师需要股票代码来分析该股票所属的行业/板块
        needs_symbol = req.analyst_type != "index_analyst"
        if needs_symbol and (not req.stock.symbol or not str(req.stock.symbol).strip()):
            raise HTTPException(status_code=400, detail="stock.symbol 不能为空")
        if not req.llm.model or not str(req.llm.model).strip():
            raise HTTPException(status_code=400, detail="llm.model 不能为空")

        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.utils.template_client import get_template_client
        from tradingagents.agents.utils.agent_context import AgentContext

        # 🔥 打印调试信息：请求参数
        logger.info("=" * 80)
        logger.info("🔍 [调试接口] 收到请求参数:")
        logger.info(f"   analyst_type: {req.analyst_type}")
        logger.info(f"   llm.provider: {req.llm.provider}")
        logger.info(f"   llm.model: {req.llm.model}")
        logger.info(f"   llm.backend_url: {req.llm.backend_url}")
        logger.info(f"   llm.temperature: {req.llm.temperature}")
        logger.info(f"   llm.max_tokens: {req.llm.max_tokens}")
        logger.info(f"   stock.symbol: {req.stock.symbol}")
        logger.info(f"   stock.analysis_date: {req.stock.analysis_date}")
        logger.info("=" * 80)

        cfg = DEFAULT_CONFIG.copy()
        cfg["llm_provider"] = req.llm.provider

        # 🔥 根据 provider 设置正确的 backend_url
        if req.llm.backend_url:
            # 如果前端明确指定了 backend_url，使用前端的值
            cfg["backend_url"] = req.llm.backend_url
        else:
            # 如果前端没有指定，根据 provider 设置默认值
            provider_urls = {
                "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com",
                "google": "https://generativelanguage.googleapis.com/v1beta",
                "anthropic": "https://api.anthropic.com",
            }
            cfg["backend_url"] = provider_urls.get(req.llm.provider, cfg.get("backend_url", ""))

        cfg["quick_think_llm"] = req.llm.model
        cfg["deep_think_llm"] = req.llm.model
        cfg["quick_model_config"] = {"max_tokens": req.llm.max_tokens, "temperature": req.llm.temperature}
        cfg["deep_model_config"] = {"max_tokens": req.llm.max_tokens, "temperature": req.llm.temperature}

        # 🔥 如果前端提供了 API Key，添加到配置中
        if req.llm.api_key:
            cfg["quick_api_key"] = req.llm.api_key
            cfg["deep_api_key"] = req.llm.api_key
            logger.info(f"✅ [调试接口] 使用前端提供的 API Key")
        else:
            logger.info(f"ℹ️ [调试接口] 未提供 API Key，将使用环境变量或数据库配置")

        # 🔥 打印配置信息
        logger.info("=" * 80)
        logger.info("🔍 [调试接口] 最终配置:")
        logger.info(f"   llm_provider: {cfg['llm_provider']}")
        logger.info(f"   backend_url: {cfg['backend_url']}")
        logger.info(f"   quick_think_llm: {cfg['quick_think_llm']}")
        logger.info(f"   deep_think_llm: {cfg['deep_think_llm']}")
        logger.info(f"   quick_model_config: {cfg['quick_model_config']}")
        logger.info(f"   deep_model_config: {cfg['deep_model_config']}")
        logger.info(f"   quick_api_key: {'已配置' if cfg.get('quick_api_key') else '未配置'}")
        logger.info(f"   deep_api_key: {'已配置' if cfg.get('deep_api_key') else '未配置'}")
        logger.info("=" * 80)

        # 🔥 验证 analyst_type 并确定使用的版本
        from core.agents import get_registry
        registry = get_registry()

        # 确定agent版本
        agent_version = "v1.0"  # 默认使用v1.0
        template_version = None

        # 如果指定了template_id，先检查模板版本
        if req.template_id:
            try:
                from app.services.prompt_template_service import PromptTemplateService
                template_service = PromptTemplateService()
                template = await template_service.get_template(req.template_id)
                if template:
                    template_version = getattr(template, 'version', 1)
                    # 根据模板版本确定agent版本
                    if template_version >= 2:
                        agent_version = "v2.0"
                    logger.info(f"🔍 [调试接口] 模板版本: {template_version}, 使用agent版本: {agent_version}")
            except Exception as e:
                logger.warning(f"⚠️ [调试接口] 获取模板版本失败: {e}, 使用默认v1.0")

        # 验证agent类型
        v1_types = [
            "market", "fundamentals", "news", "social", "index_analyst", "sector_analyst",
            "market_analyst", "fundamentals_analyst", "news_analyst", "social_media_analyst"
        ]

        if req.agent_version:
            agent_version = req.agent_version
            logger.info(f"🔍 [调试接口] 使用前端传递的agent_version: {agent_version}")
        elif str(req.analyst_type).endswith("_v2"):
            agent_version = "v2.0"
            logger.info(f"🔍 [调试接口] 根据analyst_type判定为v2.0: {req.analyst_type}")
        elif req.analyst_type in v1_types:
            agent_version = "v1.0"
            logger.info(f"🔍 [调试接口] 使用v1.0 agent类型: {req.analyst_type}")
        elif registry.is_registered(req.analyst_type):
            # v2.0 注册的agent
            agent_version = "v2.0"
            logger.info(f"🔍 [调试接口] 使用v2.0 agent类型: {req.analyst_type}")
        else:
            raise HTTPException(status_code=400, detail=f"invalid analyst_type: {req.analyst_type}")

        # 🔥 创建 AgentContext，包含所有必要参数
        # 调试接口总是使用调试模式（跳过缓存）
        ctx = AgentContext(
            user_id=str(user["id"]),
            preference_id="neutral",  # 默认使用 neutral 偏好
            session_id=None,
            request_id=None,
            is_debug_mode=True,  # 🔥 调试接口始终启用调试模式（跳过缓存）
            debug_template_id=req.template_id  # 调试模板ID（可选）
        )

        # 🔥 打印 AgentContext 信息
        logger.info("=" * 80)
        logger.info("🔍 [调试接口] AgentContext 参数:")
        logger.info(f"   user_id: {ctx.user_id}")
        logger.info(f"   preference_id: {ctx.preference_id}")
        logger.info(f"   session_id: {ctx.session_id}")
        logger.info(f"   request_id: {ctx.request_id}")
        logger.info(f"   is_debug_mode: {ctx.is_debug_mode}")
        logger.info(f"   debug_template_id: {ctx.debug_template_id}")
        logger.info("=" * 80)

        # 🔥 根据agent版本选择不同的执行路径
        logger.info("=" * 80)
        logger.info(f"🔍 [调试接口] 开始调用单个 Agent: {req.analyst_type} (版本: {agent_version})")
        logger.info("=" * 80)

        if str(agent_version).startswith("v2") or str(agent_version).startswith("2."):
            # 使用v2.0的新统一引擎
            return await _debug_v2_agent(req, ctx, cfg, user)
        else:
            # 使用v1.0的旧引擎
            return await _debug_v1_agent(req, ctx, cfg, user)


    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger("webapi").error(f"模板调试接口执行异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _debug_v1_agent(req: AnalystDebugRequest, ctx: AgentContext, cfg: dict, user: dict):
    """调试v1.0版本的agent"""
    import logging
    logger = logging.getLogger("webapi")
    logger.info(f"🔍 [v1.0调试] 开始调试v1.0 agent: {req.analyst_type}")

    # 🔥 映射v2.0的agent ID到v1.0的analyst_type
    v2_to_v1_mapping = {
        "fundamentals_analyst": "fundamentals",
        "market_analyst": "market",
        "news_analyst": "news",
        "social_media_analyst": "social",
        "index_analyst": "index_analyst",
        "sector_analyst": "sector_analyst"
    }

    # 如果是v2.0的agent ID，转换为v1.0的analyst_type
    analyst_type_for_graph = v2_to_v1_mapping.get(req.analyst_type, req.analyst_type)
    logger.info(f"🔍 [v1.0调试] 映射后的analyst_type: {analyst_type_for_graph}")

    # 创建 TradingAgentsGraph 以初始化 LLM 和 Toolkit
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    graph_full = TradingAgentsGraph(selected_analysts=[analyst_type_for_graph], config=cfg)

    from tradingagents.agents import (
        create_fundamentals_analyst,
        create_market_analyst,
        create_news_analyst,
        create_social_media_analyst,
        create_index_analyst,
        create_sector_analyst
    )
    from tradingagents.agents.utils.agent_states import AgentState
    from langgraph.graph import StateGraph, START, END

    # 根据 analyst_type 选择对应的 Agent 创建函数
    agent_creators = {
        "fundamentals": create_fundamentals_analyst,
        "market": create_market_analyst,
        "news": create_news_analyst,
        "social": create_social_media_analyst,
        "index_analyst": create_index_analyst,
        "sector_analyst": create_sector_analyst
    }

    creator = agent_creators[analyst_type_for_graph]

    # 创建 Agent 节点
    logger.info(f"📝 [v1.0调试] 创建 {req.analyst_type} Agent 节点...")
    agent_node = creator(llm=graph_full.quick_thinking_llm, toolkit=graph_full.toolkit)

    # 获取对应的工具节点
    logger.info(f"📝 [v1.0调试] 获取 {req.analyst_type} 工具节点...")
    tool_nodes = graph_full._create_tool_nodes()
    tool_node = tool_nodes.get(req.analyst_type)

    if not tool_node:
        raise HTTPException(status_code=400, detail=f"无法获取 {req.analyst_type} 的工具节点")

    # 创建单节点图
    logger.info(f"📝 [v1.0调试] 创建单节点图...")
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # 添加边
    workflow.add_edge(START, "agent")
    workflow.add_edge("tools", "agent")

    # 添加条件边：如果有工具调用，执行工具；否则结束
    def should_continue(state):
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
        return END

    workflow.add_conditional_edges("agent", should_continue)

    # 编译图
    graph = workflow.compile()

    # 创建初始状态
    needs_symbol = req.analyst_type != "index_analyst"
    analysis_date = req.stock.analysis_date or cfg.get("trade_date", "2025-08-20")

    if needs_symbol:
        ticker = str(req.stock.symbol).strip()
    else:
        ticker = "MARKET"  # 大盘分析使用特殊标识

    initial_state = AgentState(
        messages=[],
        company_of_interest=ticker,
        trade_date=analysis_date,
        sender="debug",
        market_report="",
        sentiment_report="",
        news_report="",
        fundamentals_report="",
        index_report="",
        sector_report="",
        market_tool_call_count=0,
        news_tool_call_count=0,
        sentiment_tool_call_count=0,
        fundamentals_tool_call_count=0,
        index_tool_call_count=0,
        sector_tool_call_count=0,
        agent_context=ctx.__dict__
    )

    # 🔥 执行图
    logger.info(f"📝 [v1.0调试] 开始执行图...")
    state = graph.invoke(initial_state, config={"recursion_limit": 25})

    # 提取报告
    report_key_map = {
        "market": "market_report",
        "fundamentals": "fundamentals_report",
        "news": "news_report",
        "social": "sentiment_report",
        "index_analyst": "index_report",
        "sector_analyst": "sector_report"
    }
    report_key = report_key_map[req.analyst_type]

    # 从状态中提取报告
    if isinstance(state, dict):
        report = state.get(report_key, "")
    else:
        report = getattr(state, report_key, "")

    if not report.strip():
        report = "未生成分析报告"

    return await _build_debug_response(req, report)


async def _debug_v2_agent(req: AnalystDebugRequest, ctx: AgentContext, cfg: dict, user: dict):
    """调试v2.0版本的agent"""
    import logging
    logger = logging.getLogger("webapi")
    logger.info(f"🔍 [v2.0调试] 开始调试v2.0 agent: {req.analyst_type}")

    # 🔥 映射v1.0的agent ID到v2.0的ID
    # 如果前端传递的是v1.0的ID，但指定了v2.0版本，我们需要自动映射到v2.0的ID
    v1_to_v2_mapping = {
        "fundamentals_analyst": "fundamentals_analyst_v2",
        "market_analyst": "market_analyst_v2",
        "news_analyst": "news_analyst_v2",
        "social_media_analyst": "social_analyst_v2",
        "social_analyst": "social_analyst_v2",
        "sector_analyst": "sector_analyst_v2",
        "index_analyst": "index_analyst_v2",
        # 简写ID映射
        "fundamentals": "fundamentals_analyst_v2",
        "market": "market_analyst_v2",
        "news": "news_analyst_v2",
        "social": "social_analyst_v2",
    }

    agent_id = v1_to_v2_mapping.get(req.analyst_type, req.analyst_type)
    if agent_id != req.analyst_type:
        logger.info(f"🔄 [v2.0调试] 将Agent ID从 {req.analyst_type} 映射为 {agent_id}")

    try:
        # 使用新的统一引擎
        from core.workflow.engine import WorkflowEngine
        from core.workflow.templates.single_agent_workflow import SingleAgentWorkflow
        from core.agents import get_registry
        from tradingagents.graph.trading_graph import create_llm_by_provider
        from core.config.agent_config_manager import AgentConfigManager
        from core.config.binding_manager import BindingManager
        from app.core.database import get_mongo_db_sync

        # 获取agent注册信息
        registry = get_registry()
        if not registry.is_registered(agent_id):
            raise HTTPException(status_code=400, detail=f"Agent {agent_id} 未注册")

        # 🔥 从数据库获取 Agent 配置（使用同步版本）
        db = get_mongo_db_sync()
        agent_config_manager = AgentConfigManager()
        agent_config_manager.set_database(db)

        agent_config = agent_config_manager.get_agent_config(agent_id)
        if agent_config:
            logger.info(f"✅ [v2.0调试] 从数据库加载 Agent 配置: {agent_id}")
            logger.info(f"   - 启用状态: {agent_config.get('enabled', True)}")
            logger.info(f"   - 执行配置: {agent_config.get('config', {})}")
            logger.info(f"   - 提示词模板: {agent_config.get('prompt_template_type', 'N/A')}/{agent_config.get('prompt_template_name', 'N/A')}")
        else:
            logger.warning(f"⚠️ [v2.0调试] 未找到 Agent 配置，使用默认配置: {agent_id}")
            agent_config = {}

        # 🔥 从 BindingManager 获取绑定的工具
        binding_manager = BindingManager()
        binding_manager.set_database(db)

        tool_ids = binding_manager.get_tools_for_agent(agent_id)
        if tool_ids:
            logger.info(f"✅ [v2.0调试] 从 BindingManager 获取工具: {agent_id} -> {tool_ids}")
        else:
            logger.warning(f"⚠️ [v2.0调试] 未找到绑定的工具: {agent_id}")

        # 创建自定义 LLM（如果提供了配置）
        llm = None
        if req.llm and req.llm.model:
            try:
                # 处理 backend_url，如果为空则设为 None
                backend_url = req.llm.backend_url if req.llm.backend_url and req.llm.backend_url.strip() else None
                
                # 🔥 如果前端未传递 api_key，尝试从数据库获取
                api_key = req.llm.api_key
                if not api_key:
                    try:
                        from app.services.config_service import ConfigService
                        config_service = ConfigService()
                        # 获取所有提供商配置（包含数据库和环境变量的合并逻辑）
                        providers = await config_service.get_llm_providers()
                        target_provider = next((p for p in providers if p.name == req.llm.provider), None)
                        
                        if target_provider and target_provider.api_key:
                            api_key = target_provider.api_key
                            logger.info(f"✅ [v2.0调试] 从数据库/环境变量获取到 {req.llm.provider} 的 API Key")
                        else:
                            logger.warning(f"⚠️ [v2.0调试] 未找到 {req.llm.provider} 的 API Key 配置")
                    except Exception as e:
                        logger.error(f"❌ [v2.0调试] 获取 API Key 失败: {e}")

                llm = create_llm_by_provider(
                    provider=req.llm.provider,
                    model=req.llm.model,
                    temperature=req.llm.temperature,
                    max_tokens=req.llm.max_tokens,
                    backend_url=backend_url,
                    timeout=60,  # 默认超时时间
                    api_key=api_key
                )
                logger.info(f"✅ [v2.0调试] 使用前端传入的 LLM 配置: {req.llm.provider}/{req.llm.model}")
            except Exception as e:
                logger.warning(f"⚠️ [v2.0调试] 创建自定义 LLM 失败: {e}")
                # 如果用户显式指定了 LLM 但创建失败，应该报错
                raise HTTPException(status_code=400, detail=f"无法创建指定的 LLM ({req.llm.provider}/{req.llm.model}): {e}")

        # 创建单agent工作流
        # 🔥 将 Agent 配置传递给工作流
        workflow_def = SingleAgentWorkflow(
            agent_id=agent_id,
            config={
                "stock_symbol": req.stock.symbol,
                "analysis_date": req.stock.analysis_date or "2025-12-16",
                "market_type": req.stock.market_type or "A股",
                # 🔥 传递 Agent 配置（包括执行配置、提示词模板等）
                "agent_config": agent_config
            }
        )

        # 创建工作流引擎
        logger.info(f"🔧 [v2.0调试] 创建工作流引擎...")
        logger.info(f"   - Agent ID: {agent_id}")
        logger.info(f"   - 工作流 ID: {workflow_def.id}")
        logger.info(f"   - 自定义 LLM: {'是' if llm else '否'}")

        engine = WorkflowEngine(legacy_config=cfg, llm=llm)
        engine.load(workflow_def)

        logger.info(f"✅ [v2.0调试] 工作流引擎已加载")

        # 准备输入
        # ⚠️ 注意：v2.0 Agent 需要 ticker 和 trade_date 参数
        inputs = {
            "stock_symbol": req.stock.symbol,
            "ticker": req.stock.symbol,  # 映射为 Agent 需要的参数名
            "analysis_date": req.stock.analysis_date or "2025-12-16",
            "trade_date": req.stock.analysis_date or "2025-12-16",  # 映射为 Agent 需要的参数名
            "company_of_interest": req.stock.symbol,  # 兼容旧字段
            "market_type": req.stock.market_type or "A股",
            "context": ctx,
            "skip_cache": True,  # 🔥 调试模式跳过缓存
            "prompt_overrides": req.prompt_overrides or {}
        }

        # 执行工作流
        logger.info(f"=" * 100)
        logger.info(f"📝 [v2.0调试] 开始执行v2.0工作流...")
        logger.info(f"   - 输入参数: {list(inputs.keys())}")
        logger.info(f"   - 股票代码: {req.stock.symbol}")
        logger.info(f"   - 分析日期: {inputs['analysis_date']}")
        logger.info(f"=" * 100)

        result = await engine.execute_async(inputs)

        logger.info(f"=" * 100)
        logger.info(f"✅ [v2.0调试] 工作流执行完成")
        logger.info(f"   - 返回字段: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        logger.info(f"=" * 100)

        # 提取报告
        try:
            metadata = registry.get_metadata(agent_id)
            output_field = None
            if metadata and hasattr(metadata, 'output_field') and getattr(metadata, 'output_field'):
                output_field = getattr(metadata, 'output_field')
            elif metadata and hasattr(metadata, 'outputs') and getattr(metadata, 'outputs'):
                outputs = getattr(metadata, 'outputs')
                if isinstance(outputs, list) and len(outputs) > 0 and hasattr(outputs[0], 'name'):
                    output_field = outputs[0].name
            report_key = output_field or "final_report"
            report = result.get(report_key, "")
            if not isinstance(report, str) or not report.strip():
                report = "未生成分析报告"
        except Exception as e:
            logger.warning(f"⚠️ [v2.0调试] 提取报告失败: {e}")
            report = "未生成分析报告"

        return await _build_debug_response(req, report)

    except Exception as e:
        logger.error(f"❌ [v2.0调试] v2.0调试失败: {e}")
        # 不再回退到 v1.0
        raise HTTPException(status_code=500, detail=f"v2.0调试失败: {e}")


async def _build_debug_response(req: AnalystDebugRequest, report: str):
    """构建调试响应"""
    import logging
    logger = logging.getLogger("webapi")

    # 🔥 获取模板元数据（如果有）
    tpl_meta = {}
    try:
        if req.template_id:
            from app.services.prompt_template_service import PromptTemplateService
            template_service = PromptTemplateService()
            template = await template_service.get_template(req.template_id)
            if template:
                tmp = template.model_dump()
                tpl_meta = {
                    "name": tmp.get("template_name"),
                    "description": tmp.get("remark"),
                    "source": "user" if not tmp.get("is_system") else "system",
                    "template_id": str(tmp.get("id")),
                    "version": tmp.get("version", 1),
                    "agent_type": tmp.get("agent_type"),
                    "agent_name": tmp.get("agent_name"),
                    "preference_type": tmp.get("preference_type"),
                    "status": tmp.get("status")
                }
        else:
            tpl_meta = {}
    except Exception as e:
        logger.warning(f"⚠️ [调试接口] 获取模板元数据失败: {e}")
        tpl_meta = {}

    # 🔥 构建返回数据
    logger.info("=" * 80)
    logger.info("🔍 [调试接口] 返回结果:")
    logger.info(f"   analyst_type: {req.analyst_type}")
    logger.info(f"   symbol: {req.stock.symbol}")
    logger.info(f"   report_length: {len(report) if report else 0}")
    logger.info(f"   template_id: {req.template_id}")
    logger.info("=" * 80)

    return {
        "success": True,
        "data": {
            "analyst_type": req.analyst_type,
            "symbol": req.stock.symbol,
            "analysis_date": req.stock.analysis_date,
            "report": report,
            "report_length": len(report) if report else 0,
            "template": tpl_meta,
            "debug_mode": bool(req.template_id),
            "debug_template_id": req.template_id
        },
        "message": "调试分析完成"
    }
