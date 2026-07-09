# 配置系统迁移指南

## 📋 概述

本文档介绍如何将现有的TradingAgents配置系统迁移到新的webapi+frontend架构中。

## 🏗️ 架构变化

### 旧版配置系统
- **tradingagents/config**: JSON文件存储配置
- **web/modules/config_management**: Streamlit界面管理
- **config/*.json**: 配置文件存储

### 新版配置系统
- **webapi/models/config**: 配置数据模型
- **webapi/services/config_service**: 配置业务逻辑
- **webapi/routers/config**: 配置API接口
- **frontend/src/views/Settings**: Vue.js配置界面
- **MongoDB**: 数据库存储配置

## 🚀 迁移步骤

### 1. 准备工作

确保以下服务正常运行：
```bash
# 启动MongoDB
docker-compose up -d mongodb

# 启动webapi服务
cd webapi
python main.py

# 启动前端服务
cd frontend
npm run dev
```

### 2. 执行配置迁移

#### 方法一：使用迁移脚本
```bash
# 运行迁移脚本
python scripts/migrate_config_to_webapi.py

# 测试迁移结果
python scripts/test_migration.py
```

#### 方法二：通过API接口
```bash
# 调用迁移API
curl -X POST http://localhost:8000/api/config/migrate-legacy \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 方法三：通过前端界面
1. 访问 http://localhost:3000/settings
2. 点击"配置管理"
3. 选择"导入导出"标签
4. 点击"迁移传统配置"

### 3. 验证迁移结果

#### 检查大模型配置
```bash
curl -X GET http://localhost:8000/api/config/llm \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 检查系统设置
```bash
curl -X GET http://localhost:8000/api/config/settings \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 检查完整系统配置
```bash
curl -X GET http://localhost:8000/api/config/system \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📊 配置数据映射

### 模型配置映射
| 旧版字段 | 新版字段 | 说明 |
|---------|---------|------|
| provider | provider | 供应商名称 |
| model_name | model_name | 模型名称 |
| api_key | api_key | API密钥 |
| base_url | api_base | API基础URL |
| max_tokens | max_tokens | 最大Token数 |
| temperature | temperature | 温度参数 |
| enabled | enabled | 是否启用 |

### 系统设置映射
| 旧版字段 | 新版字段 | 说明 |
|---------|---------|------|
| default_provider | default_provider | 默认供应商 |
| default_model | default_llm | 默认大模型 |
| enable_cost_tracking | enable_cost_tracking | 成本跟踪 |
| cost_alert_threshold | cost_alert_threshold | 成本警告阈值 |
| currency_preference | currency_preference | 货币偏好 |
| auto_save_usage | auto_save_usage | 自动保存使用记录 |
| max_usage_records | max_usage_records | 最大使用记录数 |

## 🔧 新功能特性

### 1. 统一配置管理
- 所有配置存储在MongoDB中
- 支持配置版本控制
- 提供配置历史记录

### 2. RESTful API接口
- 完整的CRUD操作
- 配置测试和验证
- 批量操作支持

### 3. 现代化前端界面
- Vue.js + Element Plus
- 响应式设计
- 实时配置更新

### 4. 配置导入导出
- JSON格式导出
- 配置备份和恢复
- 跨环境配置迁移

## 🛠️ 使用新配置系统

### 前端界面操作

#### 访问配置管理
1. 打开浏览器访问 http://localhost:3000
2. 登录系统
3. 导航到"设置" -> "配置管理"

#### 管理大模型配置
1. 选择"大模型配置"标签
2. 点击"添加模型"按钮
3. 填写模型信息并保存
4. 可以设置默认模型、测试连接、删除配置

#### 管理数据源配置
1. 选择"数据源配置"标签
2. 查看现有数据源
3. 测试数据源连接
4. 设置默认数据源

#### 管理系统设置
1. 选择"系统设置"标签
2. 修改各项系统参数
3. 点击"保存设置"

### API接口调用

#### 获取系统配置
```javascript
import { configApi } from '@/api/config'

// 获取完整系统配置
const systemConfig = await configApi.getSystemConfig()

// 获取大模型配置列表
const llmConfigs = await configApi.getLLMConfigs()

// 获取系统设置
const settings = await configApi.getSystemSettings()
```

#### 更新配置
```javascript
// 添加大模型配置
await configApi.updateLLMConfig({
  provider: 'openai',
  model_name: 'gpt-4',
  api_key: 'your-api-key',
  max_tokens: 4000,
  temperature: 0.7,
  enabled: true
})

// 更新系统设置
await configApi.updateSystemSettings({
  max_concurrent_tasks: 5,
  enable_cache: true,
  log_level: 'INFO'
})
```

## 🔄 向后兼容性

### 传统配置文件支持
- 新系统仍然支持读取传统JSON配置文件
- 通过unified_config模块实现兼容
- 配置修改会同步到传统格式

### 渐进式迁移
- 可以逐步迁移各个模块
- 新旧系统可以并存
- 不影响现有功能

## 🚨 注意事项

### 数据备份
- 迁移前请备份现有配置文件
- 建议先在测试环境验证
- 保留原始配置文件作为备份

### 环境变量
- API密钥等敏感信息仍建议使用环境变量
- 新系统会优先读取环境变量
- 确保.env文件配置正确

### 权限管理
- 新系统需要用户认证
- 确保有正确的访问权限
- 管理员权限才能修改系统配置

## 🐛 故障排除

### 迁移失败
1. 检查数据库连接
2. 确认配置文件格式正确
3. 查看错误日志
4. 验证权限设置

### 配置不生效
1. 检查配置是否保存成功
2. 确认服务是否重启
3. 验证配置格式
4. 查看系统日志

### 前端访问问题
1. 确认webapi服务运行正常
2. 检查网络连接
3. 验证用户认证状态
4. 查看浏览器控制台错误

## 📞 技术支持

如果在迁移过程中遇到问题，请：
1. 查看系统日志
2. 运行测试脚本诊断
3. 检查配置文件格式
4. 联系技术支持团队
