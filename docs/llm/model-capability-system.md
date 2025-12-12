# 模型能力分级系统

## 📋 概述

模型能力分级系统是一个智能的模型选择和推荐系统，旨在帮助用户根据分析深度自动选择最合适的AI模型，确保分析质量的同时优化成本。

## 🎯 核心功能

### 1. 三维度模型评估

#### 维度1：能力等级（Capability Level）
- **1级 - ⚡基础**：适合快速分析和简单任务
- **2级 - 📊标准**：适合基础和标准分析
- **3级 - 🎯高级**：适合标准和深度分析
- **4级 - 🔥专业**：适合深度和全面分析
- **5级 - 👑旗舰**：适合所有级别，最强推理能力

#### 维度2：适用角色（Suitable Roles）
- **quick_analysis**：适合快速分析任务（数据收集、工具调用）
- **deep_analysis**：适合深度推理任务（综合决策、风险评估）
- **both**：通用模型，两种角色都适合

#### 维度3：模型特性（Features）
- **tool_calling**：支持工具调用（必需）
- **long_context**：支持长上下文
- **reasoning**：强推理能力
- **vision**：支持视觉理解
- **fast_response**：快速响应
- **cost_effective**：成本效益高

### 2. 分析深度要求

| 深度级别 | 最低能力 | 快速模型最低 | 深度模型最低 | 必需特性 |
|---------|---------|------------|------------|---------|
| 快速 | 1 | 1 | 1 | tool_calling |
| 基础 | 1 | 1 | 2 | tool_calling |
| 标准 | 2 | 1 | 2 | tool_calling |
| 深度 | 3 | 2 | 3 | tool_calling |
| 全面 | 4 | 2 | 4 | tool_calling |

### 3. 支持的模型厂商

#### 阿里百炼（DashScope）
- qwen-turbo（基础级）
- qwen-plus（标准级）
- qwen-max（专业级）
- qwen3-max（专业级）

#### OpenAI
- gpt-3.5-turbo（基础级）
- gpt-4（高级级）
- gpt-4-turbo（专业级）
- gpt-4o-mini（标准级）
- o1-mini（高级级）
- o1（旗舰级）
- o4-mini（专业级）

#### DeepSeek
- deepseek-chat（高级级）

#### 百度文心（Qianfan）
- ernie-3.5（标准级）
- ernie-4.0（专业级）
- ernie-4.0-turbo（高级级）

#### 智谱AI（GLM）
- glm-3-turbo（基础级）
- glm-4（高级级）
- glm-4-plus（专业级）

#### Anthropic Claude
- claude-3-haiku（标准级）
- claude-3-sonnet（高级级）
- claude-3-opus（专业级）
- claude-3.5-sonnet（旗舰级）

#### Google Gemini
- gemini-pro（高级级）
- gemini-1.5-pro（专业级）
- gemini-1.5-flash（标准级）
- gemini-2.0-flash（专业级）
- gemini-2.5-flash-lite-preview-06-17（标准级）

#### 月之暗面（Moonshot）
- moonshot-v1-8k（标准级）
- moonshot-v1-32k（高级级）
- moonshot-v1-128k（专业级）

## 🚀 使用方式

### 后端API

#### 1. 获取默认模型配置
```http
GET /api/model-capabilities/default-configs
```

#### 2. 获取分析深度要求
```http
GET /api/model-capabilities/depth-requirements
```

#### 3. 推荐模型
```http
POST /api/model-capabilities/recommend
Content-Type: application/json

{
  "research_depth": "全面"
}
```

响应示例：
```json
{
  "success": true,
  "data": {
    "quick_model": "qwen-plus",
    "deep_model": "qwen-max",
    "quick_model_info": {
      "capability_level": 2,
      "suitable_roles": ["both"],
      "features": ["tool_calling", "reasoning"]
    },
    "deep_model_info": {
      "capability_level": 4,
      "suitable_roles": ["deep_analysis"],
      "features": ["tool_calling", "reasoning", "long_context"]
    },
    "reason": "全面分析推荐：快速模型 qwen-plus（等级2）适合数据收集，深度模型 qwen-max（等级4）适合推理决策。"
  }
}
```

#### 4. 验证模型对
```http
POST /api/model-capabilities/validate
Content-Type: application/json

{
  "quick_model": "qwen-turbo",
  "deep_model": "qwen-turbo",
  "research_depth": "全面"
}
```

响应示例：
```json
{
  "success": true,
  "data": {
    "valid": false,
    "warnings": [
      "❌ 深度模型 qwen-turbo 能力等级(1)低于全面分析要求(4)",
      "⚠️ 深度模型 qwen-turbo 不适合深度推理角色"
    ],
    "recommendations": [
      "建议深度模型使用: qwen-max, qwen3-max, gpt-4-turbo"
    ]
  }
}
```

#### 5. 批量初始化模型能力
```http
POST /api/model-capabilities/batch-init
Content-Type: application/json

{
  "overwrite": false
}
```

### 前端使用

#### 1. 导入API
```typescript
import { recommendModels, validateModels } from '@/api/modelCapabilities'
```

#### 2. 推荐模型
```typescript
const getRecommendation = async () => {
  const res = await recommendModels('全面')
  console.log('推荐模型:', res.data)
}
```

#### 3. 验证模型
```typescript
const validateSelection = async () => {
  const res = await validateModels('qwen-turbo', 'qwen-turbo', '全面')
  if (!res.data.valid) {
    console.warn('模型不合适:', res.data.warnings)
  }
}
```

## 💡 智能推荐逻辑

### 场景1：5级全面分析
```
用户选择：5级全面分析
系统推荐：
  - 快速模型：qwen-plus（标准级，支持工具调用）
  - 深度模型：qwen-max（专业级，强推理能力）
原因：全面分析需要专业级以上的深度模型
```

### 场景2：1级快速分析
```
用户选择：1级快速分析
系统推荐：
  - 快速模型：qwen-turbo（基础级，快速响应）
  - 深度模型：qwen-plus（标准级，成本效益）
原因：快速分析优先选择响应快、成本低的模型
```

### 场景3：用户指定不合适的模型
```
用户选择：5级全面分析 + qwen-turbo（基础级）
系统验证：❌ qwen-turbo 不满足全面分析要求
系统操作：自动切换到 qwen-max
日志记录：记录警告和切换原因
```

## 📊 前端UI展示

### 模型选择器
- 显示能力等级徽章（⚡基础/📊标准/🎯高级/🔥专业/👑旗舰）
- 显示角色标签（⚡快速/🧠深度）
- 显示厂商信息

### 智能提示
- 根据分析深度自动验证模型选择
- 显示警告和推荐信息
- 实时响应用户操作

## 🔧 技术实现

### 后端架构
```
app/
├── constants/
│   └── model_capabilities.py      # 模型能力常量定义
├── models/
│   └── config.py                   # 数据模型扩展
├── services/
│   ├── simple_analysis_service.py  # 分析服务集成
│   └── model_capability_service.py # 模型能力管理服务
└── routers/
    └── model_capabilities.py       # API路由
```

### 前端架构
```
frontend/src/
├── api/
│   └── modelCapabilities.ts        # API客户端
└── views/
    └── Analysis/
        └── SingleAnalysis.vue      # 单股分析页面
```

## 📝 配置示例

### 添加新模型
在 `app/constants/model_capabilities.py` 中添加：

```python
DEFAULT_MODEL_CAPABILITIES = {
    # ... 现有配置
    
    "your-new-model": {
        "capability_level": 3,
        "suitable_roles": [ModelRole.BOTH],
        "features": [ModelFeature.TOOL_CALLING, ModelFeature.REASONING],
        "recommended_depths": ["基础", "标准", "深度"],
        "performance_metrics": {"speed": 4, "cost": 4, "quality": 4},
        "description": "您的新模型描述"
    },
}
```

## 🎉 优势

1. **智能化**：自动推荐和验证，减少用户决策负担
2. **灵活性**：支持多厂商、多模型，不绑定特定供应商
3. **可扩展**：新增模型只需配置元数据
4. **成本优化**：避免过度使用昂贵模型
5. **质量保证**：防止使用不合适的模型
6. **用户友好**：清晰的视觉提示和实时反馈

## 🔮 未来计划

- [ ] 配置管理页面集成（支持编辑模型能力参数）
- [ ] 批量初始化现有模型的能力元数据
- [ ] 添加单元测试和集成测试
- [ ] 模型性能监控和自动调优
- [ ] 基于历史数据的智能推荐优化

