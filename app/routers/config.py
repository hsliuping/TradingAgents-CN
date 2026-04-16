"""
配置管理API路由
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.routers.auth_db import get_current_user
from app.models.user import User
from app.models.config import (
    SystemConfigResponse, LLMConfigRequest, DataSourceConfigRequest,
    DatabaseConfigRequest, ConfigTestRequest, ConfigTestResponse,
    LLMConfig, DataSourceConfig, DatabaseConfig,
    LLMProvider, LLMProviderRequest, LLMProviderResponse,
    MarketCategory, MarketCategoryRequest, DataSourceGrouping,
    DataSourceGroupingRequest, DataSourceOrderRequest,
    ModelCatalog, ModelInfo
)
from app.services.config_service import config_service
from datetime import datetime
from app.utils.timezone import now_tz

from app.services.operation_log_service import log_operation
from app.models.operation_log import ActionType
from app.services.config_provider import provider as config_provider
from app.core.response import ok



router = APIRouter(prefix="/config", tags=["配置管理"])
logger = logging.getLogger("webapi")


# ===== 配置重载端点 =====

@router.post("/reload", summary="重新加载配置")
async def reload_config(current_user: dict = Depends(get_current_user)):
    """
    重新加载配置并桥接到环境变量

    用于配置更新后立即生效，无需重启服务
    """
    try:
        from app.core.config_bridge import reload_bridged_config

        success = reload_bridged_config()

        if success:
            await log_operation(
                user_id=str(current_user.get("user_id", "")),
                username=current_user.get("username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="重载配置",
                details={"action": "reload_config"},
                ip_address="",
                user_agent=""
            )

            return ok(
                data={
                    "success": True,
                    "message": "配置重载成功",
                    "data": {
                        "reloaded_at": now_tz().isoformat()
                    }
                },
                message="配置重载成功"
            )
        else:
            return ok(
                data={
                    "success": False,
                    "message": "配置重载失败，请查看日志"
                },
                message="配置重载失败，请查看日志"
            )
    except Exception as e:
        logger.error(f"配置重载失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置重载失败: {str(e)}"
        )


# ===== 方案A：敏感字段响应脱敏 & 请求清洗 =====
from copy import deepcopy

def _sanitize_llm_configs(items):
    try:
        return [LLMConfig(**{**i.model_dump(), "api_key": None}) for i in items]
    except Exception:
        return items


def _sort_llm_configs_by_newest(items):
    indexed_items = list(enumerate(items))

    def get_sort_key(indexed_item):
        index, item = indexed_item
        time_value = getattr(item, "created_at", None) or getattr(item, "updated_at", None)
        if not time_value:
            return (0, index)

        try:
            return (1, time_value.timestamp())
        except Exception:
            return (0, index)

    return [item for _, item in sorted(indexed_items, key=get_sort_key, reverse=True)]

def _sanitize_datasource_configs(items):
    """
    脱敏数据源配置，返回缩略的 API Key

    逻辑：
    1. 如果数据库中有有效的 API Key，返回缩略版本
    2. 如果数据库中没有，尝试从环境变量读取并返回缩略版本
    3. 如果都没有，返回 None
    """
    try:
        from app.utils.api_key_utils import (
            is_valid_api_key,
            truncate_api_key,
            get_env_api_key_for_datasource
        )

        result = []
        for item in items:
            data = item.model_dump()

            # 处理 API Key
            db_key = data.get("api_key")
            if is_valid_api_key(db_key):
                # 数据库中有有效的 API Key，返回缩略版本
                data["api_key"] = truncate_api_key(db_key)
            else:
                # 数据库中没有有效的 API Key，尝试从环境变量读取
                ds_type = data.get("type")
                if isinstance(ds_type, str):
                    env_key = get_env_api_key_for_datasource(ds_type)
                    if env_key:
                        # 环境变量中有有效的 API Key，返回缩略版本
                        data["api_key"] = truncate_api_key(env_key)
                    else:
                        data["api_key"] = None
                else:
                    data["api_key"] = None

            # 处理 API Secret（同样的逻辑）
            db_secret = data.get("api_secret")
            if is_valid_api_key(db_secret):
                data["api_secret"] = truncate_api_key(db_secret)
            else:
                data["api_secret"] = None

            result.append(DataSourceConfig(**data))

        return result
    except Exception as e:
        print(f"⚠️ 脱敏数据源配置失败: {e}")
        return items

def _sanitize_database_configs(items):
    try:
        return [DatabaseConfig(**{**i.model_dump(), "password": None}) for i in items]
    except Exception:
        return items

def _sanitize_kv(d: Dict[str, Any]) -> Dict[str, Any]:
    """对字典中的可能敏感键进行脱敏（仅用于响应）。"""
    try:
        if not isinstance(d, dict):
            return d
        sens_patterns = ("key", "secret", "password", "token", "client_secret")
        redacted = {}
        for k, v in d.items():
            if isinstance(k, str) and any(p in k.lower() for p in sens_patterns):
                redacted[k] = None
            else:
                redacted[k] = v
        return redacted
    except Exception:
        return d




class SetDefaultRequest(BaseModel):
    """设置默认配置请求"""
    name: str


class FetchProviderModelsRequest(BaseModel):
    """从厂家 API 获取模型列表时的过滤参数"""
    type: str | None = None
    modalities: str | None = None
    features: List[str] | None = None
    provider_names: List[str] | None = None
    model_keyword: str | None = None
    sort_by: str | None = None
    sort_order: str | None = None
    limit: int | None = None
    recommended_only: bool = False
    tools_only: bool = False
    exclude_preview: bool = True


@router.get("/system", response_model=dict)
async def get_system_config(
    current_user: User = Depends(get_current_user)
):
    """获取系统配置"""
    try:
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="系统配置不存在"
            )

        return ok(data=SystemConfigResponse(
            config_name=config.config_name,
            config_type=config.config_type,
            llm_configs=_sanitize_llm_configs(config.llm_configs),
            default_llm=config.default_llm,
            data_source_configs=_sanitize_datasource_configs(config.data_source_configs),
            default_data_source=config.default_data_source,
            database_configs=_sanitize_database_configs(config.database_configs),
            system_settings=_sanitize_kv(config.system_settings),
            created_at=config.created_at,
            updated_at=config.updated_at,
            version=config.version,
            is_active=config.is_active
        ), message="获取系统配置成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统配置失败: {str(e)}"
        )


# ========== 大模型厂家管理 ==========

@router.get("/llm/providers", response_model=dict)
async def get_llm_providers(
    current_user: User = Depends(get_current_user)
):
    """获取所有大模型厂家"""
    try:
        from app.utils.api_key_utils import (
            is_valid_api_key,
            truncate_api_key,
            get_env_api_key_for_provider
        )

        providers = await config_service.get_llm_providers()
        result = []

        for provider in providers:
            # 处理 API Key：优先使用数据库配置，如果数据库没有则检查环境变量
            db_key_valid = is_valid_api_key(provider.api_key)
            if db_key_valid:
                # 数据库中有有效的 API Key，返回缩略版本
                api_key_display = truncate_api_key(provider.api_key)
            else:
                # 数据库中没有有效的 API Key，尝试从环境变量读取
                env_key = get_env_api_key_for_provider(provider.name)
                if env_key:
                    # 环境变量中有有效的 API Key，返回缩略版本
                    api_key_display = truncate_api_key(env_key)
                else:
                    api_key_display = None

            # 处理 API Secret（同样的逻辑）
            db_secret_valid = is_valid_api_key(provider.api_secret)
            if db_secret_valid:
                api_secret_display = truncate_api_key(provider.api_secret)
            else:
                # 注意：API Secret 通常不在环境变量中，所以这里只检查数据库
                api_secret_display = None

            result.append(
                LLMProviderResponse(
                    id=str(provider.id),
                    name=provider.name,
                    display_name=provider.display_name,
                    description=provider.description,
                    website=provider.website,
                    api_doc_url=provider.api_doc_url,
                    logo_url=provider.logo_url,
                    is_active=provider.is_active,
                    supported_features=provider.supported_features,
                    default_base_url=provider.default_base_url,
                    # 返回缩略的 API Key（前6位 + "..." + 后6位）
                    api_key=api_key_display,
                    api_secret=api_secret_display,
                    extra_config={
                        **provider.extra_config,
                        "has_api_key": bool(api_key_display),
                        "has_api_secret": bool(api_secret_display)
                    },
                    created_at=provider.created_at,
                    updated_at=provider.updated_at
                )
            )

        return ok(data=result, message="获取厂家列表成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取厂家列表失败: {str(e)}"
        )


@router.post("/llm/providers", response_model=dict)
async def add_llm_provider(
    request: LLMProviderRequest,
    current_user: User = Depends(get_current_user)
):
    """添加大模型厂家"""
    try:
        from app.utils.api_key_utils import should_skip_api_key_update

        provider_data = request.model_dump()

        # 新增时也允许保存完整密钥；占位符/截断值则跳过该字段
        if 'api_key' in provider_data:
            api_key = provider_data.get('api_key', '')
            if should_skip_api_key_update(api_key):
                del provider_data['api_key']

        if 'api_secret' in provider_data:
            api_secret = provider_data.get('api_secret', '')
            if should_skip_api_key_update(api_secret):
                del provider_data['api_secret']

        provider = LLMProvider(**provider_data)
        provider_id = await config_service.add_llm_provider(provider)

        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="add_llm_provider",
                details={"provider_id": str(provider_id), "name": request.name},
                success=True,
            )
        except Exception:
            pass

        return ok(data={"message": "厂家添加成功", "id": str(provider_id)}, message="厂家添加成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加厂家失败: {str(e)}"
        )


@router.put("/llm/providers/{provider_id}", response_model=dict)
async def update_llm_provider(
    provider_id: str,
    request: LLMProviderRequest,
    current_user: User = Depends(get_current_user)
):
    """更新大模型厂家"""
    try:
        from app.utils.api_key_utils import should_skip_api_key_update

        update_data = request.model_dump(exclude_unset=True)

        # 🔥 修改：处理 API Key 的更新逻辑
        # 1. 如果 API Key 是空字符串，表示用户想清空密钥 → 保存空字符串
        # 2. 如果 API Key 是占位符或截断的密钥（如 "sk-99054..."），则删除该字段（不更新）
        # 3. 如果 API Key 是有效的完整密钥，则更新
        if 'api_key' in update_data:
            api_key = update_data.get('api_key', '')
            # 如果应该跳过更新（占位符或截断的密钥），则删除该字段
            if should_skip_api_key_update(api_key):
                del update_data['api_key']
            # 如果是空字符串，保留（表示清空）
            # 如果是有效的完整密钥，保留（表示更新）

        if 'api_secret' in update_data:
            api_secret = update_data.get('api_secret', '')
            # 同样的逻辑处理 API Secret
            if should_skip_api_key_update(api_secret):
                del update_data['api_secret']

        success = await config_service.update_llm_provider(provider_id, update_data)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_llm_provider",
                    details={"provider_id": provider_id, "changed_keys": list(request.model_dump().keys())},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "厂家更新成功"}, message="厂家更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="厂家不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新厂家失败: {str(e)}"
        )


@router.delete("/llm/providers/{provider_id}", response_model=dict)
async def delete_llm_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user)
):
    """删除大模型厂家"""
    try:
        success = await config_service.delete_llm_provider(provider_id)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="delete_llm_provider",
                    details={"provider_id": provider_id},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "厂家删除成功"}, message="厂家删除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="厂家不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除厂家失败: {str(e)}"
        )


@router.patch("/llm/providers/{provider_id}/toggle", response_model=dict)
async def toggle_llm_provider(
    provider_id: str,
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """切换大模型厂家状态"""
    try:
        is_active = request.get("is_active", True)
        success = await config_service.toggle_llm_provider(provider_id, is_active)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="toggle_llm_provider",
                    details={"provider_id": provider_id, "is_active": bool(is_active)},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": f"厂家已{'启用' if is_active else '禁用'}"}, message=f"厂家已{'启用' if is_active else '禁用'}")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="厂家不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"切换厂家状态失败: {str(e)}"
        )


@router.post("/llm/providers/{provider_id}/fetch-models", response_model=dict)
async def fetch_provider_models(
    provider_id: str,
    request: FetchProviderModelsRequest | None = None,
    current_user: User = Depends(get_current_user)
):
    """从厂家 API 获取模型列表"""
    try:
        filters = request.model_dump(exclude_none=True) if request else None
        logger.info(
            "🔍 [API] POST /api/config/llm/providers/%s/fetch-models user=%s filters=%s",
            provider_id,
            getattr(current_user, "username", None),
            filters,
        )
        result = await config_service.fetch_provider_models(provider_id, filters)
        logger.info(
            "📦 [API] fetch-models result provider_id=%s success=%s models=%s message=%s",
            provider_id,
            result.get("success"),
            len(result.get("models") or []),
            result.get("message"),
        )
        return ok(data=result, message=result.get("message", "获取模型列表成功"))
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取模型列表失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型列表失败: {str(e)}"
        )


@router.post("/llm/providers/migrate-env", response_model=dict)
async def migrate_env_to_providers(
    current_user: User = Depends(get_current_user)
):
    """将环境变量配置迁移到厂家管理"""
    try:
        result = await config_service.migrate_env_to_providers()
        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="migrate_env_to_providers",
                details={
                    "migrated_count": result.get("migrated_count", 0),
                    "skipped_count": result.get("skipped_count", 0)
                },
                success=bool(result.get("success", False)),
            )
        except Exception:
            pass

        return ok(
            data={
                "message": result["message"],
                "data": {
                    "migrated_count": result.get("migrated_count", 0),
                    "skipped_count": result.get("skipped_count", 0)
                }
            },
            message=result["message"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"环境变量迁移失败: {str(e)}"
        )


@router.post("/llm/providers/init-aggregators", response_model=dict)
async def init_aggregator_providers(
    current_user: User = Depends(get_current_user)
):
    """初始化聚合渠道厂家配置（302.AI、OpenRouter等）"""
    try:
        result = await config_service.init_aggregator_providers()

        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="init_aggregator_providers",
                details={
                    "added_count": result.get("added", 0),
                    "skipped_count": result.get("skipped", 0)
                },
                success=bool(result.get("success", False)),
            )
        except Exception:
            pass

        return ok(
            data={
                "success": result["success"],
                "message": result["message"],
                "data": {
                    "added_count": result.get("added", 0),
                    "skipped_count": result.get("skipped", 0)
                }
            },
            message=result["message"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化聚合渠道失败: {str(e)}"
        )


@router.post("/llm/providers/{provider_id}/test", response_model=dict)
async def test_provider_api(
    provider_id: str,
    current_user: User = Depends(get_current_user)
):
    """测试厂家API密钥"""
    try:
        logger.info(f"🧪 收到API测试请求 - provider_id: {provider_id}")
        result = await config_service.test_provider_api(provider_id)
        logger.info(f"🧪 API测试结果: {result}")
        return ok(data=result, message=result.get("message", "测试厂家API完成"))
    except Exception as e:
        logger.error(f"测试厂家API失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"测试厂家API失败: {str(e)}"
        )


# ========== 大模型配置管理 ==========

@router.post("/llm", response_model=dict)
async def add_llm_config(
    request: LLMConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """添加或更新大模型配置"""
    try:
        logger.info(f"🔧 添加/更新大模型配置开始")
        logger.info(f"📊 请求数据: {request.model_dump()}")
        logger.info(f"🏷️ 厂家: {request.provider}, 模型: {request.model_name}")

        # 创建LLM配置
        llm_config_data = request.model_dump()
        logger.info(f"📋 原始配置数据: {llm_config_data}")

        # 如果没有提供API密钥，从厂家配置中获取
        if not llm_config_data.get('api_key'):
            logger.info(f"🔑 API密钥为空，从厂家配置获取: {request.provider}")

            # 获取厂家配置
            providers = await config_service.get_llm_providers()
            logger.info(f"📊 找到 {len(providers)} 个厂家配置")

            for p in providers:
                logger.info(f"   - 厂家: {p.name}, 有API密钥: {bool(p.api_key)}")

            provider_config = next((p for p in providers if p.name == request.provider), None)

            if provider_config:
                logger.info(f"✅ 找到厂家配置: {provider_config.name}")
                if provider_config.api_key:
                    llm_config_data['api_key'] = provider_config.api_key
                    logger.info(f"✅ 成功获取厂家API密钥 (长度: {len(provider_config.api_key)})")
                else:
                    logger.warning(f"⚠️ 厂家 {request.provider} 没有配置API密钥")
                    llm_config_data['api_key'] = ""
            else:
                logger.warning(f"⚠️ 未找到厂家 {request.provider} 的配置")
                llm_config_data['api_key'] = ""
        else:
            logger.info(f"🔑 使用提供的API密钥 (长度: {len(llm_config_data.get('api_key', ''))})")

        logger.info(f"📋 最终配置数据: {llm_config_data}")
        # 🔥 修改：允许通过 REST 写入密钥，但如果是无效的密钥则清空
        # 无效的密钥：空字符串、占位符（your_xxx）、长度不够
        if 'api_key' in llm_config_data:
            api_key = llm_config_data.get('api_key', '')
            # 如果是无效的 Key，则清空（让系统使用环境变量）
            if not api_key or api_key.startswith('your_') or api_key.startswith('your-') or len(api_key) <= 10:
                llm_config_data['api_key'] = ""


        # 尝试创建LLMConfig对象
        try:
            llm_config = LLMConfig(**llm_config_data)
            logger.info(f"✅ LLMConfig对象创建成功")
        except Exception as e:
            logger.error(f"❌ LLMConfig对象创建失败: {e}")
            logger.error(f"📋 失败的数据: {llm_config_data}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"配置数据验证失败: {str(e)}"
            )

        # 保存配置
        success = await config_service.update_llm_config(llm_config)

        if success:
            logger.info(f"✅ 大模型配置更新成功: {llm_config.provider}/{llm_config.model_name}")

            # 同步定价配置到 tradingagents
            try:
                from app.core.config_bridge import sync_pricing_config_now
                sync_pricing_config_now()
                logger.info(f"✅ 定价配置已同步到 tradingagents")
            except Exception as e:
                logger.warning(f"⚠️  同步定价配置失败: {e}")

            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_llm_config",
                    details={"provider": llm_config.provider, "model_name": llm_config.model_name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "大模型配置更新成功", "model_name": llm_config.model_name}, message="大模型配置更新成功")
        else:
            logger.error(f"❌ 大模型配置保存失败")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="大模型配置更新失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 添加大模型配置异常: {e}")
        import traceback
        logger.error(f"📋 异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加大模型配置失败: {str(e)}"
        )


@router.post("/datasource", response_model=dict)
async def add_data_source_config(
    request: DataSourceConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """添加数据源配置"""
    try:
        # 开源版本：所有用户都可以修改配置

        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="系统配置不存在"
            )

        # 添加新的数据源配置
        # 🔥 修改：支持保存 API Key（与大模型厂家管理逻辑一致）
        from app.utils.api_key_utils import should_skip_api_key_update, is_valid_api_key

        _req = request.model_dump()

        # 处理 API Key
        if 'api_key' in _req:
            api_key = _req.get('api_key', '')
            # 如果是占位符或截断的密钥，清空该字段
            if should_skip_api_key_update(api_key):
                _req['api_key'] = ""
            # 如果是空字符串，保留（表示使用环境变量）
            elif api_key == '':
                _req['api_key'] = ''
            # 如果是新输入的密钥，必须验证有效性
            elif not is_valid_api_key(api_key):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API Key 无效：长度必须大于 10 个字符，且不能是占位符"
                )
            # 有效的完整密钥，保留

        # 处理 API Secret
        if 'api_secret' in _req:
            api_secret = _req.get('api_secret', '')
            if should_skip_api_key_update(api_secret):
                _req['api_secret'] = ""
            # 如果是空字符串，保留
            elif api_secret == '':
                _req['api_secret'] = ''
            # 如果是新输入的密钥，必须验证有效性
            elif not is_valid_api_key(api_secret):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API Secret 无效：长度必须大于 10 个字符，且不能是占位符"
                )

        ds_config = DataSourceConfig(**_req)
        config.data_source_configs.append(ds_config)

        success = await config_service.save_system_config(config)
        if success:
            # 🆕 自动创建数据源分组关系
            market_categories = _req.get('market_categories', [])
            if market_categories:
                for category_id in market_categories:
                    try:
                        grouping = DataSourceGrouping(
                            data_source_name=ds_config.name,
                            market_category_id=category_id,
                            priority=ds_config.priority,
                            enabled=ds_config.enabled
                        )
                        await config_service.add_datasource_to_category(grouping)
                    except Exception as e:
                        # 如果分组已存在或其他错误，记录但不影响主流程
                        logger.warning(f"自动创建数据源分组失败: {str(e)}")

            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_data_source_config",
                    details={"name": ds_config.name, "market_categories": market_categories},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "数据源配置添加成功", "name": ds_config.name}, message="数据源配置添加成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="数据源配置添加失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据源配置失败: {str(e)}"
        )


@router.post("/database", response_model=dict)
async def add_database_config(
    request: DatabaseConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """添加数据库配置"""
    try:
        # 开源版本：所有用户都可以修改配置

        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="系统配置不存在"
            )

        # 添加新的数据库配置（方案A：清洗敏感字段）
        _req = request.model_dump()
        _req['password'] = ""
        db_config = DatabaseConfig(**_req)
        config.database_configs.append(db_config)

        success = await config_service.save_system_config(config)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_database_config",
                    details={"name": db_config.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"success": True, "message": "数据库配置添加成功", "name": db_config.name}, message="数据库配置添加成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="数据库配置添加失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据库配置失败: {str(e)}"
        )


@router.post("/test", response_model=dict)
async def test_config(
    request: ConfigTestRequest,
    current_user: User = Depends(get_current_user)
):
    """测试配置连接"""
    try:
        if request.config_type == "llm":
            llm_config = LLMConfig(**request.config_data)
            result = await config_service.test_llm_config(llm_config)
        elif request.config_type == "datasource":
            ds_config = DataSourceConfig(**request.config_data)
            result = await config_service.test_data_source_config(ds_config)
        elif request.config_type == "database":
            db_config = DatabaseConfig(**request.config_data)
            result = await config_service.test_database_config(db_config)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的配置类型"
            )

        response = ConfigTestResponse(**result)
        return ok(data=response.model_dump(), message=response.message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试配置失败: {str(e)}"
        )


@router.post("/database/{db_name}/test", response_model=dict)
async def test_saved_database_config(
    db_name: str,
    current_user: dict = Depends(get_current_user)
):
    """测试已保存的数据库配置（从数据库中获取完整配置包括密码）"""
    try:
        logger.info(f"🧪 测试已保存的数据库配置: {db_name}")

        # 从数据库获取完整的系统配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="系统配置不存在"
            )

        # 查找指定的数据库配置
        db_config = None
        for db in config.database_configs:
            if db.name == db_name:
                db_config = db
                break

        if not db_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在"
            )

        logger.info(f"✅ 找到数据库配置: {db_config.name} ({db_config.type})")
        logger.info(f"📍 连接信息: {db_config.host}:{db_config.port}")
        logger.info(f"🔐 用户名: {db_config.username or '(无)'}")
        logger.info(f"🔐 密码: {'***' if db_config.password else '(无)'}")

        # 使用完整配置进行测试
        result = await config_service.test_database_config(db_config)

        response = ConfigTestResponse(**result)
        return ok(data=response.model_dump(), message=response.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 测试数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试数据库配置失败: {str(e)}"
        )


@router.get("/llm", response_model=dict)
async def get_llm_configs(
    current_user: User = Depends(get_current_user)
):
    """获取所有大模型配置"""
    try:
        logger.info("🔄 开始获取大模型配置...")
        config = await config_service.get_system_config()

        if not config:
            logger.warning("⚠️ 系统配置为空，返回空列表")
            return ok(data=[], message="获取大模型配置成功")

        logger.info(f"📊 系统配置存在，大模型配置数量: {len(config.llm_configs)}")

        # 如果没有大模型配置，创建一些示例配置
        if not config.llm_configs:
            logger.info("🔧 没有大模型配置，创建示例配置...")
            # 这里可以根据已有的厂家创建示例配置
            # 暂时返回空列表，让前端显示"暂无配置"

        # 获取所有供应商信息，用于过滤被禁用供应商的模型
        providers = await config_service.get_llm_providers()
        active_provider_names = {p.name for p in providers if p.is_active}

        # 过滤：只返回启用的模型 且 供应商也启用的模型
        filtered_configs = [
            llm_config for llm_config in config.llm_configs
            if llm_config.enabled and llm_config.provider in active_provider_names
        ]

        sorted_configs = _sort_llm_configs_by_newest(filtered_configs)

        logger.info(f"✅ 过滤后的大模型配置数量: {len(sorted_configs)} (原始: {len(config.llm_configs)})")

        return ok(data=_sanitize_llm_configs(sorted_configs), message="获取大模型配置成功")
    except Exception as e:
        logger.error(f"❌ 获取大模型配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取大模型配置失败: {str(e)}"
        )


@router.delete("/llm/{provider}/{model_name}")
async def delete_llm_config(
    provider: str,
    model_name: str,
    current_user: User = Depends(get_current_user)
):
    """删除大模型配置"""
    try:
        logger.info(f"🗑️ 删除大模型配置请求 - provider: {provider}, model_name: {model_name}")
        success = await config_service.delete_llm_config(provider, model_name)

        if success:
            logger.info(f"✅ 大模型配置删除成功 - {provider}/{model_name}")

            # 同步定价配置到 tradingagents
            try:
                from app.core.config_bridge import sync_pricing_config_now
                sync_pricing_config_now()
                logger.info(f"✅ 定价配置已同步到 tradingagents")
            except Exception as e:
                logger.warning(f"⚠️  同步定价配置失败: {e}")

            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="delete_llm_config",
                    details={"provider": provider, "model_name": model_name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "大模型配置删除成功"}, message="大模型配置删除成功")
        else:
            logger.warning(f"⚠️ 未找到大模型配置 - {provider}/{model_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="大模型配置不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除大模型配置异常 - {provider}/{model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除大模型配置失败: {str(e)}"
        )


@router.post("/llm/set-default")
async def set_default_llm(
    request: SetDefaultRequest,
    current_user: User = Depends(get_current_user)
):
    """设置默认大模型"""
    try:
        success = await config_service.set_default_llm(request.name)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="set_default_llm",
                    details={"name": request.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "默认大模型设置成功", "default_llm": request.name}, message="默认大模型设置成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定的大模型不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置默认大模型失败: {str(e)}"
        )


@router.get("/datasource", response_model=dict)
async def get_data_source_configs(
    current_user: User = Depends(get_current_user)
):
    """获取所有数据源配置"""
    try:
        config = await config_service.get_system_config()
        if not config:
            return ok(data=[], message="获取数据源配置成功")
        return ok(data=_sanitize_datasource_configs(config.data_source_configs), message="获取数据源配置成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据源配置失败: {str(e)}"
        )


@router.put("/datasource/{name}", response_model=dict)
async def update_data_source_config(
    name: str,
    request: DataSourceConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """更新数据源配置"""
    try:
        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="系统配置不存在"
            )

        # 查找并更新数据源配置
        from app.utils.api_key_utils import should_skip_api_key_update, is_valid_api_key

        def _truncate_api_key(api_key: str, prefix_len: int = 6, suffix_len: int = 6) -> str:
            """截断 API Key 用于显示"""
            if not api_key or len(api_key) <= prefix_len + suffix_len:
                return api_key
            return f"{api_key[:prefix_len]}...{api_key[-suffix_len:]}"

        for i, ds_config in enumerate(config.data_source_configs):
            if ds_config.name == name:
                # 更新配置
                # 🔥 修改：处理 API Key 的更新逻辑（与大模型厂家管理逻辑一致）
                _req = request.model_dump()

                # 处理 API Key
                if 'api_key' in _req:
                    api_key = _req.get('api_key')
                    logger.info(f"🔍 [API Key 验证] 收到的 API Key: {repr(api_key)} (类型: {type(api_key).__name__}, 长度: {len(api_key) if api_key else 0})")

                    # 如果是 None 或空字符串，保留原值（不更新）
                    if api_key is None or api_key == '':
                        logger.info(f"⏭️  [API Key 验证] None 或空字符串，保留原值")
                        _req['api_key'] = ds_config.api_key or ""
                    # 🔥 如果包含 "..."（截断标记），需要验证是否是未修改的原值
                    elif api_key and "..." in api_key:
                        logger.info(f"🔍 [API Key 验证] 检测到截断标记，验证是否与数据库原值匹配")

                        # 对数据库中的完整 API Key 进行相同的截断处理
                        if ds_config.api_key:
                            truncated_db_key = _truncate_api_key(ds_config.api_key)
                            logger.info(f"🔍 [API Key 验证] 数据库原值截断后: {truncated_db_key}")
                            logger.info(f"🔍 [API Key 验证] 收到的值: {api_key}")

                            # 比较截断后的值
                            if api_key == truncated_db_key:
                                # 相同，说明用户没有修改，保留数据库中的完整值
                                logger.info(f"✅ [API Key 验证] 截断值匹配，保留数据库原值")
                                _req['api_key'] = ds_config.api_key
                            else:
                                # 不同，说明用户修改了但修改得不完整
                                logger.error(f"❌ [API Key 验证] 截断值不匹配，用户可能修改了不完整的密钥")
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"API Key 格式错误：检测到截断标记但与数据库中的值不匹配，请输入完整的 API Key"
                                )
                        else:
                            # 数据库中没有原值，但前端发送了截断值，这是不合理的
                            logger.error(f"❌ [API Key 验证] 数据库中没有原值，但收到了截断值")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"API Key 格式错误：请输入完整的 API Key"
                            )
                    # 如果是占位符，则不更新（保留原值）
                    elif should_skip_api_key_update(api_key):
                        logger.info(f"⏭️  [API Key 验证] 跳过更新（占位符），保留原值")
                        _req['api_key'] = ds_config.api_key or ""
                    # 如果是新输入的密钥，必须验证有效性
                    elif not is_valid_api_key(api_key):
                        logger.error(f"❌ [API Key 验证] 验证失败: '{api_key}' (长度: {len(api_key)})")
                        logger.error(f"   - 长度检查: {len(api_key)} > 10? {len(api_key) > 10}")
                        logger.error(f"   - 占位符前缀检查: startswith('your_')? {api_key.startswith('your_')}, startswith('your-')? {api_key.startswith('your-')}")
                        logger.error(f"   - 占位符后缀检查: endswith('_here')? {api_key.endswith('_here')}, endswith('-here')? {api_key.endswith('-here')}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"API Key 无效：长度必须大于 10 个字符，且不能是占位符（当前长度: {len(api_key)}）"
                        )
                    else:
                        logger.info(f"✅ [API Key 验证] 验证通过，将更新密钥 (长度: {len(api_key)})")
                    # 有效的完整密钥，保留（表示更新）

                # 处理 API Secret
                if 'api_secret' in _req:
                    api_secret = _req.get('api_secret')
                    logger.info(f"🔍 [API Secret 验证] 收到的 API Secret: {repr(api_secret)} (类型: {type(api_secret).__name__}, 长度: {len(api_secret) if api_secret else 0})")

                    # 如果是 None 或空字符串，保留原值（不更新）
                    if api_secret is None or api_secret == '':
                        logger.info(f"⏭️  [API Secret 验证] None 或空字符串，保留原值")
                        _req['api_secret'] = ds_config.api_secret or ""
                    # 🔥 如果包含 "..."（截断标记），需要验证是否是未修改的原值
                    elif api_secret and "..." in api_secret:
                        logger.info(f"🔍 [API Secret 验证] 检测到截断标记，验证是否与数据库原值匹配")

                        # 对数据库中的完整 API Secret 进行相同的截断处理
                        if ds_config.api_secret:
                            truncated_db_secret = _truncate_api_key(ds_config.api_secret)
                            logger.info(f"🔍 [API Secret 验证] 数据库原值截断后: {truncated_db_secret}")
                            logger.info(f"🔍 [API Secret 验证] 收到的值: {api_secret}")

                            # 比较截断后的值
                            if api_secret == truncated_db_secret:
                                # 相同，说明用户没有修改，保留数据库中的完整值
                                logger.info(f"✅ [API Secret 验证] 截断值匹配，保留数据库原值")
                                _req['api_secret'] = ds_config.api_secret
                            else:
                                # 不同，说明用户修改了但修改得不完整
                                logger.error(f"❌ [API Secret 验证] 截断值不匹配，用户可能修改了不完整的密钥")
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"API Secret 格式错误：检测到截断标记但与数据库中的值不匹配，请输入完整的 API Secret"
                                )
                        else:
                            # 数据库中没有原值，但前端发送了截断值，这是不合理的
                            logger.error(f"❌ [API Secret 验证] 数据库中没有原值，但收到了截断值")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"API Secret 格式错误：请输入完整的 API Secret"
                            )
                    # 如果是占位符，则不更新（保留原值）
                    elif should_skip_api_key_update(api_secret):
                        logger.info(f"⏭️  [API Secret 验证] 跳过更新（占位符），保留原值")
                        _req['api_secret'] = ds_config.api_secret or ""
                    # 如果是新输入的密钥，必须验证有效性
                    elif not is_valid_api_key(api_secret):
                        logger.error(f"❌ [API Secret 验证] 验证失败: '{api_secret}' (长度: {len(api_secret)})")
                        logger.error(f"   - 长度检查: {len(api_secret)} > 10? {len(api_secret) > 10}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"API Secret 无效：长度必须大于 10 个字符，且不能是占位符（当前长度: {len(api_secret)}）"
                        )
                    else:
                        logger.info(f"✅ [API Secret 验证] 验证通过，将更新密钥 (长度: {len(api_secret)})")

                updated_config = DataSourceConfig(**_req)
                config.data_source_configs[i] = updated_config

                success = await config_service.save_system_config(config)
                if success:
                    # 🆕 同步市场分类关系
                    new_categories = set(_req.get('market_categories', []))

                    # 获取当前的分组关系
                    current_groupings = await config_service.get_datasource_groupings()
                    current_categories = set(
                        g.market_category_id
                        for g in current_groupings
                        if g.data_source_name == name
                    )

                    # 需要添加的分类
                    to_add = new_categories - current_categories
                    for category_id in to_add:
                        try:
                            grouping = DataSourceGrouping(
                                data_source_name=name,
                                market_category_id=category_id,
                                priority=updated_config.priority,
                                enabled=updated_config.enabled
                            )
                            await config_service.add_datasource_to_category(grouping)
                        except Exception as e:
                            logger.warning(f"添加数据源分组失败: {str(e)}")

                    # 需要删除的分类
                    to_remove = current_categories - new_categories
                    for category_id in to_remove:
                        try:
                            await config_service.remove_datasource_from_category(name, category_id)
                        except Exception as e:
                            logger.warning(f"删除数据源分组失败: {str(e)}")

                    # 审计日志（忽略异常）
                    try:
                        await log_operation(
                            user_id=str(getattr(current_user, "id", "")),
                            username=getattr(current_user, "username", "unknown"),
                            action_type=ActionType.CONFIG_MANAGEMENT,
                            action="update_data_source_config",
                            details={"name": name, "market_categories": list(new_categories)},
                            success=True,
                        )
                    except Exception:
                        pass
                    return ok(data={"message": "数据源配置更新成功"}, message="数据源配置更新成功")
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="数据源配置更新失败"
                    )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源配置不存在"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据源配置失败: {str(e)}"
        )


@router.delete("/datasource/{name}", response_model=dict)
async def delete_data_source_config(
    name: str,
    current_user: User = Depends(get_current_user)
):
    """删除数据源配置"""
    try:
        # 获取当前配置
        config = await config_service.get_system_config()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="系统配置不存在"
            )

        # 查找并删除数据源配置
        for i, ds_config in enumerate(config.data_source_configs):
            if ds_config.name == name:
                config.data_source_configs.pop(i)

                success = await config_service.save_system_config(config)
                if success:
                    # 审计日志（忽略异常）
                    try:
                        await log_operation(
                            user_id=str(getattr(current_user, "id", "")),
                            username=getattr(current_user, "username", "unknown"),
                            action_type=ActionType.CONFIG_MANAGEMENT,
                            action="delete_data_source_config",
                            details={"name": name},
                            success=True,
                        )
                    except Exception:
                        pass
                    return ok(data={"message": "数据源配置删除成功"}, message="数据源配置删除成功")
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="数据源配置删除失败"
                    )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源配置不存在"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除数据源配置失败: {str(e)}"
        )


# ==================== 市场分类管理 ====================

@router.get("/market-categories", response_model=dict)
async def get_market_categories(
    current_user: User = Depends(get_current_user)
):
    """获取所有市场分类"""
    try:
        categories = await config_service.get_market_categories()
        return ok(data=categories, message="获取市场分类成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取市场分类失败: {str(e)}"
        )


@router.post("/market-categories", response_model=dict)
async def add_market_category(
    request: MarketCategoryRequest,
    current_user: User = Depends(get_current_user)
):
    """添加市场分类"""
    try:
        category = MarketCategory(**request.model_dump())
        success = await config_service.add_market_category(category)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_market_category",
                    details={"id": str(getattr(category, 'id', ''))},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "市场分类添加成功", "id": category.id}, message="市场分类添加成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="市场分类ID已存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加市场分类失败: {str(e)}"
        )


@router.put("/market-categories/{category_id}", response_model=dict)
async def update_market_category(
    category_id: str,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """更新市场分类"""
    try:
        success = await config_service.update_market_category(category_id, request)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_market_category",
                    details={"category_id": category_id, "changed_keys": list(request.keys())},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "市场分类更新成功"}, message="市场分类更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="市场分类不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新市场分类失败: {str(e)}"
        )


@router.delete("/market-categories/{category_id}", response_model=dict)
async def delete_market_category(
    category_id: str,
    current_user: User = Depends(get_current_user)
):
    """删除市场分类"""
    try:
        success = await config_service.delete_market_category(category_id)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="delete_market_category",
                    details={"category_id": category_id},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "市场分类删除成功"}, message="市场分类删除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法删除分类，可能还有数据源使用此分类"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除市场分类失败: {str(e)}"
        )


# ==================== 数据源分组管理 ====================

@router.get("/datasource-groupings", response_model=dict)
async def get_datasource_groupings(
    current_user: User = Depends(get_current_user)
):
    """获取所有数据源分组关系"""
    try:
        groupings = await config_service.get_datasource_groupings()
        return ok(data=groupings, message="获取数据源分组关系成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据源分组关系失败: {str(e)}"
        )


@router.post("/datasource-groupings", response_model=dict)
async def add_datasource_to_category(
    request: DataSourceGroupingRequest,
    current_user: User = Depends(get_current_user)
):
    """将数据源添加到分类"""
    try:
        grouping = DataSourceGrouping(**request.model_dump())
        success = await config_service.add_datasource_to_category(grouping)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="add_datasource_to_category",
                    details={"data_source_name": request.data_source_name, "category_id": request.category_id},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "数据源添加到分类成功"}, message="数据源添加到分类成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数据源已在该分类中"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据源到分类失败: {str(e)}"
        )


@router.delete("/datasource-groupings/{data_source_name}/{category_id}", response_model=dict)
async def remove_datasource_from_category(
    data_source_name: str,
    category_id: str,
    current_user: User = Depends(get_current_user)
):
    """从分类中移除数据源"""
    try:
        success = await config_service.remove_datasource_from_category(data_source_name, category_id)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="remove_datasource_from_category",
                    details={"data_source_name": data_source_name, "category_id": category_id},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "数据源从分类中移除成功"}, message="数据源从分类中移除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="数据源分组关系不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从分类中移除数据源失败: {str(e)}"
        )


@router.put("/datasource-groupings/{data_source_name}/{category_id}", response_model=dict)
async def update_datasource_grouping(
    data_source_name: str,
    category_id: str,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """更新数据源分组关系"""
    try:
        success = await config_service.update_datasource_grouping(data_source_name, category_id, request)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_datasource_grouping",
                    details={"data_source_name": data_source_name, "category_id": category_id, "changed_keys": list(request.keys())},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "数据源分组关系更新成功"}, message="数据源分组关系更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="数据源分组关系不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据源分组关系失败: {str(e)}"
        )


@router.put("/market-categories/{category_id}/datasource-order", response_model=dict)
async def update_category_datasource_order(
    category_id: str,
    request: DataSourceOrderRequest,
    current_user: User = Depends(get_current_user)
):
    """更新分类中数据源的排序"""
    try:
        success = await config_service.update_category_datasource_order(category_id, request.data_sources)

        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_category_datasource_order",
                    details={"category_id": category_id, "data_sources": request.data_sources},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "数据源排序更新成功"}, message="数据源排序更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="数据源排序更新失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据源排序失败: {str(e)}"
        )


@router.post("/datasource/set-default")
async def set_default_data_source(
    request: SetDefaultRequest,
    current_user: User = Depends(get_current_user)
):
    """设置默认数据源"""
    try:
        success = await config_service.set_default_data_source(request.name)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="set_default_datasource",
                    details={"name": request.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "默认数据源设置成功", "default_data_source": request.name}, message="默认数据源设置成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定的数据源不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置默认数据源失败: {str(e)}"
        )


@router.get("/settings", response_model=dict)
async def get_system_settings(
    current_user: User = Depends(get_current_user)
):
    """获取系统设置"""
    try:
        effective = await config_provider.get_effective_system_settings()
        return ok(data=_sanitize_kv(effective), message="获取系统设置成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统设置失败: {str(e)}"
        )


@router.get("/settings/meta", response_model=dict)
async def get_system_settings_meta(
    current_user: User = Depends(get_current_user)
):
    """获取系统设置的元数据（敏感性、可编辑性、来源、是否有值）。
    返回结构：{success, data: {items: [{key,sensitive,editable,source,has_value}]}, message}
    """
    try:
        meta_map = await config_provider.get_system_settings_meta()
        items = [
            {"key": k, **v} for k, v in meta_map.items()
        ]
        return ok(data={"items": items}, message="获取系统设置元数据成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统设置元数据失败: {str(e)}"
        )


@router.put("/settings", response_model=dict)
async def update_system_settings(
    settings: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """更新系统设置"""
    try:
        # 打印接收到的设置（用于调试）
        logger.info(f"📝 接收到的系统设置更新请求，包含 {len(settings)} 项")
        if 'quick_analysis_model' in settings:
            logger.info(f"  ✓ quick_analysis_model: {settings['quick_analysis_model']}")
        else:
            logger.warning(f"  ⚠️  未包含 quick_analysis_model")
        if 'deep_analysis_model' in settings:
            logger.info(f"  ✓ deep_analysis_model: {settings['deep_analysis_model']}")
        else:
            logger.warning(f"  ⚠️  未包含 deep_analysis_model")

        success = await config_service.update_system_settings(settings)
        if success:
            # 审计日志（忽略日志异常，不影响主流程）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="update_system_settings",
                    details={"changed_keys": list(settings.keys())},
                    success=True,
                )
            except Exception:
                pass
            # 失效缓存
            try:
                config_provider.invalidate()
            except Exception:
                pass
            return ok(data={"message": "系统设置更新成功"}, message="系统设置更新成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统设置更新失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        # 审计失败记录（忽略日志异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.CONFIG_MANAGEMENT,
                action="update_system_settings",
                details={"changed_keys": list(settings.keys())},
                success=False,
                error_message=str(e),
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新系统设置失败: {str(e)}"
        )


@router.post("/export", response_model=dict)
async def export_config(
    current_user: User = Depends(get_current_user)
):
    """导出配置"""
    try:
        config_data = await config_service.export_config()
        # 审计日志（忽略异常）
        try:
            await log_operation(
                user_id=str(getattr(current_user, "id", "")),
                username=getattr(current_user, "username", "unknown"),
                action_type=ActionType.DATA_EXPORT,
                action="export_config",
                details={"size": len(str(config_data))},
                success=True,
            )
        except Exception:
            pass
        return ok(
            data={
                "message": "配置导出成功",
                "data": config_data,
                "exported_at": now_tz().isoformat()
            },
            message="配置导出成功"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出配置失败: {str(e)}"
        )


@router.post("/import", response_model=dict)
async def import_config(
    config_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """导入配置"""
    try:
        success = await config_service.import_config(config_data)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.DATA_IMPORT,
                    action="import_config",
                    details={"keys": list(config_data.keys())[:10]},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "配置导入成功"}, message="配置导入成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="配置导入失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入配置失败: {str(e)}"
        )


@router.post("/migrate-legacy", response_model=dict)
async def migrate_legacy_config(
    current_user: User = Depends(get_current_user)
):
    """迁移传统配置"""
    try:
        success = await config_service.migrate_legacy_config()
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="migrate_legacy_config",
                    details={},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": "传统配置迁移成功"}, message="传统配置迁移成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="传统配置迁移失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"迁移传统配置失败: {str(e)}"
        )


@router.post("/default/llm", response_model=dict)
async def set_default_llm(
    request: SetDefaultRequest,
    current_user: User = Depends(get_current_user)
):
    """设置默认大模型"""
    try:
        # 开源版本：所有用户都可以修改配置

        success = await config_service.set_default_llm(request.name)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="set_default_llm",
                    details={"name": request.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": f"默认大模型已设置为: {request.name}"}, message=f"默认大模型已设置为: {request.name}")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="设置默认大模型失败，请检查模型名称是否正确"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置默认大模型失败: {str(e)}"
        )


@router.post("/default/datasource", response_model=dict)
async def set_default_data_source(
    request: SetDefaultRequest,
    current_user: User = Depends(get_current_user)
):
    """设置默认数据源"""
    try:
        # 开源版本：所有用户都可以修改配置

        success = await config_service.set_default_data_source(request.name)
        if success:
            # 审计日志（忽略异常）
            try:
                await log_operation(
                    user_id=str(getattr(current_user, "id", "")),
                    username=getattr(current_user, "username", "unknown"),
                    action_type=ActionType.CONFIG_MANAGEMENT,
                    action="set_default_datasource",
                    details={"name": request.name},
                    success=True,
                )
            except Exception:
                pass
            return ok(data={"message": f"默认数据源已设置为: {request.name}"}, message=f"默认数据源已设置为: {request.name}")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="设置默认数据源失败，请检查数据源名称是否正确"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置默认数据源失败: {str(e)}"
        )


@router.get("/models", response_model=dict)
async def get_available_models(
    current_user: User = Depends(get_current_user)
):
    """获取可用的模型列表"""
    try:
        models = await config_service.get_available_models()
        return ok(data=models, message="获取模型列表成功")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型列表失败: {str(e)}"
        )


# ========== 模型目录管理 ==========

@router.get("/model-catalog", response_model=dict)
async def get_model_catalog(
    current_user: User = Depends(get_current_user)
):
    """获取所有模型目录"""
    try:
        catalogs = await config_service.get_model_catalog()
        return ok(
            data=[catalog.model_dump(by_alias=False) for catalog in catalogs],
            message="获取模型目录成功"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型目录失败: {str(e)}"
        )


@router.get("/model-catalog/{provider}", response_model=dict)
async def get_provider_model_catalog(
    provider: str,
    current_user: User = Depends(get_current_user)
):
    """获取指定厂家的模型目录"""
    try:
        catalog = await config_service.get_provider_models(provider)
        if not catalog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到厂家 {provider} 的模型目录"
            )
        return ok(data=catalog.model_dump(by_alias=False), message="获取模型目录成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型目录失败: {str(e)}"
        )


class ModelCatalogRequest(BaseModel):
    """模型目录请求"""
    provider: str
    provider_name: str
    models: List[Dict[str, Any]]


@router.post("/model-catalog", response_model=dict)
async def save_model_catalog(
    request: ModelCatalogRequest,
    current_user: User = Depends(get_current_user)
):
    """保存或更新模型目录"""
    try:
        logger.info(f"📝 收到保存模型目录请求: provider={request.provider}, models数量={len(request.models)}")
        logger.info(f"📝 请求数据: {request.model_dump()}")

        # 转换为 ModelInfo 列表
        models = [ModelInfo(**m) for m in request.models]
        logger.info(f"✅ 成功转换 {len(models)} 个模型")

        catalog = ModelCatalog(
            provider=request.provider,
            provider_name=request.provider_name,
            models=models
        )
        logger.info(f"✅ 创建 ModelCatalog 对象成功")

        success = await config_service.save_model_catalog(catalog)
        logger.info(f"💾 保存结果: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存模型目录失败"
            )

        # 记录操作日志
        await log_operation(
            user_id=str(current_user["id"]),
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action="update_model_catalog",
            details={"provider": request.provider, "provider_name": request.provider_name, "models_count": len(request.models)}
        )

        return ok(data={"success": True, "message": "模型目录保存成功"}, message="模型目录保存成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 保存模型目录失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存模型目录失败: {str(e)}"
        )


@router.delete("/model-catalog/{provider}", response_model=dict)
async def delete_model_catalog(
    provider: str,
    current_user: User = Depends(get_current_user)
):
    """删除模型目录"""
    try:
        success = await config_service.delete_model_catalog(provider)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到厂家 {provider} 的模型目录"
            )

        # 记录操作日志
        await log_operation(
            user_id=str(current_user["id"]),
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action="delete_model_catalog",
            details={"provider": provider}
        )

        return ok(data={"success": True, "message": "模型目录删除成功"}, message="模型目录删除成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除模型目录失败: {str(e)}"
        )


@router.post("/model-catalog/init", response_model=dict)
async def init_model_catalog(
    current_user: User = Depends(get_current_user)
):
    """初始化默认模型目录"""
    try:
        success = await config_service.init_default_model_catalog()
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="初始化模型目录失败"
            )

        return ok(data={"success": True, "message": "模型目录初始化成功"}, message="模型目录初始化成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化模型目录失败: {str(e)}"
        )


# ===== 数据库配置管理端点 =====

@router.get("/database", response_model=dict)
async def get_database_configs(
    current_user: dict = Depends(get_current_user)
):
    """获取所有数据库配置"""
    try:
        logger.info("🔄 获取数据库配置列表...")
        configs = await config_service.get_database_configs()
        logger.info(f"✅ 获取到 {len(configs)} 个数据库配置")
        return ok(data=configs, message="获取数据库配置成功")
    except Exception as e:
        logger.error(f"❌ 获取数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库配置失败: {str(e)}"
        )


@router.get("/database/{db_name}", response_model=dict)
async def get_database_config(
    db_name: str,
    current_user: dict = Depends(get_current_user)
):
    """获取指定的数据库配置"""
    try:
        logger.info(f"🔄 获取数据库配置: {db_name}")
        config = await config_service.get_database_config(db_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在"
            )

        return ok(data=config, message="获取数据库配置成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库配置失败: {str(e)}"
        )


@router.post("/database", response_model=dict)
async def add_database_config(
    request: DatabaseConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """添加数据库配置"""
    try:
        logger.info(f"➕ 添加数据库配置: {request.name}")

        # 转换为 DatabaseConfig 对象
        db_config = DatabaseConfig(**request.model_dump())

        # 添加配置
        success = await config_service.add_database_config(db_config)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="添加数据库配置失败，可能已存在同名配置"
            )

        # 记录操作日志
        await log_operation(
            user_id=current_user["id"],
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action=f"添加数据库配置: {request.name}",
            details={"name": request.name, "type": request.type, "host": request.host, "port": request.port}
        )

        return ok(data={"success": True, "message": "数据库配置添加成功"}, message="数据库配置添加成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 添加数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据库配置失败: {str(e)}"
        )


@router.put("/database/{db_name}", response_model=dict)
async def update_database_config(
    db_name: str,
    request: DatabaseConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """更新数据库配置"""
    try:
        logger.info(f"🔄 更新数据库配置: {db_name}")

        # 检查名称是否匹配
        if db_name != request.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL中的名称与请求体中的名称不匹配"
            )

        # 转换为 DatabaseConfig 对象
        db_config = DatabaseConfig(**request.model_dump())

        # 更新配置
        success = await config_service.update_database_config(db_config)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在"
            )

        # 记录操作日志
        await log_operation(
            user_id=current_user["id"],
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action=f"更新数据库配置: {db_name}",
            details={"name": request.name, "type": request.type, "host": request.host, "port": request.port}
        )

        return ok(data={"success": True, "message": "数据库配置更新成功"}, message="数据库配置更新成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据库配置失败: {str(e)}"
        )


@router.delete("/database/{db_name}", response_model=dict)
async def delete_database_config(
    db_name: str,
    current_user: dict = Depends(get_current_user)
):
    """删除数据库配置"""
    try:
        logger.info(f"🗑️ 删除数据库配置: {db_name}")

        # 删除配置
        success = await config_service.delete_database_config(db_name)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"数据库配置 '{db_name}' 不存在"
            )

        # 记录操作日志
        await log_operation(
            user_id=current_user["id"],
            username=current_user.get("username", "unknown"),
            action_type=ActionType.CONFIG_MANAGEMENT,
            action=f"删除数据库配置: {db_name}",
            details={"name": db_name}
        )

        return ok(data={"success": True, "message": "数据库配置删除成功"}, message="数据库配置删除成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除数据库配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除数据库配置失败: {str(e)}"
        )
