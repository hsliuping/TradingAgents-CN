# 配置迁移测试指南

## 📋 概述

本文档说明如何测试配置迁移功能，验证用户在配置向导或配置管理中设置的配置是否被 TradingAgents 核心库正确使用。

## 🎯 测试目标

验证以下功能：

1. ✅ 配置向导设置的 API 密钥被 TradingAgents 使用
2. ✅ 配置管理添加的模型被 TradingAgents 使用
3. ✅ 配置更新后可以热重载（无需重启）
4. ✅ 环境变量桥接正常工作
5. ✅ 配置优先级正确（统一配置 > 环境变量）

## 🔧 实现的功能

### 1. 环境变量桥接

**文件**: `app/core/config_bridge.py`

**功能**:
- 将统一配置中的 API 密钥写入环境变量
- 将默认模型写入环境变量
- 将数据源配置写入环境变量（包括超时、重试、缓存等细节）
- 将系统运行时配置写入环境变量

**桥接的环境变量**:
```bash
# 大模型 API 密钥
OPENAI_API_KEY
ANTHROPIC_API_KEY
GOOGLE_API_KEY
DEEPSEEK_API_KEY
DASHSCOPE_API_KEY
QIANFAN_API_KEY

# 默认模型
TRADINGAGENTS_DEFAULT_MODEL
TRADINGAGENTS_QUICK_MODEL
TRADINGAGENTS_DEEP_MODEL

# 数据源基础配置
TUSHARE_TOKEN
FINNHUB_API_KEY

# 数据源细节配置（每个数据源）
{SOURCE}_TIMEOUT              # 超时时间
{SOURCE}_RATE_LIMIT           # 速率限制
{SOURCE}_MAX_RETRIES          # 最大重试次数
{SOURCE}_CACHE_TTL            # 缓存 TTL
{SOURCE}_CACHE_ENABLED        # 是否启用缓存

# TradingAgents 运行时配置
TA_HK_MIN_REQUEST_INTERVAL_SECONDS
TA_HK_TIMEOUT_SECONDS
TA_HK_MAX_RETRIES
TA_HK_RATE_LIMIT_WAIT_SECONDS
TA_HK_CACHE_TTL_SECONDS
TA_USE_APP_CACHE

# 系统配置
APP_TIMEZONE
CURRENCY_PREFERENCE
```

### 2. 启动时自动桥接

**文件**: `app/main.py`

**时机**: 后端启动时（`lifespan` 函数中）

**日志输出**:
```
🔧 开始桥接配置到环境变量...
  ✓ 桥接 DEEPSEEK_API_KEY (长度: 64)
  ✓ 桥接默认模型: deepseek-chat
  ✓ 桥接快速分析模型: qwen-turbo
  ✓ 桥接深度分析模型: qwen-plus
✅ 配置桥接完成，共桥接 4 项配置
```

### 3. 配置热重载 API

**端点**: `POST /api/config/reload`

**功能**: 重新加载配置并桥接到环境变量，无需重启服务

**前端**: 配置管理页面右上角的"重载配置"按钮

## 🧪 测试步骤

### 测试 1：配置向导设置的配置生效

#### 步骤

1. **清除现有配置**
   ```javascript
   // 在浏览器控制台执行
   localStorage.removeItem('config_wizard_completed');
   location.reload();
   ```

2. **完成配置向导**
   - 选择 DeepSeek
   - 输入 API 密钥：`sk-your-deepseek-api-key`
   - 选择 AKShare 数据源
   - 点击"完成"

3. **检查后端日志**
   ```
   🔧 开始桥接配置到环境变量...
     ✓ 桥接 DEEPSEEK_API_KEY (长度: 64)
     ✓ 桥接默认模型: deepseek-chat
   ✅ 配置桥接完成
   ```

4. **执行股票分析**
   - 访问"股票分析"页面
   - 输入股票代码：`000001`
   - 点击"开始分析"

5. **验证结果**
   - 检查后端日志，确认使用了 DeepSeek API
   - 检查分析结果是否正常返回

#### 预期结果

- ✅ 分析使用配置向导设置的 DeepSeek API 密钥
- ✅ 不需要在 `.env` 文件中设置 `DEEPSEEK_API_KEY`
- ✅ 后端日志显示正确的模型名称

### 测试 2：配置管理添加的模型生效

#### 步骤

1. **访问配置管理**
   - 访问 `/settings/config`
   - 切换到"厂家管理"标签

2. **添加新厂家**
   - 点击"添加厂家"
   - 选择预设：OpenAI
   - 输入 API 密钥：`sk-your-openai-api-key`
   - 点击"添加"

3. **添加模型配置**
   - 切换到"大模型配置"标签
   - 点击"添加模型"
   - 选择供应商：OpenAI
   - 选择模型：gpt-4
   - 点击"添加"

4. **设置为默认模型**
   - 在模型列表中找到 gpt-4
   - 点击"设为默认"

5. **重载配置**
   - 点击页面右上角的"重载配置"按钮
   - 等待成功提示

6. **执行股票分析**
   - 访问"股票分析"页面
   - 执行分析

#### 预期结果

- ✅ 分析使用新添加的 OpenAI GPT-4 模型
- ✅ 使用配置管理中设置的 API 密钥
- ✅ 无需重启后端服务

### 测试 3：配置热重载

#### 步骤

1. **修改现有配置**
   - 在配置管理中修改 API 密钥
   - 或者修改默认模型

2. **点击重载配置**
   - 点击页面右上角的"重载配置"按钮
   - 查看成功提示

3. **检查后端日志**
   ```
   🔄 重新加载配置桥接...
     清除环境变量: TRADINGAGENTS_DEFAULT_MODEL
     清除环境变量: DEEPSEEK_API_KEY
   🔧 开始桥接配置到环境变量...
     ✓ 桥接 OPENAI_API_KEY (长度: 51)
     ✓ 桥接默认模型: gpt-4
   ✅ 配置桥接完成
   ```

4. **立即执行分析**
   - 不重启后端
   - 执行股票分析

#### 预期结果

- ✅ 新配置立即生效
- ✅ 无需重启后端服务
- ✅ 分析使用更新后的配置

### 测试 4：配置优先级

#### 步骤

1. **同时设置统一配置和环境变量**
   - 在 `.env` 文件中设置：`DEEPSEEK_API_KEY=old-key-from-env`
   - 在配置管理中设置：`sk-new-key-from-config`

2. **重启后端服务**
   ```powershell
   # 停止服务
   Ctrl+C
   
   # 启动服务
   cd app
   uvicorn main:app --reload
   ```

3. **检查后端日志**
   - 查看桥接日志
   - 确认使用的是哪个密钥

4. **执行分析**
   - 执行股票分析
   - 检查使用的 API 密钥

#### 预期结果

- ✅ 统一配置优先于环境变量
- ✅ 使用配置管理中设置的密钥（`sk-new-key-from-config`）
- ✅ 环境变量作为后备方案

### 测试 5：数据源细节配置

#### 步骤

1. **配置数据源细节**
   - 访问配置管理 → 数据源配置
   - 编辑 Tushare 数据源
   - 设置超时时间：60 秒
   - 设置速率限制：120 次/分钟
   - 在 `config_params` 中添加：
     ```json
     {
       "max_retries": 5,
       "cache_ttl": 7200,
       "cache_enabled": true
     }
     ```

2. **重载配置**
   - 点击"重载配置"按钮

3. **检查环境变量**
   - 在后端日志中查看桥接信息
   - 应该看到：
     ```
     ✓ 桥接 TUSHARE_TIMEOUT: 60
     ✓ 桥接 TUSHARE_RATE_LIMIT: 2.0
     ✓ 桥接 TUSHARE_MAX_RETRIES: 5
     ✓ 桥接 TUSHARE_CACHE_TTL: 7200
     ✓ 桥接 TUSHARE_CACHE_ENABLED: true
     ```

4. **执行分析**
   - 执行股票分析
   - 观察 Tushare 数据源的行为

#### 预期结果

- ✅ 数据源使用配置的超时时间
- ✅ 数据源遵守配置的速率限制
- ✅ 失败时重试 5 次
- ✅ 缓存有效期为 7200 秒

### 测试 6：系统运行时配置

#### 步骤

1. **配置系统设置**
   - 访问配置管理 → 系统设置
   - 设置港股最小请求间隔：3.0 秒
   - 设置港股请求超时：90 秒
   - 设置港股最大重试：5 次
   - 启用"使用 App 缓存优先"

2. **重载配置**
   - 点击"重载配置"按钮

3. **检查环境变量**
   - 在后端日志中查看桥接信息
   - 应该看到：
     ```
     ✓ 桥接 TA_HK_MIN_REQUEST_INTERVAL_SECONDS: 3.0
     ✓ 桥接 TA_HK_TIMEOUT_SECONDS: 90
     ✓ 桥接 TA_HK_MAX_RETRIES: 5
     ✓ 桥接 TA_USE_APP_CACHE: true
     ```

4. **执行港股分析**
   - 执行港股股票分析（如 00700）
   - 观察请求间隔和超时行为

#### 预期结果

- ✅ 港股请求间隔至少 3 秒
- ✅ 请求超时时间为 90 秒
- ✅ 失败时重试 5 次
- ✅ 优先使用 App 缓存

### 测试 7：向后兼容性

#### 步骤

1. **只使用环境变量**
   - 清空数据库中的配置
   - 只在 `.env` 文件中设置 API 密钥

2. **启动后端**
   - 检查启动日志

3. **执行分析**
   - 执行股票分析

#### 预期结果

- ✅ 系统仍然可以正常工作
- ✅ 使用 `.env` 文件中的配置
- ✅ 向后兼容旧的配置方式

## 🔍 调试技巧

### 1. 检查环境变量

在后端代码中添加调试输出：

```python
import os
print(f"DEEPSEEK_API_KEY: {os.environ.get('DEEPSEEK_API_KEY', 'NOT SET')[:20]}...")
print(f"TRADINGAGENTS_DEFAULT_MODEL: {os.environ.get('TRADINGAGENTS_DEFAULT_MODEL', 'NOT SET')}")
```

### 2. 检查配置桥接日志

查看后端日志中的桥接信息：

```
grep "桥接" app.log
```

### 3. 检查 TradingAgents 使用的配置

在 `tradingagents/graph/trading_graph.py` 中添加日志：

```python
logger.info(f"使用的 API 密钥: {api_key[:20]}...")
logger.info(f"使用的模型: {self.config['deep_think_llm']}")
```

### 4. 使用配置重载 API

通过 API 测试配置重载：

```bash
curl -X POST http://localhost:8000/api/config/reload \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## ⚠️ 常见问题

### Q1: 配置向导完成后，分析仍然报错"API 密钥未找到"

**原因**: 配置桥接失败或未执行

**解决方案**:
1. 检查后端启动日志，确认配置桥接是否成功
2. 点击"重载配置"按钮手动触发桥接
3. 检查数据库中是否正确保存了配置

### Q2: 修改配置后不生效

**原因**: 未执行配置重载

**解决方案**:
1. 点击配置管理页面右上角的"重载配置"按钮
2. 或者重启后端服务

### Q3: 环境变量和统一配置冲突

**原因**: 配置优先级不明确

**解决方案**:
- 统一配置优先于环境变量
- 如果想使用环境变量，清空数据库中的配置
- 如果想使用统一配置，删除 `.env` 中的相关配置

### Q4: 配置桥接失败

**原因**: 数据库连接失败或配置格式错误

**解决方案**:
1. 检查 MongoDB 连接是否正常
2. 检查配置数据格式是否正确
3. 查看详细的错误日志

## 📝 测试检查清单

- [ ] 配置向导设置的配置生效
- [ ] 配置管理添加的模型生效
- [ ] 配置热重载功能正常
- [ ] 环境变量桥接正常工作
- [ ] 配置优先级正确
- [ ] 向后兼容性正常
- [ ] 错误处理正确
- [ ] 日志输出清晰

## 🎯 成功标准

测试通过的标准：

1. ✅ 用户在配置向导中设置的 API 密钥被正确使用
2. ✅ 用户在配置管理中添加的模型被正确使用
3. ✅ 配置更新后可以热重载，无需重启服务
4. ✅ 环境变量桥接日志清晰，易于调试
5. ✅ 配置优先级符合预期（统一配置 > 环境变量）
6. ✅ 向后兼容，不破坏现有的环境变量配置方式
7. ✅ 错误处理完善，失败时有明确的提示

## 📚 相关文档

- [配置迁移计划](./CONFIG_MIGRATION_PLAN.md)
- [配置向导使用说明](./CONFIG_WIZARD.md)
- [配置向导 vs 配置管理](./CONFIG_WIZARD_VS_CONFIG_MANAGEMENT.md)
- [配置向导后端集成](./CONFIG_WIZARD_BACKEND_INTEGRATION.md)

