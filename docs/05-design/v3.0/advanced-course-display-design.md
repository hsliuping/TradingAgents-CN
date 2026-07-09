# 高级课程展示设计方案

## 1. 需求分析

### 1.1 现状
- ✅ 已有学习中心（`/learning`），展示初级课程
- ✅ 已有License系统，可以判断用户是否为高级学员（`isPro`）
- ✅ 高级课程内容已编写完成（24课，位于 `docs/courses/advanced/expanded/`）

### 1.2 目标
- 🎯 在学习中心添加高级课程展示区域
- 🎯 只有高级学员（`isPro = true`）才能访问高级课程
- 🎯 未认证用户看到"升级提示"卡片
- 🎯 已认证用户看到完整的课程列表和详情

---

## 2. 设计方案

### 2.1 页面结构

```
学习中心首页 (/learning)
├── 基础教程（免费，现有）
│   ├── AI基础知识
│   ├── 提示词工程
│   └── ...
│
└── 高级课程（需认证）
    ├── 未认证：显示"升级提示"卡片
    └── 已认证：显示课程列表
        ├── 基础篇（2课）
        ├── 选股篇（3课）
        ├── 择时篇（3课）
        ├── 执行篇（2课）
        ├── 持仓管理篇（2课）
        ├── 风险管理篇（2课）
        ├── 复盘改进篇（2课）
        ├── 短线实战篇（3课）
        ├── 中长线实战篇（3课）
        └── 交易计划建立（2课）
```

### 2.2 UI设计

#### 2.2.1 学习中心首页改造

**新增高级课程区域**：
- 位置：在基础教程下方
- 标题：`🎓 高级课程` + `<el-tag type="warning">PRO</el-tag>`
- 未认证用户：显示"升级提示"卡片（带锁图标）
- 已认证用户：显示课程分类卡片

#### 2.2.2 高级课程列表页

**路由**：`/learning/advanced`
- 显示所有课程分类
- 每个分类显示课程数量和进度
- 点击分类进入课程详情页

#### 2.2.3 高级课程详情页

**路由**：`/learning/advanced/:category/:lesson`
- 显示课程内容（Markdown渲染）
- 显示课程导航（上一课/下一课）
- 显示学习进度

---

## 3. 技术实现

### 3.1 前端组件

#### 3.1.1 学习中心首页改造

**文件**：`frontend/src/views/Learning/index.vue`

**新增内容**：
```vue
<!-- 高级课程区域 -->
<section class="advanced-courses-section">
  <div class="section-header">
    <h2>🎓 高级课程</h2>
    <el-tag type="warning" size="large">PRO</el-tag>
  </div>

  <!-- 未认证：升级提示 -->
  <LicenseGate v-if="!isPro">
    <template #locked>
      <AdvancedCourseUpgradeCard />
    </template>
  </LicenseGate>

  <!-- 已认证：课程分类 -->
  <div v-else class="course-categories">
    <el-row :gutter="20">
      <el-col 
        v-for="category in advancedCourseCategories" 
        :key="category.id"
        :xs="24" :sm="12" :md="8" :lg="6"
      >
        <el-card 
          class="category-card" 
          shadow="hover" 
          @click="navigateToAdvanced(category.id)"
        >
          <div class="card-icon">{{ category.icon }}</div>
          <h3>{{ category.name }}</h3>
          <p>{{ category.description }}</p>
          <el-tag type="success" size="small">
            {{ category.lessonCount }}课
          </el-tag>
        </el-card>
      </el-col>
    </el-row>
  </div>
</section>
```

#### 3.1.2 LicenseGate组件

**文件**：`frontend/src/components/LicenseGate.vue`（新建）

**功能**：
- 检查用户License状态
- 未认证时显示锁定内容
- 已认证时显示正常内容

#### 3.1.3 高级课程升级提示卡片

**文件**：`frontend/src/components/AdvancedCourseUpgradeCard.vue`（新建）

**内容**：
- 标题："解锁高级课程"
- 描述：说明高级课程的价值
- 按钮："前往认证"（跳转到 `/settings/license`）

#### 3.1.4 高级课程列表页

**文件**：`frontend/src/views/Learning/Advanced.vue`（新建）

**功能**：
- 显示所有课程分类
- 显示每个分类的课程列表
- 显示学习进度

#### 3.1.5 高级课程详情页

**文件**：`frontend/src/views/Learning/AdvancedLesson.vue`（新建）

**功能**：
- 加载并渲染Markdown课程内容
- 显示课程导航
- 记录学习进度

### 3.2 课程数据配置

**文件**：`frontend/src/config/advancedCourses.ts`（新建）

**内容**：
```typescript
export interface CourseCategory {
  id: string
  name: string
  icon: string
  description: string
  lessonCount: number
  lessons: Lesson[]
}

export interface Lesson {
  id: string
  title: string
  file: string  // Markdown文件路径
  order: number
}

export const advancedCourseCategories: CourseCategory[] = [
  {
    id: 'basics',
    name: '基础篇',
    icon: '📚',
    description: '从散户到系统交易者的基础概念',
    lessonCount: 2,
    lessons: [
      { id: 'lesson-1', title: '第1课：从散户到系统交易者', file: '01-基础篇-第1课.md', order: 1 },
      { id: 'lesson-2', title: '第2课：可进化投资系统的核心循环', file: '01-基础篇-第2课.md', order: 2 }
    ]
  },
  // ... 其他分类
]
```

### 3.3 路由配置

**文件**：`frontend/src/router/index.ts`

**新增路由**：
```typescript
{
  path: '/learning/advanced',
  name: 'AdvancedCourses',
  component: () => import('@/views/Learning/Advanced.vue'),
  meta: {
    title: '高级课程',
    requiresPro: true  // 需要高级学员权限
  }
},
{
  path: '/learning/advanced/:category/:lesson',
  name: 'AdvancedLesson',
  component: () => import('@/views/Learning/AdvancedLesson.vue'),
  meta: {
    title: '高级课程详情',
    requiresPro: true
  }
}
```

### 3.4 权限检查

**路由守卫**：
```typescript
router.beforeEach((to, from, next) => {
  // 检查是否需要高级学员权限
  if (to.meta.requiresPro) {
    const licenseStore = useLicenseStore()
    if (!licenseStore.isPro) {
      ElMessage.warning('此功能需要高级学员权限，请先认证')
      next('/settings/license')
      return
    }
  }
  next()
})
```

### 3.5 后端API（可选）

如果需要学习进度追踪，可以添加：

**文件**：`app/routers/learning.py`（新建）

**API端点**：
- `GET /api/learning/advanced/courses` - 获取课程列表
- `GET /api/learning/advanced/lesson/:category/:lesson` - 获取课程内容
- `POST /api/learning/advanced/progress` - 更新学习进度
- `GET /api/learning/advanced/progress` - 获取学习进度

---

## 4. 实现步骤

### 步骤1：创建LicenseGate组件
- [ ] 创建 `frontend/src/components/LicenseGate.vue`
- [ ] 实现License状态检查逻辑

### 步骤2：创建升级提示卡片
- [ ] 创建 `frontend/src/components/AdvancedCourseUpgradeCard.vue`
- [ ] 设计UI和跳转逻辑

### 步骤3：改造学习中心首页
- [ ] 修改 `frontend/src/views/Learning/index.vue`
- [ ] 添加高级课程区域
- [ ] 集成LicenseGate组件

### 步骤4：创建课程数据配置
- [ ] 创建 `frontend/src/config/advancedCourses.ts`
- [ ] 定义所有课程分类和课程数据

### 步骤5：创建高级课程列表页
- [ ] 创建 `frontend/src/views/Learning/Advanced.vue`
- [ ] 实现课程分类展示

### 步骤6：创建高级课程详情页
- [ ] 创建 `frontend/src/views/Learning/AdvancedLesson.vue`
- [ ] 实现Markdown渲染和导航

### 步骤7：配置路由
- [ ] 添加高级课程路由
- [ ] 添加路由守卫权限检查

### 步骤8：测试
- [ ] 测试未认证用户访问
- [ ] 测试已认证用户访问
- [ ] 测试课程内容加载和显示

---

## 5. 课程文件映射

### 5.1 文件路径映射

课程文件位于：`docs/courses/advanced/expanded/`

前端访问方式：
- 开发环境：使用 `?raw` 导入
- 生产环境：通过API加载（或打包到静态资源）

### 5.2 文件命名规范

- 文件名格式：`{章节编号}-{章节名}-{课程编号}课.md`
- 例如：`01-基础篇-第1课.md`

---

## 6. 用户体验优化

### 6.1 未认证用户
- 显示清晰的升级提示
- 说明高级课程的价值
- 提供一键跳转到认证页面

### 6.2 已认证用户
- 清晰的课程分类
- 学习进度显示
- 课程导航（上一课/下一课）
- 响应式设计（移动端适配）

---

## 7. 未来扩展

### 7.1 学习进度追踪
- 记录用户学习进度
- 显示完成百分比
- 学习证书（完成所有课程）

### 7.2 课程搜索
- 全文搜索课程内容
- 按关键词筛选

### 7.3 课程评价
- 用户评分
- 学习反馈

---

**最后更新**：2025-01-02


