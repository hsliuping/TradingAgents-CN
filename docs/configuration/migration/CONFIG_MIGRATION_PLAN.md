# 配置系统迁移计划

## 📋 问题概述

当前系统存在**配置双轨制**问题：

1. **后端 API 层**：使用新版统一配置系统（`unified_config`）
2. **TradingAgents 核心库**：仍使用旧版配置（`DEFAULT_CONFIG` + 环境变量）

这导致用户在配置向导或配置管理界面设置的配置**不会被实际的分析引擎使用**。

## 🔍 当前配置使用情况

### ✅ 已迁移到新版配置

| 模块 | 文件 | 使用方式 |
|------|------|----------|
| 配置 API | `app/routers/config.py` | `unified_config` |
| 配置服务 | `app/services/config_service.py` | `unified_config` |
| 分析服务 | `app/services/analysis_service.py` | `unified_config.get_quick_analysis_model()` |
| 配置提供者 | `app/services/config_provider.py` | 合并 ENV + DB 配置 |
| 系统启动 | `app/main.py` | `config_service.get_system_config()` |

### ❌ 仍使用旧版配置

| 模块 | 文件 | 问题 |
|------|------|------|
| TradingAgents 核心 | `tradingagents/graph/trading_graph.py` | 使用 `DEFAULT_CONFIG` + `os.getenv()` |
| 配置创建函数 | `app/services/simple_analysis_service.py` | `create_analysis_config()` 基于 `DEFAULT_CONFIG` |
| CLI 工具 | `cli/main.py` | 使用 `DEFAULT_CONFIG.copy()` |
| 配置管理器 | `tradingagents/config/config_manager.py` | 独立的配置系统 |

## 🎯 迁移目标

### 目标 1：TradingAgents 使用统一配置

**修改文件**：`tradingagents/graph/trading_graph.py`

**当前代码**：
```python
# 从环境变量读取 API 密钥
google_api_key = os.getenv('GOOGLE_API_KEY')
if not google_api_key:
    raise ValueError("请设置GOOGLE_API_KEY环境变量")

self.deep_thinking_llm = ChatGoogleGenerativeAI(
    model=self.config["deep_think_llm"],
    google_api_key=google_api_key
)
```

**目标代码**：
```python
# 从统一配置读取
from app.core.unified_config import unified_config

llm_config = unified_config.get_llm_config_by_name(self.config["deep_think_llm"])
if not llm_config:
    raise ValueError(f"未找到模型配置: {self.config['deep_think_llm']}")

self.deep_thinking_llm = ChatGoogleGenerativeAI(
    model=llm_config.model_name,
    google_api_key=llm_config.api_key,
    base_url=llm_config.api_base
)
```

### 目标 2：配置创建函数使用统一配置

**修改文件**：`app/services/simple_analysis_service.py`

**当前代码**：
```python
def create_analysis_config(
    research_depth: str,
    selected_analysts: list,
    quick_model: str,
    deep_model: str,
    llm_provider: str,
    market_type: str = "A股"
) -> dict:
    # 从DEFAULT_CONFIG开始
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model
    # ...
```

**目标代码**：
```python
def create_analysis_config(
    research_depth: str,
    selected_analysts: list,
    quick_model: Optional[str] = None,
    deep_model: Optional[str] = None,
    market_type: str = "A股"
) -> dict:
    from app.core.unified_config import unified_config
    
    # 从统一配置获取模型
    quick_model = quick_model or unified_config.get_quick_analysis_model()
    deep_model = deep_model or unified_config.get_deep_analysis_model()
    
    # 自动推断 provider
    quick_config = unified_config.get_llm_config_by_name(quick_model)
    llm_provider = quick_config.provider.value if quick_config else "dashscope"
    
    # 构建配置
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model
    # ...
```

### 目标 3：CLI 工具使用统一配置

**修改文件**：`cli/main.py`

**当前代码**：
```python
config = DEFAULT_CONFIG.copy()
config.update({
    "llm_provider": "dashscope",
    "llm_model": "qwen-turbo",
    "quick_think_llm": "qwen-turbo",
    "deep_think_llm": "qwen-plus",
})
```

**目标代码**：
```python
from app.core.unified_config import unified_config

# 从统一配置读取
quick_model = unified_config.get_quick_analysis_model()
deep_model = unified_config.get_deep_analysis_model()

config = DEFAULT_CONFIG.copy()
config.update({
    "quick_think_llm": quick_model,
    "deep_think_llm": deep_model,
    "llm_provider": unified_config.get_default_provider(),
})
```

## 🚀 迁移步骤

### 阶段 1：准备工作（已完成）

- [x] 创建统一配置系统（`app/core/unified_config.py`）
- [x] 创建配置向导（`frontend/src/components/ConfigWizard.vue`）
- [x] 实现配置 API（`app/routers/config.py`）
- [x] 配置向导保存到后端

### 阶段 2：核心库迁移（待完成）

- [ ] 修改 `tradingagents/graph/trading_graph.py`
  - [ ] 添加 `unified_config` 导入
  - [ ] 替换所有 `os.getenv()` 调用
  - [ ] 从统一配置读取 API 密钥和模型配置
  
- [ ] 修改 `app/services/simple_analysis_service.py`
  - [ ] 更新 `create_analysis_config()` 函数
  - [ ] 移除硬编码的 provider 映射
  - [ ] 使用 `unified_config` 获取模型配置

- [ ] 修改 `cli/main.py`
  - [ ] 使用 `unified_config` 读取配置
  - [ ] 保留命令行参数覆盖功能

### 阶段 3：测试验证（待完成）

- [ ] 单元测试
  - [ ] 测试配置读取
  - [ ] 测试 API 密钥获取
  - [ ] 测试模型初始化

- [ ] 集成测试
  - [ ] 测试配置向导 → 分析执行流程
  - [ ] 测试配置管理 → 分析执行流程
  - [ ] 测试 CLI 工具

- [ ] 端到端测试
  - [ ] 用户完成配置向导
  - [ ] 执行股票分析
  - [ ] 验证使用正确的模型和 API 密钥

### 阶段 4：文档更新（待完成）

- [ ] 更新用户文档
  - [ ] 配置向导使用说明
  - [ ] 配置管理使用说明
  - [ ] 环境变量说明（标记为可选）

- [ ] 更新开发文档
  - [ ] 配置系统架构
  - [ ] 配置迁移指南
  - [ ] API 文档

## 🔧 技术细节

### 配置优先级

```
命令行参数 > 统一配置（DB） > 环境变量 > 默认值
```

### API 密钥获取逻辑

```python
def get_api_key_for_model(model_name: str) -> str:
    """获取模型的 API 密钥"""
    # 1. 从模型配置获取
    llm_config = unified_config.get_llm_config_by_name(model_name)
    if llm_config and llm_config.api_key:
        return llm_config.api_key
    
    # 2. 从厂家配置获取
    if llm_config:
        provider_config = unified_config.get_provider_config(llm_config.provider)
        if provider_config and provider_config.api_key:
            return provider_config.api_key
    
    # 3. 从环境变量获取（兼容旧版）
    env_key = f"{llm_config.provider.upper()}_API_KEY"
    api_key = os.getenv(env_key)
    if api_key:
        logger.warning(f"⚠️ 使用环境变量 {env_key}，建议在配置管理中设置")
        return api_key
    
    # 4. 失败
    raise ValueError(f"未找到模型 {model_name} 的 API 密钥")
```

### 向后兼容

为了保持向后兼容，迁移过程中：

1. **保留环境变量支持**：如果统一配置中没有找到，回退到环境变量
2. **保留 DEFAULT_CONFIG**：作为默认值的来源
3. **渐进式迁移**：先迁移后端，再迁移 CLI，最后移除旧代码

## 📝 注意事项

### 1. 循环依赖问题

`tradingagents` 库不应该直接依赖 `app` 模块，需要通过以下方式解决：

**方案 A：依赖注入**
```python
class TradingAgentsGraph:
    def __init__(self, config: Dict[str, Any], config_provider=None):
        self.config_provider = config_provider or DefaultConfigProvider()
        # 使用 config_provider 获取配置
```

**方案 B：配置文件**
```python
# 将统一配置导出为 JSON 文件
# TradingAgents 从文件读取
config_file = Path("~/.tradingagents/config.json")
```

**方案 C：环境变量桥接**（推荐）
```python
# app 层在启动时将配置写入环境变量
# TradingAgents 从环境变量读取
os.environ['TRADINGAGENTS_QUICK_MODEL'] = unified_config.get_quick_analysis_model()
os.environ['TRADINGAGENTS_DEEP_MODEL'] = unified_config.get_deep_analysis_model()
```

### 2. 性能考虑

- 配置读取应该有缓存机制
- 避免每次分析都查询数据库
- 使用 `@lru_cache` 缓存配置对象

### 3. 安全考虑

- API 密钥不应该记录到日志
- 配置导出时应该脱敏
- 前端不应该接收完整的 API 密钥

## 🎯 预期效果

迁移完成后：

1. ✅ 用户在配置向导设置的配置**立即生效**
2. ✅ 配置管理界面的修改**实时应用**
3. ✅ 不再需要手动编辑 `.env` 文件
4. ✅ 支持多用户、多配置
5. ✅ 配置可以导入导出
6. ✅ 完整的配置审计日志

## 📚 相关文档

- [统一配置系统](./UNIFIED_CONFIG.md)
- [配置向导使用说明](./CONFIG_WIZARD.md)
- [配置向导后端集成](./CONFIG_WIZARD_BACKEND_INTEGRATION.md)
- [配置管理 API](./configuration_analysis.md)

