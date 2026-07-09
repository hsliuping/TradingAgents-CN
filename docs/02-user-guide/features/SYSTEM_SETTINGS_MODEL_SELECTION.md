# 系统设置 - 模型选择优化

## 功能概述

优化了系统设置页面中的模型选择功能，使"数据供应商"、"快速分析模型"和"深度决策模型"三个字段从已配置的大模型中选择，而不是手动输入。

## 改进内容

### 1. 数据供应商选择

**之前**：下拉框显示固定的厂家列表（阿里百炼、OpenAI、Google 等）

**现在**：
- 只显示已启用的厂家（`is_active = true`）
- 显示厂家的显示名称和启用状态标签
- 支持搜索过滤

**实现**：
```vue
<el-form-item label="数据供应商">
  <el-select 
    v-model="systemSettings.default_provider" 
    placeholder="选择已启用的厂家"
    filterable
  >
    <el-option
      v-for="provider in enabledProviders"
      :key="provider.id"
      :label="provider.display_name"
      :value="provider.id"
    >
      <div style="display: flex; justify-content: space-between;">
        <span>{{ provider.display_name }}</span>
        <el-tag v-if="provider.is_active" type="success" size="small">已启用</el-tag>
      </div>
    </el-option>
  </el-select>
</el-form-item>
```

### 2. 快速分析模型选择

**之前**：文本输入框，需要手动输入模型代码（如 `qwen-turbo`）

**现在**：
- 下拉框显示选定供应商的所有已启用模型
- 显示模型的显示名称和代码
- 支持搜索过滤
- 自动根据供应商变化更新可选模型列表

**实现**：
```vue
<el-form-item label="快速分析模型">
  <el-select 
    v-model="systemSettings.quick_analysis_model" 
    placeholder="选择快速分析模型"
    filterable
  >
    <el-option
      v-for="model in availableModelsForProvider(systemSettings.default_provider)"
      :key="`${model.provider}/${model.model_name}`"
      :label="model.model_display_name || model.model_name"
      :value="model.model_name"
    >
      <div style="display: flex; flex-direction: column;">
        <span>{{ model.model_display_name || model.model_name }}</span>
        <span style="font-size: 12px; color: #909399;">{{ model.model_name }}</span>
      </div>
    </el-option>
  </el-select>
</el-form-item>
```

### 3. 深度决策模型选择

**之前**：文本输入框，需要手动输入模型代码（如 `qwen-max`）

**现在**：
- 与快速分析模型相同的改进
- 下拉框显示选定供应商的所有已启用模型
- 显示模型的显示名称和代码
- 支持搜索过滤

## 技术实现

### 计算属性

#### enabledProviders
获取所有已启用的厂家：

```typescript
const enabledProviders = computed(() => {
  return providers.value.filter(p => p.is_active)
})
```

#### availableModelsForProvider
根据厂家 ID 获取该厂家的所有已启用模型：

```typescript
const availableModelsForProvider = (providerId: string) => {
  if (!providerId) return []
  return llmConfigs.value.filter(config => 
    config.provider === providerId && config.enabled
  )
}
```

### 监听器

当用户切换供应商时，自动清空不匹配的模型选择：

```typescript
watch(
  () => systemSettings.value.default_provider,
  (newProvider, oldProvider) => {
    if (newProvider !== oldProvider && newProvider) {
      const availableModels = availableModelsForProvider(newProvider)
      const quickModel = systemSettings.value.quick_analysis_model
      const deepModel = systemSettings.value.deep_analysis_model
      
      // 如果当前选择的快速分析模型不属于新供应商，清空
      if (quickModel && !availableModels.find(m => m.model_name === quickModel)) {
        systemSettings.value.quick_analysis_model = ''
      }
      
      // 如果当前选择的深度决策模型不属于新供应商，清空
      if (deepModel && !availableModels.find(m => m.model_name === deepModel)) {
        systemSettings.value.deep_analysis_model = ''
      }
    }
  }
)
```

## 使用流程

### 配置流程

1. **配置厂家**
   - 进入"配置管理" → "厂家管理"
   - 添加或启用需要的厂家（如：阿里百炼）
   - 确保厂家状态为"已启用"

2. **配置模型**
   - 进入"配置管理" → "大模型配置"
   - 为启用的厂家添加模型配置
   - 确保模型状态为"已启用"

3. **系统设置**
   - 进入"配置管理" → "系统设置"
   - 从"数据供应商"下拉框中选择已启用的厂家
   - 从"快速分析模型"下拉框中选择该厂家的模型
   - 从"深度决策模型"下拉框中选择该厂家的模型
   - 点击"保存设置"

### 示例场景

#### 场景 1：使用阿里百炼

1. 选择数据供应商：`阿里百炼 (dashscope)`
2. 快速分析模型下拉框显示：
   - `Qwen3系列Flash模型 - 快速经济` (qwen-turbo)
   - `Qwen3系列Plus模型 - 平衡性能` (qwen-plus)
   - `Qwen3系列Max模型 - 顶级性能` (qwen-max)
3. 选择快速分析模型：`qwen-turbo`
4. 选择深度决策模型：`qwen-max`

#### 场景 2：切换到 OpenAI

1. 将数据供应商从 `dashscope` 改为 `openai`
2. 系统自动清空之前选择的 `qwen-turbo` 和 `qwen-max`
3. 快速分析模型下拉框显示 OpenAI 的模型：
   - `GPT-4o` (gpt-4o)
   - `GPT-4 Turbo` (gpt-4-turbo)
   - `GPT-3.5 Turbo` (gpt-3.5-turbo)
4. 重新选择适合的模型

## 优势

### 1. 避免输入错误
- 不再需要手动输入模型代码
- 避免拼写错误导致的配置失败
- 确保选择的模型确实存在且已配置

### 2. 提高配置效率
- 直观的下拉选择，无需记忆模型代码
- 显示模型的友好名称，更容易理解
- 支持搜索过滤，快速找到目标模型

### 3. 数据一致性
- 只能选择已配置且已启用的厂家和模型
- 切换厂家时自动清空不匹配的模型
- 确保系统设置与实际配置保持一致

### 4. 更好的用户体验
- 清晰的视觉反馈（显示名称 + 代码）
- 智能的联动逻辑（厂家变化 → 模型列表更新）
- 友好的提示信息

## 注意事项

### 1. 配置顺序
必须按照以下顺序配置：
1. 先配置厂家（厂家管理）
2. 再配置模型（大模型配置）
3. 最后在系统设置中选择

### 2. 启用状态
- 只有 `is_active = true` 的厂家才会出现在数据供应商列表中
- 只有 `enabled = true` 的模型才会出现在模型选择列表中

### 3. 模型可用性
如果下拉框中没有可选的模型：
- 检查是否已配置该厂家的模型
- 检查模型是否已启用
- 检查厂家是否已启用

### 4. 切换厂家
切换厂家时，如果当前选择的模型不属于新厂家，会被自动清空。这是正常行为，需要重新选择新厂家的模型。

## 相关文件

### 前端
- `frontend/src/views/Settings/ConfigManagement.vue` - 系统设置页面

### 后端
- `app/routers/config.py` - 配置管理 API
- `app/services/config_service.py` - 配置服务
- `app/models/config.py` - 配置数据模型

## 测试建议

### 1. 基本功能测试
- [ ] 数据供应商下拉框只显示已启用的厂家
- [ ] 选择厂家后，模型下拉框显示该厂家的已启用模型
- [ ] 模型选项显示显示名称和代码
- [ ] 支持搜索过滤

### 2. 联动测试
- [ ] 切换厂家时，不匹配的模型被清空
- [ ] 切换厂家后，模型列表正确更新
- [ ] 保存后再次编辑，选择正确显示

### 3. 边界情况测试
- [ ] 没有启用的厂家时，数据供应商下拉框为空
- [ ] 选择的厂家没有启用的模型时，模型下拉框为空
- [ ] 禁用当前选择的厂家后，系统设置的行为

### 4. 数据持久化测试
- [ ] 保存设置后刷新页面，选择正确显示
- [ ] 修改设置后保存，数据正确更新
- [ ] 导出配置包含正确的设置

## 未来改进

1. **模型推荐**：根据模型的性能和价格，自动推荐适合的快速/深度模型
2. **模型对比**：在选择时显示模型的详细信息（价格、性能、上下文长度等）
3. **批量配置**：支持一键配置常用的厂家和模型组合
4. **配置验证**：在保存前验证选择的模型是否可用
5. **历史记录**：记录模型选择的历史，方便快速切换

