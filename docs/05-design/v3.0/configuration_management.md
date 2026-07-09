# TradingAgents-CN 配置管理设计

## 📋 概述

本文档描述了TradingAgents-CN系统的配置管理机制，包括配置文件结构、环境变量管理、动态配置更新等。

---

## 🔧 配置文件结构

### 1. 主配置文件 (.env)

```bash
# ===========================================
# TradingAgents-CN 主配置文件
# ===========================================

# ===== LLM配置 =====
# DeepSeek配置
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 阿里百炼配置
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI配置 (可选)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Google Gemini配置 (可选)
GOOGLE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ===== 数据源配置 =====
# Tushare配置
TUSHARE_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# FinnHub配置 (可选)
FINNHUB_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ===== 数据库配置 =====
# MongoDB配置
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=tradingagents

# Redis配置
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# ===== 系统配置 =====
# 日志级别
LOG_LEVEL=INFO

# 缓存配置
CACHE_TTL=3600
CACHE_MAX_SIZE=1000

# 并发配置
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=30

# ===== Web界面配置 =====
# Streamlit配置
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 报告导出配置
EXPORT_FORMATS=markdown,docx,pdf
MAX_EXPORT_SIZE=50MB
```

### 2. 默认配置 (default_config.py)

```python
# TradingAgents-CN 默认配置
DEFAULT_CONFIG = {
    # ===== 系统配置 =====
    "system": {
        "version": "0.1.7",
        "debug": False,
        "log_level": "INFO",
        "timezone": "Asia/Shanghai"
    },
    
    # ===== LLM配置 =====
    "llm": {
        "default_model": "deepseek",
        "models": {
            "deepseek": {
                "model_name": "deepseek-chat",
                "temperature": 0.1,
                "max_tokens": 4000,
                "timeout": 60
            },
            "qwen": {
                "model_name": "qwen-plus-latest",
                "temperature": 0.1,
                "max_tokens": 4000,
                "timeout": 60
            },
            "gemini": {
                "model_name": "gemini-pro",
                "temperature": 0.1,
                "max_tokens": 4000,
                "timeout": 60
            }
        }
    },
    
    # ===== 数据源配置 =====
    "data_sources": {
        "china": {
            "primary": "akshare",
            "fallback": ["tushare", "baostock"],
            "timeout": 30,
            "retry_count": 3
        },
        "us": {
            "primary": "yfinance",
            "fallback": ["finnhub"],
            "timeout": 30,
            "retry_count": 3
        },
        "hk": {
            "primary": "akshare",
            "fallback": ["yfinance"],
            "timeout": 30,
            "retry_count": 3
        }
    },
    
    # ===== 缓存配置 =====
    "cache": {
        "enabled": True,
        "backend": "redis",  # redis, memory, file
        "ttl": {
            "stock_data": 3600,      # 1小时
            "news_data": 1800,       # 30分钟
            "analysis_result": 7200  # 2小时
        },
        "max_size": {
            "memory": 1000,
            "file": 10000
        }
    },
    
    # ===== 分析师配置 =====
    "analysts": {
        "enabled": ["fundamentals", "market", "news", "social"],
        "parallel_execution": True,
        "timeout": 180,  # 3分钟
        "retry_count": 2
    },
    
    # ===== 风险管理配置 =====
    "risk_management": {
        "enabled": True,
        "risk_levels": ["aggressive", "conservative", "neutral"],
        "max_risk_score": 1.0,
        "default_risk_tolerance": 0.5
    },
    
    # ===== Web界面配置 =====
    "web": {
        "port": 8501,
        "host": "0.0.0.0",
        "theme": "light",
        "sidebar_width": 300,
        "max_upload_size": "50MB"
    },
    
    # ===== 导出配置 =====
    "export": {
        "formats": ["markdown", "docx", "pdf"],
        "default_format": "markdown",
        "include_charts": True,
        "watermark": True
    }
}
```

### 3. 环境特定配置

#### 开发环境 (config/development.py)
```python
DEVELOPMENT_CONFIG = {
    "system": {
        "debug": True,
        "log_level": "DEBUG"
    },
    "llm": {
        "models": {
            "deepseek": {
                "temperature": 0.2,  # 开发环境允许更多创造性
                "max_tokens": 2000   # 减少token使用
            }
        }
    },
    "cache": {
        "backend": "memory",  # 开发环境使用内存缓存
        "ttl": {
            "stock_data": 300,  # 5分钟，便于测试
        }
    }
}
```

#### 生产环境 (config/production.py)
```python
PRODUCTION_CONFIG = {
    "system": {
        "debug": False,
        "log_level": "INFO"
    },
    "llm": {
        "models": {
            "deepseek": {
                "temperature": 0.1,  # 生产环境更保守
                "max_tokens": 4000
            }
        }
    },
    "cache": {
        "backend": "redis",   # 生产环境使用Redis
        "ttl": {
            "stock_data": 3600,  # 1小时
        }
    },
    "security": {
        "api_rate_limit": 100,  # 每分钟100次请求
        "enable_auth": True,
        "session_timeout": 3600
    }
}
```

---

## 🔄 配置管理机制

### 1. 配置加载器

```python
class ConfigManager:
    def __init__(self, env: str = "development"):
        self.env = env
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置的优先级顺序"""
        config = DEFAULT_CONFIG.copy()
        
        # 1. 加载环境特定配置
        env_config = self._load_env_config()
        config = self._merge_config(config, env_config)
        
        # 2. 加载环境变量
        env_vars = self._load_env_variables()
        config = self._merge_config(config, env_vars)
        
        # 3. 加载用户自定义配置
        user_config = self._load_user_config()
        config = self._merge_config(config, user_config)
        
        return config
    
    def _load_env_variables(self) -> Dict[str, Any]:
        """从环境变量加载配置"""
        env_config = {}
        
        # LLM配置
        if os.getenv("DEEPSEEK_API_KEY"):
            env_config["deepseek_api_key"] = os.getenv("DEEPSEEK_API_KEY")
        
        if os.getenv("DASHSCOPE_API_KEY"):
            env_config["dashscope_api_key"] = os.getenv("DASHSCOPE_API_KEY")
        
        # 数据源配置
        if os.getenv("TUSHARE_TOKEN"):
            env_config["tushare_token"] = os.getenv("TUSHARE_TOKEN")
        
        # 数据库配置
        if os.getenv("MONGODB_URL"):
            env_config["mongodb_url"] = os.getenv("MONGODB_URL")
        
        if os.getenv("REDIS_URL"):
            env_config["redis_url"] = os.getenv("REDIS_URL")
        
        return env_config
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套键"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def validate(self) -> List[str]:
        """验证配置的有效性"""
        errors = []
        
        # 验证必需的API密钥
        required_keys = [
            "deepseek_api_key",
            "dashscope_api_key", 
            "tushare_token"
        ]
        
        for key in required_keys:
            if not self.get(key):
                errors.append(f"缺少必需的配置: {key}")
        
        # 验证数据库连接
        mongodb_url = self.get("mongodb_url")
        if mongodb_url and not self._validate_mongodb_url(mongodb_url):
            errors.append("MongoDB连接URL格式错误")
        
        return errors
```

### 2. 动态配置更新

```python
class DynamicConfigManager:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.watchers = []
    
    def watch(self, key: str, callback: Callable[[Any], None]) -> None:
        """监听配置变化"""
        self.watchers.append((key, callback))
    
    def update_config(self, key: str, value: Any) -> None:
        """更新配置并通知监听者"""
        old_value = self.config_manager.get(key)
        self.config_manager.set(key, value)
        
        # 通知监听者
        for watch_key, callback in self.watchers:
            if key.startswith(watch_key):
                callback(value)
        
        # 记录配置变更
        logger.info(f"配置更新: {key} = {value} (原值: {old_value})")
    
    def reload_from_file(self, file_path: str) -> None:
        """从文件重新加载配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                new_config = json.load(f)
            
            for key, value in new_config.items():
                self.update_config(key, value)
                
            logger.info(f"从文件重新加载配置: {file_path}")
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
```

---

## 🔒 安全配置

### 1. API密钥管理

```python
class SecureConfigManager:
    def __init__(self):
        self.encryption_key = self._get_encryption_key()
    
    def _get_encryption_key(self) -> bytes:
        """获取加密密钥"""
        key = os.getenv("CONFIG_ENCRYPTION_KEY")
        if not key:
            # 生成新的加密密钥
            key = Fernet.generate_key()
            logger.warning("未找到加密密钥，已生成新密钥")
        return key.encode() if isinstance(key, str) else key
    
    def encrypt_value(self, value: str) -> str:
        """加密配置值"""
        f = Fernet(self.encryption_key)
        encrypted = f.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """解密配置值"""
        f = Fernet(self.encryption_key)
        encrypted = base64.b64decode(encrypted_value.encode())
        return f.decrypt(encrypted).decode()
    
    def store_api_key(self, service: str, api_key: str) -> None:
        """安全存储API密钥"""
        encrypted_key = self.encrypt_value(api_key)
        # 存储到安全的配置存储中
        self._store_encrypted_config(f"{service}_api_key", encrypted_key)
    
    def get_api_key(self, service: str) -> str:
        """获取API密钥"""
        encrypted_key = self._get_encrypted_config(f"{service}_api_key")
        if encrypted_key:
            return self.decrypt_value(encrypted_key)
        return None
```

### 2. 配置验证

```python
class ConfigValidator:
    def __init__(self):
        self.validation_rules = {
            "deepseek_api_key": self._validate_deepseek_key,
            "tushare_token": self._validate_tushare_token,
            "mongodb_url": self._validate_mongodb_url,
            "redis_url": self._validate_redis_url
        }
    
    def validate_all(self, config: Dict[str, Any]) -> List[str]:
        """验证所有配置"""
        errors = []
        
        for key, validator in self.validation_rules.items():
            value = config.get(key)
            if value:
                error = validator(value)
                if error:
                    errors.append(f"{key}: {error}")
        
        return errors
    
    def _validate_deepseek_key(self, key: str) -> str:
        """验证DeepSeek API密钥格式"""
        if not key.startswith("sk-"):
            return "DeepSeek API密钥应以'sk-'开头"
        if len(key) < 20:
            return "DeepSeek API密钥长度不足"
        return None
    
    def _validate_tushare_token(self, token: str) -> str:
        """验证Tushare Token格式"""
        if len(token) != 32:
            return "Tushare Token应为32位字符"
        return None
    
    def _validate_mongodb_url(self, url: str) -> str:
        """验证MongoDB连接URL"""
        if not url.startswith("mongodb://"):
            return "MongoDB URL应以'mongodb://'开头"
        return None
```

---

## 📊 配置监控

### 1. 配置使用统计

```python
class ConfigMonitor:
    def __init__(self):
        self.usage_stats = {}
        self.access_log = []
    
    def track_access(self, key: str, value: Any) -> None:
        """跟踪配置访问"""
        timestamp = datetime.now()
        
        # 更新使用统计
        if key not in self.usage_stats:
            self.usage_stats[key] = {
                "access_count": 0,
                "first_access": timestamp,
                "last_access": timestamp
            }
        
        self.usage_stats[key]["access_count"] += 1
        self.usage_stats[key]["last_access"] = timestamp
        
        # 记录访问日志
        self.access_log.append({
            "timestamp": timestamp,
            "key": key,
            "value_type": type(value).__name__
        })
    
    def get_usage_report(self) -> Dict[str, Any]:
        """生成配置使用报告"""
        return {
            "total_configs": len(self.usage_stats),
            "most_accessed": max(
                self.usage_stats.items(),
                key=lambda x: x[1]["access_count"]
            )[0] if self.usage_stats else None,
            "usage_stats": self.usage_stats
        }
```

### 2. 配置健康检查

```python
class ConfigHealthChecker:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def check_health(self) -> Dict[str, Any]:
        """检查配置健康状态"""
        health_status = {
            "overall": "healthy",
            "checks": {}
        }
        
        # 检查API密钥有效性
        api_checks = self._check_api_keys()
        health_status["checks"]["api_keys"] = api_checks
        
        # 检查数据库连接
        db_checks = self._check_database_connections()
        health_status["checks"]["databases"] = db_checks
        
        # 检查缓存系统
        cache_checks = self._check_cache_system()
        health_status["checks"]["cache"] = cache_checks
        
        # 确定整体健康状态
        if any(check["status"] == "error" for check in health_status["checks"].values()):
            health_status["overall"] = "unhealthy"
        elif any(check["status"] == "warning" for check in health_status["checks"].values()):
            health_status["overall"] = "degraded"
        
        return health_status
    
    def _check_api_keys(self) -> Dict[str, Any]:
        """检查API密钥状态"""
        # 实现API密钥有效性检查
        pass
    
    def _check_database_connections(self) -> Dict[str, Any]:
        """检查数据库连接状态"""
        # 实现数据库连接检查
        pass
```

---

## 🚀 部署配置

### 1. Docker环境配置

```dockerfile
# Dockerfile中的配置管理
ENV ENVIRONMENT=production
ENV CONFIG_PATH=/app/config
ENV LOG_LEVEL=INFO

# 复制配置文件
COPY config/ /app/config/
COPY .env.example /app/.env.example

# 设置配置文件权限
RUN chmod 600 /app/config/*
```

### 2. Kubernetes配置

```yaml
# ConfigMap for application configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: tradingagents-config
data:
  app.yaml: |
    system:
      log_level: INFO
      debug: false
    cache:
      backend: redis
      ttl:
        stock_data: 3600

---
# Secret for sensitive configuration
apiVersion: v1
kind: Secret
metadata:
  name: tradingagents-secrets
type: Opaque
data:
  deepseek-api-key: <base64-encoded-key>
  tushare-token: <base64-encoded-token>
```

---

## 📋 最佳实践

### 1. 配置管理原则
- **分离关注点**: 将配置与代码分离
- **环境隔离**: 不同环境使用不同配置
- **安全第一**: 敏感信息加密存储
- **版本控制**: 配置变更可追溯
- **验证机制**: 配置加载前进行验证

### 2. 配置更新流程
1. **开发阶段**: 在开发环境测试配置变更
2. **测试验证**: 在测试环境验证配置有效性
3. **生产部署**: 通过自动化流程部署到生产环境
4. **监控检查**: 部署后监控系统健康状态
5. **回滚准备**: 准备配置回滚方案

### 3. 故障处理
- **配置备份**: 定期备份重要配置
- **降级策略**: 配置加载失败时的降级方案
- **告警机制**: 配置异常时及时告警
- **恢复流程**: 快速恢复配置的标准流程
