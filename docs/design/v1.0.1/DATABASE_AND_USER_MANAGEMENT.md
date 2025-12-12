# 数据库和用户管理设计

## 📋 概述

本文档设计提示词模板系统的数据库存储、用户管理、分析偏好和历史记录功能。

**注意**: 系统已有现成的 `users` 集合，本设计基于现有用户表进行扩展。

---

## 🗄️ 数据库架构

### 现有集合 (已存在)

#### users 集合 - 用户信息
```javascript
{
    _id: ObjectId,
    username: String,
    email: String,
    hashed_password: String,
    is_active: Boolean,
    is_verified: Boolean,
    is_admin: Boolean,
    created_at: DateTime,
    updated_at: DateTime,
    last_login: DateTime,
    preferences: {
        default_market: String,
        default_depth: String,
        default_analysts: [String],
        auto_refresh: Boolean,
        refresh_interval: Number,
        ui_theme: String,
        language: String,
        notifications_enabled: Boolean
    },
    daily_quota: Number,
    concurrent_limit: Number,
    total_analyses: Number,
    successful_analyses: Number,
    failed_analyses: Number,
    favorite_stocks: [Object]
}
```

### 新增集合

#### 1. analysis_preferences 集合 - 分析偏好
```javascript
{
    _id: ObjectId,
    user_id: ObjectId,  // 关联到users._id
    preference_type: String,  // 'aggressive', 'neutral', 'conservative'
    description: String,
    risk_level: Number,  // 0.0-1.0
    confidence_threshold: Number,  // 0.0-1.0
    position_size_multiplier: Number,  // 0.5-2.0
    decision_speed: String,  // 'fast', 'normal', 'slow'
    is_default: Boolean,
    created_at: DateTime,
    updated_at: DateTime
}
```

#### 2. prompt_templates 集合 - 模板存储
```javascript
{
    _id: ObjectId,
    agent_type: String,  // 'analysts', 'researchers', 'debators', 'managers', 'trader'
    agent_name: String,  // 具体Agent名称
    template_name: String,  // 模板名称
    preference_type: String,  // 'aggressive', 'neutral', 'conservative', null表示通用
    content: {
        system_prompt: String,
        tool_guidance: String,
        analysis_requirements: String,
        output_format: String,
        constraints: String
    },
    is_system: Boolean,  // true表示系统模板，false表示用户自定义
    created_by: ObjectId,  // 关联到users._id，系统模板为null
    base_template_id: ObjectId,  // 对于用户模板：来源的系统模板ID；系统模板为null
    base_version: Number,  // 创建时对应的系统模板版本号，用于后续对比提醒
    status: String,  // 'draft', 'active'，草稿/启用状态
    created_at: DateTime,
    updated_at: DateTime,
    version: Number  // 当前版本号
}
```

#### 3. user_template_configs 集合 - 用户模板配置
```javascript
{
    _id: ObjectId,
    user_id: ObjectId,  // 关联到users._id
    agent_type: String,
    agent_name: String,
    template_id: ObjectId,  // 关联到prompt_templates._id
    preference_id: ObjectId,  // 关联到analysis_preferences._id
    is_active: Boolean,
    created_at: DateTime,
    updated_at: DateTime
}
```

#### 4. template_history 集合 - 模板修改历史
```javascript
{
    _id: ObjectId,
    template_id: ObjectId,  // 关联到prompt_templates._id
    user_id: ObjectId,  // 关联到users._id，系统模板为null
    version: Number,  // 版本号
    content: {
        system_prompt: String,
        tool_guidance: String,
        analysis_requirements: String,
        output_format: String,
        constraints: String
    },
    change_description: String,
    change_type: String,  // 'create', 'update', 'delete', 'restore'
    created_at: DateTime
}
```

#### 5. template_comparison 集合 - 模板对比记录
```javascript
{
    _id: ObjectId,
    user_id: ObjectId,  // 关联到users._id
    template_id_1: ObjectId,  // 关联到prompt_templates._id
    template_id_2: ObjectId,  // 关联到prompt_templates._id
    version_1: Number,
    version_2: Number,
    differences: [
        {
            field: String,
            old_value: String,
            new_value: String,
            change_type: String  // 'added', 'removed', 'modified'
        }
    ],
    created_at: DateTime
}
```

---

## 👥 用户管理设计

### 现有用户模型 (app/models/user.py)
```python
class User(BaseModel):
    """用户模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    username: str
    email: str
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    preferences: UserPreferences  # 现有偏好设置
    daily_quota: int = 1000
    concurrent_limit: int = 3
    total_analyses: int = 0
    successful_analyses: int = 0
    failed_analyses: int = 0
    favorite_stocks: List[FavoriteStock] = []
```

### 扩展用户偏好 (在现有preferences基础上)
```python
class UserPreferences(BaseModel):
    """用户偏好设置 (扩展)"""
    # 现有字段
    default_market: str = "A股"
    default_depth: str = "3"
    default_analysts: List[str] = []
    auto_refresh: bool = True
    refresh_interval: int = 30
    ui_theme: str = "light"
    language: str = "zh-CN"
    notifications_enabled: bool = True

    # 新增字段 - 分析偏好
    analysis_preference_type: str = "neutral"  # 'aggressive', 'neutral', 'conservative'
    analysis_preference_id: Optional[str] = None  # 关联到analysis_preferences._id
```

### 用户操作
- ✅ 创建用户 (现有)
- ✅ 更新用户信息 (现有)
- ✅ 删除用户 (现有)
- ✅ 查询用户 (现有)
- ✅ 用户认证 (现有)
- ✅ 获取用户的分析偏好 (新增)
- ✅ 设置用户的默认偏好 (新增)

---

## 🎯 分析偏好设计

### 三种分析偏好

#### 1. 激进偏好 (Aggressive)
- **特点**: 高风险、高收益、快速决策
- **应用**:
  - 分析师: 更激进的评分标准
  - 研究员: 更看好的观点
  - 辩手: 更激进的风险评估
  - 交易员: 更大的仓位建议

#### 2. 中性偏好 (Neutral)
- **特点**: 平衡风险收益、理性决策
- **应用**:
  - 分析师: 中立的评分标准
  - 研究员: 平衡的观点
  - 辩手: 中立的风险评估
  - 交易员: 适中的仓位建议

#### 3. 保守偏好 (Conservative)
- **特点**: 低风险、稳定收益、谨慎决策
- **应用**:
  - 分析师: 保守的评分标准
  - 研究员: 更看空的观点
  - 辩手: 保守的风险评估
  - 交易员: 较小的仓位建议

### 偏好模型
```python
class AnalysisPreference:
    preference_id: str
    user_id: str
    preference_type: str  # 'aggressive', 'neutral', 'conservative'
    description: str
    is_default: bool
    created_at: datetime

    # 配置参数
    risk_level: float  # 0.0-1.0
    confidence_threshold: float  # 0.0-1.0
    position_size_multiplier: float  # 0.5-2.0
    decision_speed: str  # 'fast', 'normal', 'slow'
```

---

## 📝 历史记录设计

### 版本管理
```python
class TemplateHistory:
    history_id: str
    template_id: str
    version: int
    content: str
    change_description: str
    change_type: str  # 'create', 'update', 'delete', 'restore'
    created_by: str
    created_at: datetime
```

### 历史操作
- ✅ 记录每次修改
- ✅ 版本回滚
- ✅ 版本对比
- ✅ 修改历史查询
- ✅ 修改统计

### 对比功能
```python
class TemplateComparison:
    comparison_id: str
    user_id: str
    template_id_1: str
    template_id_2: str
    version_1: int
    version_2: int
    comparison_result: Dict  # 差异详情
    created_at: datetime
```

---

## 🧩 模板语义与生命周期

### 系统模板 vs 用户模板
- **系统模板** (`is_system = true`, `created_by = null`)
  - 由系统/管理员创建和维护
  - 普通用户只能查看，不能直接修改
  - 作为「示例模板」和默认兜底模板存在
- **用户模板** (`is_system = false`, `created_by = user_id`)
  - 用户在界面上「基于示例模板新建」时，会克隆一份系统模板作为自己的模板
  - 每个用户拥有自己独立的模板副本，不会与其他用户共享同一条记录
  - 用户只能编辑自己创建的模板（权限规则已在下文明确）

### 生效优先级
1. 查找 `user_template_configs` 中是否存在匹配 `(user_id, agent_type, agent_name, preference_id)` 且 `is_active = true` 的配置
   - 如果存在：使用该配置指向的 `template_id` 对应的**用户模板**
2. 如果用户没有配置：
   - 按 `agent_type + agent_name + preference_type` 选择对应的**系统默认模板**
   - 确保每个 Agent + 偏好组合至少有一份系统默认模板可用

> 这样可以保证：
> - 用户有自己的定制模板时，总是优先使用自己的模板
> - 用户没有定制时，总是可以回退到系统默认模板

### 草稿 vs 启用
- 新增字段：`status: 'draft' | 'active'`
- **草稿 (draft)**
  - 用于「暂存」用户当前编辑但尚未启用的内容
  - 可以有多份草稿，不影响当前正在使用的模板
  - 一般不会出现在 `user_template_configs` 的 `template_id` 中
- **启用 (active)**
  - 作为分析时实际生效的模板
  - 「保存并启用」时，将模板状态设置为 `active`，并更新/创建对应的 `user_template_configs` 记录

### 更新策略（同一用户多次修改）
- 同一用户多次编辑同一模板时：
  - 采用 **直接覆盖** 策略（最后一次保存为当前版本）
  - 每次保存都会在 `template_history` 中新增一条记录，`version` 自增
  - 不做并发冲突检测，依靠历史记录支持对比和回滚

---

## 🔄 数据流设计

### 用户选择模板流程
```
1. 用户登录
   ↓
2. 获取用户偏好
   ↓
3. 加载用户配置的模板
   ↓
4. 如果没有配置，加载默认模板
   ↓
5. 根据偏好类型加载对应模板
   ↓
6. 返回模板给Agent
```

### 用户修改模板流程
```
1. 用户编辑模板
   ↓
2. 验证模板内容
   ↓
3. 保存新版本到数据库
   ↓
4. 记录修改历史
   ↓
5. 更新用户配置
   ↓
6. 返回成功响应
```

### 模板对比流程
```
1. 用户选择两个版本
   ↓
2. 从数据库获取两个版本内容
   ↓
3. 执行差异对比
   ↓
4. 保存对比记录
   ↓
5. 返回对比结果
```

---

## 🔐 权限管理

### 权限模型
```python
class Permission:
    # 模板权限
    - view_template: 查看模板
    - edit_template: 编辑模板
    - delete_template: 删除模板
    - create_template: 创建模板
    - share_template: 分享模板

    # 历史权限
    - view_history: 查看历史
    - restore_version: 恢复版本
    - compare_versions: 对比版本

    # 偏好权限
    - manage_preferences: 管理偏好
    - set_default_preference: 设置默认偏好
```

### 权限规则
- 用户只能编辑自己的模板
- 系统模板只能查看，不能编辑
- 管理员可以管理所有模板
- 用户可以查看自己的历史记录

---

## 📊 数据模型关系图

```
users (1) ──→ (N) analysis_preferences
users (1) ──→ (N) user_template_configs
users (1) ──→ (N) prompt_templates (created_by)
users (1) ──→ (N) template_history (user_id)
users (1) ──→ (N) template_comparison (user_id)

prompt_templates (1) ──→ (N) template_history
prompt_templates (1) ──→ (N) user_template_configs
prompt_templates (1) ──→ (N) template_comparison

analysis_preferences (1) ──→ (N) user_template_configs

template_history (1) ──→ (N) template_comparison
```

### 关键关系说明

1. **users → analysis_preferences**: 一个用户可以有多个分析偏好 (激进、中性、保守)
2. **users → user_template_configs**: 一个用户可以为多个Agent配置模板
3. **users → prompt_templates**: 用户可以创建自定义模板
4. **prompt_templates → template_history**: 每个模板有完整的修改历史
5. **analysis_preferences → user_template_configs**: 用户配置可以关联到特定偏好

---

## 📏 配额与限制

### 模板数量限制（软约束）
- 每个用户在同一 `(agent_type, agent_name, preference_id)` 组合下建议的上限：
  - `active` 模板：**1 个**（通过 `user_template_configs` 保证唯一生效）
  - `draft` 模板：**3～5 个**（可通过后台配置调整）
- 超出建议上限时的处理策略：
  - API 层可以返回友好错误码（例如 400 + 明确提示），引导用户清理旧草稿
  - 管理后台可以提供「一键清理过期草稿」能力

### 模板内容长度限制
- 单个模板 `content.*` 字段（system_prompt、tool_guidance 等）总长度建议控制在：
  - **32KB～64KB** 以内（具体数值可在配置文件中调整）
- 设计上的考虑：
  - 避免超长 Prompt 导致模型响应变慢或超出上下文窗口
  - 降低数据库存储和网络传输的压力
- 实现方式建议：
  - 在 API 层做长度校验，超过上限时直接拒绝并返回明确错误信息
  - 在前端编辑器中实时显示当前长度 / 占比提示，帮助用户控制模板大小


---

## 🚀 实现步骤

### Phase 1: 数据库设计
- [ ] 创建所有表结构
- [ ] 创建索引和约束
- [ ] 创建初始数据

### Phase 2: 用户管理
- [ ] 实现用户CRUD操作
- [ ] 实现用户认证
- [ ] 实现权限管理

### Phase 3: 偏好管理
- [ ] 实现偏好CRUD操作
- [ ] 实现偏好选择
- [ ] 实现偏好应用

### Phase 4: 模板存储
- [ ] 实现模板保存
- [ ] 实现用户配置
- [ ] 实现模板加载

### Phase 5: 历史管理
- [ ] 实现历史记录
- [ ] 实现版本回滚
- [ ] 实现版本对比

---

## 📈 性能优化

### 缓存策略
- 用户偏好缓存 (Redis)
- 模板缓存 (Redis)
- 历史记录缓存 (Redis)

### 索引优化
- user_id 索引
- agent_type 索引
- preference_type 索引
- template_id 索引

### 查询优化
- 使用连接查询减少数据库访问
- 使用分页处理大量数据
- 使用异步操作处理耗时操作

---

## 🔗 与现有系统集成

### 与Agent集成
```python
# Agent初始化时
agent = create_agent(
    agent_type='fundamentals_analyst',
    user_id='user_123',
    preference_type='conservative'
)

# Agent内部自动加载用户配置的模板
template = template_manager.get_user_template(
    user_id=user_id,
    agent_type=agent_type,
    preference_type=preference_type
)
```

### 与Web API集成
- GET /api/users/{user_id}/preferences
- POST /api/users/{user_id}/preferences
- GET /api/templates/{template_id}/history
- POST /api/templates/{template_id}/compare
- GET /api/users/{user_id}/templates

---

## 📝 下一步

1. 创建数据库迁移脚本
2. 实现数据库访问层 (DAL)
3. 实现业务逻辑层 (BLL)
4. 实现API接口
5. 实现前端集成
6. 编写单元测试
7. 编写集成测试

---

**版本**: v1.0.1
**状态**: 设计完成
**下一步**: 实现数据库和用户管理功能

