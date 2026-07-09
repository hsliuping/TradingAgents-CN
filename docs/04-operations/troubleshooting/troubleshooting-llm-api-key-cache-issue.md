# LLM API Key 缓存问题说明

## 📋 问题描述

当您在数据库中更新 LLM 提供商的 API Key 后，运行中的 Agent 仍然使用旧的 API Key，导致 401 错误。

### 错误日志示例

```json
{"time": "2026-02-10 07:22:07", "name": "core.agents.base", "level": "ERROR", "message": "❌ [social_analyst_v2] LLM API 调用失败"}
{"time": "2026-02-10 07:22:07", "name": "core.agents.base", "level": "ERROR", "message": "   错误信息: Error code: 401 - {'error': {'message': 'Incorrect API key provided...', 'code': 'invalid_api_key'}}"}
```

## 🔍 问题根源

### 1. LLM 实例缓存机制

在 `core/workflow/builder.py` 中，`WorkflowBuilder` 会缓存 LLM 实例：

```python
# 第 126-128 行
if not force_refresh and self._quick_llm and self._deep_llm:
    logger.debug("[依赖提供者] LLM 实例已存在且不需要刷新，使用缓存")
    return  # ⚠️ 直接返回，不重新从数据库读取配置
```

### 2. API Key 获取流程

```
WorkflowBuilder._create_llm_instances()
  │
  ├─> get_provider_and_url_by_model_sync(model_name)  # 从数据库读取配置
  │   │
  │   ├─> 查询 llm_configs 集合（模型配置）
  │   ├─> 查询 llm_providers 集合（厂商配置）
  │   └─> 回退到环境变量 DASHSCOPE_API_KEY
  │
  └─> create_llm_by_provider(api_key=...)  # 创建 LLM 实例
      └─> 缓存 LLM 实例（self._quick_llm, self._deep_llm）
```

### 3. 缓存生命周期

- **创建时机**：首次执行工作流时创建
- **缓存位置**：`WorkflowBuilder` 实例的 `_quick_llm` 和 `_deep_llm` 属性
- **缓存时长**：直到后端服务重启或 `WorkflowBuilder` 实例被销毁

## ✅ 解决方案

### 方案 1：重启后端服务（推荐）

更新 API Key 后，重启后端服务以清除所有缓存：

```powershell
# 停止后端服务
# 按 Ctrl+C 停止 uvicorn

# 重新启动后端服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 方案 2：添加 LLM 配置刷新 API（待实现）

可以添加一个 API 端点来强制刷新 LLM 配置：

```python
# app/routers/config.py

@router.post("/llm/refresh")
async def refresh_llm_config():
    """刷新 LLM 配置（清除缓存）"""
    # 清除 WorkflowBuilder 的 LLM 缓存
    # 下次执行工作流时会重新从数据库读取配置
    pass
```

### 方案 3：使用环境变量（临时方案）

如果需要立即生效，可以：

1. 更新 `.env` 文件中的 `DASHSCOPE_API_KEY`
2. 重启后端服务

```env
# .env
DASHSCOPE_API_KEY=sk-新的API密钥
```

## 🎯 最佳实践

### 1. 更新 API Key 的正确流程

```
1. 在 Web 界面更新 API Key
   └─> 系统管理 → LLM 配置 → 编辑厂商配置

2. 测试 API Key
   └─> 点击"测试连接"按钮，确认新 API Key 有效

3. 重启后端服务
   └─> 确保所有缓存的 LLM 实例使用新的 API Key

4. 验证
   └─> 运行一个分析任务，检查日志确认使用新的 API Key
```

### 2. 验证 API Key 是否生效

查看日志中的 API Key 来源：

```json
{"message": "[依赖提供者] 创建 LLM:"}
{"message": "  - Quick API Key 来源: 数据库配置"}  // ✅ 应该显示"数据库配置"
{"message": "  - Quick API Key: 已配置 (前3位: sk-)"}
```

### 3. 避免 API Key 冲突

确保只在一个地方配置 API Key：

- ✅ **推荐**：在数据库中配置（通过 Web 界面）
- ⚠️ **不推荐**：在 `.env` 文件中配置（会被数据库配置覆盖）

## 📝 相关代码位置

| 文件 | 说明 |
|------|------|
| `core/workflow/builder.py` | LLM 实例缓存逻辑（第 111-210 行） |
| `app/services/simple_analysis_service.py` | API Key 获取逻辑（第 100-330 行） |
| `tradingagents/llm_adapters/dashscope_openai_adapter.py` | DashScope LLM 初始化（第 54-68 行） |

## 🔧 未来改进

1. **自动刷新机制**：检测到数据库配置变更时自动刷新 LLM 实例
2. **配置版本号**：为 LLM 配置添加版本号，变更时自动失效缓存
3. **热重载**：支持不重启服务即可刷新 LLM 配置

---

**最后更新**: 2026-02-10  
**相关问题**: LLM API Key 更新后仍然使用旧密钥

