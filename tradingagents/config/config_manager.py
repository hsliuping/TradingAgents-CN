#!/usr/bin/env python3
"""
配置管理器
管理API密钥、模型配置、费率设置等

⚠️ DEPRECATED: 此模块已废弃，将在 2026-03-31 后移除
   请使用新的配置系统: app.services.config_service.ConfigService
   迁移指南: docs/DEPRECATION_NOTICE.md
   迁移脚本: scripts/migrate_config_to_db.py
"""

import json
import os
import re
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv

# 发出废弃警告
warnings.warn(
    "ConfigManager is deprecated and will be removed in version 2.0 (2026-03-31). "
    "Please use app.services.config_service.ConfigService instead. "
    "See docs/DEPRECATION_NOTICE.md for migration guide.",
    DeprecationWarning,
    stacklevel=2
)

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
# 运行时设置：读取系统时区
from tradingagents.config.runtime_settings import get_timezone_name
logger = get_logger('agents')

# 导入数据模型（避免循环导入）
from .usage_models import UsageRecord, ModelConfig, PricingConfig

try:
    from .mongodb_storage import MongoDBStorage
    MONGODB_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ [ConfigManager] 导入 MongoDBStorage 失败 (ImportError): {e}")
    import traceback
    logger.error(f"   堆栈: {traceback.format_exc()}")
    MONGODB_AVAILABLE = False
    MongoDBStorage = None
except Exception as e:
    logger.error(f"❌ [ConfigManager] 导入 MongoDBStorage 失败 (Exception): {e}")
    import traceback
    logger.error(f"   堆栈: {traceback.format_exc()}")
    MONGODB_AVAILABLE = False
    MongoDBStorage = None


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

        self.models_file = self.config_dir / "models.json"
        self.pricing_file = self.config_dir / "pricing.json"
        self.usage_file = self.config_dir / "usage.json"
        self.settings_file = self.config_dir / "settings.json"

        # 加载.env文件（保持向后兼容）
        self._load_env_file()

        # 初始化MongoDB存储（如果可用）
        self.mongodb_storage = None
        self._init_mongodb_storage()

        self._init_default_configs()

    def _load_env_file(self):
        """加载.env文件（保持向后兼容）"""
        # 尝试从项目根目录加载.env文件
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / ".env"

        if env_file.exists():
            # 🔧 [修复] override=False 确保环境变量优先级高于 .env 文件
            # 这样 Docker 容器中的环境变量不会被 .env 文件中的占位符覆盖
            logger.info(f"🔍 [ConfigManager] 加载 .env 文件: {env_file}")
            logger.info(f"🔍 [ConfigManager] 加载前 DASHSCOPE_API_KEY: {'有值' if os.getenv('DASHSCOPE_API_KEY') else '空'}")

            load_dotenv(env_file, override=False)

            logger.info(f"🔍 [ConfigManager] 加载后 DASHSCOPE_API_KEY: {'有值' if os.getenv('DASHSCOPE_API_KEY') else '空'}")

    def _get_env_api_key(self, provider: str) -> str:
        """从环境变量获取API密钥"""
        env_key_map = {
            "dashscope": "DASHSCOPE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY"
        }

        env_key = env_key_map.get(provider.lower())
        if env_key:
            api_key = os.getenv(env_key, "")
            # 对OpenAI密钥进行格式验证（始终启用）
            if provider.lower() == "openai" and api_key:
                if not self.validate_openai_api_key_format(api_key):
                    logger.warning(f"⚠️ OpenAI API密钥格式不正确，将被忽略: {api_key[:10]}...")
                    return ""
            return api_key
        return ""
    
    def validate_openai_api_key_format(self, api_key: str) -> bool:
        """
        验证OpenAI API密钥格式
        
        OpenAI API密钥格式规则：
        1. 以 'sk-' 开头
        2. 总长度通常为51个字符
        3. 包含字母、数字和可能的特殊字符
        
        Args:
            api_key: 要验证的API密钥
            
        Returns:
            bool: 格式是否正确
        """
        if not api_key or not isinstance(api_key, str):
            return False
        
        # 检查是否以 'sk-' 开头
        if not api_key.startswith('sk-'):
            return False
        
        # 检查长度（OpenAI密钥通常为51个字符）
        if len(api_key) != 51:
            return False
        
        # 检查格式：sk- 后面应该是48个字符的字母数字组合
        pattern = r'^sk-[A-Za-z0-9]{48}$'
        if not re.match(pattern, api_key):
            return False
        
        return True
    
    def _init_mongodb_storage(self):
        """初始化MongoDB存储"""
        logger.info("🔧 [ConfigManager] 开始初始化 MongoDB 存储...")

        if not MONGODB_AVAILABLE:
            logger.warning("⚠️ [ConfigManager] pymongo 未安装，无法使用 MongoDB 存储")
            return

        # 检查是否启用MongoDB存储
        use_mongodb_env = os.getenv("USE_MONGODB_STORAGE", "false")
        use_mongodb = use_mongodb_env.lower() == "true"

        logger.info(f"🔍 [ConfigManager] USE_MONGODB_STORAGE={use_mongodb_env} (解析为: {use_mongodb})")

        if not use_mongodb:
            logger.info("ℹ️ [ConfigManager] MongoDB 存储未启用，将使用 JSON 文件存储")
            return

        try:
            connection_string = os.getenv("MONGODB_CONNECTION_STRING")
            database_name = os.getenv("MONGODB_DATABASE_NAME", "tradingagents")

            logger.info(f"🔍 [ConfigManager] MONGODB_CONNECTION_STRING={'已设置' if connection_string else '未设置'}")
            logger.info(f"🔍 [ConfigManager] MONGODB_DATABASE_NAME={database_name}")

            if not connection_string:
                logger.error("❌ [ConfigManager] MONGODB_CONNECTION_STRING 未设置，无法初始化 MongoDB 存储")
                return

            logger.info(f"🔄 [ConfigManager] 正在创建 MongoDBStorage 实例...")
            self.mongodb_storage = MongoDBStorage(
                connection_string=connection_string,
                database_name=database_name
            )

            if self.mongodb_storage.is_connected():
                logger.info(f"✅ [ConfigManager] MongoDB存储已启用: {database_name}.token_usage")
            else:
                self.mongodb_storage = None
                logger.warning("⚠️ [ConfigManager] MongoDB连接失败，将使用JSON文件存储")

        except Exception as e:
            logger.error(f"❌ [ConfigManager] MongoDB初始化失败: {e}", exc_info=True)
            self.mongodb_storage = None

    def _init_default_configs(self):
        """初始化默认配置"""
        # 默认模型配置
        if not self.models_file.exists():
            default_models = [
                ModelConfig(
                    provider="dashscope",
                    model_name="qwen-turbo",
                    api_key="",
                    max_tokens=4000,
                    temperature=0.7
                ),
                ModelConfig(
                    provider="dashscope",
                    model_name="qwen-plus-latest",
                    api_key="",
                    max_tokens=8000,
                    temperature=0.7
                ),
                ModelConfig(
                    provider="openai",
                    model_name="gpt-3.5-turbo",
                    api_key="",
                    max_tokens=4000,
                    temperature=0.7,
                    enabled=False
                ),
                ModelConfig(
                    provider="openai",
                    model_name="gpt-4",
                    api_key="",
                    max_tokens=8000,
                    temperature=0.7,
                    enabled=False
                ),
                ModelConfig(
                    provider="google",
                    model_name="gemini-2.5-pro",
                    api_key="",
                    max_tokens=4000,
                    temperature=0.7,
                    enabled=False
                ),
                ModelConfig(
                    provider="deepseek",
                    model_name="deepseek-chat",
                    api_key="",
                    max_tokens=8000,
                    temperature=0.7,
                    enabled=False
                )
            ]
            self.save_models(default_models)
        
        # 默认定价配置
        if not self.pricing_file.exists():
            default_pricing = [
                # 阿里百炼定价 (人民币)
                PricingConfig("dashscope", "qwen-turbo", 0.002, 0.006, "CNY"),
                PricingConfig("dashscope", "qwen-plus-latest", 0.004, 0.012, "CNY"),
                PricingConfig("dashscope", "qwen-max", 0.02, 0.06, "CNY"),

                # DeepSeek定价 (人民币) - 2025年最新价格
                PricingConfig("deepseek", "deepseek-chat", 0.0014, 0.0028, "CNY"),
                PricingConfig("deepseek", "deepseek-coder", 0.0014, 0.0028, "CNY"),

                # OpenAI定价 (美元)
                PricingConfig("openai", "gpt-3.5-turbo", 0.0015, 0.002, "USD"),
                PricingConfig("openai", "gpt-4", 0.03, 0.06, "USD"),
                PricingConfig("openai", "gpt-4-turbo", 0.01, 0.03, "USD"),

                # Google定价 (美元)
                PricingConfig("google", "gemini-2.5-pro", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-2.5-flash", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-2.0-flash", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-1.5-pro", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-1.5-flash", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-2.5-flash-lite-preview-06-17", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-pro", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-pro-vision", 0.00025, 0.0005, "USD"),
            ]
            self.save_pricing(default_pricing)
        
        # 默认设置
        if not self.settings_file.exists():
            # 导入默认数据目录配置
            import os
            default_data_dir = os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data")
            
            default_settings = {
                "default_provider": "dashscope",
                "default_model": "qwen-turbo",
                "enable_cost_tracking": True,
                "cost_alert_threshold": 100.0,  # 成本警告阈值
                "currency_preference": "CNY",
                "auto_save_usage": True,
                "max_usage_records": 10000,
                "data_dir": default_data_dir,  # 数据目录配置
                "cache_dir": os.path.join(default_data_dir, "cache"),  # 缓存目录
                "results_dir": os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "results"),  # 结果目录
                "auto_create_dirs": True,  # 自动创建目录
                "openai_enabled": False,  # OpenAI模型是否启用
            }
            self.save_settings(default_settings)
    
    def load_models(self) -> List[ModelConfig]:
        """加载模型配置，优先使用.env中的API密钥"""
        try:
            with open(self.models_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                models = [ModelConfig(**item) for item in data]

                # 获取设置
                settings = self.load_settings()
                openai_enabled = settings.get("openai_enabled", False)

                # 合并.env中的API密钥（优先级更高）
                for model in models:
                    env_api_key = self._get_env_api_key(model.provider)
                    if env_api_key:
                        model.api_key = env_api_key
                        # 如果.env中有API密钥，自动启用该模型
                        if not model.enabled:
                            model.enabled = True
                    
                    # 特殊处理OpenAI模型
                    if model.provider.lower() == "openai":
                        # 检查OpenAI是否在配置中启用
                        if not openai_enabled:
                            model.enabled = False
                            logger.info(f"🔒 OpenAI模型已禁用: {model.model_name}")
                        # 如果有API密钥但格式不正确，禁用模型（验证始终启用）
                        elif model.api_key and not self.validate_openai_api_key_format(model.api_key):
                            model.enabled = False
                            logger.warning(f"⚠️ OpenAI模型因密钥格式不正确而禁用: {model.model_name}")

                return models
        except Exception as e:
            logger.error(f"加载模型配置失败: {e}")
            return []
    
    def save_models(self, models: List[ModelConfig]):
        """保存模型配置"""
        try:
            data = [asdict(model) for model in models]
            with open(self.models_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存模型配置失败: {e}")
    
    def load_pricing(self) -> List[PricingConfig]:
        """加载定价配置"""
        try:
            with open(self.pricing_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [PricingConfig(**item) for item in data]
        except Exception as e:
            logger.error(f"加载定价配置失败: {e}")
            return []
    
    def save_pricing(self, pricing: List[PricingConfig]):
        """保存定价配置"""
        try:
            data = [asdict(price) for price in pricing]
            with open(self.pricing_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存定价配置失败: {e}")
    
    def load_usage_records(self) -> List[UsageRecord]:
        """加载使用记录"""
        try:
            if not self.usage_file.exists():
                return []
            with open(self.usage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [UsageRecord(**item) for item in data]
        except Exception as e:
            logger.error(f"加载使用记录失败: {e}")
            return []
    
    def save_usage_records(self, records: List[UsageRecord]):
        """保存使用记录"""
        try:
            data = [asdict(record) for record in records]
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存使用记录失败: {e}")
    
    def add_usage_record(self, provider: str, model_name: str, input_tokens: int,
                        output_tokens: int, session_id: str, analysis_type: str = "stock_analysis"):
        """添加使用记录"""
        # 计算成本和货币单位
        cost, currency = self.calculate_cost(provider, model_name, input_tokens, output_tokens)

        record = UsageRecord(
            timestamp=datetime.now(ZoneInfo(get_timezone_name())).isoformat(),
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            currency=currency,
            session_id=session_id,
            analysis_type=analysis_type
        )

        # 🔍 详细日志：记录保存位置
        logger.info(f"💾 [Token记录] 准备保存: {provider}/{model_name}, 输入={input_tokens}, 输出={output_tokens}, 成本=¥{cost:.4f}, session={session_id}")

        # 优先使用MongoDB存储
        if self.mongodb_storage and self.mongodb_storage.is_connected():
            logger.info(f"📊 [Token记录] 使用 MongoDB 存储 (数据库: {self.mongodb_storage.database_name}, 集合: {self.mongodb_storage.collection_name})")
            success = self.mongodb_storage.save_usage_record(record)
            if success:
                logger.info(f"✅ [Token记录] MongoDB 保存成功: {provider}/{model_name}")
                return record
            else:
                logger.error(f"⚠️ [Token记录] MongoDB保存失败，回退到JSON文件存储")
        else:
            # 🔍 详细日志：为什么没有使用MongoDB
            if self.mongodb_storage is None:
                logger.warning(f"⚠️ [Token记录] MongoDB存储未初始化 (mongodb_storage=None)")
                logger.warning(f"   💡 请检查环境变量: USE_MONGODB_STORAGE={os.getenv('USE_MONGODB_STORAGE', '未设置')}")
            elif not self.mongodb_storage.is_connected():
                logger.warning(f"⚠️ [Token记录] MongoDB未连接 (is_connected=False)")

            logger.info(f"📄 [Token记录] 使用 JSON 文件存储: {self.usage_file}")

        # 回退到JSON文件存储
        records = self.load_usage_records()
        records.append(record)

        # 限制记录数量
        settings = self.load_settings()
        max_records = settings.get("max_usage_records", 10000)
        if len(records) > max_records:
            records = records[-max_records:]

        self.save_usage_records(records)
        logger.info(f"✅ [Token记录] JSON 文件保存成功: {self.usage_file}")
        return record
    
    def calculate_cost(self, provider: str, model_name: str, input_tokens: int, output_tokens: int) -> tuple[float, str]:
        """
        计算使用成本

        Returns:
            tuple[float, str]: (成本, 货币单位)
        """
        pricing_configs = self.load_pricing()

        for pricing in pricing_configs:
            if pricing.provider == provider and pricing.model_name == model_name:
                input_cost = (input_tokens / 1000) * pricing.input_price_per_1k
                output_cost = (output_tokens / 1000) * pricing.output_price_per_1k
                total_cost = input_cost + output_cost
                return round(total_cost, 6), pricing.currency

        # 只在找不到配置时输出调试信息
        logger.warning(f"⚠️ [calculate_cost] 未找到匹配的定价配置: {provider}/{model_name}")
        logger.debug(f"⚠️ [calculate_cost] 可用的配置:")
        for pricing in pricing_configs:
            logger.debug(f"⚠️ [calculate_cost]   - {pricing.provider}/{pricing.model_name}")

        return 0.0, "CNY"
    
    def load_settings(self) -> Dict[str, Any]:
        """加载设置，合并.env中的配置"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                # 如果设置文件不存在，创建默认设置
                settings = {
                    "default_provider": "dashscope",
                    "default_model": "qwen-turbo",
                    "enable_cost_tracking": True,
                    "cost_alert_threshold": 100.0,
                    "currency_preference": "CNY",
                    "auto_save_usage": True,
                    "max_usage_records": 10000,
                    "data_dir": os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data"),
                    "cache_dir": os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data", "cache"),
                    "results_dir": os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "results"),
                    "auto_create_dirs": True,
                    "openai_enabled": False,
                }
                self.save_settings(settings)
        except Exception as e:
            logger.error(f"加载设置失败: {e}")
            settings = {}

        # 合并.env中的其他配置
        env_settings = {
            "finnhub_api_key": os.getenv("FINNHUB_API_KEY", ""),
            "reddit_client_id": os.getenv("REDDIT_CLIENT_ID", ""),
            "reddit_client_secret": os.getenv("REDDIT_CLIENT_SECRET", ""),
            "reddit_user_agent": os.getenv("REDDIT_USER_AGENT", ""),
            "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", ""),
            "log_level": os.getenv("TRADINGAGENTS_LOG_LEVEL", "INFO"),
            "data_dir": os.getenv("TRADINGAGENTS_DATA_DIR", ""),  # 数据目录环境变量
            "cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", ""),  # 缓存目录环境变量
        }

        # 添加OpenAI相关配置
        openai_enabled_env = os.getenv("OPENAI_ENABLED", "").lower()
        if openai_enabled_env in ["true", "false"]:
            env_settings["openai_enabled"] = openai_enabled_env == "true"

        # 只有当环境变量存在且不为空时才覆盖
        for key, value in env_settings.items():
            # 对于布尔值，直接使用
            if isinstance(value, bool):
                settings[key] = value
            # 对于字符串，只有非空时才覆盖
            elif value != "" and value is not None:
                settings[key] = value

        return settings

    def get_env_config_status(self) -> Dict[str, Any]:
        """获取.env配置状态"""
        return {
            "env_file_exists": (Path(__file__).parent.parent.parent / ".env").exists(),
            "api_keys": {
                "dashscope": bool(os.getenv("DASHSCOPE_API_KEY")),
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "google": bool(os.getenv("GOOGLE_API_KEY")),
                "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
                "finnhub": bool(os.getenv("FINNHUB_API_KEY")),
            },
            "other_configs": {
                "reddit_configured": bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")),
                "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
                "log_level": os.getenv("TRADINGAGENTS_LOG_LEVEL", "INFO"),
            }
        }

    def save_settings(self, settings: Dict[str, Any]):
        """保存设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
    
    def get_enabled_models(self) -> List[ModelConfig]:
        """获取启用的模型"""
        models = self.load_models()
        return [model for model in models if model.enabled and model.api_key]
    
    def get_model_by_name(self, provider: str, model_name: str) -> Optional[ModelConfig]:
        """根据名称获取模型配置"""
        models = self.load_models()
        for model in models:
            if model.provider == provider and model.model_name == model_name:
                return model
        return None
    
    def get_usage_statistics(self, days: int = 30) -> Dict[str, Any]:
        """获取使用统计"""
        # 优先使用MongoDB获取统计
        if self.mongodb_storage and self.mongodb_storage.is_connected():
            try:
                # 从MongoDB获取基础统计
                stats = self.mongodb_storage.get_usage_statistics(days)
                # 获取供应商统计
                provider_stats = self.mongodb_storage.get_provider_statistics(days)
                
                if stats:
                    stats["provider_stats"] = provider_stats
                    stats["records_count"] = stats.get("total_requests", 0)
                    return stats
            except Exception as e:
                logger.error(f"⚠️ MongoDB统计获取失败，回退到JSON文件: {e}")
        
        # 回退到JSON文件统计
        records = self.load_usage_records()
        
        # 过滤最近N天的记录
        from datetime import datetime, timedelta

        local_tz = ZoneInfo(get_timezone_name())
        cutoff_date = datetime.now(local_tz) - timedelta(days=days)
        
        recent_records = []
        for record in records:
            try:
                record_date = datetime.fromisoformat(record.timestamp)
                if record_date.tzinfo is None:
                    record_date = record_date.replace(tzinfo=local_tz)
                if record_date >= cutoff_date:
                    recent_records.append(record)
            except:
                continue
        
        # 统计数据
        total_cost = sum(record.cost for record in recent_records)
        total_input_tokens = sum(record.input_tokens for record in recent_records)
        total_output_tokens = sum(record.output_tokens for record in recent_records)
        
        # 按供应商统计
        provider_stats = {}
        for record in recent_records:
            if record.provider not in provider_stats:
                provider_stats[record.provider] = {
                    "cost": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "requests": 0
                }
            provider_stats[record.provider]["cost"] += record.cost
            provider_stats[record.provider]["input_tokens"] += record.input_tokens
            provider_stats[record.provider]["output_tokens"] += record.output_tokens
            provider_stats[record.provider]["requests"] += 1
        
        return {
            "period_days": days,
            "total_cost": round(total_cost, 4),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_requests": len(recent_records),
            "provider_stats": provider_stats,
            "records_count": len(recent_records)
        }
    
    def get_data_dir(self) -> str:
        """获取数据目录路径"""
        settings = self.load_settings()
        data_dir = settings.get("data_dir")
        if not data_dir:
            # 如果没有配置，使用默认路径
            data_dir = os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data")
        return data_dir

    def set_data_dir(self, data_dir: str):
        """设置数据目录路径"""
        settings = self.load_settings()
        settings["data_dir"] = data_dir
        # 同时更新缓存目录
        settings["cache_dir"] = os.path.join(data_dir, "cache")
        self.save_settings(settings)
        
        # 如果启用自动创建目录，则创建目录
        if settings.get("auto_create_dirs", True):
            self.ensure_directories_exist()

    def ensure_directories_exist(self):
        """确保必要的目录存在"""
        settings = self.load_settings()
        
        directories = [
            settings.get("data_dir"),
            settings.get("cache_dir"),
            settings.get("results_dir"),
            os.path.join(settings.get("data_dir", ""), "finnhub_data"),
            os.path.join(settings.get("data_dir", ""), "finnhub_data", "news_data"),
            os.path.join(settings.get("data_dir", ""), "finnhub_data", "insider_sentiment"),
            os.path.join(settings.get("data_dir", ""), "finnhub_data", "insider_transactions")
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    logger.info(f"✅ 创建目录: {directory}")
                except Exception as e:
                    logger.error(f"❌ 创建目录失败 {directory}: {e}")
    
    def set_openai_enabled(self, enabled: bool):
        """设置OpenAI模型启用状态"""
        settings = self.load_settings()
        settings["openai_enabled"] = enabled
        self.save_settings(settings)
        logger.info(f"🔧 OpenAI模型启用状态已设置为: {enabled}")
    
    def is_openai_enabled(self) -> bool:
        """检查OpenAI模型是否启用"""
        settings = self.load_settings()
        return settings.get("openai_enabled", False)
    
    def get_openai_config_status(self) -> Dict[str, Any]:
        """获取OpenAI配置状态"""
        openai_key = os.getenv("OPENAI_API_KEY", "")
        key_valid = self.validate_openai_api_key_format(openai_key) if openai_key else False
        
        return {
            "api_key_present": bool(openai_key),
            "api_key_valid_format": key_valid,
            "enabled": self.is_openai_enabled(),
            "models_available": self.is_openai_enabled() and key_valid,
            "api_key_preview": f"{openai_key[:10]}..." if openai_key else "未配置"
        }


class TokenTracker:
    """Token使用跟踪器"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def track_usage(self, provider: str, model_name: str, input_tokens: int,
                   output_tokens: int, session_id: str = None, analysis_type: str = "stock_analysis"):
        """跟踪Token使用"""
        if session_id is None:
            session_id = f"session_{datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y%m%d_%H%M%S')}"

        # 检查是否启用成本跟踪
        settings = self.config_manager.load_settings()
        cost_tracking_enabled = settings.get("enable_cost_tracking", True)

        if not cost_tracking_enabled:
            return None

        # 添加使用记录
        record = self.config_manager.add_usage_record(
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            session_id=session_id,
            analysis_type=analysis_type
        )

        # 检查成本警告
        if record:
            self._check_cost_alert(record.cost)

        return record

    def _check_cost_alert(self, current_cost: float):
        """检查成本警告"""
        settings = self.config_manager.load_settings()
        threshold = settings.get("cost_alert_threshold", 100.0)

        # 获取今日总成本
        today_stats = self.config_manager.get_usage_statistics(1)
        total_today = today_stats["total_cost"]

        if total_today >= threshold:
            logger.warning(f"⚠️ 成本警告: 今日成本已达到 ¥{total_today:.4f}，超过阈值 ¥{threshold}",
                          extra={'cost': total_today, 'threshold': threshold, 'event_type': 'cost_alert'})

    def get_session_cost(self, session_id: str) -> float:
        """获取会话成本"""
        records = self.config_manager.load_usage_records()
        session_cost = sum(record.cost for record in records if record.session_id == session_id)
        return session_cost

    def estimate_cost(self, provider: str, model_name: str, estimated_input_tokens: int,
                     estimated_output_tokens: int) -> tuple[float, str]:
        """
        估算成本

        Returns:
            tuple[float, str]: (成本, 货币单位)
        """
        return self.config_manager.calculate_cost(
            provider, model_name, estimated_input_tokens, estimated_output_tokens
        )




# 全局配置管理器实例 - 使用项目根目录的配置
def _get_project_config_dir():
    """获取项目根目录的配置目录"""
    # 从当前文件位置推断项目根目录
    current_file = Path(__file__)  # tradingagents/config/config_manager.py
    project_root = current_file.parent.parent.parent  # 向上三级到项目根目录
    return str(project_root / "config")

config_manager = ConfigManager(_get_project_config_dir())
token_tracker = TokenTracker(config_manager)
