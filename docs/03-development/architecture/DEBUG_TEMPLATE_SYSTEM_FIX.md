# 调试模板系统修复总结

## 问题描述

调试接口 `/api/templates/debug/analyst` 在调用时出现以下问题：

1. **缺失 AgentContext 参数** - 调试接口没有传递必要的参数给 Agent
2. **调试模板无法使用** - 即使指定了 `template_id`，Agent 也不会使用该模板
3. **LLM 配置错误** - 当 `backend_url` 为空时，使用了错误的 URL

## 解决方案

### 1️⃣ 添加调试模式支持

**文件**: `tradingagents/agents/utils/agent_context.py`

添加两个新字段到 `AgentContext`:
```python
is_debug_mode: bool = False  # 是否为调试模式
debug_template_id: Optional[str] = None  # 调试模式下使用的模板ID
```

**优势**:
- 支持在不修改当前使用模板的情况下测试新模板
- 调试模板优先级最高，优先于用户模板和系统模板

### 2️⃣ 修改 TemplateClient 支持调试模板

**文件**: `tradingagents/utils/template_client.py`

在 `get_effective_template()` 方法中添加调试模式逻辑:

```python
# 🔥 检查是否为调试模式
is_debug_mode = context and getattr(context, 'is_debug_mode', False)
debug_template_id = context and getattr(context, 'debug_template_id', None) if is_debug_mode else None

if is_debug_mode and debug_template_id:
    # 优先使用调试模板
    template = self.templates_collection.find_one({"_id": ObjectId(debug_template_id)})
    if template:
        return template.get("content")
```

**优先级顺序**:
1. 调试模板 (is_debug_mode=True, debug_template_id 存在)
2. 用户模板 (user_id 存在，is_active=True)
3. 系统模板 (is_system=True, status=active)

### 3️⃣ 修改调试接口传递完整参数

**文件**: `app/routers/templates_debug.py`

```python
ctx = AgentContext(
    user_id=str(user["id"]),
    preference_id="neutral",
    is_debug_mode=bool(req.template_id),  # 自动检测调试模式
    debug_template_id=req.template_id  # 传递调试模板ID
)
```

### 4️⃣ 修复 LLM backend_url 配置

**文件**: `app/routers/templates_debug.py`

当 `backend_url` 为空时，根据 `provider` 自动设置正确的 URL:

```python
provider_urls = {
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "anthropic": "https://api.anthropic.com",
}
cfg["backend_url"] = provider_urls.get(req.llm.provider, cfg.get("backend_url", ""))
```

## 工作流程

### 调试流程

1. **前端发送请求**:
   ```json
   {
     "analyst_type": "fundamentals",
     "template_id": "6919a866fa8b760161a9167c",
     "llm": {
       "provider": "dashscope",
       "model": "qwen-plus",
       "backend_url": ""
     }
   }
   ```

2. **调试接口处理**:
   - 检测到 `template_id` 存在，设置 `is_debug_mode=true`
   - 根据 `provider="dashscope"` 设置正确的 `backend_url`
   - 创建 AgentContext 并传递给 Agent

3. **Agent 获取模板**:
   - TemplateClient 检测到调试模式
   - 优先查找指定的调试模板
   - 如果调试模板不存在，自动降级到正常流程

4. **LLM 调用**:
   - 使用正确的 API 端点和参数
   - 成功调用 DashScope/OpenAI/其他提供商

## 测试验证

运行测试脚本验证功能:

```bash
python scripts/v1.0.1/test_debug_mode.py
```

**测试项**:
- ✅ AgentContext 调试模式参数
- ✅ TemplateClient 调试模式支持
- ✅ 调试模板优先级

## 提交记录

1. `96121cd` - fix: 调试接口添加缺失的AgentContext参数
2. `ccb4154` - feat: 添加调试模式支持，允许使用指定的模板进行调试
3. `25d81f2` - fix: 调试接口根据provider自动设置正确的backend_url

## 后续改进

- [ ] 添加调试模式的日志级别控制
- [ ] 支持调试模式下的性能监控
- [ ] 添加调试结果的持久化存储
- [ ] 支持调试模式下的参数回放

