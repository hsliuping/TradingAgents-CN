# 模型名称显示优化

## 问题描述

用户反馈了两个问题：

1. **模型代码（name）没有体现**：在模型选择下拉框中，只显示了模型的显示名称，没有显示实际的模型代码（API 调用时使用的标识符）
2. **价格字段编辑后显示为空**：设置了使用价格后保存，第二次编辑进来时价格字段显示为空

## 解决方案

### 1. 模型名称字段拆分

将原来的单一"模型名称"字段拆分为两个独立字段：

- **模型显示名称** (`model_display_name`)：用于界面显示的友好名称
  - 示例：`Qwen3系列Flash模型 - 快速经济`
  
- **模型代码** (`model_name`)：实际调用 API 时使用的模型标识符
  - 示例：`qwen-turbo`

### 2. 下拉列表选择优化

添加了一个"选择模型"下拉框，当用户从列表中选择模型时：
- 自动填充"模型显示名称"
- 自动填充"模型代码"
- 自动填充价格信息（输入价格、输出价格、货币单位）

### 3. 价格字段加载修复

修复了编辑配置时价格字段显示为空的问题：
- 使用 `??` 运算符确保即使价格为 `0` 也能正确保留
- 更新了前后端的数据模型，确保价格字段正确传输

## 技术实现

### 前端修改

#### 1. 更新数据模型

**文件**: `frontend/src/api/config.ts`

```typescript
export interface LLMConfig {
  provider: string
  model_name: string
  model_display_name?: string  // 新增：模型显示名称
  // ... 其他字段
  input_price_per_1k?: number
  output_price_per_1k?: number
  currency?: string
}
```

#### 2. 更新表单结构

**文件**: `frontend/src/views/Settings/components/LLMConfigDialog.vue`

```vue
<!-- 选择模型（下拉列表） -->
<el-form-item label="选择模型" v-if="modelOptions.length > 0">
  <el-select
    v-model="selectedModelKey"
    placeholder="从列表中选择模型"
    @change="handleModelSelect"
  >
    <el-option
      v-for="model in modelOptions"
      :key="model.value"
      :label="model.label"
      :value="model.value"
    >
      <div style="display: flex; flex-direction: column;">
        <span>{{ model.label }}</span>
        <span style="font-size: 12px; color: #909399;">代码: {{ model.value }}</span>
      </div>
    </el-option>
  </el-select>
</el-form-item>

<!-- 模型显示名称 -->
<el-form-item label="模型显示名称" prop="model_display_name">
  <el-input
    v-model="formData.model_display_name"
    placeholder="输入模型的显示名称"
  />
</el-form-item>

<!-- 模型代码 -->
<el-form-item label="模型代码" prop="model_name">
  <el-input
    v-model="formData.model_name"
    placeholder="输入模型的API调用代码"
  />
</el-form-item>
```

#### 3. 添加自动填充逻辑

```typescript
// 处理从下拉列表选择模型
const handleModelSelect = (modelCode: string) => {
  if (!modelCode) return

  const selectedModel = modelOptions.value.find(m => m.value === modelCode)
  if (selectedModel) {
    // 自动填充模型代码和显示名称
    formData.value.model_name = selectedModel.value
    formData.value.model_display_name = selectedModel.label
    
    // 自动填充价格信息
    const modelInfo = getModelInfo(formData.value.provider, modelCode)
    if (modelInfo) {
      formData.value.input_price_per_1k = modelInfo.input_price_per_1k
      formData.value.output_price_per_1k = modelInfo.output_price_per_1k
      formData.value.currency = modelInfo.currency
    }
  }
}
```

#### 4. 修复价格字段加载

```typescript
watch(
  () => props.config,
  (config) => {
    if (config) {
      formData.value = {
        ...defaultFormData,
        ...config,
        // 确保价格字段正确加载，即使是 0 也要保留
        input_price_per_1k: config.input_price_per_1k ?? defaultFormData.input_price_per_1k,
        output_price_per_1k: config.output_price_per_1k ?? defaultFormData.output_price_per_1k,
        currency: config.currency || defaultFormData.currency,
        model_display_name: config.model_display_name || ''
      }
    }
  }
)
```

#### 5. 更新列表显示

**文件**: `frontend/src/views/Settings/ConfigManagement.vue`

```vue
<div class="model-name-wrapper">
  <span class="model-name">{{ model.model_display_name || model.model_name }}</span>
  <span v-if="model.model_display_name" class="model-code">{{ model.model_name }}</span>
</div>
```

CSS 样式：

```scss
.model-name-wrapper {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .model-name {
    font-weight: 600;
    font-size: 16px;
  }

  .model-code {
    font-size: 12px;
    color: #909399;
    font-family: 'Courier New', monospace;
  }
}
```

### 后端修改

#### 1. 更新数据模型

**文件**: `app/models/config.py`

```python
class LLMConfig(BaseModel):
    """大模型配置"""
    provider: ModelProvider = ModelProvider.OPENAI
    model_name: str = Field(..., description="模型名称/代码")
    model_display_name: Optional[str] = Field(None, description="模型显示名称")
    # ... 其他字段
    input_price_per_1k: Optional[float] = Field(None, description="输入token价格")
    output_price_per_1k: Optional[float] = Field(None, description="输出token价格")
    currency: str = Field(default="CNY", description="货币单位")

class LLMConfigRequest(BaseModel):
    """大模型配置请求"""
    provider: ModelProvider
    model_name: str
    model_display_name: Optional[str] = None  # 新增
    # ... 其他字段
    input_price_per_1k: Optional[float] = None
    output_price_per_1k: Optional[float] = None
    currency: str = "CNY"
```

## 使用流程

### 新增配置

1. 点击"添加大模型配置"
2. 选择供应商（如：阿里百炼）
3. 从"选择模型"下拉框中选择模型（如：Qwen3系列Flash模型 - 快速经济）
4. 系统自动填充：
   - 模型显示名称：`Qwen3系列Flash模型 - 快速经济`
   - 模型代码：`qwen-turbo`
   - 输入价格：`0.0003`
   - 输出价格：`0.0006`
   - 货币单位：`CNY`
5. 用户可以手动调整任何字段
6. 点击"确定"保存

### 编辑配置

1. 点击配置卡片的"编辑"按钮
2. 对话框显示：
   - 选择模型：显示当前选中的模型
   - 模型显示名称：显示保存的显示名称
   - 模型代码：显示保存的模型代码
   - 价格信息：正确显示保存的价格（包括 0）
3. 用户可以修改任何字段
4. 点击"确定"保存

### 列表显示

在配置列表中，每个模型卡片显示：
- **主标题**：模型显示名称（如果有）或模型代码
- **副标题**：模型代码（灰色小字，等宽字体）

## 优势

1. **清晰的字段分离**：显示名称和代码分开，避免混淆
2. **自动填充**：减少手动输入，降低出错概率
3. **灵活性**：用户仍可手动输入或修改任何字段
4. **向后兼容**：如果没有显示名称，自动使用模型代码
5. **价格保留**：正确处理价格为 0 的情况

## 测试建议

1. **新增配置测试**：
   - 选择不同供应商的模型
   - 验证自动填充是否正确
   - 手动修改字段后保存

2. **编辑配置测试**：
   - 编辑已有配置
   - 验证所有字段（包括价格）是否正确显示
   - 修改后保存，再次编辑验证

3. **价格测试**：
   - 设置价格为 0
   - 设置价格为小数
   - 设置价格为大数字
   - 验证编辑时是否正确显示

4. **显示测试**：
   - 在列表中查看模型卡片
   - 验证显示名称和代码是否正确显示
   - 验证样式是否美观

## 相关文件

### 前端
- `frontend/src/api/config.ts` - API 接口定义
- `frontend/src/views/Settings/components/LLMConfigDialog.vue` - 配置对话框
- `frontend/src/views/Settings/ConfigManagement.vue` - 配置管理页面

### 后端
- `app/models/config.py` - 数据模型
- `app/routers/config.py` - API 路由

## 注意事项

1. **数据库迁移**：如果使用数据库存储配置，需要添加 `model_display_name` 字段
2. **向后兼容**：旧配置没有 `model_display_name` 字段，会自动使用 `model_name` 显示
3. **验证规则**：`model_name` 是必填的，`model_display_name` 是可选的
4. **价格精度**：价格字段使用 4 位小数精度

