# 大模型配置 - 模型能力配置 UI 更新

## 更新概述

在编辑大模型配置对话框中添加了模型能力相关的配置字段，包括：
1. **能力等级**：模型的能力等级（1-5级）
2. **适用角色**：模型适合的分析角色（快速分析/深度分析/两者都适合）
3. **推荐分析深度**：模型推荐的分析深度级别（快速/基础/标准/深度/全面）
4. **模型特性**：模型支持的特性标签（工具调用/长上下文/推理/视觉/快速响应/成本效益）

## 更新的文件

### 1. 前端类型定义 (`frontend/src/api/config.ts`)

添加了模型能力相关的字段到 `LLMConfig` 接口：

```typescript
export interface LLMConfig {
  // ... 现有字段 ...
  
  // 🆕 模型能力分级系统
  capability_level?: number  // 模型能力等级(1-5)
  suitable_roles?: string[]  // 适用角色
  features?: string[]  // 模型特性
  recommended_depths?: string[]  // 推荐的分析深度级别
  performance_metrics?: {  // 性能指标
    speed?: number
    cost?: number
    quality?: number
  }
}
```

### 2. 编辑对话框组件 (`frontend/src/views/Settings/components/LLMConfigDialog.vue`)

#### 2.1 添加了模型能力配置的 UI 表单

在"高级设置"部分之后，添加了新的"模型能力配置"分区，包含：

- **能力等级选择器**：下拉选择 1-5 级
  - 1级 - 基础模型（快速分析）
  - 2级 - 标准模型（日常使用）
  - 3级 - 高级模型（深度分析）
  - 4级 - 专业模型（专业分析）
  - 5级 - 旗舰模型（全面分析）

- **适用角色多选器**：
  - 快速分析（数据收集、工具调用）
  - 深度分析（推理、决策）
  - 两者都适合（全能型模型）

- **推荐分析深度多选器**：
  - 快速（1级）
  - 基础（2级）
  - 标准（3级）
  - 深度（4级）
  - 全面（5级）

- **模型特性多选器**：
  - 工具调用（必需特性）
  - 长上下文（支持大量历史信息）
  - 强推理能力（深度分析必需）
  - 视觉输入（支持图表分析）
  - 快速响应（响应速度快）
  - 成本效益高（性价比高）

#### 2.2 更新了表单数据默认值

```typescript
const defaultFormData = {
  // ... 现有字段 ...
  
  // 🆕 模型能力配置
  capability_level: 2,  // 默认标准级
  suitable_roles: ['both'],  // 默认两者都适合
  features: ['tool_calling'],  // 默认支持工具调用
  recommended_depths: ['快速', '基础', '标准'],  // 默认推荐1-3级分析
  performance_metrics: {
    speed: 3,
    cost: 3,
    quality: 3
  }
}
```

#### 2.3 更新了配置加载逻辑

在 `watch` 监听器中添加了模型能力字段的加载逻辑，确保编辑模式下能正确加载现有配置。

#### 2.4 添加了样式

添加了 `.text-gray-400` 和 `.text-xs` 样式类，以及下拉选项的自定义样式。

### 3. 配置管理页面 (`frontend/src/views/Settings/ConfigManagement.vue`)

#### 3.1 在模型卡片中显示能力信息

在模型卡片的定价信息之后，添加了模型能力信息的显示区域：

```vue
<div class="model-capability">
  <div class="capability-row">
    <el-icon><Star /></el-icon>
    <span class="capability-label">模型能力:</span>
  </div>
  <div class="capability-details">
    <!-- 能力等级 -->
    <div class="capability-item">
      <span class="capability-type">等级:</span>
      <el-tag>{{ getCapabilityLevelText(model.capability_level) }}</el-tag>
    </div>
    <!-- 适用角色 -->
    <div class="capability-item">
      <span class="capability-type">角色:</span>
      <el-tag>{{ getRoleText(role) }}</el-tag>
    </div>
    <!-- 推荐深度 -->
    <div class="capability-item">
      <span class="capability-type">推荐深度:</span>
      <el-tag>{{ depth }}</el-tag>
    </div>
  </div>
</div>
```

#### 3.2 添加了辅助函数

```typescript
// 获取能力等级文本
const getCapabilityLevelText = (level: number) => {
  const levelMap: Record<number, string> = {
    1: '1级-基础',
    2: '2级-标准',
    3: '3级-高级',
    4: '4级-专业',
    5: '5级-旗舰'
  }
  return levelMap[level] || `${level}级`
}

// 获取能力等级标签类型
const getCapabilityLevelType = (level: number) => {
  const typeMap: Record<number, string> = {
    1: 'info',
    2: '',
    3: 'success',
    4: 'warning',
    5: 'danger'
  }
  return typeMap[level] || ''
}

// 获取角色文本
const getRoleText = (role: string) => {
  const roleMap: Record<string, string> = {
    'quick_analysis': '快速分析',
    'deep_analysis': '深度分析',
    'both': '全能型'
  }
  return roleMap[role] || role
}
```

#### 3.3 导入了新图标

添加了 `Star` 和 `Money` 图标的导入。

#### 3.4 添加了样式

添加了 `.model-capability` 样式类，用于美化模型能力信息的显示。

## 后端支持

后端已经在以下文件中支持了这些字段：

- `app/models/config.py`：`LLMConfig` 和 `LLMConfigRequest` 模型
- `app/constants/model_capabilities.py`：模型能力常量定义

## 使用说明

1. **添加/编辑模型配置**：
   - 在"配置管理" -> "大模型配置"页面，点击"添加模型"或"编辑"按钮
   - 在对话框中填写基本配置、模型参数、定价配置等
   - 在"模型能力配置"部分，选择模型的能力等级、适用角色、推荐分析深度和特性
   - 点击"添加"或"更新"保存配置

2. **查看模型能力**：
   - 在"大模型配置"页面的模型卡片中，可以看到模型的能力信息
   - 包括能力等级、适用角色和推荐分析深度

3. **能力等级说明**：
   - **1级-基础**：适合快速分析和简单任务，响应快速，成本低
   - **2级-标准**：适合日常分析和常规任务，平衡性能和成本
   - **3级-高级**：适合深度分析和复杂推理，质量较高
   - **4级-专业**：适合专业级分析和多轮辩论，高质量输出
   - **5级-旗舰**：最强能力，适合全面分析和关键决策

4. **适用角色说明**：
   - **快速分析**：侧重数据收集、工具调用等快速任务
   - **深度分析**：侧重推理、决策等深度思考任务
   - **全能型**：两者都适合，可以处理各种类型的任务

5. **推荐分析深度说明**：
   - **快速（1级）**：任何模型都可以
   - **基础（2级）**：基础级以上
   - **标准（3级）**：标准级以上
   - **深度（4级）**：高级以上，需推理能力
   - **全面（5级）**：专业级以上，强推理能力

## 注意事项

1. **工具调用是必需特性**：所有模型都应该支持工具调用功能
2. **推理能力对深度分析很重要**：如果模型用于深度分析，建议选择"强推理能力"特性
3. **能力等级决定分析深度上限**：系统会根据模型的能力等级自动推荐合适的分析深度
4. **默认值**：新添加的模型默认为 2级-标准，适合两者，支持工具调用，推荐1-3级分析

## 测试建议

1. 添加一个新的模型配置，测试所有能力字段是否正常保存
2. 编辑现有模型配置，测试能力字段是否正确加载和更新
3. 在模型列表中查看能力信息是否正确显示
4. 测试不同能力等级的标签颜色是否正确

