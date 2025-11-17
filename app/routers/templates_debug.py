from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.routers.auth_db import get_current_user

router = APIRouter(prefix="/api/templates/debug", tags=["templates-debug"])

class DebugLLM(BaseModel):
    provider: str = Field(...)
    model: str = Field(...)
    temperature: float = Field(0.7)
    max_tokens: int = Field(2000)
    backend_url: Optional[str] = None
    api_key: Optional[str] = None

class DebugStock(BaseModel):
    symbol: str = Field(...)
    market_type: Optional[str] = None
    analysis_date: Optional[str] = None

class AnalystDebugRequest(BaseModel):
    analyst_type: str = Field(...)
    template_id: Optional[str] = None
    use_current: bool = Field(True)
    llm: DebugLLM
    stock: DebugStock
    dataopts: Optional[Dict[str, Any]] = None

@router.post("/analyst")
async def debug_analyst(req: AnalystDebugRequest, user: dict = Depends(get_current_user)):
    try:
        import logging
        logger = logging.getLogger("webapi")

        # 基本参数校验
        if not req.stock.symbol or not str(req.stock.symbol).strip():
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

        # 🔥 打印配置信息
        logger.info("=" * 80)
        logger.info("🔍 [调试接口] 最终配置:")
        logger.info(f"   llm_provider: {cfg['llm_provider']}")
        logger.info(f"   backend_url: {cfg['backend_url']}")
        logger.info(f"   quick_think_llm: {cfg['quick_think_llm']}")
        logger.info(f"   deep_think_llm: {cfg['deep_think_llm']}")
        logger.info(f"   quick_model_config: {cfg['quick_model_config']}")
        logger.info(f"   deep_model_config: {cfg['deep_model_config']}")
        logger.info("=" * 80)

        selected = []
        if req.analyst_type in ["market", "fundamentals", "news", "social"]:
            selected = [req.analyst_type]
        else:
            raise HTTPException(status_code=400, detail="invalid analyst_type")

        graph = TradingAgentsGraph(selected_analysts=selected, config=cfg)

        # 🔥 创建 AgentContext，包含所有必要参数
        ctx = AgentContext(
            user_id=str(user["id"]),
            preference_id="neutral",  # 默认使用 neutral 偏好
            session_id=None,
            request_id=None,
            is_debug_mode=bool(req.template_id),  # 如果指定了template_id，则为调试模式
            debug_template_id=req.template_id  # 调试模板ID
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

        state, decision = graph.propagate(str(req.stock.symbol).strip(), req.stock.analysis_date or cfg.get("trade_date", "2025-08-20"), agent_context=ctx.__dict__)

        report_key_map = {
            "market": "market_report",
            "fundamentals": "fundamentals_report",
            "news": "news_report",
            "social": "sentiment_report"
        }
        report_key = report_key_map[req.analyst_type]
        report = state.get(report_key, "") if isinstance(state, dict) else getattr(state, report_key, "")

        tpl_meta: Dict[str, Any] = {}
        try:
            if req.template_id:
                client = get_template_client()
                from bson import ObjectId
                tmp = client.templates_collection.find_one({"_id": ObjectId(req.template_id)})
                if tmp:
                    tpl_meta = {"source": "user" if not tmp.get("is_system") else "system", "template_id": str(tmp.get("_id")), "version": tmp.get("version", 1)}
            else:
                tpl_meta = {}
        except Exception:
            tpl_meta = {}

        return {"success": True, "data": {"report": report, "template": tpl_meta, "analyst_type": req.analyst_type, "symbol": req.stock.symbol}, "message": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger("webapi").error(f"模板调试接口执行异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))