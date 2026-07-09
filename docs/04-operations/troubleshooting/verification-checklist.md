# 调试模式修复验证清单

**日期**: 2026-01-09  
**修复内容**: 社交分析师调试模式支持

---

## ✅ 代码修复验证

### 1. AnalystAgent 基类

- [x] `core/agents/analyst.py` - 从 `state` 提取 `context`
- [x] `core/agents/analyst.py` - 添加调试日志
- [x] `core/agents/analyst.py` - 传递 `context` 给 `_build_system_prompt`
- [x] `core/agents/analyst.py` - 更新抽象方法签名

### 2. v2.0 分析师（共6个）

- [x] `core/agents/adapters/fundamentals_analyst_v2.py` - 传递 `context=context`
- [x] `core/agents/adapters/market_analyst_v2.py` - 传递 `context=context`
- [x] `core/agents/adapters/news_analyst_v2.py` - 传递 `context=context`
- [x] `core/agents/adapters/social_analyst_v2.py` - 传递 `context=context`
- [x] `core/agents/adapters/sector_analyst_v2.py` - 传递 `context=context`
- [x] `core/agents/adapters/index_analyst_v2.py` - 传递 `context=context`

### 3. 统一分析服务

- [x] `app/services/unified_analysis_service.py` - `_build_workflow_inputs` 创建 `AgentContext`
- [x] `app/services/unified_analysis_service.py` - `analyze` 方法添加 `user_id` 参数
- [x] `app/services/unified_analysis_service.py` - `analyze_sync` 方法添加 `user_id` 参数
- [x] `app/services/unified_analysis_service.py` - `execute_analysis_for_ab_test` 传递 `user_id`

---

## 🔍 功能验证

### 验证步骤

1. **重启后端服务**
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **打开前端模板调试页面**
   ```
   http://localhost/templates
   ```

3. **选择一个模板进行调试**
   - 选择分析师：社交媒体分析师
   - 选择模板：任意一个模板
   - 填写股票代码：000001.SZ
   - 填写分析日期：2026-01-09
   - 点击"开始调试"

4. **查看后端日志**

   应该看到以下日志序列：

   ```
   ✅ 第1层：调试接口
   🔍 [调试接口] AgentContext 参数:
      is_debug_mode: True
      debug_template_id: xxx

   ✅ 第2层：工作流输入
   🔍 [工作流输入] 创建 AgentContext: 
      debug_mode=True, template_id=xxx

   ✅ 第3层：Agent 层
   🔍 [social_analyst_v2] 调试模式已启用，模板ID: xxx

   ✅ 第4层：模板系统
   🔍 [调试模式] 使用调试模板ID: xxx
   ✅ [调试模式] 成功获取调试模板: analysts_v2/social_analyst_v2
   ```

---

## 📊 验证结果

### 成功标志

- [ ] 看到所有4层日志
- [ ] 模板系统成功获取调试模板
- [ ] 前端显示分析结果
- [ ] 分析结果使用了指定的模板

### 失败排查

如果缺少某一层日志，检查：

| 缺少的日志 | 可能原因 | 检查位置 |
|-----------|---------|---------|
| 第1层 | 调试接口未正确创建 `AgentContext` | `app/routers/templates_debug.py:213-220` |
| 第2层 | 工作流未创建 `AgentContext` | `app/services/unified_analysis_service.py:123-189` |
| 第3层 | Agent 未提取 `context` | `core/agents/analyst.py:109-136` |
| 第4层 | 模板系统未收到 `context` | 检查 `get_agent_prompt` 调用是否传递 `context` |

---

## 📝 测试用例

### 测试用例 1: 正常调试模式

**输入**:
- analyst_type: `social_analyst_v2`
- template_id: `<有效的模板ID>`
- stock: `000001.SZ`
- analysis_date: `2026-01-09`

**期望输出**:
- ✅ 所有4层日志都出现
- ✅ 使用指定的模板ID
- ✅ 返回分析报告

### 测试用例 2: 无效模板ID

**输入**:
- analyst_type: `social_analyst_v2`
- template_id: `invalid_id_123`
- stock: `000001.SZ`
- analysis_date: `2026-01-09`

**期望输出**:
- ⚠️ 看到警告日志：`调试模板不存在，降级到正常流程`
- ✅ 使用默认模板
- ✅ 返回分析报告

### 测试用例 3: 不指定模板ID

**输入**:
- analyst_type: `social_analyst_v2`
- template_id: `null`
- stock: `000001.SZ`
- analysis_date: `2026-01-09`

**期望输出**:
- ℹ️ `is_debug_mode: False`
- ✅ 使用默认模板（根据用户偏好）
- ✅ 返回分析报告

---

## 🎯 验证完成标准

- [x] 所有代码修改已完成
- [ ] 所有4层日志都能正常输出
- [ ] 调试模式能正确使用指定的模板ID
- [ ] 正常模式不受影响
- [ ] 所有6个分析师都支持调试模式

---

**验证人**: _____________  
**验证日期**: _____________  
**验证结果**: ⬜ 通过 / ⬜ 失败

---

**最后更新**: 2026-01-09

