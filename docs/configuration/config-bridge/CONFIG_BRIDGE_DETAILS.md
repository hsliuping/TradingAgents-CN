# 配置桥接详细说明

## 📋 概述

配置桥接模块 (`app/core/config_bridge.py`) 负责将统一配置系统中的配置桥接到环境变量，让 TradingAgents 核心库能够使用用户在 Web 界面中配置的参数。

## 🎯 桥接的配置类型

### 1. 基础配置（已实现）

#### 大模型 API 密钥

从统一配置的 `llm_configs` 集合读取，桥接到环境变量：

```python
# 示例：DeepSeek
llm_config.provider = "deepseek"
llm_config.api_key = "sk-xxx"
↓
os.environ['DEEPSEEK_API_KEY'] = "sk-xxx"
```

**支持的提供商**：
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `DEEPSEEK_API_KEY`
- `DASHSCOPE_API_KEY`
- `QIANFAN_API_KEY`

#### 默认模型

从统一配置的 `llm_configs` 集合读取默认模型：

```python
# 默认模型
default_model = unified_config.get_default_model()
os.environ['TRADINGAGENTS_DEFAULT_MODEL'] = default_model

# 快速分析模型
quick_model = unified_config.get_quick_analysis_model()
os.environ['TRADINGAGENTS_QUICK_MODEL'] = quick_model

# 深度分析模型
deep_model = unified_config.get_deep_analysis_model()
os.environ['TRADINGAGENTS_DEEP_MODEL'] = deep_model
```

#### 数据源 API 密钥

从统一配置的 `data_source_configs` 集合读取：

```python
# Tushare
ds_config.source_type = "tushare"
ds_config.api_key = "xxx"
↓
os.environ['TUSHARE_TOKEN'] = "xxx"

# FinnHub
ds_config.source_type = "finnhub"
ds_config.api_key = "xxx"
↓
os.environ['FINNHUB_API_KEY'] = "xxx"
```

### 2. 数据源细节配置（新增）⭐

从统一配置的 `data_source_configs` 集合读取细节参数：

#### 超时时间

```python
ds_config.timeout = 60
↓
os.environ['TUSHARE_TIMEOUT'] = "60"
```

#### 速率限制

```python
ds_config.rate_limit = 120  # 每分钟请求数
↓
os.environ['TUSHARE_RATE_LIMIT'] = "2.0"  # 转换为每秒请求数
```

#### 最大重试次数

```python
ds_config.config_params = {"max_retries": 5}
↓
os.environ['TUSHARE_MAX_RETRIES'] = "5"
```

#### 缓存 TTL

```python
ds_config.config_params = {"cache_ttl": 7200}
↓
os.environ['TUSHARE_CACHE_TTL'] = "7200"
```

#### 是否启用缓存

```python
ds_config.config_params = {"cache_enabled": True}
↓
os.environ['TUSHARE_CACHE_ENABLED'] = "true"
```

**支持的数据源**：
- `TUSHARE`
- `AKSHARE`
- `FINNHUB`
- `TDX`

### 3. 系统运行时配置（新增）⭐

从系统设置 (`system_settings`) 读取运行时参数：

#### TradingAgents 港股配置

```python
system_settings = {
    "ta_hk_min_request_interval_seconds": 3.0,
    "ta_hk_timeout_seconds": 90,
    "ta_hk_max_retries": 5,
    "ta_hk_rate_limit_wait_seconds": 60,
    "ta_hk_cache_ttl_seconds": 86400,
    "ta_use_app_cache": True
}
↓
os.environ['TA_HK_MIN_REQUEST_INTERVAL_SECONDS'] = "3.0"
os.environ['TA_HK_TIMEOUT_SECONDS'] = "90"
os.environ['TA_HK_MAX_RETRIES'] = "5"
os.environ['TA_HK_RATE_LIMIT_WAIT_SECONDS'] = "60"
os.environ['TA_HK_CACHE_TTL_SECONDS'] = "86400"
os.environ['TA_USE_APP_CACHE'] = "true"
```

#### 系统配置

```python
system_settings = {
    "app_timezone": "Asia/Shanghai",
    "currency_preference": "CNY"
}
↓
os.environ['APP_TIMEZONE'] = "Asia/Shanghai"
os.environ['CURRENCY_PREFERENCE'] = "CNY"
```

## 🔄 桥接流程

### 启动时自动桥接

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    await init_db()
    
    # 🔧 配置桥接
    try:
        from app.core.config_bridge import bridge_config_to_env
        bridge_config_to_env()
    except Exception as e:
        logger.warning(f"⚠️  配置桥接失败: {e}")
    
    yield
```

### 手动重载配置

```python
# 前端：点击"重载配置"按钮
↓
# 后端：POST /api/config/reload
↓
# config_bridge.py
def reload_bridged_config():
    clear_bridged_config()  # 清除旧配置
    bridge_config_to_env()  # 重新桥接
```

## 📊 桥接函数说明

### `bridge_config_to_env()`

主函数，负责桥接所有配置：

```python
def bridge_config_to_env():
    """将统一配置桥接到环境变量"""
    # 1. 桥接大模型配置（API 密钥）
    # 2. 桥接默认模型配置
    # 3. 桥接数据源配置（API 密钥）
    # 4. 桥接数据源细节配置
    # 5. 桥接系统运行时配置
```

### `_bridge_datasource_details()`

桥接数据源细节配置：

```python
def _bridge_datasource_details(data_source_configs) -> int:
    """桥接数据源细节配置到环境变量"""
    for ds_config in data_source_configs:
        # 超时时间
        # 速率限制
        # 最大重试次数
        # 缓存 TTL
        # 是否启用缓存
```

### `_bridge_system_settings()`

桥接系统运行时配置：

```python
def _bridge_system_settings() -> int:
    """桥接系统运行时配置到环境变量"""
    # TradingAgents 运行时配置
    # 时区配置
    # 货币偏好
```

### `clear_bridged_config()`

清除所有桥接的配置：

```python
def clear_bridged_config():
    """清除桥接的配置"""
    # 清除模型配置
    # 清除数据源 API 密钥
    # 清除数据源细节配置
    # 清除 TradingAgents 运行时配置
    # 清除系统配置
```

### `reload_bridged_config()`

重新加载配置：

```python
def reload_bridged_config():
    """重新加载配置并桥接到环境变量"""
    clear_bridged_config()
    return bridge_config_to_env()
```

## 🎯 TradingAgents 如何使用

### 1. 数据源配置

TradingAgents 的数据源配置管理器 (`tradingagents/config/providers_config.py`) 从环境变量读取：

```python
class DataSourceConfig:
    def _load_configs(self):
        # Tushare配置
        self._configs["tushare"] = {
            "enabled": self._get_bool_env("TUSHARE_ENABLED", True),
            "token": os.getenv("TUSHARE_TOKEN", ""),
            "timeout": self._get_int_env("TUSHARE_TIMEOUT", 30),
            "rate_limit": self._get_float_env("TUSHARE_RATE_LIMIT", 0.1),
            "max_retries": self._get_int_env("TUSHARE_MAX_RETRIES", 3),
            "cache_enabled": self._get_bool_env("TUSHARE_CACHE_ENABLED", True),
            "cache_ttl": self._get_int_env("TUSHARE_CACHE_TTL", 3600),
        }
```

### 2. 运行时配置

TradingAgents 的运行时设置 (`tradingagents/config/runtime_settings.py`) 从环境变量读取：

```python
def get_number(env_var: str, system_key: Optional[str], default: float | int, caster: Callable[[Any], Any]):
    """按优先级获取数值配置：DB(system_settings) > ENV > default"""
    # 1) DB 动态设置
    if system_key:
        eff = _get_system_settings_sync()
        if isinstance(eff, dict) and system_key in eff:
            return _coerce(eff.get(system_key), caster, default)
    
    # 2) 环境变量
    env_val = os.getenv(env_var)
    if env_val is not None and str(env_val).strip() != "":
        return _coerce(env_val, caster, default)
    
    # 3) 代码默认
    return default
```

## 📝 配置优先级

```
统一配置（MongoDB）> 环境变量（.env）> 代码默认值
```

**说明**：
1. 优先使用统一配置中的值（通过桥接到环境变量）
2. 如果统一配置中没有，使用 `.env` 文件中的环境变量
3. 如果环境变量也没有，使用代码中的默认值

## ⚠️ 注意事项

### 1. 数据库配置不桥接

MongoDB 和 Redis 配置**不会**桥接到环境变量，因为：
- 数据库配置需要在应用启动前就确定
- 修改数据库配置需要重启服务
- 不能通过 API 动态修改数据库连接

### 2. 配置更新需要重载

修改配置后，需要：
- 点击"重载配置"按钮（推荐）
- 或者重启后端服务

### 3. 日志级别

- 基础配置（API 密钥、模型）：`INFO` 级别
- 细节配置（超时、重试等）：`DEBUG` 级别

## 🧪 测试方法

详见 [`docs/CONFIG_MIGRATION_TESTING.md`](./CONFIG_MIGRATION_TESTING.md)

## 📚 相关文档

- [配置迁移计划](./CONFIG_MIGRATION_PLAN.md)
- [配置迁移实施总结](./CONFIG_MIGRATION_SUMMARY.md)
- [配置迁移测试指南](./CONFIG_MIGRATION_TESTING.md)
- [配置向导 vs 配置管理](./CONFIG_WIZARD_VS_CONFIG_MANAGEMENT.md)

