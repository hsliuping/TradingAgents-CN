"""
工作流 API 路由

提供工作流的 CRUD 和执行端点
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from app.core.response import ok, fail
from app.core.permissions import require_pro
from app.routers.auth_db import get_current_user
from app.utils.compliance import (
    GENERIC_RESEARCH_RECOMMENDATION,
    build_research_summary,
    filter_analysis_reports,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/workflows",
    tags=["workflows"]
)


# ==================== 数据模型 ====================

class Position(BaseModel):
    """节点位置"""
    x: float
    y: float


class NodeDefinition(BaseModel):
    """节点定义"""
    id: str
    type: str
    agent_id: Optional[str] = None
    label: str
    position: Position
    config: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None


class EdgeDefinition(BaseModel):
    """边定义"""
    id: str
    source: str
    target: str
    type: str = "normal"
    condition: Optional[str] = None
    label: Optional[str] = None
    animated: bool = False


class WorkflowCreate(BaseModel):
    """创建工作流请求"""
    id: Optional[str] = None  # 可选，验证时可传入
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    version: str = "1.0.0"
    nodes: List[NodeDefinition] = Field(default_factory=list)
    edges: List[EdgeDefinition] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_template: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    workflow_type: Optional[str] = None


class WorkflowUpdate(BaseModel):
    """更新工作流请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    nodes: Optional[List[NodeDefinition]] = None
    edges: Optional[List[EdgeDefinition]] = None
    tags: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    workflow_type: Optional[str] = None


class ModelConfig(BaseModel):
    """模型配置"""
    model_name: str = Field(..., description="模型名称")
    provider: str = Field(..., description="模型厂家：openai/dashscope/deepseek/google等")
    api_key: Optional[str] = Field(default=None, description="API Key（可选，默认从数据库获取）")
    api_base: Optional[str] = Field(default=None, description="API Base URL（可选）")
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_tokens: int = Field(default=2000, ge=100, le=32000)
    timeout: int = Field(default=60, ge=10, le=600)


class WorkflowExecuteRequest(BaseModel):
    """执行工作流请求"""
    ticker: Optional[str] = Field(default=None, description="股票代码（stock_analysis/etf_analysis 必填，其他类型可选）")
    analysis_date: Optional[datetime] = None
    research_depth: str = Field(default="标准", description="分析深度：快速/基础/标准/深度/全面")
    # 🆕 分析师选择（用于动态裁剪工作流）
    selected_analysts: Optional[List[str]] = Field(
        default=None,
        description="选中的分析师列表，如 ['market', 'fundamentals']，为空则使用所有分析师"
    )
    # 向后兼容旧字段
    quick_analysis_model: Optional[str] = Field(default=None, description="快速分析模型名称（向后兼容）")
    deep_analysis_model: Optional[str] = Field(default=None, description="深度分析模型名称（向后兼容）")
    # 新的完整模型配置
    quick_model_config: Optional[ModelConfig] = Field(default=None, description="快速分析模型完整配置")
    deep_model_config: Optional[ModelConfig] = Field(default=None, description="深度分析模型完整配置")
    lookback_days: int = Field(default=30, ge=1, le=365)
    max_debate_rounds: int = Field(default=3, ge=1, le=10)
    # 🆕 自定义参数（透传到 task_params，用于通用研究等场景）
    custom_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="自定义参数，会合并到任务参数中"
    )


class ValidationResult(BaseModel):
    """验证结果"""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


# ==================== API 端点 ====================

@router.get("", dependencies=[Depends(require_pro)])
async def list_workflows():
    """获取所有工作流列表"""
    try:
        from core.api import WorkflowAPI
        from core.workflow.default_workflow_provider import get_default_workflow_provider
        api = WorkflowAPI()
        workflows = api.list_all()
        return ok(workflows)
    except Exception as e:
        logger.error(f"获取工作流列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def get_templates(user: dict = Depends(get_current_user)):
    """获取预定义模板"""
    try:
        from core.api import WorkflowAPI
        from core.workflow.default_workflow_provider import get_default_workflow_provider
        api = WorkflowAPI()
        templates = api.get_templates()
        return ok(templates)
    except Exception as e:
        logger.error(f"获取模板失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}", dependencies=[Depends(require_pro)])
async def get_workflow(workflow_id: str):
    """获取单个工作流详情"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        workflow = api.get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="工作流不存在")
        return ok(workflow)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", dependencies=[Depends(require_pro)])
async def create_workflow(data: WorkflowCreate):
    """创建新工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        result = api.create(data.model_dump())

        if not result.get("success"):
            return fail(
                message="创建工作流失败",
                code=400,
                data={"errors": result.get("errors", ["创建失败"])}
            )

        return ok(result.get("workflow"), message="创建成功")
    except Exception as e:
        logger.error(f"创建工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{workflow_id}", dependencies=[Depends(require_pro)])
async def update_workflow(workflow_id: str, data: WorkflowUpdate):
    """更新工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 过滤掉 None 值
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        result = api.update(workflow_id, update_data)

        if not result.get("success"):
            error = result.get("error") or result.get("errors", ["更新失败"])
            return fail(message=str(error), code=400)

        return ok(result.get("workflow"), message="更新成功")
    except Exception as e:
        logger.error(f"更新工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}", dependencies=[Depends(require_pro)])
async def delete_workflow(workflow_id: str):
    """删除工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        result = api.delete(workflow_id)

        if not result.get("success"):
            return fail(message=result.get("error", "删除失败"), code=400)

        return ok(None, message="删除成功")
    except Exception as e:
        logger.error(f"删除工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", dependencies=[Depends(require_pro)])
async def validate_workflow(data: WorkflowCreate):
    """验证工作流定义"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        result = api.validate(data.model_dump())
        return ok(result)
    except Exception as e:
        logger.error(f"验证工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/execute", dependencies=[Depends(require_pro)])
async def execute_workflow(
    workflow_id: str,
    data: WorkflowExecuteRequest,
    user: dict = Depends(get_current_user)
):
    """执行工作流 - 使用 v2.0 统一任务引擎（异步执行）

    改进：
    - 使用 v2.0 统一任务引擎，支持异步执行
    - 返回 task_id，前端可轮询进度
    - 统一的报告格式和进度跟踪
    """
    try:
        from app.services.task_analysis_service import get_task_analysis_service
        from app.models.analysis import AnalysisTaskType
        from app.models.user import PyObjectId
        from tradingagents.utils.stock_utils import StockUtils, StockMarket
        from app.core.database import get_mongo_db

        task_service = get_task_analysis_service()
        user_id = str(user["id"])

        # 🆕 查询工作流类型和 input_config，用于动态决定参数
        db = get_mongo_db()
        wf_doc = await db.workflows.find_one(
            {"_id": workflow_id},
            {"workflow_type": 1, "input_config": 1}
        )
        workflow_type = wf_doc.get("workflow_type", "stock_analysis") if wf_doc else "stock_analysis"
        input_config = wf_doc.get("input_config") if wf_doc else None

        logger.info(f"📊 [工作流执行] workflow_id={workflow_id}, workflow_type={workflow_type}")

        # 🆕 根据 workflow_type 判断 ticker 是否必填
        TICKER_REQUIRED_TYPES = {"stock_analysis", "etf_analysis"}
        if workflow_type in TICKER_REQUIRED_TYPES and not data.ticker:
            raise HTTPException(status_code=400, detail=f"工作流类型 {workflow_type} 必须提供 ticker 参数")

        # 🆕 根据 workflow_type 映射 task_type
        WORKFLOW_TYPE_TO_TASK_TYPE = {
            "stock_analysis": AnalysisTaskType.STOCK_ANALYSIS,
            "etf_analysis": AnalysisTaskType.ETF_ANALYSIS,
            "position_analysis": AnalysisTaskType.POSITION_ANALYSIS,
            "trade_review": AnalysisTaskType.TRADE_REVIEW,
            "general": AnalysisTaskType.STOCK_ANALYSIS,  # general 没有独立 task_type，用 STOCK_ANALYSIS 作为载体
        }
        task_type = WORKFLOW_TYPE_TO_TASK_TYPE.get(workflow_type, AnalysisTaskType.STOCK_ANALYSIS)

        # 准备任务参数
        task_params = {}

        # ticker 相关参数（仅当提供了 ticker 时才设置）
        if data.ticker:
            market = StockUtils.identify_stock_market(data.ticker)
            market_type_mapping = {
                StockMarket.CHINA_A: "cn",
                StockMarket.HONG_KONG: "hk",
                StockMarket.US: "us",
                StockMarket.UNKNOWN: "cn"
            }
            market_type = market_type_mapping.get(market, "cn")
            task_params["symbol"] = data.ticker
            task_params["stock_code"] = data.ticker
            task_params["market_type"] = market_type
            logger.info(f"📊 [工作流执行] 股票 {data.ticker} 识别为市场: {market_type}")

        # 通用参数
        task_params["analysis_date"] = data.analysis_date.strftime("%Y-%m-%d") if data.analysis_date else None
        task_params["research_depth"] = data.research_depth
        task_params["quick_analysis_model"] = data.quick_analysis_model
        task_params["deep_analysis_model"] = data.deep_analysis_model
        task_params["lookback_days"] = data.lookback_days
        task_params["max_debate_rounds"] = data.max_debate_rounds
        task_params["selected_analysts"] = data.selected_analysts if hasattr(data, 'selected_analysts') else None

        # 🆕 根据 input_config.fields 的 default 值补充缺失参数
        if input_config and isinstance(input_config, dict):
            fields = input_config.get("fields", [])
            for field in fields:
                fname = field.get("name")
                if fname and fname not in task_params and fname not in ("ticker", "symbol", "stock_code"):
                    default_val = field.get("default")
                    if default_val is not None:
                        task_params[fname] = default_val
                        logger.debug(f"📋 [工作流执行] 从 input_config 补充参数: {fname}={default_val}")

        # 🆕 合并自定义参数（通用研究等场景使用）
        if data.custom_params:
            task_params.update(data.custom_params)

        # 🆕 为 general 类型工作流打上 task_category 标记，便于后续查询
        if workflow_type == "general":
            task_params["task_category"] = "general"
            logger.info(f"🏷️ [工作流执行] 标记为通用研究任务: workflow_type=general")

        logger.info(f"🚀 [工作流执行] 创建任务: workflow_id={workflow_id}, ticker={data.ticker}, user={user_id}")

        # 🔥 从用户偏好读取风险偏好设置
        from app.routers.analysis import get_user_risk_preference
        preference_type = await get_user_risk_preference(user_id)
        logger.info(f"📊 [工作流执行] 使用用户风险偏好: {preference_type}")

        # 使用 v2.0 统一任务引擎创建任务
        task = await task_service.create_task(
            user_id=PyObjectId(user_id),
            task_type=task_type,
            task_params=task_params,
            engine_type="workflow",  # 强制使用工作流引擎
            preference_type=preference_type,  # 🔥 使用用户偏好设置
            workflow_id=workflow_id  # 指定使用哪个工作流
        )

        # 异步执行任务（不等待完成）
        import asyncio
        asyncio.create_task(task_service.execute_task(task))

        logger.info(f"✅ [工作流执行] 任务已创建: task_id={task.task_id}")

        return ok({
            "task_id": task.task_id,
            "status": task.status,
            "message": "任务已提交，正在后台执行"
        }, message="任务已提交")

    except Exception as e:
        logger.error(f"❌ [工作流执行] 创建任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _save_analysis_report(
    ticker: str,
    analysis_date: Optional[datetime],
    research_depth: str,
    workflow_result: Dict[str, Any],
    model_info: str,
    task_id: Optional[str] = None,
    execution_time: float = 0.0
):
    """
    保存研究报告到 MongoDB

    从工作流执行结果中提取各个报告并保存到 analysis_reports 集合
    与单股分析保持完全一致的报告结构
    """
    try:
        from app.core.database import get_mongo_db
        from datetime import datetime as dt

        db = get_mongo_db()

        # 🔥 生成分析ID - 使用 UTC 时间保持与老版本一致
        timestamp = dt.utcnow()
        analysis_id = f"{ticker}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        # 🔍 调试：打印 workflow_result 的所有键
        logger.info(f"[报告保存] 🔍 workflow_result 包含的字段: {list(workflow_result.keys())}")
        # 检查 index_report 和 sector_report 是否存在
        if "index_report" in workflow_result:
            logger.info(f"[报告保存] ✅ index_report 存在, 长度: {len(str(workflow_result.get('index_report', '')))}")
        else:
            logger.warning(f"[报告保存] ❌ index_report 不存在于 workflow_result 中")
        if "sector_report" in workflow_result:
            logger.info(f"[报告保存] ✅ sector_report 存在, 长度: {len(str(workflow_result.get('sector_report', '')))}")
        else:
            logger.warning(f"[报告保存] ❌ sector_report 不存在于 workflow_result 中")

        # 从工作流结果中提取报告（字符串类型）
        reports = {}
        string_report_fields = [
            # 🆕 宏观研究报告（优先提取）
            ("index_report", "大盘指数研究报告"),
            ("sector_report", "行业板块研究报告"),
            # 个股研究报告
            ("market_report", "市场研究报告"),
            ("sentiment_report", "情绪研究报告"),
            ("news_report", "新闻研究报告"),
            ("fundamentals_report", "基本面研究报告"),
            # 风险与辩论相关直出字段（如果存在，直接保存）
            ("risk_assessment", "风险评估结论"),
            ("bull_report", "积极证据研究报告"),
            ("bear_report", "谨慎证据研究报告"),
            ("risky_opinion", "高弹性情景观点"),
            ("safe_opinion", "防御情景观点"),
            ("neutral_opinion", "中性风险观点"),
            ("investment_plan", "研究团队研究结论"),
            ("trader_investment_plan", "研究整合意见"),
            ("final_trade_decision", "最终研究结论"),
        ]

        def _extract_text(v):
            if isinstance(v, str):
                return v
            if isinstance(v, dict):
                for k in ("content", "markdown", "text", "message", "report"):
                    x = v.get(k)
                    if isinstance(x, str) and x.strip():
                        return x
            return ""
        for field_name, report_name in string_report_fields:
            content_raw = workflow_result.get(field_name, "")
            content = _extract_text(content_raw)
            if content and isinstance(content, str) and len(content.strip()) > 5:
                reports[field_name] = content
                logger.info(f"[报告保存] 提取报告: {report_name} ({len(content)} 字符)")

        # 处理研究团队辩论状态（字典类型）- 拆分为独立子报告
        investment_debate = workflow_result.get("investment_debate_state", {})
        if investment_debate and isinstance(investment_debate, dict):
            # 1. 多头研究员报告
            bull_history = _extract_text(investment_debate.get("bull_history", ""))
            if bull_history and len(bull_history.strip()) > 5:
                reports["bull_researcher"] = bull_history
                logger.info(f"[报告保存] 提取报告: 多头研究员 ({len(bull_history)} 字符)")

            # 2. 空头研究员报告
            bear_history = _extract_text(investment_debate.get("bear_history", ""))
            if bear_history and len(bear_history.strip()) > 5:
                reports["bear_researcher"] = bear_history
                logger.info(f"[报告保存] 提取报告: 空头研究员 ({len(bear_history)} 字符)")

            # 3. 研究经理研究报告
            judge_decision = _extract_text(investment_debate.get("judge_decision", ""))
            if judge_decision and len(judge_decision.strip()) > 5:
                reports["research_team_decision"] = judge_decision
                logger.info(f"[报告保存] 提取报告: 研究经理分析 ({len(judge_decision)} 字符)")
            else:
                formatted = _format_research_team_report(investment_debate)
                if formatted and len(formatted.strip()) > 5:
                    reports["research_team_decision"] = formatted
                    logger.info(f"[报告保存] 生成报告: 研究经理综合决策 ({len(formatted)} 字符)")

        # 处理风险管理团队辩论状态（字典类型）- 拆分为独立子报告
        risk_debate = workflow_result.get("risk_debate_state", {})
        if risk_debate and isinstance(risk_debate, dict):
            # 1. 激进分析师报告
            risky_history = _extract_text(risk_debate.get("risky_history", ""))
            if risky_history and len(risky_history.strip()) > 5:
                reports["risky_analyst"] = risky_history
                logger.info(f"[报告保存] 提取报告: 激进分析师 ({len(risky_history)} 字符)")

            # 2. 保守分析师报告
            safe_history = _extract_text(risk_debate.get("safe_history", ""))
            if safe_history and len(safe_history.strip()) > 5:
                reports["safe_analyst"] = safe_history
                logger.info(f"[报告保存] 提取报告: 保守分析师 ({len(safe_history)} 字符)")

            # 3. 中性分析师报告
            neutral_history = _extract_text(risk_debate.get("neutral_history", ""))
            if neutral_history and len(neutral_history.strip()) > 5:
                reports["neutral_analyst"] = neutral_history
                logger.info(f"[报告保存] 提取报告: 中性分析师 ({len(neutral_history)} 字符)")

            # 4. 风险评估师决策报告
            judge_decision = _extract_text(risk_debate.get("judge_decision", ""))
            if judge_decision and len(judge_decision.strip()) > 5:
                reports["risk_management_decision"] = judge_decision
                logger.info(f"[报告保存] 提取报告: 风险评估师 ({len(judge_decision)} 字符)")
            else:
                formatted = _format_risk_management_report(risk_debate)
                if formatted and len(formatted.strip()) > 5:
                    reports["risk_management_decision"] = formatted
                    logger.info(f"[报告保存] 生成报告: 风险管理团队综合决策 ({len(formatted)} 字符)")

        if not reports:
            logger.warning("[报告保存] 没有找到任何报告内容，跳过保存")
            return

        # 获取股票名称和市场类型
        stock_name = ticker
        market_type = "A股"
        try:
            from tradingagents.utils.stock_utils import StockUtils
            market_info = StockUtils.get_market_info(ticker)
            market_type_map = {
                "china_a": "A股",
                "hong_kong": "港股",
                "us": "美股",
                "unknown": "A股"
            }
            market_type = market_type_map.get(market_info.get("market", "unknown"), "A股")

            # 尝试获取股票名称
            if market_info.get("market") == "china_a":
                from tradingagents.dataflows.interface import get_china_stock_info_unified
                stock_info = get_china_stock_info_unified(ticker)
                if "股票名称:" in stock_info:
                    stock_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
        except Exception as e:
            logger.warning(f"[报告保存] 获取股票信息失败: {e}")

        # 从最终研究结论中提取 recommendation 和 confidence_score
        recommendation, confidence_score, risk_level = _extract_recommendation_and_confidence(
            workflow_result, reports
        )

        # 🔥 提取 decision 字段（与单股分析保持一致）
        decision = workflow_result.get("decision", {})
        if not decision:
            # 如果没有 decision 字段，尝试从最终研究结论中构建
            final_decision_text = _extract_text(workflow_result.get("final_trade_decision", ""))
            if final_decision_text:
                decision = {
                    "action": recommendation,
                    "confidence": confidence_score,
                    "risk_level": risk_level,
                    "reasoning": final_decision_text[:200]  # 截取前200字符作为理由
                }

        # 🔥 提取关键要点（与单股分析保持一致）
        key_points = workflow_result.get("key_points", [])
        if not key_points:
            # 如果没有 key_points，尝试从摘要中提取
            summary_text = _extract_text(workflow_result.get("final_trade_decision", ""))
            if summary_text:
                # 简单提取：按行分割，取前5行作为关键要点
                lines = [line.strip() for line in summary_text.split('\n') if line.strip()]
                key_points = lines[:5]

        # 构建文档（与单股分析完全一致）
        document = {
            "analysis_id": analysis_id,
            "stock_symbol": ticker,
            "stock_name": stock_name,
            "market_type": market_type,
            "model_info": model_info,
            "analysis_date": analysis_date.strftime('%Y-%m-%d') if analysis_date else timestamp.strftime('%Y-%m-%d'),
            "timestamp": timestamp,
            "status": "completed",
            "source": "workflow",

            # 分析结果摘要
            "summary": (_extract_text(workflow_result.get("final_trade_decision", ""))[:500]
                        if workflow_result.get("final_trade_decision") else ""),
            "analysts": _get_analysts_from_reports(reports),
            "research_depth": research_depth,

            # 报告内容
            "reports": reports,

            # 🔥 关键字段：decision（与单股分析保持一致）
            "decision": decision,

            # 元数据
            "created_at": timestamp,
            "updated_at": timestamp,

            # API特有字段（与单股分析保持一致）
            "task_id": task_id or "",
            "recommendation": recommendation,
            "confidence_score": confidence_score,
            "risk_level": risk_level,
            "key_points": key_points,
            "execution_time": execution_time,
            "tokens_used": workflow_result.get("tokens_used", 0),

            # 🆕 性能指标数据（与单股分析保持一致）
            "performance_metrics": workflow_result.get("performance_metrics", {})
        }

        # 保存到 MongoDB
        result = await db.analysis_reports.insert_one(document)

        if result.inserted_id:
            logger.info(f"✅ [报告保存] 研究报告已保存到MongoDB: {analysis_id}, 共 {len(reports)} 个报告模块")
        else:
            logger.error("❌ [报告保存] MongoDB插入失败")

    except Exception as e:
        logger.error(f"❌ [报告保存] 保存研究报告失败: {e}")
        import traceback
        logger.error(f"❌ [报告保存] 详细错误: {traceback.format_exc()}")


def _extract_recommendation_and_confidence(
    workflow_result: Dict[str, Any],
    reports: Dict[str, Any]
) -> tuple:
    """
    从工作流结果中提取 recommendation、confidence_score 和 risk_level

    提取逻辑：
    1. recommendation: 从安全报告中提取研究摘要
    2. confidence_score: 从文本中提取置信度，或根据分析一致性计算
    3. risk_level: 从风险管理决策中提取

    Returns:
        tuple: (recommendation, confidence_score, risk_level)
    """
    import re

    def _text(v):
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            for k in ("content", "markdown", "text", "message", "report"):
                x = v.get(k)
                if isinstance(x, str) and x.strip():
                    return x
        return ""

    recommendation = GENERIC_RESEARCH_RECOMMENDATION
    confidence_score = 0.0
    risk_level = "中等"

    safe_reports = filter_analysis_reports(reports or {})
    research_summary = build_research_summary(safe_reports, workflow_result.get("summary", ""))
    if research_summary:
        recommendation = research_summary[:200]

    # 2. 提取 confidence_score（置信度）
    # 尝试从文本中提取置信度数值
    confidence_patterns = [
        r'置信度[：:]\s*([0-9.]+)%?',
        r'confidence[：:]\s*([0-9.]+)%?',
        r'可信度[：:]\s*([0-9.]+)%?',
        r'把握[：:]\s*([0-9.]+)%?',
    ]
    for pattern in confidence_patterns:
        match = re.search(pattern, research_summary, re.IGNORECASE)
        if match:
            try:
                conf_val = float(match.group(1))
                # 如果值大于1，认为是百分比，需要除以100
                if conf_val > 1:
                    conf_val = conf_val / 100
                confidence_score = min(1.0, max(0.0, conf_val))
                break
            except ValueError:
                pass

    # 如果没有提取到，根据分析一致性估算置信度
    if confidence_score == 0.0:
        # 检查有多少个报告达成一致
        report_count = len(safe_reports)
        if report_count >= 10:
            confidence_score = 0.85  # 完整分析
        elif report_count >= 7:
            confidence_score = 0.75  # 标准分析
        elif report_count >= 4:
            confidence_score = 0.65  # 基础分析
        else:
            confidence_score = 0.55  # 快速分析

    # 3. 提取 risk_level（风险等级）
    risk_decision = _text(reports.get("risk_management_decision", ""))
    if risk_decision:
        if re.search(r'高风险|风险较高|谨慎', risk_decision):
            risk_level = "高风险"
        elif re.search(r'低风险|风险较低|安全', risk_decision):
            risk_level = "低风险"
        else:
            risk_level = "中等"

    logger.info(f"[报告保存] 提取结果: recommendation={len(recommendation)}字符, confidence={confidence_score:.2f}, risk={risk_level}")

    return recommendation, confidence_score, risk_level


def _get_analysts_from_reports(reports: Dict[str, Any]) -> List[str]:
    """
    根据保存的报告动态生成分析师列表

    返回格式与旧系统兼容，用于前端显示 tabs
    """
    # 报告字段到分析师标识的映射
    report_to_analyst = {
        # 分析师团队（4个）
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        # 研究团队（3个）
        "bull_researcher": "bull_researcher",
        "bear_researcher": "bear_researcher",
        "research_team_decision": "research_manager",
        # 交易团队（1个）
        "trader_investment_plan": "trader",
        # 风险管理团队（4个）
        "risky_analyst": "risky_analyst",
        "safe_analyst": "safe_analyst",
        "neutral_analyst": "neutral_analyst",
        "risk_management_decision": "portfolio_manager",
        # 最终研究结论（1个）
        "final_trade_decision": "final_decision",
    }

    analysts = []
    for report_key, analyst_id in report_to_analyst.items():
        if report_key in reports and reports[report_key]:
            # 检查报告内容是否有效（非空字符串或非空字典）
            content = reports[report_key]
            if isinstance(content, str) and len(content) > 10:
                analysts.append(analyst_id)
            elif isinstance(content, dict) and content:
                analysts.append(analyst_id)

    return analysts


def _format_research_team_report(debate_state: Dict[str, Any]) -> str:
    """
    格式化研究团队研究报告

    从 investment_debate_state 中提取 bull_history, bear_history, judge_decision
    """
    parts = []
    parts.append("# 🔬 研究团队研究报告\n")

    # 多头研究员分析
    bull_history = debate_state.get("bull_history", "")
    if bull_history:
        parts.append("## 📈 多头研究员分析\n")
        parts.append(bull_history)
        parts.append("\n")

    # 空头研究员分析
    bear_history = debate_state.get("bear_history", "")
    if bear_history:
        parts.append("## 📉 空头研究员分析\n")
        parts.append(bear_history)
        parts.append("\n")

    # 研究经理综合结论
    judge_decision = debate_state.get("judge_decision", "")
    if judge_decision:
        parts.append("## 🎯 研究经理综合结论\n")
        parts.append(judge_decision)
        parts.append("\n")

    return "\n".join(parts) if len(parts) > 1 else ""


def _format_risk_management_report(debate_state: Dict[str, Any]) -> str:
    """
    格式化风险审阅结论

    从 risk_debate_state 中提取 risky_history, safe_history, neutral_history, judge_decision
    """
    parts = []
    parts.append("# 👔 风险审阅结论\n")

    # 高弹性情景分析师观点
    risky_history = debate_state.get("risky_history", "")
    if risky_history:
        parts.append("## 🔥 高弹性情景分析师观点\n")
        parts.append(risky_history)
        parts.append("\n")

    # 防御情景分析师观点
    safe_history = debate_state.get("safe_history", "")
    if safe_history:
        parts.append("## 🛡️ 防御情景分析师观点\n")
        parts.append(safe_history)
        parts.append("\n")

    # 基准情景分析师观点
    neutral_history = debate_state.get("neutral_history", "")
    if neutral_history:
        parts.append("## ⚖️ 基准情景分析师观点\n")
        parts.append(neutral_history)
        parts.append("\n")

    # 风险评估师最终结论
    judge_decision = debate_state.get("judge_decision", "")
    if judge_decision:
        parts.append("## 🎯 风险评估师最终结论\n")
        parts.append(judge_decision)
        parts.append("\n")

    return "\n".join(parts) if len(parts) > 1 else ""


async def _build_legacy_config(data: WorkflowExecuteRequest) -> Dict[str, Any]:
    """
    构建遗留智能体的 LLM 配置

    优先使用新的 ModelConfig，否则从数据库根据模型名称查询

    旧代码中的使用方式：
    - quick_thinking_llm: 用于分析师、研究员(Bull/Bear)、研究整合员、风险情景分析师
    - deep_thinking_llm: 用于研究整合员(Research Manager)、风险评估师(Risk Manager)
    """
    config = {}

    # 🔑 添加 selected_analysts（用于动态裁剪工作流）
    if data.selected_analysts:
        config["selected_analysts"] = data.selected_analysts
        logger.info(f"[工作流执行] 选中的分析师: {data.selected_analysts}")

    # 优先使用新的完整配置
    if data.quick_model_config:
        qc = data.quick_model_config
        config["llm_provider"] = qc.provider
        config["quick_think_llm"] = qc.model_name
        config["backend_url"] = qc.api_base or ""
        config["quick_api_key"] = qc.api_key
        config["quick_temperature"] = qc.temperature
        config["quick_max_tokens"] = qc.max_tokens
        config["quick_timeout"] = qc.timeout

        # 如果没有 deep 配置，默认使用 quick 的配置
        if not data.deep_model_config:
            config["deep_think_llm"] = qc.model_name
            config["deep_api_key"] = qc.api_key

    if data.deep_model_config:
        dc = data.deep_model_config
        config["deep_think_llm"] = dc.model_name
        config["deep_api_key"] = dc.api_key
        config["deep_backend_url"] = dc.api_base or ""
        config["deep_temperature"] = dc.temperature
        config["deep_max_tokens"] = dc.max_tokens
        config["deep_timeout"] = dc.timeout

        # 如果 quick 和 deep 厂家不同，标记为混合模式
        if data.quick_model_config and data.quick_model_config.provider != dc.provider:
            config["quick_llm_provider"] = data.quick_model_config.provider
            config["deep_llm_provider"] = dc.provider
        elif not data.quick_model_config:
            # 如果没有 quick 配置，使用 deep 的配置
            config["llm_provider"] = dc.provider
            config["quick_think_llm"] = dc.model_name
            config["quick_api_key"] = dc.api_key

    # 如果已经有了完整配置，需要从数据库补全 API Key
    if config and not config.get("quick_api_key"):
        config = await _fill_api_keys_from_db(config)

    # 如果没有新配置，尝试从旧字段和数据库获取
    if not config:
        config = await _get_llm_config_for_model(
            data.quick_analysis_model,
            data.deep_analysis_model
        )

    return config


async def _fill_api_keys_from_db(config: Dict[str, Any]) -> Dict[str, Any]:
    """从数据库填充 API Keys"""
    from app.core.database import get_mongo_db
    import os

    db = get_mongo_db()

    provider = config.get("llm_provider") or config.get("quick_llm_provider")
    if provider:
        provider_doc = await db.llm_providers.find_one({"name": provider})
        if provider_doc:
            api_key = provider_doc.get("api_key", "")
            if api_key and not api_key.startswith("sk-xxx"):
                config["quick_api_key"] = api_key
                if not config.get("deep_api_key"):
                    config["deep_api_key"] = api_key

    # 如果 deep 厂家不同，也需要获取其 API Key
    deep_provider = config.get("deep_llm_provider")
    if deep_provider and deep_provider != provider:
        provider_doc = await db.llm_providers.find_one({"name": deep_provider})
        if provider_doc:
            api_key = provider_doc.get("api_key", "")
            if api_key and not api_key.startswith("sk-xxx"):
                config["deep_api_key"] = api_key

    return config


async def _get_llm_config_for_model(quick_model: Optional[str], deep_model: Optional[str]) -> Dict[str, Any]:
    """
    根据模型名称从数据库获取完整的 LLM 配置

    Args:
        quick_model: 快速分析模型名称
        deep_model: 深度分析模型名称

    Returns:
        包含 provider、api_key、backend_url 等的完整配置
    """
    if not quick_model and not deep_model:
        return {}

    from app.core.database import get_mongo_db

    db = get_mongo_db()

    # 获取系统配置
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )

    if not config_doc or "llm_configs" not in config_doc:
        logger.warning("[工作流执行] 数据库中没有 LLM 配置")
        return {}

    llm_configs = config_doc["llm_configs"]

    # 查找匹配的模型配置
    target_model = quick_model or deep_model
    model_config = None

    for cfg in llm_configs:
        if cfg.get("model_name") == target_model and cfg.get("enabled", True):
            model_config = cfg
            break

    if not model_config:
        logger.warning(f"[工作流执行] 未找到模型配置: {target_model}")
        return {}

    # 获取厂家配置
    provider_name = model_config.get("provider", "")
    provider_doc = await db.llm_providers.find_one({"name": provider_name})

    api_key = None
    backend_url = model_config.get("api_base", "")

    if provider_doc:
        api_key = provider_doc.get("api_key", "")
        if not backend_url:
            backend_url = provider_doc.get("default_base_url", "")

    # 如果数据库没有 API Key，尝试从环境变量获取
    if not api_key or api_key.startswith("sk-xxx"):
        import os
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "dashscope": "DASHSCOPE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
        }
        env_name = env_key_map.get(provider_name.lower())
        if env_name:
            api_key = os.getenv(env_name)

    result = {
        "llm_provider": provider_name,
        "quick_think_llm": quick_model or target_model,
        "deep_think_llm": deep_model or target_model,
        "backend_url": backend_url,
        "api_key": api_key,
        "quick_temperature": model_config.get("temperature", 0.1),
        "quick_max_tokens": model_config.get("max_tokens", 2000),
        "quick_timeout": model_config.get("timeout", 60),
    }

    logger.info(f"[工作流执行] 从数据库获取模型配置: provider={provider_name}, model={target_model}")

    return result


class CreateFromTemplateRequest(BaseModel):
    """从模板创建请求"""
    template_id: str
    name: str


@router.post("/from-template", dependencies=[Depends(require_pro)])
async def create_from_template(data: CreateFromTemplateRequest):
    """从模板创建工作流"""
    template_id = data.template_id
    name = data.name
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 获取模板
        templates = api.get_templates()
        template = next((t for t in templates if t.get("id") == template_id), None)

        if template is None:
            raise HTTPException(status_code=404, detail="模板不存在")

        # 创建新工作流
        new_workflow = {
            **template,
            "name": name,
            "is_template": False
        }
        # 移除原 ID，让系统生成新 ID
        new_workflow.pop("id", None)
        new_workflow.pop("created_at", None)
        new_workflow.pop("updated_at", None)

        result = api.create(new_workflow)

        if not result.get("success"):
            return fail(
                message="从模板创建失败",
                code=400,
                data={"errors": result.get("errors", ["创建失败"])}
            )

        return ok(result.get("workflow"), message="创建成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从模板创建工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DuplicateRequest(BaseModel):
    """复制工作流请求"""
    name: str


@router.post("/{workflow_id}/duplicate", dependencies=[Depends(require_pro)])
async def duplicate_workflow(workflow_id: str, data: DuplicateRequest):
    """复制工作流"""
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()

        # 获取原工作流
        workflow = api.get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="工作流不存在")

        # 创建副本
        new_workflow = {
            **workflow,
            "name": data.name,
            "is_template": False,
        }
        # 移除原 ID，让系统生成新 ID
        new_workflow.pop("id", None)
        new_workflow.pop("created_at", None)
        new_workflow.pop("updated_at", None)

        result = api.create(new_workflow)

        if not result.get("success"):
            return fail(
                message="复制失败",
                code=400,
                data={"errors": result.get("errors", ["复制失败"])}
            )

        return ok(result.get("workflow"), message="复制成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"复制工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/set-default", dependencies=[Depends(require_pro)])
async def set_as_default(workflow_id: str):
    """设为默认分析流"""
    try:
        from core.api import WorkflowAPI
        from core.workflow.default_workflow_provider import get_default_workflow_provider
        api = WorkflowAPI()

        # 获取工作流
        workflow = api.get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="工作流不存在")

        workflow_name = workflow.get("name", "")
        provider = get_default_workflow_provider()
        workflow_type = provider.infer_workflow_type(workflow, workflow_id)

        # 保存为默认分析流配置：文件用于本地兜底，数据库用于运行时加载
        import json
        from pathlib import Path

        config_path = Path("config/settings.json")
        config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

        config.setdefault("default_workflows", {})
        config["default_workflows"][workflow_type] = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
        }
        if workflow_type == "stock_analysis":
            config["default_workflow_id"] = workflow_id
            config["default_workflow_name"] = workflow_name

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        from app.core.database import get_mongo_db
        db = get_mongo_db()
        await db.workflows.update_many(
            {"workflow_type": workflow_type, "is_default": True},
            {"$set": {"is_default": False, "updated_at": datetime.utcnow()}},
        )
        await db.workflows.update_many(
            {"config.workflow_type": workflow_type, "is_default": True},
            {"$set": {"is_default": False, "updated_at": datetime.utcnow()}},
        )
        await db.workflows.update_one(
            {"id": workflow_id},
            {
                "$set": {
                    "is_default": True,
                    "workflow_type": workflow_type,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        await db.system_configs.update_one(
            {"is_active": True},
            {
                "$set": {
                    "active_workflow_id": workflow_id,
                    "active_workflow_name": workflow_name,
                    "default_workflow_id": workflow_id,
                    "default_workflow_name": workflow_name,
                    f"default_workflows.{workflow_type}": {
                        "workflow_id": workflow_id,
                        "workflow_name": workflow_name,
                    },
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {"created_at": datetime.utcnow()},
            },
            upsert=True,
        )

        return ok(message=f"已将 '{workflow_name}' 设为 {workflow_type} 默认分析流")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置默认分析流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
