"""
个人交易计划 API 路由
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel

from app.services.trading_system_service import get_trading_system_service, TradingSystemService
from app.services.trading_plan_evaluation_service import get_trading_plan_evaluation_service, TradingPlanEvaluationService
from app.utils.error_formatter import ErrorFormatter
from app.models.trading_system import (
    TradingSystem,
    TradingSystemCreate,
    TradingSystemUpdate,
    TradingSystemVersion,
    TradingSystemVersionCreate,
    TradingSystemPublish
)
from app.core.permissions import require_feature
from app.routers.auth_db import get_current_user

logger = logging.getLogger(__name__)


def _to_dict(obj) -> dict:
    """统一将 Pydantic 模型或普通对象转为 dict。"""
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {}


def _format_stock_rules(stock_selection: dict) -> str:
    """格式化选股规则为人类可读文本。"""
    if not stock_selection:
        return ""
    parts = []
    must_have = stock_selection.get("must_have") or []
    exclude = stock_selection.get("exclude") or []
    bonus = stock_selection.get("bonus") or []
    
    if must_have:
        parts.append(f"  - 必备条件: {[item.get('description', str(item)) for item in must_have if item]}")
    if exclude:
        parts.append(f"  - 排除条件: {[item.get('description', str(item)) for item in exclude if item]}")
    if bonus:
        parts.append(f"  - 加分条件: {[item.get('description', str(item)) for item in bonus if item]}")
    return "\n".join(parts)


def _format_timing_rules(timing: dict) -> str:
    """格式化择时规则为人类可读文本。"""
    if not timing:
        return ""
    entry_signals = timing.get("entry_signals") or []
    if not entry_signals:
        return ""
    signals = [item.get("description", str(item)) for item in entry_signals if item]
    if signals:
        return f"  - 入场信号: {signals}"
    return ""


def _format_position_rules(position: dict) -> str:
    """格式化仓位规则为人类可读文本。"""
    if not position:
        return ""
    parts = []
    max_per_stock = position.get("max_per_stock")
    max_holdings = position.get("max_holdings")
    min_holdings = position.get("min_holdings")
    
    if max_per_stock is not None:
        parts.append(f"  - 单只股票仓位上限: {max_per_stock * 100}%")
    if max_holdings is not None:
        parts.append(f"  - 最大持股数: {max_holdings}只")
    if min_holdings is not None:
        parts.append(f"  - 最小持股数: {min_holdings}只")
    return "\n".join(parts)


def _format_risk_rules(risk_mgmt: dict) -> str:
    """格式化风险规则为人类可读文本。"""
    if not risk_mgmt:
        return ""
    parts = []
    stop_loss = risk_mgmt.get("stop_loss") or {}
    take_profit = risk_mgmt.get("take_profit") or {}
    
    sl_type = stop_loss.get("type", "")
    sl_desc = stop_loss.get("description", "")
    if sl_type == "percentage":
        pct = stop_loss.get("percentage")
        if sl_desc:
            parts.append(f"  - 止损: {sl_desc}")
        elif pct:
            parts.append(f"  - 止损: {pct * 100}%")
    elif sl_type:
        parts.append(f"  - 止损: {stop_loss}")
    
    tp_type = take_profit.get("type", "")
    tp_desc = take_profit.get("description", "")
    if tp_type == "percentage":
        pct = take_profit.get("percentage")
        if tp_desc:
            parts.append(f"  - 止盈: {tp_desc}")
        elif pct:
            parts.append(f"  - 止盈: {pct * 100}%")
    elif tp_type == "trailing":
        pullback = take_profit.get("trailing_pullback_pct")
        activation = take_profit.get("activation_profit_pct")
        if tp_desc:
            parts.append(f"  - 止盈: {tp_desc}")
        elif pullback and activation:
            parts.append(f"  - 止盈: 移动止盈，浮盈{activation * 100}%后激活，回撤{pullback * 100}%触发")
    elif tp_type:
        parts.append(f"  - 止盈: {take_profit}")
    
    return "\n".join(parts)


def _format_discipline_rules(discipline: dict) -> str:
    """格式化纪律规则为人类可读文本。"""
    if not discipline:
        return ""
    parts = []
    must_do = discipline.get("must_do") or []
    must_not = discipline.get("must_not") or []
    
    if must_do:
        parts.append(f"  - 必须做: {[str(item) for item in must_do if item]}")
    if must_not:
        parts.append(f"  - 严禁做: {[str(item) for item in must_not if item]}")
    return "\n".join(parts)


async def _sync_trading_system_to_user_preference(
    user_id: str,
    system,
    source: str = "trading_system_activated",
) -> None:
    """将激活/发布的交易计划核心要素同步到 mem0 user_preference scope。

    完整同步交易计划的所有核心要素，让智能助手真正理解用户的交易体系。
    包括：基本信息、选股规则、择时规则、仓位管理、风险控制、交易纪律。
    """
    if not user_id or system is None:
        return
    try:
        name = getattr(system, "name", "") or ""
        style = getattr(system, "style", "") or getattr(system, "trading_style", "") or ""
        risk_profile = getattr(system, "risk_profile", "") or ""
        version = str(getattr(system, "version", "") or "")
        description = getattr(system, "description", "") or ""
        
        # 获取完整交易计划数据
        stock_selection = _to_dict(getattr(system, "stock_selection", None))
        timing = _to_dict(getattr(system, "timing", None))
        position = _to_dict(getattr(system, "position", None))
        risk_mgmt = _to_dict(getattr(system, "risk_management", None))
        discipline = _to_dict(getattr(system, "discipline", None))

        # 构建标题
        title = f"用户当前交易计划：{name}"
        if version:
            title += f"（v{version}）"
        
        parts = [title]
        
        # 基本描述
        if description:
            parts.append(f"交易理念: {description[:100]}...")
        
        # 交易风格和风险偏好
        style_map = {
            "short_term": "短线（持仓1-5天）",
            "medium_term": "中线（持仓1-3月）",
            "long_term": "长线（持仓3月+）"
        }
        risk_map = {
            "conservative": "保守（低风险，低回撤）",
            "balanced": "中性（平衡风险收益）",
            "aggressive": "激进（高风险，高收益）"
        }
        if style:
            parts.append(f"交易风格: {style_map.get(style, style)}")
        if risk_profile:
            parts.append(f"风险偏好: {risk_map.get(risk_profile, risk_profile)}")
        
        # 选股规则
        stock_rules_text = _format_stock_rules(stock_selection)
        if stock_rules_text:
            parts.append("【选股规则】")
            parts.append(stock_rules_text)
        
        # 择时规则
        timing_text = _format_timing_rules(timing)
        if timing_text:
            parts.append("【择时规则】")
            parts.append(timing_text)
        
        # 仓位规则
        position_text = _format_position_rules(position)
        if position_text:
            parts.append("【仓位管理】")
            parts.append(position_text)
        
        # 风险规则
        risk_text = _format_risk_rules(risk_mgmt)
        if risk_text:
            parts.append("【风险控制】")
            parts.append(risk_text)
        
        # 纪律规则
        discipline_text = _format_discipline_rules(discipline)
        if discipline_text:
            parts.append("【交易纪律】")
            parts.append(discipline_text)

        content = "\n".join(parts).strip()

        from app.core.database import get_mongo_db
        from core.memory.service import get_memory_service
        from core.memory.models import MemoryScope

        system_id_str = str(getattr(system, "id", "") or "")

        db = get_mongo_db()
        svc = get_memory_service(db)

        # 仅清理"同一 system_id"的旧记忆，保证每个交易计划在 user_preference
        # 中始终只有最新一条；不影响其他计划（用户可能有中长期/短期/机动多个计划并存）
        # 也不影响用户通过 remember_this 主动登记的偏好。
        if system_id_str:
            try:
                old_items = await svc.get_all(
                    user_id=user_id,
                    scopes=[MemoryScope.USER_PREFERENCE],
                    metadata_filters={
                        "category": "trading_discipline",
                        "system_id": system_id_str,
                    },
                    limit=50,
                )
                removed = 0
                for item in (old_items.get("items") or []):
                    meta = getattr(item, "metadata", None) or {}
                    src = (meta.get("source") or "").strip()
                    # 仅清理由交易计划同步进来的，不动用户 remember_this 写入的
                    if src.startswith("trading_system_"):
                        try:
                            if await svc.delete_memory(item.id):
                                removed += 1
                        except Exception:
                            pass
                if removed:
                    logger.info(
                        f"[trading_system] 清理了 system={system_id_str} 的 {removed} 条旧记忆 user={user_id}"
                    )
            except Exception as e:
                logger.debug(f"[trading_system] 清理旧记忆失败（已忽略）: {e}")

        result = await svc.store(
            [{"role": "user", "content": content}],
            user_id=user_id,
            agent_id="assistant",
            scope=MemoryScope.USER_PREFERENCE,
            metadata={
                "source": source,
                "category": "trading_discipline",
                "system_id": system_id_str,
                "system_name": name,
                "system_version": version,
            },
            infer=False,
        )
        if result.success:
            logger.info(
                f"[trading_system] 已同步到 user_preference: user={user_id} source={source} system={system_id_str}"
            )
        else:
            logger.warning(
                f"[trading_system] 同步 user_preference 失败: {result.error}"
            )
    except Exception as e:
        logger.warning(f"[trading_system] 同步 user_preference 异常（已忽略）: {e}")


async def _purge_trading_system_memory(user_id: str, system_id: str) -> None:
    """删除交易计划时，清理 mem0 中由该计划产生的 user_preference 记忆。"""
    if not user_id or not system_id:
        return
    try:
        from app.core.database import get_mongo_db
        from core.memory.service import get_memory_service
        from core.memory.models import MemoryScope

        sid = str(system_id)
        db = get_mongo_db()
        svc = get_memory_service(db)
        old_items = await svc.get_all(
            user_id=user_id,
            scopes=[MemoryScope.USER_PREFERENCE],
            metadata_filters={"category": "trading_discipline", "system_id": sid},
            limit=50,
        )
        removed = 0
        for item in (old_items.get("items") or []):
            meta = getattr(item, "metadata", None) or {}
            if (meta.get("source") or "").strip().startswith("trading_system_"):
                try:
                    if await svc.delete_memory(item.id):
                        removed += 1
                except Exception:
                    pass
        if removed:
            logger.info(
                f"[trading_system] 已随计划删除清理 {removed} 条记忆 user={user_id} system={sid}"
            )
    except Exception as e:
        logger.debug(f"[trading_system] 删除计划时清理记忆失败（已忽略）: {e}")

router = APIRouter(
    prefix="/api/v1/trading-systems",
    tags=["trading-systems"]
)


# 统一响应格式
class ApiResponse(BaseModel):
    success: bool = True
    data: dict = {}
    message: str = ""


class GenerateRiskRulesRequest(BaseModel):
    style: str = "medium_term"
    risk_profile: str = "balanced"
    risk_style: str = "balanced"
    description: Optional[str] = ""
    current_rules: Optional[dict] = None


class GenerateModuleRulesRequest(BaseModel):
    module: str
    style: str = "medium_term"
    risk_profile: str = "balanced"
    description: Optional[str] = ""
    current_rules: Optional[dict] = None


class OptimizationDiscussionMessage(BaseModel):
    role: str
    content: str


class OptimizationDiscussionRequest(BaseModel):
    trading_plan_data: dict
    evaluation_result: Optional[dict] = None
    user_question: Optional[str] = ""
    selected_suggestions: List[str] = []
    conversation_history: List[OptimizationDiscussionMessage] = []


def ok(data=None, message="操作成功"):
    """成功响应"""
    return ApiResponse(success=True, data=data or {}, message=message)


def error(message="操作失败", data=None):
    """错误响应"""
    return ApiResponse(success=False, data=data or {}, message=message)


def format_user_error(prefix: str, exc: Exception, context: Optional[dict] = None) -> str:
    """格式化用户可见错误，优先拦截 LLM 账号/配额等常见问题。"""
    detail = ErrorFormatter.format_user_message(str(exc), context=context)
    return f"{prefix}：{detail}"


def serialize_system(service: TradingSystemService, system: TradingSystem) -> dict:
    """序列化交易计划，并附带规则告警。"""
    data = system.dict()
    data["validation_warnings"] = service.get_system_validation_warnings(system)
    return data


@router.post("", response_model=ApiResponse)
async def create_trading_system(
    system_data: TradingSystemCreate,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """创建交易计划"""
    try:
        user_id = current_user["id"]
        system = service.create_system(user_id, system_data)
        return ok(data={"system": serialize_system(service, system)}, message="交易计划创建成功")
    except Exception as e:
        logger.error(f"创建交易计划失败: {e}")
        return error(message=f"创建交易计划失败: {str(e)}")


@router.get("", response_model=ApiResponse)
async def list_trading_systems(
    is_active: Optional[bool] = Query(None, description="是否只获取激活的系统"),
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取交易计划列表"""
    try:
        user_id = current_user["id"]
        logger.info(f"开始获取交易计划列表: user_id={user_id}, is_active={is_active}")

        systems = service.list_systems(user_id, is_active=is_active)
        logger.info(f"服务层返回 {len(systems)} 个系统")

        # 转换为字典
        systems_dict = []
        for idx, s in enumerate(systems):
            logger.info(f"序列化第 {idx+1} 个系统: {s.name}")
            try:
                system_dict = serialize_system(service, s)
                logger.info(f"系统 {s.name} 序列化后的键: {list(system_dict.keys())}")
                systems_dict.append(system_dict)
            except Exception as e:
                logger.error(f"序列化系统 {s.name} 失败: {e}")
                raise

        logger.info(f"成功序列化所有系统")
        return ok(data={
            "systems": systems_dict,
            "total": len(systems_dict)
        })
    except Exception as e:
        logger.error(f"获取交易计划列表失败: {e}", exc_info=True)
        return error(message=f"获取交易计划列表失败: {str(e)}")


@router.get("/active", response_model=ApiResponse)
async def get_active_trading_system(
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取当前激活的交易计划"""
    try:
        user_id = current_user["id"]
        system = service.get_active_system(user_id)
        if not system:
            return ok(data={"system": None}, message="未找到激活的交易计划")
        return ok(data={"system": serialize_system(service, system)})
    except Exception as e:
        logger.error(f"获取激活交易计划失败: {e}")
        return error(message=f"获取激活交易计划失败: {str(e)}")


@router.get("/{system_id}", response_model=ApiResponse)
async def get_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取交易计划详情"""
    try:
        user_id = current_user["id"]
        system = service.get_effective_system(system_id, user_id)
        if not system:
            return error(message="交易计划不存在")
        return ok(data={"system": serialize_system(service, system)})
    except Exception as e:
        logger.error(f"获取交易计划详情失败: {e}")
        return error(message=f"获取交易计划详情失败: {str(e)}")


@router.put("/{system_id}", response_model=ApiResponse)
async def update_trading_system(
    system_id: str,
    update_data: TradingSystemUpdate,
    save_as_draft: bool = Query(False, description="是否保存为草稿（已发布版本时，草稿不影响正式版本）"),
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """更新交易计划（保存草稿，不创建版本）"""
    try:
        user_id = current_user["id"]
        system = service.update_system(system_id, user_id, update_data, save_as_draft=save_as_draft)
        if not system:
            return error(message="交易计划不存在")
        
        message = "草稿已保存" if save_as_draft else "交易计划更新成功"
        return ok(data={"system": serialize_system(service, system)}, message=message)
    except Exception as e:
        logger.error(f"更新交易计划失败: {e}")
        return error(message=f"更新交易计划失败: {str(e)}")


@router.post("/{system_id}/publish", response_model=ApiResponse)
async def publish_trading_system(
    system_id: str,
    publish_data: TradingSystemPublish,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """发布交易计划（创建新版本并更新状态为已发布）"""
    try:
        user_id = current_user["id"]
        update_data = publish_data.update_data
        # 创建发布数据（不包含 update_data）
        from app.models.trading_system import TradingSystemPublish as PublishModel
        publish_info = PublishModel(
            improvement_summary=publish_data.improvement_summary,
            new_version=publish_data.new_version
        )
        system = service.publish_system(system_id, user_id, publish_info, update_data)
        if not system:
            return error(message="交易计划不存在")
        # 同步到 mem0 user_preference（异步、降级安全）
        await _sync_trading_system_to_user_preference(user_id, system, source="trading_system_published")
        return ok(
            data={"system": serialize_system(service, system)},
            message=f"交易计划已发布，版本号：v{system.version}"
        )
    except Exception as e:
        logger.error(f"发布交易计划失败: {e}")
        return error(message=f"发布交易计划失败: {str(e)}")


@router.delete("/{system_id}", response_model=ApiResponse)
async def delete_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """删除交易计划"""
    try:
        user_id = current_user["id"]
        success = service.delete_system(system_id, user_id)
        if not success:
            return error(message="交易计划不存在或删除失败")
        # 同步清理 mem0 中由该计划产生的 user_preference 记忆
        await _purge_trading_system_memory(user_id, system_id)
        return ok(message="交易计划删除成功")
    except Exception as e:
        logger.error(f"删除交易计划失败: {e}")
        return error(message=f"删除交易计划失败: {str(e)}")


@router.post("/{system_id}/activate", response_model=ApiResponse)
async def activate_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """激活交易计划"""
    try:
        user_id = current_user["id"]
        # 先检查系统是否存在
        system = service.get_system(system_id, user_id)
        if not system:
            return error(message="交易计划不存在")
        # 检查是否为草稿状态
        if system.status != "published":
            return error(message="草稿状态的交易计划不能设为默认，请先发布")
        # 执行激活
        system = service.activate_system(system_id, user_id)
        if not system:
            return error(message="激活失败")
        # 同步到 mem0 user_preference（异步、降级安全）
        await _sync_trading_system_to_user_preference(user_id, system)
        return ok(data={"system": serialize_system(service, system)}, message="交易计划激活成功")
    except Exception as e:
        logger.error(f"激活交易计划失败: {e}")
        return error(message=f"激活交易计划失败: {str(e)}")


@router.post("/{system_id}/evaluate", response_model=ApiResponse)
async def evaluate_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    _license=Depends(require_feature("trading_plan_check")),
    service: TradingSystemService = Depends(get_trading_system_service),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """AI评估交易计划（已保存的计划）"""
    try:
        user_id = current_user["id"]
        
        # 获取交易计划
        system = service.get_system(system_id, user_id)
        if not system:
            return error(message="交易计划不存在")
        
        # 调用AI评估（传入system_id以保存历史记录）
        evaluation_result = await evaluation_service.evaluate_trading_plan(system, user_id, system_id)
        
        return ok(
            data={"evaluation": evaluation_result},
            message="交易计划评估完成"
        )
    except Exception as e:
        logger.error(f"评估交易计划失败: {e}", exc_info=True)
        return error(message=format_user_error("评估交易计划失败", e))


@router.get("/{system_id}/evaluations", response_model=ApiResponse)
async def get_evaluation_history(
    system_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    _license=Depends(require_feature("trading_plan_check")),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """获取交易计划评估历史"""
    try:
        user_id = current_user["id"]
        
        history = await evaluation_service.get_evaluation_history(
            system_id=system_id,
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        
        return ok(
            data=history,
            message="获取评估历史成功"
        )
    except Exception as e:
        logger.error(f"获取评估历史失败: {e}", exc_info=True)
        return error(message=f"获取评估历史失败：{str(e)}")


@router.get("/evaluations/{evaluation_id}", response_model=ApiResponse)
async def get_evaluation_detail(
    evaluation_id: str,
    current_user: dict = Depends(get_current_user),
    _license=Depends(require_feature("trading_plan_check")),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """获取评估详情"""
    try:
        user_id = current_user["id"]
        
        detail = await evaluation_service.get_evaluation_detail(evaluation_id, user_id)
        
        if not detail:
            return error(message="评估记录不存在", code=404)
        
        return ok(
            data={"evaluation": detail},
            message="获取评估详情成功"
        )
    except Exception as e:
        logger.error(f"获取评估详情失败: {e}", exc_info=True)
        return error(message=f"获取评估详情失败：{str(e)}")


@router.post("/evaluate-draft", response_model=ApiResponse)
async def evaluate_trading_plan_draft(
    trading_plan_data: TradingSystemCreate,
    current_user: dict = Depends(get_current_user),
    _license=Depends(require_feature("trading_plan_check")),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """AI评估交易计划草稿（未保存的计划）"""
    try:
        user_id = current_user["id"]
        
        # 将创建请求转换为字典（添加user_id以便评估）
        plan_dict = trading_plan_data.dict()
        plan_dict["user_id"] = user_id
        
        # 调用AI评估
        evaluation_result = await evaluation_service.evaluate_trading_plan_data(plan_dict, user_id)
        
        return ok(
            data={"evaluation": evaluation_result},
            message="交易计划评估完成"
        )
    except Exception as e:
        logger.error(f"评估交易计划草稿失败: {e}", exc_info=True)
        return error(message=format_user_error("评估交易计划失败", e))


@router.post("/generate-risk-rules", response_model=ApiResponse)
async def generate_risk_rules(
    request: GenerateRiskRulesRequest,
    current_user: dict = Depends(get_current_user),
    _license=Depends(require_feature("trading_plan_check")),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """AI生成风险管理规则（止损/止盈/时间止损/逻辑止损）"""
    try:
        user_id = current_user["id"]
        rules = await evaluation_service.generate_risk_management_rules(
            user_id=user_id,
            style=request.style,
            risk_profile=request.risk_profile,
            risk_style=request.risk_style,
            description=request.description or "",
            current_rules=request.current_rules or {}
        )
        return ok(data={"risk_management": rules}, message="风险管理规则生成成功")
    except Exception as e:
        logger.error(f"生成风险管理规则失败: {e}", exc_info=True)
        return error(message=format_user_error("生成风险管理规则失败", e))


@router.post("/generate-module-rules", response_model=ApiResponse)
async def generate_module_rules(
    request: GenerateModuleRulesRequest,
    current_user: dict = Depends(get_current_user),
    _license=Depends(require_feature("trading_plan_check")),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """AI生成选股/择时/风控等模块的结构化规则"""
    try:
        user_id = current_user["id"]
        rules = await evaluation_service.generate_module_rules(
            user_id=user_id,
            module=request.module,
            style=request.style,
            risk_profile=request.risk_profile,
            description=request.description or "",
            current_rules=request.current_rules or {}
        )
        return ok(data={"module": request.module, "rules": rules}, message="模块规则生成成功")
    except Exception as e:
        logger.error(f"生成模块规则失败: {e}", exc_info=True)
        return error(message=format_user_error("生成模块规则失败", e))


@router.post("/optimize-discussion", response_model=ApiResponse)
async def discuss_trading_plan_optimization(
    request: OptimizationDiscussionRequest,
    current_user: dict = Depends(get_current_user),
    _license=Depends(require_feature("trading_plan_check")),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """围绕评估结果进行 AI 讨论，并返回可选择应用的结构化优化项。"""
    try:
        user_id = current_user["id"]
        plan_dict = dict(request.trading_plan_data or {})
        plan_dict["user_id"] = plan_dict.get("user_id") or user_id

        discussion = await evaluation_service.discuss_optimization_suggestions(
            user_id=user_id,
            trading_plan_data=plan_dict,
            evaluation_result=request.evaluation_result or {},
            user_question=request.user_question or "",
            selected_suggestions=request.selected_suggestions or [],
            conversation_history=[item.dict() for item in request.conversation_history or []]
        )
        return ok(data={"discussion": discussion}, message="优化讨论生成成功")
    except Exception as e:
        logger.error(f"优化讨论生成失败: {e}", exc_info=True)
        return error(message=format_user_error("优化讨论生成失败", e))


# ==================== 版本管理相关接口 ====================

@router.post("/{system_id}/versions", response_model=ApiResponse)
async def create_trading_system_version(
    system_id: str,
    version_data: TradingSystemVersionCreate,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """创建交易计划新版本"""
    try:
        user_id = current_user["id"]
        version = service.create_version(system_id, user_id, version_data)
        if not version:
            return error(message="交易计划不存在")
        return ok(data={"version": version.dict()}, message=f"版本 {version.version} 创建成功")
    except Exception as e:
        logger.error(f"创建版本失败: {e}")
        return error(message=f"创建版本失败: {str(e)}")


@router.get("/{system_id}/versions", response_model=ApiResponse)
async def list_trading_system_versions(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取交易计划的所有版本"""
    try:
        user_id = current_user["id"]
        versions = service.list_versions(system_id, user_id)
        versions_dict = [v.dict() for v in versions]
        return ok(data={"versions": versions_dict, "total": len(versions_dict)})
    except Exception as e:
        logger.error(f"获取版本列表失败: {e}")
        return error(message=f"获取版本列表失败: {str(e)}")


@router.get("/versions/{version_id}", response_model=ApiResponse)
async def get_trading_system_version(
    version_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取版本详情"""
    try:
        user_id = current_user["id"]
        version = service.get_version(version_id, user_id)
        if not version:
            return error(message="版本不存在")
        return ok(data={"version": version.dict()})
    except Exception as e:
        logger.error(f"获取版本详情失败: {e}")
        return error(message=f"获取版本详情失败: {str(e)}")


@router.post("/{system_id}/versions/{version_id}/restore", response_model=ApiResponse)
async def restore_version_as_draft(
    system_id: str,
    version_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """将指定版本恢复为草稿"""
    try:
        user_id = current_user["id"]
        system = service.restore_version_as_draft(system_id, version_id, user_id)
        if not system:
            return error(message="版本不存在或恢复失败")
        return ok(data={"system": serialize_system(service, system)}, message="版本已恢复为草稿")
    except Exception as e:
        logger.error(f"恢复版本为草稿失败: {e}")
        return error(message=f"恢复版本为草稿失败: {str(e)}")

