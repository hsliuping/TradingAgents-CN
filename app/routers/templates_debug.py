from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.routers.auth_db import get_current_user

router = APIRouter(prefix="/api/v1/templates/debug", tags=["templates-debug"])

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
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.utils.template_client import get_template_client
        from tradingagents.agents.utils.agent_context import AgentContext

        cfg = DEFAULT_CONFIG.copy()
        cfg["llm_provider"] = req.llm.provider
        cfg["backend_url"] = req.llm.backend_url or cfg.get("backend_url", "")
        cfg["quick_think_llm"] = req.llm.model
        cfg["deep_think_llm"] = req.llm.model
        cfg["quick_model_config"] = {"max_tokens": req.llm.max_tokens, "temperature": req.llm.temperature}
        cfg["deep_model_config"] = {"max_tokens": req.llm.max_tokens, "temperature": req.llm.temperature}

        selected = []
        if req.analyst_type in ["market", "fundamentals", "news", "social"]:
            selected = [req.analyst_type]
        else:
            raise HTTPException(status_code=400, detail="invalid analyst_type")

        graph = TradingAgentsGraph(selected_analysts=selected, config=cfg)

        ctx = AgentContext(user_id=str(user["id"]))
        state, decision = graph.propagate(req.stock.symbol, req.stock.analysis_date or cfg.get("trade_date", "2025-08-20"), agent_context=ctx.__dict__)

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
        raise HTTPException(status_code=500, detail=str(e))