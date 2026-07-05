"""
模型能力管理API路由
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.services.model_capability_service import get_model_capability_service
from app.constants.model_capabilities import (
    DEFAULT_MODEL_CAPABILITIES,
    ANALYSIS_DEPTH_REQUIREMENTS,
    CAPABILITY_DESCRIPTIONS,
    ModelRole,
    ModelFeature,
    get_model_capability_badge,
    get_role_badge,
    get_feature_badge
)
from app.core.unified_config import unified_config
from app.core.response import ok, fail
from app.services.config_service import config_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-capabilities", tags=["模型能力管理"])


# ==================== 请求/响应模型 ====================

class ModelCapabilityInfo(BaseModel):
    """模型能力信息"""
    model_name: str
    capability_level: int
    suitable_roles: List[str]
    features: List[str]
    recommended_depths: List[str]
    performance_metrics: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class ModelRecommendationRequest(BaseModel):
    """模型推荐请求"""
    research_depth: str = Field(..., description="研究深度：快速/基础/标准/深度/全面")


class ModelRecommendationResponse(BaseModel):
    """模型推荐响应"""
    quick_model: str
    deep_model: str
    quick_model_info: ModelCapabilityInfo
    deep_model_info: ModelCapabilityInfo
    reason: str


class ModelValidationRequest(BaseModel):
    """模型验证请求"""
    quick_model: str
    deep_model: str
    research_depth: str


class ModelValidationResponse(BaseModel):
    """模型验证响应"""
    valid: bool
    warnings: List[str]
    recommendations: List[str]


class BatchInitRequest(BaseModel):
    """批量初始化请求"""
    overwrite: bool = Field(default=False, description="是否覆盖已有配置")


# ==================== API路由 ====================

@router.get("/default-configs")
async def get_default_model_configs():
    """
    获取所有默认模型能力配置

    返回预定义的常见模型能力配置，用于参考和初始化。
    """
    try:
        # 转换为可序列化的格式
        configs = {}
        for model_name, config in DEFAULT_MODEL_CAPABILITIES.items():
            configs[model_name] = {
                "model_name": model_name,
                "capability_level": config["capability_level"],
                "suitable_roles": [str(role) for role in config["suitable_roles"]],
                "features": [str(feature) for feature in config["features"]],
                "recommended_depths": config["recommended_depths"],
                "performance_metrics": config.get("performance_metrics"),
                "description": config.get("description")
            }

        return {
            "success": True,
            "data": configs,
            "message": "获取默认模型配置成功"
        }
    except Exception as e:
        logger.error(f"获取默认模型配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/depth-requirements", response_model=dict)
async def get_depth_requirements():
    """
    获取分析深度要求

    返回各个分析深度对模型的最低要求。
    """
    try:
        # 转换为可序列化的格式
        requirements = {}
        for depth, req in ANALYSIS_DEPTH_REQUIREMENTS.items():
            requirements[depth] = {
                "min_capability": req["min_capability"],
                "quick_model_min": req["quick_model_min"],
                "deep_model_min": req["deep_model_min"],
                "required_features": [str(f) for f in req["required_features"]],
                "description": req["description"]
            }

        return ok(requirements, "获取分析深度要求成功")
    except Exception as e:
        logger.error(f"获取分析深度要求失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capability-descriptions", response_model=dict)
async def get_capability_descriptions():
    """获取能力等级描述"""
    try:
        return ok(CAPABILITY_DESCRIPTIONS, "获取能力等级描述成功")
    except Exception as e:
        logger.error(f"获取能力等级描述失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/badges", response_model=dict)
async def get_all_badges():
    """
    获取所有徽章样式

    返回能力等级、角色、特性的徽章样式配置。
    """
    try:
        badges = {
            "capability_levels": {
                str(level): get_model_capability_badge(level)
                for level in range(1, 6)
            },
            "roles": {
                str(role): get_role_badge(role)
                for role in ModelRole
            },
            "features": {
                str(feature): get_feature_badge(feature)
                for feature in ModelFeature
            }
        }

        return ok(badges, "获取徽章样式成功")
    except Exception as e:
        logger.error(f"获取徽章样式失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend", response_model=dict)
async def recommend_models(request: ModelRecommendationRequest):
    """
    推荐模型

    根据分析深度推荐最合适的模型对。
    """
    try:
        capability_service = get_model_capability_service()

        # 获取推荐模型
        quick_model, deep_model = capability_service.recommend_models_for_depth(
            request.research_depth
        )

        logger.info(f"🔍 推荐模型: quick={quick_model}, deep={deep_model}")

        # 获取模型详细信息
        quick_info = capability_service.get_model_config(quick_model)
        deep_info = capability_service.get_model_config(deep_model)

        logger.info(f"🔍 模型详细信息: quick_info={quick_info}, deep_info={deep_info}")

        # 生成推荐理由
        depth_req = ANALYSIS_DEPTH_REQUIREMENTS.get(
            request.research_depth,
            ANALYSIS_DEPTH_REQUIREMENTS["标准"]
        )

        # 获取能力等级描述
        capability_desc = {
            1: "基础级",
            2: "标准级",
            3: "高级",
            4: "专业级",
            5: "旗舰级"
        }

        quick_level_desc = capability_desc.get(quick_info['capability_level'], "标准级")
        deep_level_desc = capability_desc.get(deep_info['capability_level'], "标准级")

        reason = (
            f"• 快速模型：{quick_level_desc}，注重速度和成本，适合数据收集\n"
            f"• 深度模型：{deep_level_desc}，注重质量和推理，适合分析决策"
        )

        response_data = {
            "quick_model": quick_model,
            "deep_model": deep_model,
            "quick_model_info": quick_info,
            "deep_model_info": deep_info,
            "reason": reason
        }

        logger.info(f"🔍 返回的响应数据: {response_data}")

        return ok(response_data, "模型推荐成功")
    except Exception as e:
        logger.error(f"模型推荐失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=dict)
async def validate_models(request: ModelValidationRequest):
    """
    验证模型对

    验证选择的模型对是否适合指定的分析深度。
    """
    try:
        capability_service = get_model_capability_service()

        # 验证模型对
        validation = capability_service.validate_model_pair(
            request.quick_model,
            request.deep_model,
            request.research_depth
        )

        return ok(validation, "模型验证完成")
    except Exception as e:
        logger.error(f"模型验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-init", response_model=dict)
async def batch_init_capabilities(request: BatchInitRequest):
    """
    批量初始化模型能力

    为数据库中的模型配置自动填充能力参数。
    """
    try:
        # 从 MongoDB 获取系统配置（包含完整的 LLM 配置列表）
        system_config = await config_service.get_system_config()
        if not system_config or not system_config.llm_configs:
            return ok(
                {"updated_count": 0, "skipped_count": 0, "total_count": 0},
                "未找到模型配置，无需初始化"
            )

        llm_configs = system_config.llm_configs
        updated_count = 0
        skipped_count = 0
        updated_models = []  # 记录被更新的模型，最后一次性保存

        for config in llm_configs:
            model_name = config.model_name

            # 检查是否已有能力配置
            has_capability = (
                getattr(config, 'capability_level', None) is not None
                and getattr(config, 'capability_level', 0) > 0
            )

            if has_capability and not request.overwrite:
                skipped_count += 1
                continue

            # 从默认配置获取能力参数
            if model_name in DEFAULT_MODEL_CAPABILITIES:
                default_config = DEFAULT_MODEL_CAPABILITIES[model_name]

                # 更新能力字段
                config.capability_level = default_config["capability_level"]
                config.suitable_roles = [str(role) for role in default_config["suitable_roles"]]
                config.features = [str(feature) for feature in default_config["features"]]
                config.recommended_depths = default_config["recommended_depths"]
                config.performance_metrics = default_config.get("performance_metrics")

                updated_models.append(config)
                updated_count += 1
                logger.info(f"已初始化模型 {model_name} 的能力参数")
            else:
                logger.warning(f"模型 {model_name} 没有默认配置，跳过")
                skipped_count += 1

        # 一次性保存到数据库
        if updated_models:
            success = await config_service.save_system_config(system_config)
            if not success:
                logger.error("批量初始化保存到数据库失败")
                raise HTTPException(status_code=500, detail="保存到数据库失败")
            logger.info(f"批量初始化完成，已保存 {updated_count} 个模型的能力参数到数据库")

        return ok(
            {
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "total_count": len(llm_configs)
            },
            f"批量初始化完成：更新{updated_count}个，跳过{skipped_count}个"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量初始化失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/{model_name}", response_model=dict)
async def get_model_capability(model_name: str):
    """
    获取指定模型的能力信息

    Args:
        model_name: 模型名称
    """
    try:
        capability_service = get_model_capability_service()
        config = capability_service.get_model_config(model_name)

        return ok(config, f"获取模型 {model_name} 能力信息成功")
    except Exception as e:
        logger.error(f"获取模型能力信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

