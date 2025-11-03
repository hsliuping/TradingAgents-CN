"""
启动配置验证器

验证系统启动所需的必需配置项，提供友好的错误提示。
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConfigLevel(Enum):
    """配置级别"""
    REQUIRED = "required"      # 必需配置，缺少则无法启动
    RECOMMENDED = "recommended"  # 推荐配置，缺少会影响功能
    OPTIONAL = "optional"      # 可选配置，缺少不影响基本功能


@dataclass
class ConfigItem:
    """配置项"""
    key: str                    # 配置键名
    level: ConfigLevel          # 配置级别
    description: str            # 配置描述
    example: Optional[str] = None  # 配置示例
    help_url: Optional[str] = None  # 帮助链接
    validator: Optional[callable] = None  # 自定义验证函数


@dataclass
class ValidationResult:
    """验证结果"""
    success: bool               # 是否验证成功
    missing_required: List[ConfigItem]  # 缺少的必需配置
    missing_recommended: List[ConfigItem]  # 缺少的推荐配置
    invalid_configs: List[tuple[ConfigItem, str]]  # 无效的配置（配置项，错误信息）
    warnings: List[str]         # 警告信息


class StartupValidator:
    """启动配置验证器"""
    
    # 必需配置项
    REQUIRED_CONFIGS = [
        ConfigItem(
            key="MONGODB_HOST",
            level=ConfigLevel.REQUIRED,
            description="MongoDB主机地址",
            example="localhost"
        ),
        ConfigItem(
            key="MONGODB_PORT",
            level=ConfigLevel.REQUIRED,
            description="MongoDB端口",
            example="27017",
            validator=lambda v: v.isdigit() and 1 <= int(v) <= 65535
        ),
        ConfigItem(
            key="MONGODB_DATABASE",
            level=ConfigLevel.REQUIRED,
            description="MongoDB数据库名称",
            example="tradingagents"
        ),
        ConfigItem(
            key="REDIS_HOST",
            level=ConfigLevel.REQUIRED,
            description="Redis主机地址",
            example="localhost"
        ),
        ConfigItem(
            key="REDIS_PORT",
            level=ConfigLevel.REQUIRED,
            description="Redis端口",
            example="6379",
            validator=lambda v: v.isdigit() and 1 <= int(v) <= 65535
        ),
        ConfigItem(
            key="JWT_SECRET",
            level=ConfigLevel.REQUIRED,
            description="JWT密钥（用于生成认证令牌）",
            example="your-super-secret-jwt-key-change-in-production",
            validator=lambda v: len(v) >= 16
        ),
    ]
    
    # 推荐配置项
    RECOMMENDED_CONFIGS = [
        ConfigItem(
            key="DEEPSEEK_API_KEY",
            level=ConfigLevel.RECOMMENDED,
            description="DeepSeek API密钥（推荐，性价比高）",
            example="sk-xxx",
            help_url="https://platform.deepseek.com/"
        ),
        ConfigItem(
            key="DASHSCOPE_API_KEY",
            level=ConfigLevel.RECOMMENDED,
            description="阿里百炼API密钥（推荐，国产稳定）",
            example="sk-xxx",
            help_url="https://dashscope.aliyun.com/"
        ),
        ConfigItem(
            key="TUSHARE_TOKEN",
            level=ConfigLevel.RECOMMENDED,
            description="Tushare Token（推荐，专业A股数据）",
            example="xxx",
            help_url="https://tushare.pro/register?reg=tacn"
        ),
    ]
    
    def __init__(self):
        self.result = ValidationResult(
            success=True,
            missing_required=[],
            missing_recommended=[],
            invalid_configs=[],
            warnings=[]
        )

    def _is_valid_api_key(self, api_key: str) -> bool:
        """
        判断 API Key 是否有效（不是占位符）

        Args:
            api_key: 待验证的 API Key

        Returns:
            bool: True 表示有效，False 表示无效或占位符
        """
        if not api_key:
            return False

        # 去除首尾空格和引号
        api_key = api_key.strip().strip('"').strip("'")

        # 检查是否为空
        if not api_key:
            return False

        # 检查是否为占位符（前缀）
        if api_key.startswith('your_') or api_key.startswith('your-'):
            return False

        # 检查是否为占位符（后缀）
        if api_key.endswith('_here') or api_key.endswith('-here'):
            return False

        # 检查长度（大多数 API Key 都 > 10 个字符）
        if len(api_key) <= 10:
            return False

        return True

    def validate(self) -> ValidationResult:
        """
        验证配置
        
        Returns:
            ValidationResult: 验证结果
        """
        logger.info("🔍 开始验证启动配置...")
        
        # 验证必需配置
        self._validate_required_configs()
        
        # 验证推荐配置
        self._validate_recommended_configs()
        
        # 检查安全配置
        self._check_security_configs()
        
        # 设置验证结果
        self.result.success = len(self.result.missing_required) == 0 and len(self.result.invalid_configs) == 0
        
        # 输出验证结果
        self._print_validation_result()
        
        return self.result
    
    def _validate_required_configs(self):
        """验证必需配置"""
        for config in self.REQUIRED_CONFIGS:
            value = os.getenv(config.key)
            
            if not value:
                self.result.missing_required.append(config)
                logger.error(f"❌ 缺少必需配置: {config.key}")
            elif config.validator and not config.validator(value):
                self.result.invalid_configs.append((config, "配置值格式不正确"))
                logger.error(f"❌ 配置格式错误: {config.key}")
            else:
                logger.debug(f"✅ {config.key}: 已配置")
    
    def _validate_recommended_configs(self):
        """验证推荐配置"""
        for config in self.RECOMMENDED_CONFIGS:
            value = os.getenv(config.key)

            if not value:
                self.result.missing_recommended.append(config)
                logger.warning(f"⚠️  缺少推荐配置: {config.key}")
            elif not self._is_valid_api_key(value):
                # API Key 存在但是占位符，视为未配置
                self.result.missing_recommended.append(config)
                logger.warning(f"⚠️  {config.key} 配置为占位符，视为未配置")
            else:
                logger.debug(f"✅ {config.key}: 已配置")
    
    def _check_security_configs(self):
        """检查安全配置"""
        # 检查JWT密钥是否使用默认值
        jwt_secret = os.getenv("JWT_SECRET", "")
        if jwt_secret in ["change-me-in-production", "your-super-secret-jwt-key-change-in-production"]:
            self.result.warnings.append(
                "⚠️  JWT_SECRET 使用默认值，生产环境请务必修改！"
            )
        
        # 检查CSRF密钥是否使用默认值
        csrf_secret = os.getenv("CSRF_SECRET", "")
        if csrf_secret in ["change-me-csrf-secret", "your-csrf-secret-key-change-in-production"]:
            self.result.warnings.append(
                "⚠️  CSRF_SECRET 使用默认值，生产环境请务必修改！"
            )
        
        # 检查是否在生产环境使用DEBUG模式
        debug = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes", "on")
        if not debug:
            logger.info("ℹ️  生产环境模式")
        else:
            logger.info("ℹ️  开发环境模式（DEBUG=true）")
    
    def _print_validation_result(self):
        """输出验证结果"""
        logger.info("\n" + "=" * 70)
        logger.info("TradingAgents-CN Configuration Validation Result")
        logger.info("=" * 70)
        
        # 必需配置
        if self.result.missing_required:
            logger.info("\nMissing required configurations:")
            for config in self.result.missing_required:
                logger.info(f"   - {config.key}")
                logger.info(f"     Description: {config.description}")
                if config.example:
                    logger.info(f"     Example: {config.example}")
                if config.help_url:
                    logger.info(f"     Help: {config.help_url}")
        else:
            logger.info("\nAll required configurations are complete")

        # 无效配置
        if self.result.invalid_configs:
            logger.info("\nInvalid configurations:")
            for config, error in self.result.invalid_configs:
                logger.info(f"   - {config.key}: {error}")
                if config.example:
                    logger.info(f"     Example: {config.example}")

        # 推荐配置
        if self.result.missing_recommended:
            logger.info("\nMissing recommended configurations (won't affect startup):")
            for config in self.result.missing_recommended:
                logger.info(f"   - {config.key}")
                logger.info(f"     Description: {config.description}")
                if config.help_url:
                    logger.info(f"     Get it from: {config.help_url}")

        # 警告信息
        if self.result.warnings:
            logger.info("\nSecurity warnings:")
            for warning in self.result.warnings:
                logger.info(f"   - {warning}")

        # 总结
        logger.info("\n" + "=" * 70)
        if self.result.success:
            logger.info("Configuration validation passed, system can start")
            if self.result.missing_recommended:
                logger.info("Tip: Configure recommended items for better functionality")
        else:
            logger.info("Configuration validation failed, please check the above items")
            logger.info("Configuration guide: docs/configuration_guide.md")
        logger.info("=" * 70 + "\n")
    
    def raise_if_failed(self):
        """如果验证失败则抛出异常"""
        if not self.result.success:
            error_messages = []
            
            if self.result.missing_required:
                error_messages.append(
                    f"缺少必需配置: {', '.join(c.key for c in self.result.missing_required)}"
                )
            
            if self.result.invalid_configs:
                error_messages.append(
                    f"配置格式错误: {', '.join(c.key for c, _ in self.result.invalid_configs)}"
                )
            
            raise ConfigurationError(
                "配置验证失败:\n" + "\n".join(f"  • {msg}" for msg in error_messages) +
                "\n\n请检查 .env 文件并参考 docs/configuration_guide.md"
            )


class ConfigurationError(Exception):
    """配置错误异常"""
    pass


def validate_startup_config() -> ValidationResult:
    """
    验证启动配置（便捷函数）
    
    Returns:
        ValidationResult: 验证结果
    
    Raises:
        ConfigurationError: 如果验证失败
    """
    validator = StartupValidator()
    result = validator.validate()
    validator.raise_if_failed()
    return result

