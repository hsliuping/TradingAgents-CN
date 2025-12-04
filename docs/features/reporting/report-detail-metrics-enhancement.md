# 报告详情页面 - 关键指标增强

## 概述

增强了分析报告详情页面的关键指标展示，添加了更直观的**置信度评分**和**风险等级**可视化组件。

## 新增功能

### 1. 置信度评分（圆形进度条）

#### 功能特点
- **圆形进度条**：使用 Element Plus 的 `el-progress` 组件，以圆形进度条形式展示 0-100 分的置信度评分
- **动态颜色**：根据评分自动调整颜色
  - 80-100 分：绿色（高信心）
  - 60-79 分：蓝色（中高信心）
  - 40-59 分：橙色（中等信心）
  - 0-39 分：红色（低信心）
- **信心标签**：在进度条下方显示对应的信心等级文字

#### 实现代码

```vue
<el-progress
  type="circle"
  :percentage="normalizeConfidenceScore(report.confidence_score || 0)"
  :width="120"
  :stroke-width="10"
  :color="getConfidenceColor(normalizeConfidenceScore(report.confidence_score || 0))"
>
  <template #default="{ percentage }">
    <span class="confidence-text">
      <span class="confidence-number">{{ percentage }}</span>
      <span class="confidence-unit">分</span>
    </span>
  </template>
</el-progress>
```

#### 辅助函数

```typescript
// 将后端返回的 0-1 小数转换为 0-100 的百分制
const normalizeConfidenceScore = (score: number) => {
  // 如果已经是 0-100 的范围，直接返回
  if (score > 1) {
    return Math.round(score)
  }
  // 如果是 0-1 的小数，转换为百分制
  return Math.round(score * 100)
}

// 根据评分返回颜色
const getConfidenceColor = (score: number) => {
  if (score >= 80) return '#67C23A' // 高信心 - 绿色
  if (score >= 60) return '#409EFF' // 中高信心 - 蓝色
  if (score >= 40) return '#E6A23C' // 中等信心 - 橙色
  return '#F56C6C' // 低信心 - 红色
}

// 根据评分返回标签
const getConfidenceLabel = (score: number) => {
  if (score >= 80) return '高信心'
  if (score >= 60) return '中高信心'
  if (score >= 40) return '中等信心'
  return '低信心'
}
```

### 2. 风险等级（星级显示）

#### 功能特点
- **星级展示**：使用 1-5 颗星表示风险等级
  - ⭐ 低风险（1星）
  - ⭐⭐ 中低风险（2星）
  - ⭐⭐⭐ 中等风险（3星）
  - ⭐⭐⭐⭐ 中高风险（4星）
  - ⭐⭐⭐⭐⭐ 高风险（5星）
- **动态颜色**：风险等级文字根据风险程度显示不同颜色
  - 低风险：绿色
  - 中低风险：浅绿色
  - 中等风险：橙色
  - 中高/高风险：红色
- **风险描述**：在星级下方显示风险等级的详细描述
- **星星动画**：激活的星星有脉冲动画效果

#### 实现代码

```vue
<div class="risk-display">
  <div class="risk-stars">
    <el-icon
      v-for="star in 5"
      :key="star"
      class="star-icon"
      :class="{ active: star <= getRiskStars(report.risk_level || '中等') }"
    >
      <StarFilled />
    </el-icon>
  </div>
  <div class="risk-label" :style="{ color: getRiskColor(report.risk_level || '中等') }">
    {{ report.risk_level || '中等' }}风险
  </div>
  <div class="risk-description">{{ getRiskDescription(report.risk_level || '中等') }}</div>
</div>
```

#### 辅助函数

```typescript
// 根据风险等级返回星星数量
const getRiskStars = (riskLevel: string) => {
  const riskMap: Record<string, number> = {
    '低': 1,
    '中低': 2,
    '中等': 3,
    '中高': 4,
    '高': 5
  }
  return riskMap[riskLevel] || 3
}

// 根据风险等级返回颜色
const getRiskColor = (riskLevel: string) => {
  const colorMap: Record<string, string> = {
    '低': '#67C23A',      // 绿色
    '中低': '#95D475',    // 浅绿色
    '中等': '#E6A23C',    // 橙色
    '中高': '#F56C6C',    // 红色
    '高': '#F56C6C'       // 深红色
  }
  return colorMap[riskLevel] || '#E6A23C'
}

// 根据风险等级返回描述
const getRiskDescription = (riskLevel: string) => {
  const descMap: Record<string, string> = {
    '低': '风险较小，适合稳健投资者',
    '中低': '风险可控，适合大多数投资者',
    '中等': '风险适中，需要谨慎评估',
    '中高': '风险较高，需要密切关注',
    '高': '风险很高，建议谨慎投资'
  }
  return descMap[riskLevel] || '请根据自身风险承受能力决策'
}
```

### 3. 投资建议

保持原有的 Markdown 渲染方式，支持富文本格式的投资建议展示。

### 4. 关键要点

- 使用列表形式展示关键要点
- 每个要点前有绿色的勾选图标
- 鼠标悬停时有背景色变化效果
- 卡片式布局，更易阅读

## 样式增强

### 1. 卡片样式
- 圆角边框（12px）
- 悬停效果：阴影 + 轻微上移
- 渐变过渡动画

### 2. 图标增强
- 所有标签都添加了对应的图标
- 图标大小和颜色统一

### 3. 动画效果
- 星星脉冲动画（`starPulse`）
- 卡片悬停动画
- 列表项悬停效果

### 4. 响应式布局
- 使用 Element Plus 的栅格系统（`el-row` + `el-col`）
- 三列等宽布局（每列 span="8"）
- 间距统一（gutter="24"）

## 数据字段

### 后端返回的报告数据结构

```typescript
interface Report {
  id: string
  stock_symbol: string
  recommendation: string          // 投资建议（Markdown 格式）
  confidence_score: number        // 置信度评分（0-1 的小数，例如 0.85 表示 85%）
  risk_level: string             // 风险等级（低/中低/中等/中高/高）
  key_points: string[]           // 关键要点数组
  // ... 其他字段
}
```

**重要说明**：后端返回的 `confidence_score` 是 **0-1 的小数**（例如 0.85），前端需要转换为 0-100 的百分制显示。

## 修改的文件

### 前端
- **`frontend/src/views/Reports/ReportDetail.vue`**
  - 模板部分：重构关键指标卡片
  - 脚本部分：添加辅助函数
  - 样式部分：增强视觉效果

## 视觉效果

### 置信度评分
```
┌─────────────────────┐
│  📊 置信度评分       │
│                     │
│      ╱───╲          │
│    ╱   85  ╲        │
│   │    分   │       │
│    ╲       ╱        │
│      ╲───╱          │
│                     │
│      高信心          │
└─────────────────────┘
```

### 风险等级
```
┌─────────────────────┐
│  ⚠️  风险等级        │
│                     │
│  ⭐⭐⭐⭐⭐          │
│                     │
│     高风险          │
│                     │
│ 风险很高，建议谨慎   │
│     投资            │
└─────────────────────┘
```

## 使用示例

### 访问报告详情页面

1. 进入分析报告列表页面（`/reports`）
2. 点击任意报告的"查看详情"按钮
3. 在报告详情页面查看增强后的关键指标卡片

### 预期效果

- **置信度评分**：显示圆形进度条，颜色根据评分动态变化
- **风险等级**：显示 1-5 颗星，颜色和描述根据风险等级变化
- **投资建议**：以 Markdown 格式渲染，支持富文本
- **关键要点**：列表形式展示，每项前有勾选图标

## 兼容性

### 数据兼容
- 如果 `confidence_score` 为空，默认显示 0 分
- 如果 `risk_level` 为空，默认显示"中等"风险
- 如果 `key_points` 为空或不存在，不显示关键要点部分

### 浏览器兼容
- 支持所有现代浏览器（Chrome、Firefox、Safari、Edge）
- 使用 CSS3 动画和过渡效果
- 使用 Element Plus 组件，确保跨浏览器一致性

## 后续优化建议

1. **数据可视化**
   - 添加历史置信度评分趋势图
   - 添加风险等级变化趋势

2. **交互增强**
   - 点击置信度评分显示详细计算依据
   - 点击风险等级显示风险因素分析

3. **个性化**
   - 允许用户自定义风险等级阈值
   - 允许用户自定义置信度评分颜色

4. **导出功能**
   - 支持将关键指标导出为图片
   - 支持将关键指标包含在 PDF 报告中

## 总结

通过这次增强，报告详情页面的关键指标展示更加直观和美观：

- ✅ 置信度评分使用圆形进度条，一目了然
- ✅ 风险等级使用星级展示，符合用户习惯
- ✅ 添加了动态颜色和动画效果，提升用户体验
- ✅ 保持了数据的完整性和准确性
- ✅ 兼容旧数据，不会出现显示错误

这些改进使得用户能够更快速地理解分析报告的核心信息，做出更明智的投资决策。

