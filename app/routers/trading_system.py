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
from app.routers.auth_db import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trading-systems", tags=["trading-systems"])


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
        return ok(data={"system": system.dict()}, message="交易计划创建成功")
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
                system_dict = s.dict()
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
        return ok(data={"system": system.dict()})
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
        return ok(data={"system": system.dict()})
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
        return ok(data={"system": system.dict()}, message=message)
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
        return ok(
            data={"system": system.dict()},
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
        system = service.activate_system(system_id, user_id)
        if not system:
            return error(message="交易计划不存在")
        return ok(data={"system": system.dict()}, message="交易计划激活成功")
    except Exception as e:
        logger.error(f"激活交易计划失败: {e}")
        return error(message=f"激活交易计划失败: {str(e)}")


@router.post("/{system_id}/evaluate", response_model=ApiResponse)
async def evaluate_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
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
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """AI生成选股/择时/风控等模块的结构化规则。"""
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

