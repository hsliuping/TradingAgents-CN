# 调试模式日志参考

**快速参考**: 如何通过日志验证调试模式是否正常工作

---

## 🔍 关键日志标识

### ✅ 正常工作的日志序列

```
1️⃣ [调试接口] AgentContext 创建
   🔍 [调试接口] AgentContext 参数:
      is_debug_mode: True
      debug_template_id: 67791e5e8e0e5e0e5e0e5e0f

2️⃣ [工作流] AgentContext 传递
   🔍 [工作流输入] 创建 AgentContext: 
      debug_mode=True, template_id=67791e5e8e0e5e0e5e0e5e0f

3️⃣ [Agent] 调试模式识别
   🔍 [social_analyst_v2] 调试模式已启用，模板ID: 67791e5e8e0e5e0e5e0e5e0f

4️⃣ [模板系统] 调试模板获取
   🔍 [调试模式] 使用调试模板ID: 67791e5e8e0e5e0e5e0e5e0f
   ✅ [调试模式] 成功获取调试模板: analysts_v2/social_analyst_v2
```

---

## ❌ 常见错误日志

### 错误1: context 未传递

```
❌ 缺少日志：
   - 没有 "🔍 [social_analyst_v2] 调试模式已启用"
   - 没有 "🔍 [调试模式] 使用调试模板ID"

✅ 解决方案：
   - 检查 Agent 的 _build_system_prompt 方法是否传递了 context 参数
   - 检查 get_agent_prompt 调用是否包含 context=context
```

### 错误2: 模板不存在

```
⚠️ [调试模式] 调试模板不存在: 67791e5e8e0e5e0e5e0e5e0f，降级到正常流程

✅ 解决方案：
   - 在 MongoDB 中查询 prompt_templates 集合
   - 确认 template_id 是否存在
   - 检查前端传递的 template_id 是否正确
```

### 错误3: 模板ID格式错误

```
❌ [调试模式] 获取调试模板失败: invalid ObjectId

✅ 解决方案：
   - 确认 template_id 是有效的 24 位十六进制字符串
   - 检查前端是否正确传递了 template_id
```

---

## 🔧 调试命令

### 查看实时日志

```bash
# Windows PowerShell
Get-Content logs\app.log -Tail 50 -Wait | Select-String "调试|debug"

# Linux/Mac
tail -f logs/app.log | grep -i "调试\|debug"
```

### 搜索特定模板ID的日志

```bash
# Windows PowerShell
Select-String -Path logs\app.log -Pattern "67791e5e8e0e5e0e5e0e5e0f"

# Linux/Mac
grep "67791e5e8e0e5e0e5e0e5e0f" logs/app.log
```

### 查看最近的调试会话

```bash
# Windows PowerShell
Get-Content logs\app.log -Tail 200 | Select-String "调试接口|AgentContext"

# Linux/Mac
tail -200 logs/app.log | grep "调试接口\|AgentContext"
```

---

## 📊 日志级别说明

| 级别 | 标识 | 含义 |
|------|------|------|
| INFO | `🔍` | 调试信息（正常流程） |
| INFO | `✅` | 成功操作 |
| WARNING | `⚠️` | 警告（降级处理） |
| ERROR | `❌` | 错误（失败） |

---

## 🎯 快速诊断流程

1. **检查是否启用调试模式**
   ```
   搜索: "is_debug_mode: True"
   ```

2. **检查模板ID是否传递**
   ```
   搜索: "debug_template_id: <你的模板ID>"
   ```

3. **检查Agent是否识别**
   ```
   搜索: "[<agent_id>] 调试模式已启用"
   ```

4. **检查模板是否获取成功**
   ```
   搜索: "成功获取调试模板"
   ```

---

## 📝 日志文件位置

- **开发环境**: `logs/app.log`
- **Docker 环境**: `/app/logs/app.log`
- **便携版**: `logs/app.log`

---

**最后更新**: 2026-01-09

