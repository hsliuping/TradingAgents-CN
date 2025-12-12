# 移除自选股价格提醒功能

## 变更说明

根据用户需求，暂时移除自选股功能中的价格提醒功能。

## 修改内容

### 前端修改

#### 1. `frontend/src/views/Favorites/index.vue`

##### 页面描述（第 4-10 行）
```vue
<!-- 修改前 -->
<p class="page-description">
  管理您关注的股票，设置价格提醒
</p>

<!-- 修改后 -->
<p class="page-description">
  管理您关注的股票
</p>
```

##### 添加自选股对话框（第 233-242 行）
移除了"价格提醒"表单项：
```vue
<!-- 移除的内容 -->
<el-form-item label="价格提醒">
  <el-row :gutter="8">
    <el-col :span="12">
      <el-input
        v-model.number="addForm.alert_price_high"
        placeholder="上限价格"
        type="number"
      />
    </el-col>
    <el-col :span="12">
      <el-input
        v-model.number="addForm.alert_price_low"
        placeholder="下限价格"
        type="number"
      />
    </el-col>
  </el-row>
</el-form-item>
```

##### 编辑自选股对话框（第 273-276 行）
移除了"价格提醒"表单项（同上）

##### 数据模型（第 411-417 行）
```typescript
// 修改前
const addForm = ref({
  stock_code: '',
  stock_name: '',
  market: 'A股',
  tags: [],
  notes: '',
  alert_price_high: null,
  alert_price_low: null
})

// 修改后
const addForm = ref({
  stock_code: '',
  stock_name: '',
  market: 'A股',
  tags: [],
  notes: ''
})
```

##### 编辑表单数据模型（第 432-438 行）
```typescript
// 修改前
const editForm = ref({
  stock_code: '',
  stock_name: '',
  market: 'A股',
  tags: [] as string[],
  notes: '',
  alert_price_high: null as number | null,
  alert_price_low: null as number | null,
})

// 修改后
const editForm = ref({
  stock_code: '',
  stock_name: '',
  market: 'A股',
  tags: [] as string[],
  notes: ''
})
```

##### showAddDialog 函数（第 620-629 行）
```typescript
// 修改前
const showAddDialog = () => {
  addForm.value = {
    stock_code: '',
    stock_name: '',
    market: 'A股',
    tags: [],
    notes: '',
    alert_price_high: null,
    alert_price_low: null
  }
  addDialogVisible.value = true
}

// 修改后
const showAddDialog = () => {
  addForm.value = {
    stock_code: '',
    stock_name: '',
    market: 'A股',
    tags: [],
    notes: ''
  }
  addDialogVisible.value = true
}
```

##### handleUpdateFavorite 函数（第 658-676 行）
```typescript
// 修改前
const handleUpdateFavorite = async () => {
  try {
    editLoading.value = true
    const payload = {
      tags: editForm.value.tags,
      notes: editForm.value.notes,
      alert_price_high: editForm.value.alert_price_high,
      alert_price_low: editForm.value.alert_price_low
    }
    // ...
  }
}

// 修改后
const handleUpdateFavorite = async () => {
  try {
    editLoading.value = true
    const payload = {
      tags: editForm.value.tags,
      notes: editForm.value.notes
    }
    // ...
  }
}
```

##### editFavorite 函数（第 679-688 行）
```typescript
// 修改前
const editFavorite = (row: any) => {
  editForm.value = {
    stock_code: row.stock_code,
    stock_name: row.stock_name,
    market: row.market || 'A股',
    tags: Array.isArray(row.tags) ? [...row.tags] : [],
    notes: row.notes || '',
    alert_price_high: row.alert_price_high ?? null,
    alert_price_low: row.alert_price_low ?? null,
  }
  editDialogVisible.value = true
}

// 修改后
const editFavorite = (row: any) => {
  editForm.value = {
    stock_code: row.stock_code,
    stock_name: row.stock_name,
    market: row.market || 'A股',
    tags: Array.isArray(row.tags) ? [...row.tags] : [],
    notes: row.notes || ''
  }
  editDialogVisible.value = true
}
```

### 后端保留

**注意**：后端的价格提醒字段（`alert_price_high`、`alert_price_low`）暂时保留，以便将来需要时可以快速恢复该功能。

相关文件：
- `app/routers/favorites.py` - API 路由（保留字段定义）
- `app/models/user.py` - 数据模型（保留字段定义）
- `app/services/favorites_service.py` - 业务逻辑（保留字段处理）

## 影响范围

### 前端
- ✅ 自选股列表页面：移除价格提醒相关 UI
- ✅ 添加自选股对话框：移除价格提醒输入框
- ✅ 编辑自选股对话框：移除价格提醒输入框
- ✅ 数据模型：移除价格提醒字段

### 后端
- ⚠️ **保留不变**：API 接口仍然接受 `alert_price_high` 和 `alert_price_low` 参数
- ⚠️ **保留不变**：数据库模型仍然包含价格提醒字段
- ⚠️ **保留不变**：业务逻辑仍然处理价格提醒数据

### API 兼容性
- ✅ **向后兼容**：前端不再发送价格提醒字段，后端会将其设置为 `null`
- ✅ **向前兼容**：如果将来恢复该功能，只需修改前端代码即可

## 测试验证

### 测试步骤

1. **添加自选股**：
   - 打开自选股页面
   - 点击"添加自选股"按钮
   - ✅ 确认对话框中没有"价格提醒"输入框
   - 填写股票代码、名称、市场等信息
   - 点击"添加"
   - ✅ 确认添加成功

2. **编辑自选股**：
   - 在自选股列表中点击"编辑"按钮
   - ✅ 确认对话框中没有"价格提醒"输入框
   - 修改标签或备注
   - 点击"保存"
   - ✅ 确认保存成功

3. **页面描述**：
   - ✅ 确认页面描述为"管理您关注的股票"（不包含"设置价格提醒"）

## 恢复方案

如果将来需要恢复价格提醒功能，只需：

1. **恢复前端代码**：
   - 恢复"价格提醒"表单项
   - 恢复数据模型中的 `alert_price_high` 和 `alert_price_low` 字段
   - 恢复相关函数中的价格提醒字段处理

2. **后端无需修改**：
   - 后端代码已经支持价格提醒功能
   - 数据库模型已经包含价格提醒字段

3. **参考本文档**：
   - 本文档记录了所有修改的位置
   - 可以通过 Git 历史查看具体的修改内容

## 相关文件

### 前端
- `frontend/src/views/Favorites/index.vue` - 自选股页面（已修改）
- `frontend/src/api/favorites.ts` - 自选股 API（保留字段定义，但前端不再使用）

### 后端（保留不变）
- `app/routers/favorites.py` - 自选股路由
- `app/models/user.py` - 用户模型
- `app/services/favorites_service.py` - 自选股服务

## 总结

本次修改仅移除了前端的价格提醒功能，后端保持不变。这样做的好处是：

1. ✅ **满足当前需求**：用户不再看到价格提醒相关的 UI
2. ✅ **保持灵活性**：将来可以快速恢复该功能
3. ✅ **向后兼容**：不影响现有数据和 API
4. ✅ **易于维护**：修改范围小，风险低

