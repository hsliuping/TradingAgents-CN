# 配置指南 (v0.1.7)

## 概述

TradingAgents-CN 提供了统一的配置系统，所有配置通过 `.env` 文件管理。本指南详细介绍了所有可用的配置选项和最佳实践，包括v0.1.7新增的Docker部署和报告导出配置。

## 🎯 v0.1.7 配置新特性

### 容器化部署配置
- ✅ **Docker环境变量**: 支持容器化部署的环境配置
- ✅ **服务发现**: 自动配置容器间服务连接
- ✅ **数据卷配置**: 持久化数据存储配置

### 报告导出配置
- ✅ **导出格式选择**: 支持Word/PDF/Markdown格式配置
- ✅ **导出路径配置**: 自定义导出文件存储路径
- ✅ **格式转换配置**: Pandoc和wkhtmltopdf配置选项

### LLM模型扩展
- ✅ **DeepSeek V3集成**: 成本优化的中文模型
- ✅ **智能模型路由**: 根据任务自动选择最优模型
- ✅ **成本控制配置**: 详细的成本监控和限制

## 配置文件结构

### .env 配置文件 (推荐)
```bash
# ===========================================
# TradingAgents-CN 配置文件 (v0.1.7)
# ===========================================

# 🧠 LLM 配置 (多模型支持)
# 🇨🇳 DeepSeek (推荐 - 成本低，中文优化)
DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
DEEPSEEK_ENABLED=true

# 🇨🇳 阿里百炼通义千问 (推荐 - 中文理解好)
DASHSCOPE_API_KEY=your_dashscope_api_key_here
QWEN_ENABLED=true

# 🌍 Google AI Gemini (推荐 - 推理能力强)
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_ENABLED=true

# 🤖 OpenAI (可选 - 通用能力强，成本较高)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ENABLED=false

# 📊 数据源配置
FINNHUB_API_KEY=your_finnhub_api_key_here
TUSHARE_TOKEN=your_tushare_token

# 🗄️ 数据库配置 (Docker自动配置)
MONGODB_ENABLED=false
REDIS_ENABLED=false
MONGODB_HOST=localhost
MONGODB_PORT=27018
REDIS_HOST=localhost
REDIS_PORT=6380

# 📁 路径配置
TRADINGAGENTS_RESULTS_DIR=./results
TRADINGAGENTS_DATA_DIR=./data
```

## 配置选项详解

### 1. 路径配置

#### project_dir
- **类型**: `str`
- **默认值**: 项目根目录
- **说明**: 项目根目录路径，用于定位其他相对路径

#### results_dir
- **类型**: `str`
- **默认值**: `"./results"`
- **环境变量**: `TRADINGAGENTS_RESULTS_DIR`
- **说明**: 分析结果存储目录

```python
config = {
    "results_dir": "/path/to/custom/results",  # 自定义结果目录
}
```

#### data_cache_dir
- **类型**: `str`
- **默认值**: `"tradingagents/dataflows/data_cache"`
- **说明**: 数据缓存目录

### 2. LLM 配置

#### llm_provider
- **类型**: `str`
- **可选值**: `"openai"`, `"anthropic"`, `"google"`
- **默认值**: `"openai"`
- **说明**: 大语言模型提供商

```python
# OpenAI 配置
config = {
    "llm_provider": "openai",
    "backend_url": "https://api.openai.com/v1",
    "deep_think_llm": "gpt-4o",
    "quick_think_llm": "gpt-4o-mini",
}

# Anthropic 配置
config = {
    "llm_provider": "anthropic",
    "backend_url": "https://api.anthropic.com",
    "deep_think_llm": "claude-3-opus-20240229",
    "quick_think_llm": "claude-3-haiku-20240307",
}

# Google 配置
config = {
    "llm_provider": "google",
    "backend_url": "https://generativelanguage.googleapis.com/v1",
    "deep_think_llm": "gemini-pro",
    "quick_think_llm": "gemini-pro",
}
```

#### deep_think_llm
- **类型**: `str`
- **默认值**: `"o4-mini"`
- **说明**: 用于深度思考任务的模型（如复杂分析、辩论）

**推荐模型**:
- **高性能**: `"gpt-4o"`, `"claude-3-opus-20240229"`
- **平衡**: `"gpt-4o-mini"`, `"claude-3-sonnet-20240229"`
- **经济**: `"gpt-3.5-turbo"`, `"claude-3-haiku-20240307"`

#### quick_think_llm
- **类型**: `str`
- **默认值**: `"gpt-4o-mini"`
- **说明**: 用于快速任务的模型（如数据处理、格式化）

### 3. 辩论和讨论配置

#### max_debate_rounds
- **类型**: `int`
- **默认值**: `1`
- **范围**: `1-10`
- **说明**: 研究员辩论的最大轮次

```python
# 不同场景的推荐配置
config_scenarios = {
    "quick_analysis": {"max_debate_rounds": 1},      # 快速分析
    "standard": {"max_debate_rounds": 2},            # 标准分析
    "thorough": {"max_debate_rounds": 3},            # 深度分析
    "comprehensive": {"max_debate_rounds": 5},       # 全面分析
}
```

#### max_risk_discuss_rounds
- **类型**: `int`
- **默认值**: `1`
- **范围**: `1-5`
- **说明**: 风险管理讨论的最大轮次

#### max_recur_limit
- **类型**: `int`
- **默认值**: `100`
- **说明**: 递归调用的最大限制，防止无限循环

### 4. 工具配置

#### online_tools
- **类型**: `bool`
- **默认值**: `True`
- **说明**: 是否使用在线数据工具

```python
# 在线模式 - 获取实时数据
config = {"online_tools": True}

# 离线模式 - 使用缓存数据
config = {"online_tools": False}
```

## 高级配置选项

### 1. 智能体权重配置
```python
config = {
    "analyst_weights": {
        "fundamentals": 0.3,    # 基本面分析权重
        "technical": 0.3,       # 技术分析权重
        "news": 0.2,           # 新闻分析权重
        "social": 0.2,         # 社交媒体分析权重
    }
}
```

### 2. 风险管理配置
```python
config = {
    "risk_management": {
        "risk_threshold": 0.8,           # 风险阈值
        "max_position_size": 0.1,        # 最大仓位比例
        "stop_loss_threshold": 0.05,     # 止损阈值
        "take_profit_threshold": 0.15,   # 止盈阈值
    }
}
```

### 3. 数据源配置
```python
config = {
    "data_sources": {
        "primary": "finnhub",            # 主要数据源
        "fallback": ["yahoo", "alpha_vantage"],  # 备用数据源
        "cache_ttl": {
            "price_data": 300,           # 价格数据缓存5分钟
            "fundamental_data": 86400,   # 基本面数据缓存24小时
            "news_data": 3600,          # 新闻数据缓存1小时
        }
    }
}
```

### 4. 性能优化配置
```python
config = {
    "performance": {
        "parallel_analysis": True,       # 并行分析
        "max_workers": 4,               # 最大工作线程数
        "timeout": 300,                 # 超时时间（秒）
        "retry_attempts": 3,            # 重试次数
        "batch_size": 10,               # 批处理大小
    }
}
```

## 环境变量配置

### 必需的环境变量
```bash
# OpenAI API
export OPENAI_API_KEY="your_openai_api_key"

# FinnHub API
export FINNHUB_API_KEY="your_finnhub_api_key"

# 可选的环境变量
export ANTHROPIC_API_KEY="your_anthropic_api_key"
export GOOGLE_API_KEY="your_google_api_key"
export TRADINGAGENTS_RESULTS_DIR="/custom/results/path"
```

### .env 文件配置
```bash
# .env 文件
OPENAI_API_KEY=your_openai_api_key
FINNHUB_API_KEY=your_finnhub_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key
TRADINGAGENTS_RESULTS_DIR=./custom_results
TRADINGAGENTS_LOG_LEVEL=INFO
```

## 配置最佳实践

### 1. 成本优化配置
```python
# 低成本配置
cost_optimized_config = {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4o-mini",
    "quick_think_llm": "gpt-4o-mini",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "online_tools": False,  # 使用缓存数据
}
```

### 2. 高性能配置
```python
# 高性能配置
high_performance_config = {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4o",
    "quick_think_llm": "gpt-4o",
    "max_debate_rounds": 3,
    "max_risk_discuss_rounds": 2,
    "online_tools": True,
    "performance": {
        "parallel_analysis": True,
        "max_workers": 8,
    }
}
```

### 3. 开发环境配置
```python
# 开发环境配置
dev_config = {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4o-mini",
    "quick_think_llm": "gpt-4o-mini",
    "max_debate_rounds": 1,
    "online_tools": True,
    "debug": True,
    "log_level": "DEBUG",
}
```

### 4. 生产环境配置
```python
# 生产环境配置
prod_config = {
    "llm_provider": "openai",
    "deep_think_llm": "gpt-4o",
    "quick_think_llm": "gpt-4o-mini",
    "max_debate_rounds": 2,
    "max_risk_discuss_rounds": 1,
    "online_tools": True,
    "performance": {
        "parallel_analysis": True,
        "max_workers": 4,
        "timeout": 600,
        "retry_attempts": 3,
    },
    "logging": {
        "level": "INFO",
        "file": "/var/log/tradingagents.log",
    }
}
```

## 配置验证

### 配置验证器
```python
class ConfigValidator:
    """配置验证器"""
    
    def validate(self, config: Dict) -> Tuple[bool, List[str]]:
        """验证配置的有效性"""
        errors = []
        
        # 检查必需字段
        required_fields = ["llm_provider", "deep_think_llm", "quick_think_llm"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # 检查LLM提供商
        valid_providers = ["openai", "anthropic", "google"]
        if config.get("llm_provider") not in valid_providers:
            errors.append(f"Invalid llm_provider. Must be one of: {valid_providers}")
        
        # 检查数值范围
        if config.get("max_debate_rounds", 1) < 1:
            errors.append("max_debate_rounds must be >= 1")
        
        return len(errors) == 0, errors

# 使用示例
validator = ConfigValidator()
is_valid, errors = validator.validate(config)
if not is_valid:
    print("Configuration errors:", errors)
```

## 动态配置更新

### 运行时配置更新
```python
class TradingAgentsGraph:
    def update_config(self, new_config: Dict):
        """运行时更新配置"""
        
        # 验证新配置
        validator = ConfigValidator()
        is_valid, errors = validator.validate(new_config)
        
        if not is_valid:
            raise ValueError(f"Invalid configuration: {errors}")
        
        # 更新配置
        self.config.update(new_config)
        
        # 重新初始化受影响的组件
        self._reinitialize_components()
    
    def _reinitialize_components(self):
        """重新初始化组件"""
        # 重新初始化LLM
        self._setup_llms()
        
        # 重新初始化智能体
        self._setup_agents()
```

通过合理的配置，您可以根据不同的使用场景优化 TradingAgents-CN 的性能和成本。

## 🐳 Docker部署配置 (v0.1.7新增)

### Docker环境变量

```bash
# === Docker特定配置 ===
# 数据库连接 (使用容器服务名)
MONGODB_URL=mongodb://mongodb:27017/tradingagents
REDIS_URL=redis://redis:6379

# 服务端口配置
WEB_PORT=8501
MONGODB_PORT=27017
REDIS_PORT=6379
MONGO_EXPRESS_PORT=8081
REDIS_COMMANDER_PORT=8082
```

## 📄 报告导出配置 (v0.1.7新增)

### 导出功能配置

```bash
# === 报告导出配置 ===
# 启用导出功能
EXPORT_ENABLED=true

# 默认导出格式 (word,pdf,markdown)
EXPORT_DEFAULT_FORMAT=word,pdf

# 导出文件路径
EXPORT_OUTPUT_PATH=./exports

# Pandoc配置
PANDOC_PATH=/usr/bin/pandoc
WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf
```

## 🧠 LLM模型路由配置 (v0.1.7新增)

### 智能模型选择

```bash
# === 模型路由配置 ===
# 启用智能路由
LLM_SMART_ROUTING=true

# 默认模型优先级
LLM_PRIORITY_ORDER=deepseek,qwen,gemini,openai

# 成本控制
LLM_DAILY_COST_LIMIT=10.0
LLM_COST_ALERT_THRESHOLD=8.0
```

## 最佳实践 (v0.1.7更新)

### 1. 安全性
- 🔐 **API密钥保护**: 永远不要将 `.env` 文件提交到版本控制
- 🔒 **权限控制**: 设置适当的文件权限 (600)
- 🛡️ **密钥轮换**: 定期更换API密钥

### 2. 性能优化
- ⚡ **模型选择**: 根据任务选择合适的模型
- 💾 **缓存策略**: 合理配置缓存TTL
- 🔄 **连接池**: 优化数据库连接池大小

### 3. 成本控制
- 💰 **成本监控**: 设置合理的成本限制
- 📊 **使用统计**: 定期查看Token使用情况
- 🎯 **模型优化**: 优先使用成本效益高的模型

---

*最后更新: 2025-07-13*
*版本: cn-0.1.7*
