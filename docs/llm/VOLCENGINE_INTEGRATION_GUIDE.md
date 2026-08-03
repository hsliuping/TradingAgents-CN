# 火山方舟（Volcengine Ark）模型接入指南

> 本指南记录 TradingAgentsCN 项目接入火山方舟过程中遇到的问题与解决办法，供 **v2.0 / v3.0** 版本接入时直接参考，避免重复踩坑。

## 📋 概述

火山方舟（Volcengine Ark）是字节跳动旗下的 LLM 推理服务平台，提供 OpenAI 兼容接口。本项目接入时需要处理以下关键差异：

1. **两种订阅套餐**：Agent Plan 与 Coding Plan，支持的模型范围不同
2. **推理模型特殊参数**：`doubao-seed-2.x` 系列是推理模型，会先深度思考再输出，单次响应可达 165 秒
3. **`reasoning_effort` 参数**：火山方舟通用参数，控制思考深度，可大幅降低响应时间和 token 消耗

## 🎯 套餐对比：Agent Plan vs Coding Plan

| 维度 | Agent Plan (volcengine) | Coding Plan (volcengine_coding) |
|------|------------------------|--------------------------------|
| Provider 标识 | `volcengine` | `volcengine_coding` |
| Base URL | `https://ark.cn-beijing.volces.com/api/v3` | `https://ark.cn-beijing.volces.com/api/coding/v3` |
| 默认测试模型 | `Doubao-Seed-2.1-turbo` | `doubao-seed-2.0-code` |
| 支持模型数量 | 全量模型 | 仅 ~10 个编码相关模型 |
| 2.1 版本模型 | ✅ 支持 | ❌ 不支持（需过滤） |
| 模型列表过滤 | 宽松，按前缀 `doubao-` / `ep-` 过滤 | 严格白名单 + 排除 `doubao-seed-2.1` |

## 🔧 关键配置项

### 1. 数据库 Provider 注册（`app/scripts/init_providers.py`）

```python
# volcengine (Agent Plan)
{
    "name": "volcengine",
    "display_name": "火山方舟",
    "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "test_model": "Doubao-Seed-2.1-turbo",
    "website": "https://www.volcengine.com/solutions/ark",  # ⚠️ 不要用带 utm_ 参数的活动链接
    "is_aggregator": False,
}

# volcengine_coding (Coding Plan)
{
    "name": "volcengine_coding",
    "display_name": "火山方舟编程",
    "default_base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
    "test_model": "doubao-seed-2.0-code",
    "is_aggregator": False,
}
```

**⚠️ 注意**：`website` 字段必须使用官方产品首页，不要使用带 `utm_` 参数的活动推广链接（如 `https://www.volcengine.com/activity/ai618?utm_campaign=...`）。

### 2. 模型 ID 命名规范

火山方舟的模型 ID 是 **带日期后缀的小写连字符格式**，例如：
- ✅ 正确：`doubao-seed-2-1-turbo-260628`
- ❌ 错误：`Doubao-Seed-2.1-turbo`（驼峰 + 点号，会返回 404）
- ❌ 错误：`doubao-seed-3-5-250515`（不存在，会返回 404）

**v2.0/v3.0 接入时**：务必让用户在控制台确认模型的精确 ID，不要凭印象推断。

### 3. 模型列表拉取与过滤（`app/services/config_service.py`）

火山方舟支持通过 `/models` 端点自动拉取可用模型列表，但需要做两层过滤：

```python
def _filter_popular_models(models, provider):
    # 1. 通用前缀过滤
    model_prefixes = ["gpt-", "claude-", "gemini-", "qwen-", "deepseek-",
                      "doubao-", "ep-", ...]  # 必须包含 doubao- 和 ep-

    # 2. Coding Plan 专项白名单过滤
    if provider == "volcengine_coding":
        coding_whitelist = [
            "doubao-seed-2.0-code",
            "doubao-1.5-pro-code",
            "glm-5.2",
            "kimi-k2.7-code",
            ...
        ]
        models = [m for m in models if m in coding_whitelist]
        # 排除 2.1 版本（Coding Plan 不支持）
        models = [m for m in models if "doubao-seed-2.1" not in m.lower()]

    # 3. 拉取结果默认倒序，最新的应放最上面
    models = list(reversed(models))
    return models
```

## 🧠 reasoning_effort 参数详解（核心特性）

### 背景

`doubao-seed-2.x` 系列是**推理模型（Reasoning Models）**，会先进行深度思考（产生 reasoning_tokens）再输出最终答案。这导致：

- **默认响应时间极长**：单次响应可达 **165 秒**，远超默认 60 秒超时
- **token 消耗巨大**：单次 reasoning_tokens 可达 7597

### reasoning_effort 参数

火山方舟通用参数 `reasoning_effort` 控制思考深度：

| 取值 | 说明 | 适用场景 |
|------|------|---------|
| `none` | 不思考 | 简单查询 |
| `minimal` | 最小思考 | 快速任务 |
| `low` | 浅度思考（**推荐默认值**） | 常规分析 |
| `medium` | 中度思考 | 复杂分析 |
| `high` | 深度思考 | 关键决策 |
| `xhigh` | 极深度思考 | 极复杂推理 |
| `max` | 最大思考 | 最高质量需求 |

### 性能对比实测

| 配置 | 响应时间 | reasoning_tokens | 提速 | token 减少 |
|------|---------|------------------|------|-----------|
| 不设置 | 165.3s | 7597 | - | - |
| `low` | 74.3s | 3310 | **55%** | **52%** |

**结论**：对 `doubao-seed-2.x` 模型，**建议默认设置 `reasoning_effort=low`**，可同时大幅降低响应时间和 token 消耗。

### 数据模型字段（`app/models/config.py`）

```python
class LLMConfig(BaseModel):
    reasoning_effort: Optional[str] = Field(
        default=None,
        description="推理模型思考深度 (none/minimal/low/medium/high/xhigh/max)，仅火山方舟推理模型支持"
    )
```

⚠️ 该字段必须同时添加到：
- `LLMConfig`（数据库模型）
- `LLMConfigRequest`（请求模型）
- `LLMProviderRequest` / `LLMProviderResponse`（含 `test_model` 字段，否则界面修改不生效）

### 数据库更新语法

更新嵌套数组中的子字段时，需使用 MongoDB 位置操作符 `$`：

```javascript
db.system_configs.updateOne(
  {"is_active": true, "llm_configs.model_name": "doubao-seed-2-1-turbo-260628"},
  {$set: {"llm_configs.$.reasoning_effort": "low"}}
)
```

### 数据库验证脚本（`data/temp/check_db.py`）

更新完数据库后，务必用验证脚本确认 `reasoning_effort` 已正确写入。脚本位置：[data/temp/check_db.py](file:///c:/TradingAgentsCN/data/temp/check_db.py)

```python
import os, sys
sys.path.insert(0, r"c:\TradingAgentsCN")
os.chdir(r"c:\TradingAgentsCN")
from dotenv import load_dotenv
load_dotenv()
from app.core.config import settings
from pymongo import MongoClient

print(f"MONGO_URI: {settings.MONGO_URI}")
print(f"MONGO_DB: {settings.MONGO_DB}")

c = MongoClient(settings.MONGO_URI)
db = c[settings.MONGO_DB]

# 确保更新的是正确的数据库
config = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
print(f"\nConfig version: {config.get('version')}")
print(f"Config _id: {config.get('_id')}")

for lc in config.get("llm_configs", []):
    if "doubao-seed-2" in lc.get("model_name", ""):
        print(f"  {lc['model_name']}: reasoning_effort={lc.get('reasoning_effort', 'N/A')}")

c.close()
```

**预期输出**（4 个 doubao-seed-2 模型都已设置）：
```
Config version: 1
Config _id: 65f...
  doubao-seed-2-1-turbo-260628: reasoning_effort=low
  doubao-seed-2-1-flash-250628: reasoning_effort=low
  doubao-seed-2-1-pro-250628: reasoning_effort=low
  doubao-seed-2-0-code: reasoning_effort=low
```

⚠️ 如果输出 `reasoning_effort=N/A`，说明数据库未更新成功，需检查：
1. 是否更新了正确的数据库（v3.0 使用端口 27019，禁止操作主开发库 27017）
2. `is_active: true` 的配置文档是否是最新版本
3. MongoDB 位置操作符 `$` 的匹配条件是否正确

### 批量更新脚本

一次性更新所有 `doubao-seed-2.x` 模型的 `reasoning_effort`：

```javascript
// MongoDB Shell
db.system_configs.updateMany(
  {
    "is_active": true,
    "llm_configs.model_name": {$regex: "doubao-seed-2"}
  },
  {$set: {"llm_configs.$[elem].reasoning_effort": "low"}}
)
```

⚠️ `updateMany` + 数组过滤需使用 `$[elem]` filtered position operator（MongoDB 3.6+），而不是 `$`（只更新第一个匹配项）。如需更新多个数组元素，必须用 `$[elem]` 配合 `arrayFilters`：

```javascript
db.system_configs.updateOne(
  {"is_active": true},
  {$set: {"llm_configs.$[elem].reasoning_effort": "low"}},
  {arrayFilters: [{"elem.model_name": {$regex: "doubao-seed-2"}}]}
)
```

### 日志验证方法

更新数据库并重启后端后，发起一次分析任务，在日志中确认 `reasoning_effort` 生效。

**日志位置**：[logs/tradingagents.log](file:///c:/TradingAgentsCN/logs/tradingagents.log)

搜索关键字：
```powershell
# PowerShell 查看最近 reasoning_effort 相关日志
Select-String -Path .\logs\tradingagents.log -Pattern "reasoning_effort" -Tail 20
```

**正常日志示例**：
```
🔧 [模型配置] doubao-seed-2-1-turbo-260628 reasoning_effort=low
```

**异常日志示例**（说明配置未生效）：
```
🔧 [模型配置] doubao-seed-2-1-turbo-260628 reasoning_effort=None
```

如果出现 `reasoning_effort=None`，参考 FAQ Q4 排查（通常是分析任务运行时数据库尚未更新，重启后端重试即可）。

## 🔗 reasoning_effort 完整数据流

```
DB (system_configs.llm_configs[].reasoning_effort)
    ↓
service 层 (_load_model_config_from_db / 直接读取)
    ↓
config dict (quick_model_config / deep_model_config)
    ↓
TradingAgentsGraph.__init__ (从 config 读取)
    ↓
_quick_extra / _deep_extra 字典
    ↓
_create_provider_pair(quick_extra_kwargs=..., deep_extra_kwargs=...)
    ↓
create_llm_by_provider(**extra_kwargs)
    ↓
create_llm_client(**kwargs) → OpenAIClient
    ↓
OpenAIClient.get_llm() → model_kwargs={"reasoning_effort": ...}
    ↓
langchain_openai.ChatOpenAI(model_kwargs={"reasoning_effort": ...})
    ↓
API 请求体 {"reasoning_effort": "low"}
```

## 📁 修改文件清单

接入火山方舟需要修改以下文件：

### 后端核心

| 文件 | 修改内容 |
|------|---------|
| [app/scripts/init_providers.py](file:///c:/TradingAgentsCN/app/scripts/init_providers.py) | 注册 volcengine 和 volcengine_coding 两个 provider |
| [app/services/config_service.py](file:///c:/TradingAgentsCN/app/services/config_service.py) | 模型列表过滤逻辑，Coding Plan 白名单 + 排除 2.1 |
| [app/models/config.py](file:///c:/TradingAgentsCN/app/models/config.py) | `LLMConfig` / `LLMConfigRequest` / `LLMProviderRequest` / `LLMProviderResponse` 添加 `reasoning_effort` 和 `test_model` 字段 |

### LLM 客户端

| 文件 | 修改内容 |
|------|---------|
| [tradingagents/llm_clients/openai_client.py](file:///c:/TradingAgentsCN/tradingagents/llm_clients/openai_client.py) | 默认 timeout 60s→300s；通过 `model_kwargs` 传递 `reasoning_effort` |

关键代码：
```python
DEFAULT_TIMEOUT = 300  # 推理模型可能需要长时间思考
DEFAULT_MAX_RETRIES = 2

# 在 get_llm() 方法中
model_kwargs = {}
if "reasoning_effort" in self.kwargs and self.kwargs["reasoning_effort"]:
    model_kwargs["reasoning_effort"] = self.kwargs["reasoning_effort"]
if model_kwargs:
    llm_kwargs["model_kwargs"] = model_kwargs
```

### 图引擎

| 文件 | 修改内容 |
|------|---------|
| [tradingagents/graph/trading_graph.py](file:///c:/TradingAgentsCN/tradingagents/graph/trading_graph.py) | 从 config 读取 reasoning_effort，通过 `_quick_extra`/`_deep_extra` 传递到所有 7 个 provider 分支 |

关键代码：
```python
# __init__ 中
quick_reasoning_effort = quick_config.get("reasoning_effort")
deep_reasoning_effort = deep_config.get("reasoning_effort")

_quick_extra = {}
_deep_extra = {}
if quick_reasoning_effort:
    _quick_extra["reasoning_effort"] = quick_reasoning_effort
if deep_reasoning_effort:
    _deep_extra["reasoning_effort"] = deep_reasoning_effort

# 所有 7 个 provider 分支的 _create_provider_pair 调用都加上：
quick_extra_kwargs=_quick_extra if _quick_extra else None,
deep_extra_kwargs=_deep_extra if _deep_extra else None,
```

### 服务层（3 个调用点）

| 文件 | 修改内容 |
|------|---------|
| [app/services/simple_analysis_service.py](file:///c:/TradingAgentsCN/app/services/simple_analysis_service.py) | 新增 `_load_model_config_from_db()` 函数，从数据库读取 reasoning_effort |
| [app/services/analysis_service.py](file:///c:/TradingAgentsCN/app/services/analysis_service.py) | 3 个调用点都从 MongoDB 读取模型配置，含 reasoning_effort |

服务层读取配置的关键代码：
```python
def _load_model_config_from_db(model_name: str) -> dict:
    """从数据库读取模型配置参数"""
    doc = collection.find_one({"is_active": True}, sort=[("version", -1)])
    if doc and "llm_configs" in doc:
        for config_dict in doc["llm_configs"]:
            if config_dict.get("model_name") == model_name:
                result = {
                    "max_tokens": config_dict.get("max_tokens", 4000),
                    "temperature": config_dict.get("temperature", 0.7),
                    "timeout": config_dict.get("timeout", 180),
                    "retry_times": config_dict.get("retry_times", 3),
                    "api_base": config_dict.get("api_base"),
                }
                re = config_dict.get("reasoning_effort")
                if re:
                    result["reasoning_effort"] = re
                return result
    return {}
```

### 风险管理 Agent

| 文件 | 修改内容 |
|------|---------|
| [tradingagents/agents/managers/risk_manager.py](file:///c:/TradingAgentsCN/tradingagents/agents/managers/risk_manager.py) | 增加 None 检查和耗时日志，避免空响应导致误报 |

```python
if response is None:
    logger.warning(f"⚠️ [Risk Manager] LLM响应为 None (耗时 {elapsed_time:.2f}秒)")
    response_content = ""
elif hasattr(response, 'content') and response.content:
    response_content = response.content.strip()
```

### 前端

| 文件 | 修改内容 |
|------|---------|
| [frontend/src/api/config.ts](file:///c:/TradingAgentsCN/frontend/src/api/config.ts) | `LLMProvider` 接口添加 `test_model`、`api_key`、`api_secret` 字段 |
| 前端 ProviderDialog.vue | 添加测试模型输入框 |

## ❓ 常见问题与解决方案（FAQ）

### Q1：界面修改测试模型不生效，仍用旧的 gpt-3.5-turbo

**原因**：`LLMProviderRequest` 没有 `test_model` 字段，Pydantic `model_dump(exclude_unset=True)` 直接丢弃。

**修复**：在 `LLMProviderRequest` 和 `LLMProviderResponse` 都添加 `test_model` 字段，路由构建响应时传入 `provider.test_model`。

### Q2：模型返回 404 Not Found

**原因**：模型 ID 拼写错误。火山方舟的模型 ID 是带日期后缀的小写连字符格式。

**修复**：使用正确的模型 ID，如 `doubao-seed-2-1-turbo-260628`。让用户在控制台确认精确 ID。

### Q3：Risk Manager 报 "LLM响应为空或无效"

**原因**：`doubao-seed-2.x` 是推理模型，单次响应 165 秒，远超默认 60 秒超时，导致空响应。

**修复**：
1. `openai_client.py` 默认 timeout 60s → 300s
2. 设置 `reasoning_effort=low`，响应时间降至 74 秒（提速 55%）

### Q4：日志显示 reasoning_effort=None，但数据库确实有值

**原因**：分析任务运行时，数据库尚未写入 reasoning_effort（运行中读取的是旧数据）。

**修复**：重启后端后重新运行分析任务。

### Q5：Coding Plan 模型列表包含 2.1 版本导致调用失败

**原因**：Coding Plan 不支持 2.1 版本模型。

**修复**：在 `_filter_popular_models` 中对 `volcengine_coding` 厂家加白名单过滤 + 排除 `doubao-seed-2.1`。

### Q6：Tushare 报 `[Errno 13] Permission denied: 'C:\\Users\\hsliu\\tk.csv'`

**原因**：tushare 的 `upass.py` 会尝试在用户主目录写文件，权限不足。

**修复**：monkey patch tushare 的 `upass.py`，避免在用户主目录写文件。

### Q7：模型列表拉取不到

**原因**：模型列表过滤逻辑没有包含 `doubao-` 和 `ep-` 前缀。

**修复**：在 `_filter_popular_models` 的 `model_prefixes` 中添加这两个前缀。

### Q8：拉取的模型顺序是倒序，最新模型在最后

**原因**：API 返回顺序问题。

**修复**：过滤后执行 `models = list(reversed(models))`，让最新模型在最上面。

## ✅ v2.0 / v3.0 接入 Checklist

接入新版本时，按以下顺序逐项检查：

### 第 1 步：Provider 注册
- [ ] 在 `init_providers.py` 注册 `volcengine` 和 `volcengine_coding`
- [ ] `website` 使用官方首页（不带 utm_ 参数）
- [ ] `default_base_url` 正确（注意 Coding Plan 是 `/api/coding/v3`）
- [ ] `test_model` 使用正确的模型 ID

### 第 2 步：数据模型
- [ ] `LLMConfig` 添加 `reasoning_effort` 字段
- [ ] `LLMConfigRequest` 添加 `reasoning_effort` 字段
- [ ] `LLMProvider` / `LLMProviderRequest` / `LLMProviderResponse` 添加 `test_model` 字段

### 第 3 步：模型列表过滤
- [ ] `_filter_popular_models` 的 `model_prefixes` 包含 `doubao-` 和 `ep-`
- [ ] `volcengine_coding` 厂家加白名单过滤
- [ ] 排除 `doubao-seed-2.1` 版本
- [ ] 拉取结果反转，最新模型在最上面

### 第 4 步：LLM 客户端
- [ ] `openai_client.py` 默认 timeout 设为 300 秒
- [ ] 通过 `model_kwargs` 传递 `reasoning_effort` 到 API

### 第 5 步：图引擎
- [ ] `trading_graph.py` 的 `__init__` 读取 `reasoning_effort`
- [ ] 所有 7 个 provider 分支都传递 `quick_extra_kwargs` / `deep_extra_kwargs`

### 第 6 步：服务层
- [ ] `simple_analysis_service.py` 实现 `_load_model_config_from_db()`
- [ ] `analysis_service.py` 3 个调用点都从数据库读取配置
- [ ] 配置字典含 `reasoning_effort` 字段

### 第 7 步：前端
- [ ] `LLMProvider` 接口添加 `test_model`、`api_key`、`api_secret`
- [ ] `ProviderDialog.vue` 添加测试模型输入框
- [ ] （可选）模型配置界面添加 `reasoning_effort` 配置项

### 第 8 步：数据库初始化
- [ ] 对所有 `doubao-seed-2.x` 模型设置 `reasoning_effort=low`
- [ ] 使用 MongoDB 位置操作符 `$` 更新嵌套数组字段

### 第 9 步：验证测试（端到端）

**9.1 数据库层验证**
- [ ] 运行 `data/temp/check_db.py`，4 个 doubao-seed-2 模型均显示 `reasoning_effort=low`
- [ ] 确认更新的是 v3.0 专用数据库（端口 27019），未污染主开发库（27017）

**9.2 连接测试**
- [ ] 管理界面的 provider 连接测试通过（使用 `test_model` 配置的模型）
- [ ] 测试模型 ID 正确（如 `doubao-seed-2-1-turbo-260628`），不返回 404

**9.3 功能测试**
- [ ] 工具调用（function calling）正常
- [ ] 分析任务完整跑通（含 Risk Manager，不报"LLM响应为空或无效"）

**9.4 性能与参数验证**
- [ ] 后端重启后发起一次分析任务
- [ ] 日志 `logs/tradingagents.log` 显示 `reasoning_effort=low`（而非 `None`）
- [ ] 单次 LLM 响应时间 < 100 秒（推理模型 reasoning_effort=low 预期 ~74 秒）
- [ ] reasoning_tokens 显著减少（对比不设置时的 7597，设置 low 后约 3310）

**9.5 模型列表验证**
- [ ] `volcengine` 厂家模型列表包含 doubao- / ep- 前缀模型
- [ ] `volcengine_coding` 厂家模型列表仅含 Coding Plan 白名单模型
- [ ] Coding Plan 列表不含 `doubao-seed-2.1` 版本
- [ ] 模型列表最新模型在最上面（非倒序）

## 📌 关键经验总结

1. **推理模型必须调超时**：默认 60 秒远不够，需调到 300 秒
2. **reasoning_effort 是降本利器**：`low` 可同时提速 55%、减少 token 52%
3. **模型 ID 务必精确**：火山方舟的模型 ID 带日期后缀，不能凭印象推断
4. **两种套餐模型范围不同**：Coding Plan 仅 ~10 个模型，不支持 2.1 版本
5. **Pydantic 字段必须同步**：Request/Response/Provider 三个模型都要加 `test_model`，否则界面修改不生效
6. **服务层必须从 DB 读取**：不能依赖 JSON 文件或硬编码默认值，否则数据库配置不生效
7. **全链路验证**：reasoning_effort 涉及 5 个文件的链路传递，任何一环缺失都会导致参数失效

## 🔗 参考链接

- [火山方舟官方文档](https://www.volcengine.com/solutions/ark)
- [火山方舟 API 文档](https://console.volcengine.com/ark/region:cn-beijing/docs)
- [reasoning_effort 参数说明](https://console.volcengine.com/ark/region:cn-beijing/docs/82379/1330310)
