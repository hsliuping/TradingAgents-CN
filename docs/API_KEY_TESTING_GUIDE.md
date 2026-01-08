# API Key 配置管理测试指南

## 📋 测试目标

验证 API Key 配置管理的完整流程，确保：
1. ✅ MongoDB 和 .env 配置来源明确区分
2. ✅ 配置验证正确显示颜色（绿色/黄色/红色）
3. ✅ 编辑对话框正确显示缩略 Key
4. ✅ 用户清空/填写 Key 的行为符合预期

---

## 🧪 测试场景

### 场景 1：MongoDB 有 Key，.env 也有 Key

**初始状态**：
- MongoDB `deepseek` 厂家：`api_key = "sk-abc123...xyz789"`
- .env 文件：`DEEPSEEK_API_KEY=sk-def456...uvw012`

**测试步骤**：
1. 访问"设置 → 配置验证"
2. 点击"验证配置"按钮

**预期结果**：
- ✅ `deepseek` 厂家显示 **绿色**"已配置"
- ✅ `source` 字段为 `"database"`
- ✅ `mongodb_configured` 为 `true`
- ✅ `env_configured` 为 `true`
- ✅ 系统实际使用 MongoDB 中的 Key（优先级更高）

---

### 场景 2：MongoDB 无 Key，.env 有 Key

**初始状态**：
- MongoDB `dashscope` 厂家：`api_key = ""` 或 `null`
- .env 文件：`DASHSCOPE_API_KEY=sk-ghi789...rst345`

**测试步骤**：
1. 访问"设置 → 配置验证"
2. 点击"验证配置"按钮

**预期结果**：
- ✅ `dashscope` 厂家显示 **黄色**"已配置（环境变量）"
- ✅ `source` 字段为 `"environment"`
- ✅ `mongodb_configured` 为 `false`
- ✅ `env_configured` 为 `true`
- ✅ 警告信息："大模型厂家 百炼 使用环境变量配置，建议在数据库中配置以便统一管理"
- ✅ 系统实际使用 .env 中的 Key

---

### 场景 3：MongoDB 和 .env 都无 Key

**初始状态**：
- MongoDB `openai` 厂家：`api_key = ""` 或 `null`
- .env 文件：无 `OPENAI_API_KEY` 或值为占位符

**测试步骤**：
1. 访问"设置 → 配置验证"
2. 点击"验证配置"按钮

**预期结果**：
- ✅ `openai` 厂家显示 **红色**"未配置"
- ✅ `source` 字段为 `null`
- ✅ `mongodb_configured` 为 `false`
- ✅ `env_configured` 为 `false`
- ✅ 警告信息："大模型厂家 OpenAI 已启用但未配置有效的 API Key（数据库和环境变量中都未找到）"

---

### 场景 4：编辑厂家 - MongoDB 有 Key

**初始状态**：
- MongoDB `deepseek` 厂家：`api_key = "sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"`

**测试步骤**：
1. 访问"设置 → 大模型厂家管理"
2. 点击"编辑" `deepseek` 厂家
3. 查看 API Key 输入框

**预期结果**：
- ✅ API Key 输入框显示：`sk-abc1...4yz`（前6位 + "..." + 后6位）
- ✅ 用户知道已有配置

---

### 场景 5：编辑厂家 - MongoDB 无 Key，.env 有 Key

**初始状态**：
- MongoDB `dashscope` 厂家：`api_key = ""` 或 `null`
- .env 文件：`DASHSCOPE_API_KEY=sk-def456ghi789jkl012mno345pqr678stu901vwx234yz567`

**测试步骤**：
1. 访问"设置 → 大模型厂家管理"
2. 点击"编辑" `dashscope` 厂家
3. 查看 API Key 输入框

**预期结果**：
- ✅ API Key 输入框显示：`sk-def4...z567`（前6位 + "..." + 后6位）
- ✅ 用户知道环境变量中已有配置

---

### 场景 6：用户清空 MongoDB 中的 Key

**初始状态**：
- MongoDB `deepseek` 厂家：`api_key = "sk-abc123...xyz789"`
- .env 文件：`DEEPSEEK_API_KEY=sk-def456...uvw012`

**测试步骤**：
1. 访问"设置 → 大模型厂家管理"
2. 点击"编辑" `deepseek` 厂家
3. 清空 API Key 输入框（删除所有内容）
4. 点击"保存"
5. 访问"设置 → 配置验证"
6. 点击"验证配置"按钮

**预期结果**：
- ✅ MongoDB 中的 `api_key` 被清空（变为 `""` 或 `null`）
- ✅ `deepseek` 厂家显示 **黄色**"已配置（环境变量）"
- ✅ `source` 字段为 `"environment"`
- ✅ `mongodb_configured` 为 `false`
- ✅ `env_configured` 为 `true`
- ✅ 系统实际使用 .env 中的 Key

---

### 场景 7：用户填写 MongoDB 中的 Key

**初始状态**：
- MongoDB `dashscope` 厂家：`api_key = ""` 或 `null`
- .env 文件：`DASHSCOPE_API_KEY=sk-old123...old789`

**测试步骤**：
1. 访问"设置 → 大模型厂家管理"
2. 点击"编辑" `dashscope` 厂家
3. 填写新的 API Key：`sk-new456ghi789jkl012mno345pqr678stu901vwx234yz567`
4. 点击"保存"
5. 访问"设置 → 配置验证"
6. 点击"验证配置"按钮

**预期结果**：
- ✅ MongoDB 中的 `api_key` 被更新为新值
- ✅ `dashscope` 厂家显示 **绿色**"已配置"
- ✅ `source` 字段为 `"database"`
- ✅ `mongodb_configured` 为 `true`
- ✅ `env_configured` 为 `true`
- ✅ 系统实际使用 MongoDB 中的新 Key（优先级更高）

---

### 场景 8：用户不修改缩略 Key（保持原值）

**初始状态**：
- MongoDB `deepseek` 厂家：`api_key = "sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"`

**测试步骤**：
1. 访问"设置 → 大模型厂家管理"
2. 点击"编辑" `deepseek` 厂家
3. API Key 输入框显示：`sk-abc1...4yz`
4. 不修改 API Key，修改其他字段（如 `display_name`）
5. 点击"保存"

**预期结果**：
- ✅ MongoDB 中的 `api_key` **保持不变**（不被更新）
- ✅ 其他字段（如 `display_name`）被正确更新
- ✅ 后端识别到截断 Key（包含 `...`），自动跳过更新

---

### 场景 9：数据源配置 - MongoDB 无 Key，.env 有 Key

**初始状态**：
- MongoDB `tushare` 数据源：`api_key = ""` 或 `null`
- .env 文件：`TUSHARE_TOKEN=d1el869r01qghj41hahgd1el869r01qghj41hai0`

**测试步骤**：
1. 访问"设置 → 数据源管理"
2. 点击"编辑" `tushare` 数据源
3. 查看 API Key 输入框

**预期结果**：
- ✅ API Key 输入框显示：`d1el86...j41hai0`（前6位 + "..." + 后6位）
- ✅ 用户知道环境变量中已有配置

---

### 场景 10：数据源配置验证 - MongoDB 无 Key，.env 有 Key

**初始状态**：
- MongoDB `tushare` 数据源：`api_key = ""` 或 `null`
- .env 文件：`TUSHARE_TOKEN=d1el869r01qghj41hahgd1el869r01qghj41hai0`

**测试步骤**：
1. 访问"设置 → 配置验证"
2. 点击"验证配置"按钮

**预期结果**：
- ✅ `tushare` 数据源显示 **黄色**"已配置（环境变量）"
- ✅ `source` 字段为 `"environment"`
- ✅ `mongodb_configured` 为 `false`
- ✅ `env_configured` 为 `true`
- ✅ 警告信息："数据源 Tushare 使用环境变量配置，建议在数据库中配置以便统一管理"

---

## 🔍 验证方法

### 方法 1：查看后端日志

重启后端服务，观察配置桥接日志：

```
🔧 开始桥接配置到环境变量...
  📊 从数据库读取到 8 个厂家配置
  ✓ 使用 .env 文件中的 DEEPSEEK_API_KEY (长度: 64)
  ✓ 使用数据库厂家配置的 DASHSCOPE_API_KEY (长度: 56)
  📊 从数据库读取到 3 个数据源配置
  ✓ 使用 .env 文件中的 TUSHARE_TOKEN (长度: 40)
```

### 方法 2：查看前端配置验证页面

访问"设置 → 配置验证"，观察：
- 绿色项：MongoDB 中有配置
- 黄色项：MongoDB 中无配置，.env 中有配置
- 红色项：都没有配置

### 方法 3：查看 API 响应

使用浏览器开发者工具，查看 API 响应：

**GET /api/config/llm/providers**：
```json
{
  "id": "...",
  "name": "deepseek",
  "api_key": "sk-abc1...4yz",  // 缩略格式
  "extra_config": {
    "has_api_key": true
  }
}
```

**GET /api/system/config/validate**：
```json
{
  "mongodb_validation": {
    "llm_providers": [
      {
        "name": "deepseek",
        "status": "已配置",
        "source": "database",
        "mongodb_configured": true,
        "env_configured": true
      },
      {
        "name": "dashscope",
        "status": "已配置（环境变量）",
        "source": "environment",
        "mongodb_configured": false,
        "env_configured": true
      }
    ]
  }
}
```

---

## ✅ 测试检查清单

- [ ] 场景 1：MongoDB 有 Key，.env 也有 Key → 显示绿色
- [ ] 场景 2：MongoDB 无 Key，.env 有 Key → 显示黄色
- [ ] 场景 3：MongoDB 和 .env 都无 Key → 显示红色
- [ ] 场景 4：编辑厂家 - MongoDB 有 Key → 显示缩略 Key
- [ ] 场景 5：编辑厂家 - MongoDB 无 Key，.env 有 Key → 显示缩略 Key
- [ ] 场景 6：用户清空 MongoDB 中的 Key → 显示黄色
- [ ] 场景 7：用户填写 MongoDB 中的 Key → 显示绿色
- [ ] 场景 8：用户不修改缩略 Key → 保持原值
- [ ] 场景 9：数据源配置 - MongoDB 无 Key，.env 有 Key → 显示缩略 Key
- [ ] 场景 10：数据源配置验证 - MongoDB 无 Key，.env 有 Key → 显示黄色

---

## 🐛 常见问题排查

### 问题 1：配置验证显示红色，但 .env 中有 Key

**可能原因**：
- .env 文件中的 Key 是占位符（如 `your_api_key_here`）
- .env 文件中的 Key 长度不够（<= 10）
- 环境变量名不正确（如 `DEEPSEEK_KEY` 而不是 `DEEPSEEK_API_KEY`）

**解决方法**：
1. 检查 .env 文件中的 Key 是否有效
2. 检查环境变量名是否正确
3. 重启后端服务，确保环境变量被正确加载

### 问题 2：编辑对话框显示空白，但配置验证显示黄色

**可能原因**：
- 前端缓存问题
- API 响应未正确处理

**解决方法**：
1. 刷新页面（Ctrl+F5）
2. 清除浏览器缓存
3. 检查浏览器开发者工具的 Network 标签，查看 API 响应

### 问题 3：用户清空 Key 后，配置验证仍显示绿色

**可能原因**：
- 未点击"重载配置"按钮
- 配置桥接未执行

**解决方法**：
1. 点击"重载配置"按钮
2. 或重启后端服务
3. 再次点击"验证配置"按钮

