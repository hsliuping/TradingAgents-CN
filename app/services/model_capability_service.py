"""
模型能力管理服务

提供模型能力评估、验证和推荐功能。
"""

from typing import Tuple, Dict, Optional, List, Any
from app.constants.model_capabilities import (
    ANALYSIS_DEPTH_REQUIREMENTS,
    DEFAULT_MODEL_CAPABILITIES,
    CAPABILITY_DESCRIPTIONS,
    ModelRole,
    ModelFeature
)
from app.core.unified_config import unified_config
from app.core.mapping_loader import get_mapping_loader
import logging
import re

logger = logging.getLogger(__name__)


class ModelCapabilityService:
    """模型能力管理服务"""

    def _parse_aggregator_model_name(self, model_name: str) -> Tuple[Optional[str], str]:
        """
        解析聚合渠道的模型名称

        Args:
            model_name: 模型名称，可能包含前缀（如 openai/gpt-4, anthropic/claude-3-sonnet）

        Returns:
            (原厂商, 原模型名) 元组
        """
        # 常见的聚合渠道模型名称格式：
        # - openai/gpt-4
        # - anthropic/claude-3-sonnet
        # - google/gemini-pro

        if "/" in model_name:
            parts = model_name.split("/", 1)
            if len(parts) == 2:
                provider_hint = parts[0].lower()
                original_model = parts[1]

                # 映射提供商提示到标准名称（从配置文件加载）
                provider_map = get_mapping_loader().get_provider_normalization()

                provider = provider_map.get(provider_hint)
                return provider, original_model

        return None, model_name

    def _get_model_capability_with_mapping(self, model_name: str) -> Tuple[int, Optional[str]]:
        """
        获取模型能力等级（支持聚合渠道映射）

        Returns:
            (能力等级, 映射的原模型名) 元组
        """
        # 1. 先尝试直接匹配
        if model_name in DEFAULT_MODEL_CAPABILITIES:
            return DEFAULT_MODEL_CAPABILITIES[model_name]["capability_level"], None

        # 2. 尝试解析聚合渠道模型名
        provider, original_model = self._parse_aggregator_model_name(model_name)

        if original_model and original_model != model_name:
            # 尝试用原模型名查找
            if original_model in DEFAULT_MODEL_CAPABILITIES:
                logger.info(f"🔄 聚合渠道模型映射: {model_name} -> {original_model}")
                return DEFAULT_MODEL_CAPABILITIES[original_model]["capability_level"], original_model

        # 3. 返回默认值
        return 2, None

    def get_model_capability(self, model_name: str) -> int:
        """
        获取模型的能力等级（支持聚合渠道模型映射）

        Args:
            model_name: 模型名称（可能包含聚合渠道前缀，如 openai/gpt-4）

        Returns:
            能力等级 (1-5)
        """
        # 1. 优先从数据库配置读取
        try:
            llm_configs = unified_config.get_llm_configs()
            for config in llm_configs:
                if config.model_name == model_name:
                    return getattr(config, 'capability_level', 2)
        except Exception as e:
            logger.warning(f"从配置读取模型能力失败: {e}")

        # 2. 从默认映射表读取（支持聚合渠道映射）
        capability, mapped_model = self._get_model_capability_with_mapping(model_name)
        if mapped_model:
            logger.info(f"✅ 使用映射模型 {mapped_model} 的能力等级: {capability}")

        return capability
    
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        获取模型的完整配置信息（支持聚合渠道模型映射）

        Args:
            model_name: 模型名称（可能包含聚合渠道前缀）

        Returns:
            模型配置字典
        """
        # 1. 优先从 MongoDB 数据库配置读取（使用同步客户端）
        try:
            from pymongo import MongoClient
            from app.core.config import settings
            from app.models.config import SystemConfig

            # 使用同步 MongoDB 客户端
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            collection = db.system_configs  # 注意：集合名是复数

            # 查询系统配置（与 config_service 保持一致）
            doc = collection.find_one({"is_active": True}, sort=[("version", -1)])

            logger.info(f"🔍 [MongoDB] 查询结果: doc={'存在' if doc else '不存在'}")
            if doc:
                logger.info(f"🔍 [MongoDB] 文档版本: {doc.get('version')}, is_active: {doc.get('is_active')}")

            if doc and "llm_configs" in doc:
                llm_configs = doc["llm_configs"]
                logger.info(f"🔍 [MongoDB] llm_configs 数量: {len(llm_configs)}")

                for config_dict in llm_configs:
                    if config_dict.get("model_name") == model_name:
                        logger.info(f"🔍 [MongoDB] 找到模型配置: {model_name}")
                        # 🔧 将字符串列表转换为枚举列表
                        features_str = config_dict.get('features', [])
                        features_enum = []
                        for feature_str in features_str:
                            try:
                                # 将字符串转换为 ModelFeature 枚举
                                features_enum.append(ModelFeature(feature_str))
                            except ValueError:
                                logger.warning(f"⚠️ 未知的特性值: {feature_str}")

                        # 🔧 将字符串列表转换为枚举列表
                        roles_str = config_dict.get('suitable_roles', ["both"])
                        roles_enum = []
                        for role_str in roles_str:
                            try:
                                # 将字符串转换为 ModelRole 枚举
                                roles_enum.append(ModelRole(role_str))
                            except ValueError:
                                logger.warning(f"⚠️ 未知的角色值: {role_str}")

                        # 如果没有角色，默认为 both
                        if not roles_enum:
                            roles_enum = [ModelRole.BOTH]

                        logger.info(f"📊 [MongoDB配置] {model_name}: features={features_enum}, roles={roles_enum}")

                        # 关闭连接
                        client.close()

                        return {
                            "model_name": config_dict.get("model_name"),
                            "capability_level": config_dict.get('capability_level', 2),
                            "suitable_roles": roles_enum,
                            "features": features_enum,
                            "recommended_depths": config_dict.get('recommended_depths', ["快速", "基础", "标准"]),
                            "performance_metrics": config_dict.get('performance_metrics', None)
                        }

            # 关闭连接
            client.close()

        except Exception as e:
            logger.warning(f"从 MongoDB 读取模型信息失败: {e}", exc_info=True)

        # 2. 从默认映射表读取（直接匹配）
        if model_name in DEFAULT_MODEL_CAPABILITIES:
            return DEFAULT_MODEL_CAPABILITIES[model_name]

        # 3. 尝试聚合渠道模型映射
        provider, original_model = self._parse_aggregator_model_name(model_name)
        if original_model and original_model != model_name:
            if original_model in DEFAULT_MODEL_CAPABILITIES:
                logger.info(f"🔄 聚合渠道模型映射: {model_name} -> {original_model}")
                config = DEFAULT_MODEL_CAPABILITIES[original_model].copy()
                config["model_name"] = model_name  # 保持原始模型名
                config["_mapped_from"] = original_model  # 记录映射来源
                return config

        # 4. 返回默认配置
        logger.warning(f"未找到模型 {model_name} 的配置，使用默认配置")
        return {
            "model_name": model_name,
            "capability_level": 2,
            "suitable_roles": [ModelRole.BOTH],
            "features": [ModelFeature.TOOL_CALLING],
            "recommended_depths": ["快速", "基础", "标准"],
            "performance_metrics": {"speed": 3, "cost": 3, "quality": 3}
        }
    
    def validate_model_pair(
        self,
        quick_model: str,
        deep_model: str,
        research_depth: str
    ) -> Dict[str, Any]:
        """
        验证模型对是否适合当前分析深度

        Args:
            quick_model: 快速分析模型名称
            deep_model: 深度分析模型名称
            research_depth: 研究深度（快速/基础/标准/深度/全面）

        Returns:
            验证结果字典，包含 valid, warnings, recommendations
        """
        logger.info(f"🔍 开始验证模型对: quick={quick_model}, deep={deep_model}, depth={research_depth}")

        requirements = ANALYSIS_DEPTH_REQUIREMENTS.get(research_depth, ANALYSIS_DEPTH_REQUIREMENTS["标准"])
        logger.info(f"🔍 分析深度要求: {requirements}")

        quick_config = self.get_model_config(quick_model)
        deep_config = self.get_model_config(deep_model)

        logger.info(f"🔍 快速模型配置: {quick_config}")
        logger.info(f"🔍 深度模型配置: {deep_config}")

        result = {
            "valid": True,
            "warnings": [],
            "recommendations": []
        }
        
        # 检查快速模型
        quick_level = quick_config["capability_level"]
        logger.info(f"🔍 检查快速模型能力等级: {quick_level} >= {requirements['quick_model_min']}?")
        if quick_level < requirements["quick_model_min"]:
            warning = f"⚠️ 快速模型 {quick_model} (能力等级{quick_level}) 低于 {research_depth} 分析的建议等级({requirements['quick_model_min']})"
            result["warnings"].append(warning)
            logger.warning(warning)

        # 检查快速模型角色适配
        quick_roles = quick_config.get("suitable_roles", [])
        logger.info(f"🔍 检查快速模型角色: {quick_roles}")
        if ModelRole.QUICK_ANALYSIS not in quick_roles and ModelRole.BOTH not in quick_roles:
            warning = f"💡 模型 {quick_model} 不是为快速分析优化的，可能影响数据收集效率"
            result["warnings"].append(warning)
            logger.warning(warning)

        # 检查快速模型是否支持工具调用
        quick_features = quick_config.get("features", [])
        logger.info(f"🔍 检查快速模型特性: {quick_features}")
        if ModelFeature.TOOL_CALLING not in quick_features:
            result["valid"] = False
            warning = f"❌ 快速模型 {quick_model} 不支持工具调用，无法完成数据收集任务"
            result["warnings"].append(warning)
            logger.error(warning)

        # 检查深度模型
        deep_level = deep_config["capability_level"]
        logger.info(f"🔍 检查深度模型能力等级: {deep_level} >= {requirements['deep_model_min']}?")
        if deep_level < requirements["deep_model_min"]:
            result["valid"] = False
            warning = f"❌ 深度模型 {deep_model} (能力等级{deep_level}) 不满足 {research_depth} 分析的最低要求(等级{requirements['deep_model_min']})"
            result["warnings"].append(warning)
            logger.error(warning)
            result["recommendations"].append(
                self._recommend_model("deep", requirements["deep_model_min"])
            )

        # 检查深度模型角色适配
        deep_roles = deep_config.get("suitable_roles", [])
        logger.info(f"🔍 检查深度模型角色: {deep_roles}")
        if ModelRole.DEEP_ANALYSIS not in deep_roles and ModelRole.BOTH not in deep_roles:
            warning = f"💡 模型 {deep_model} 不是为深度推理优化的，可能影响分析质量"
            result["warnings"].append(warning)
            logger.warning(warning)

        # 检查必需特性
        logger.info(f"🔍 检查必需特性: {requirements['required_features']}")
        for feature in requirements["required_features"]:
            if feature == ModelFeature.REASONING:
                deep_features = deep_config.get("features", [])
                logger.info(f"🔍 检查深度模型推理能力: {deep_features}")
                if feature not in deep_features:
                    warning = f"💡 {research_depth} 分析建议使用具有强推理能力的深度模型"
                    result["warnings"].append(warning)
                    logger.warning(warning)

        logger.info(f"🔍 验证结果: valid={result['valid']}, warnings={len(result['warnings'])}条")
        logger.info(f"🔍 警告详情: {result['warnings']}")

        return result
    
    def recommend_models_for_depth(
        self,
        research_depth: str
    ) -> Tuple[str, str]:
        """
        根据分析深度推荐合适的模型对
        
        Args:
            research_depth: 研究深度（快速/基础/标准/深度/全面）
            
        Returns:
            (quick_model, deep_model) 元组
        """
        requirements = ANALYSIS_DEPTH_REQUIREMENTS.get(research_depth, ANALYSIS_DEPTH_REQUIREMENTS["标准"])
        
        # 获取所有启用的模型
        try:
            llm_configs = unified_config.get_llm_configs()
            enabled_models = [c for c in llm_configs if c.enabled]
        except Exception as e:
            logger.error(f"获取模型配置失败: {e}")
            # 使用默认模型
            return self._get_default_models()
        
        if not enabled_models:
            logger.warning("没有启用的模型，使用默认配置")
            return self._get_default_models()
        
        # 筛选适合快速分析的模型
        quick_candidates = []
        for m in enabled_models:
            roles = getattr(m, 'suitable_roles', [ModelRole.BOTH])
            level = getattr(m, 'capability_level', 2)
            features = getattr(m, 'features', [])
            
            if (ModelRole.QUICK_ANALYSIS in roles or ModelRole.BOTH in roles) and \
               level >= requirements["quick_model_min"] and \
               ModelFeature.TOOL_CALLING in features:
                quick_candidates.append(m)
        
        # 筛选适合深度分析的模型
        deep_candidates = []
        for m in enabled_models:
            roles = getattr(m, 'suitable_roles', [ModelRole.BOTH])
            level = getattr(m, 'capability_level', 2)
            
            if (ModelRole.DEEP_ANALYSIS in roles or ModelRole.BOTH in roles) and \
               level >= requirements["deep_model_min"]:
                deep_candidates.append(m)
        
        # 按性价比排序（能力等级 vs 成本）
        quick_candidates.sort(
            key=lambda x: (
                getattr(x, 'capability_level', 2),
                -getattr(x, 'performance_metrics', {}).get("cost", 3) if getattr(x, 'performance_metrics', None) else 0
            ),
            reverse=True
        )
        
        deep_candidates.sort(
            key=lambda x: (
                getattr(x, 'capability_level', 2),
                getattr(x, 'performance_metrics', {}).get("quality", 3) if getattr(x, 'performance_metrics', None) else 0
            ),
            reverse=True
        )
        
        # 选择最佳模型
        quick_model = quick_candidates[0].model_name if quick_candidates else None
        deep_model = deep_candidates[0].model_name if deep_candidates else None
        
        # 如果没找到合适的，使用系统默认
        if not quick_model or not deep_model:
            return self._get_default_models()
        
        logger.info(
            f"🤖 为 {research_depth} 分析推荐模型: "
            f"quick={quick_model} (角色:快速分析), "
            f"deep={deep_model} (角色:深度推理)"
        )
        
        return quick_model, deep_model
    
    def _get_default_models(self) -> Tuple[str, str]:
        """获取默认模型对"""
        try:
            quick_model = unified_config.get_quick_analysis_model()
            deep_model = unified_config.get_deep_analysis_model()
            logger.info(f"使用系统默认模型: quick={quick_model}, deep={deep_model}")
            return quick_model, deep_model
        except Exception as e:
            logger.error(f"获取默认模型失败: {e}")
            return "qwen-turbo", "qwen-plus"
    
    def _recommend_model(self, model_type: str, min_level: int) -> str:
        """推荐满足要求的模型"""
        try:
            llm_configs = unified_config.get_llm_configs()
            for config in llm_configs:
                if config.enabled and getattr(config, 'capability_level', 2) >= min_level:
                    display_name = config.model_display_name or config.model_name
                    return f"建议使用: {display_name}"
        except Exception as e:
            logger.warning(f"推荐模型失败: {e}")

        return "建议升级模型配置"

    def save_model_capability(
        self,
        model_name: str,
        capability_level: int,
        suitable_roles: List[str],
        features: List[str],
        recommended_depths: List[str],
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存模型能力配置到数据库

        Args:
            model_name: 模型名称
            capability_level: 能力等级 (1-5)
            suitable_roles: 适用角色列表
            features: 特性列表
            recommended_depths: 推荐分析深度列表
            performance_metrics: 性能指标

        Returns:
            是否保存成功
        """
        try:
            from pymongo import MongoClient
            from app.core.config import settings

            # 使用同步 MongoDB 客户端
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            collection = db.system_configs

            # 获取当前激活的配置
            doc = collection.find_one({"is_active": True}, sort=[("version", -1)])

            if not doc:
                logger.warning("没有找到激活的系统配置，无法保存模型能力")
                client.close()
                return False

            # 更新 llm_configs 中对应模型的能力配置
            llm_configs = doc.get("llm_configs", [])
            updated = False

            for i, config in enumerate(llm_configs):
                if config.get("model_name") == model_name:
                    # 更新现有配置的能力字段
                    llm_configs[i]["capability_level"] = capability_level
                    llm_configs[i]["suitable_roles"] = suitable_roles
                    llm_configs[i]["features"] = features
                    llm_configs[i]["recommended_depths"] = recommended_depths
                    if performance_metrics is not None:
                        llm_configs[i]["performance_metrics"] = performance_metrics
                    updated = True
                    logger.info(f"✅ 更新模型 {model_name} 的能力配置")
                    break

            if not updated:
                # 如果模型不存在，添加新的模型能力配置
                new_config = {
                    "model_name": model_name,
                    "capability_level": capability_level,
                    "suitable_roles": suitable_roles,
                    "features": features,
                    "recommended_depths": recommended_depths,
                    "performance_metrics": performance_metrics,
                    "enabled": True
                }
                llm_configs.append(new_config)
                logger.info(f"✅ 添加模型 {model_name} 的能力配置")

            # 更新数据库
            result = collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"llm_configs": llm_configs}}
            )

            client.close()

            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"✅ 模型能力配置保存成功: {model_name}")
                return True
            else:
                logger.warning(f"⚠️ 模型能力配置保存失败: {model_name}")
                return False

        except Exception as e:
            logger.error(f"❌ 保存模型能力配置失败: {e}", exc_info=True)
            return False

    def save_model_capabilities_batch(
        self,
        capabilities: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        批量保存模型能力配置

        Args:
            capabilities: 模型能力配置列表，每个元素包含 model_name, capability_level, suitable_roles, features, recommended_depths, performance_metrics

        Returns:
            保存结果统计 {"updated": int, "added": int, "failed": int}
        """
        try:
            from pymongo import MongoClient
            from app.core.config import settings

            # 使用同步 MongoDB 客户端
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            collection = db.system_configs

            # 获取当前激活的配置
            doc = collection.find_one({"is_active": True}, sort=[("version", -1)])

            if not doc:
                logger.warning("没有找到激活的系统配置，无法保存模型能力")
                client.close()
                return {"updated": 0, "added": 0, "failed": len(capabilities)}

            # 获取现有的 llm_configs
            llm_configs = doc.get("llm_configs", [])
            result_stats = {"updated": 0, "added": 0, "failed": 0}

            for cap in capabilities:
                model_name = cap.get("model_name")
                if not model_name:
                    result_stats["failed"] += 1
                    continue

                # 查找现有配置
                found = False
                for i, config in enumerate(llm_configs):
                    if config.get("model_name") == model_name:
                        # 更新现有配置
                        llm_configs[i]["capability_level"] = cap.get("capability_level", 2)
                        llm_configs[i]["suitable_roles"] = cap.get("suitable_roles", ["both"])
                        llm_configs[i]["features"] = cap.get("features", [])
                        llm_configs[i]["recommended_depths"] = cap.get("recommended_depths", ["快速", "基础", "标准"])
                        if "performance_metrics" in cap:
                            llm_configs[i]["performance_metrics"] = cap["performance_metrics"]
                        result_stats["updated"] += 1
                        found = True
                        break

                if not found:
                    # 添加新配置
                    new_config = {
                        "model_name": model_name,
                        "capability_level": cap.get("capability_level", 2),
                        "suitable_roles": cap.get("suitable_roles", ["both"]),
                        "features": cap.get("features", []),
                        "recommended_depths": cap.get("recommended_depths", ["快速", "基础", "标准"]),
                        "performance_metrics": cap.get("performance_metrics"),
                        "enabled": True
                    }
                    llm_configs.append(new_config)
                    result_stats["added"] += 1

            # 更新数据库
            update_result = collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"llm_configs": llm_configs}}
            )

            client.close()

            if update_result.modified_count > 0 or update_result.matched_count > 0:
                logger.info(f"✅ 批量保存模型能力配置成功: {result_stats}")
            else:
                logger.warning(f"⚠️ 批量保存模型能力配置失败")
                result_stats["failed"] = len(capabilities)

            return result_stats

        except Exception as e:
            logger.error(f"❌ 批量保存模型能力配置失败: {e}", exc_info=True)
            return {"updated": 0, "added": 0, "failed": len(capabilities)}


# 单例
_model_capability_service = None


def get_model_capability_service() -> ModelCapabilityService:
    """获取模型能力服务单例"""
    global _model_capability_service
    if _model_capability_service is None:
        _model_capability_service = ModelCapabilityService()
    return _model_capability_service

