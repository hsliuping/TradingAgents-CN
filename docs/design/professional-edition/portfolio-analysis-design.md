# 持仓分析功能设计

## 1. 功能概述

持仓分析是专业版独享功能，对用户当前持有的股票进行综合AI分析，帮助用户了解持仓结构是否合理，发现潜在风险。

### 1.1 核心功能
- **持仓健康度评估** - 分析持仓结构是否合理
- **风险敞口分析** - 评估行业集中度、个股集中度
- **持仓建议** - 是否需要调仓、减仓、加仓
- **整体收益分析** - 持仓盈亏、成本分析

### 1.2 数据来源
- 模拟交易持仓数据（`paper_positions` 集合）
- 或手动录入的用户持仓数据（新增 `real_positions` 集合）

---

## 2. 现有代码分析

### 2.1 模拟交易模块（可复用）

**后端 API**: `app/routers/paper.py`
- `GET /paper/positions` - 获取持仓列表
- `GET /paper/account` - 获取账户信息（含持仓估值）

**数据集合**:
- `paper_positions` - 持仓记录
- `paper_accounts` - 账户信息
- `paper_trades` - 交易记录

**持仓数据结构** (来自 paper.py):
```python
{
    "user_id": str,
    "code": str,           # 股票代码
    "market": str,         # CN/HK/US
    "currency": str,       # CNY/HKD/USD
    "quantity": int,       # 持仓数量
    "available_qty": int,  # 可用数量
    "avg_cost": float,     # 平均成本
    "updated_at": str
}
```

### 2.2 分析服务（可复用）

**分析服务**: `app/services/simple_analysis_service.py`
- 调用 `tradingagents` 进行AI分析
- 保存报告到 `analysis_reports` 集合

**分析报告结构**:
```python
{
    "analysis_id": str,
    "stock_symbol": str,
    "summary": str,
    "recommendation": str,
    "confidence_score": float,
    "risk_level": str,
    "reports": dict,       # 各分析师报告
    "decision": dict       # 最终决策
}
```

---

## 3. 技术设计

### 3.1 数据模型

#### 3.1.1 用户持仓集合 `real_positions`
```python
{
    "_id": ObjectId,
    "user_id": str,
    "code": str,               # 股票代码
    "name": str,               # 股票名称
    "market": str,             # CN/HK/US
    "currency": str,           # CNY/HKD/USD
    "quantity": int,           # 持仓数量
    "cost_price": float,       # 成本价
    "buy_date": datetime,      # 买入日期（可选）
    "industry": str,           # 所属行业（自动填充）
    "notes": str,              # 备注
    "source": str,             # 来源: manual/import/paper
    "created_at": datetime,
    "updated_at": datetime
}
```

#### 3.1.2 持仓分析报告集合 `portfolio_analysis_reports`
```python
{
    "_id": ObjectId,
    "analysis_id": str,        # 唯一分析ID
    "user_id": str,
    "analysis_type": str,      # portfolio_health / risk_assessment
    "analysis_date": str,      # 分析日期
    "timestamp": datetime,
    
    # 持仓快照
    "portfolio_snapshot": {
        "total_positions": int,
        "total_value": float,
        "total_cost": float,
        "unrealized_pnl": float,
        "unrealized_pnl_pct": float,
        "positions": [...]     # 持仓详情
    },
    
    # 分析结果
    "health_score": float,     # 健康度评分 0-100
    "risk_level": str,         # 低/中/高
    "industry_distribution": dict,  # 行业分布
    "concentration_analysis": dict, # 集中度分析
    
    # AI分析报告
    "ai_analysis": {
        "summary": str,
        "strengths": list,     # 优势
        "weaknesses": list,    # 劣势
        "suggestions": list,   # 建议
        "detailed_report": str
    },
    
    # 元数据
    "execution_time": float,
    "tokens_used": int,
    "created_at": datetime
}
```

### 3.2 API 设计

```
/api/portfolio
├── GET  /positions              # 获取持仓列表（合并模拟+真实）
├── POST /positions              # 添加用户持仓
├── PUT  /positions/:id          # 更新持仓
├── DELETE /positions/:id        # 删除持仓
├── POST /positions/import       # 批量导入持仓
│
├── POST /analysis               # 发起持仓分析
├── GET  /analysis/history       # 分析历史
├── GET  /analysis/:id           # 获取分析报告详情
│
└── GET  /statistics             # 持仓统计（行业分布、盈亏等）
```

### 3.3 服务层设计

**新增文件**: `app/services/portfolio_service.py`

```python
class PortfolioService:
    """持仓分析服务"""

    async def get_positions(self, user_id: str, source: str = "all") -> List[Position]
    async def add_position(self, user_id: str, position: PositionCreate) -> Position
    async def update_position(self, user_id: str, position_id: str, data: PositionUpdate) -> Position
    async def delete_position(self, user_id: str, position_id: str) -> bool
    async def import_positions(self, user_id: str, positions: List[PositionCreate]) -> ImportResult

    async def get_portfolio_statistics(self, user_id: str) -> PortfolioStats
    async def analyze_portfolio(self, user_id: str, params: AnalysisParams) -> AnalysisTask
    async def get_analysis_history(self, user_id: str, page: int, page_size: int) -> List[AnalysisReport]
    async def get_analysis_detail(self, analysis_id: str) -> AnalysisReport
```

### 3.4 AI 分析流程

```
用户发起持仓分析
       ↓
获取用户所有持仓数据
       ↓
获取每只股票的最新行情（计算市值、盈亏）
       ↓
计算持仓统计指标
  - 行业分布
  - 持仓集中度
  - 盈亏分布
       ↓
构建分析提示词
  - 持仓概况
  - 各股票基本信息
  - 市场环境
       ↓
调用大模型分析（使用现有 LLM 基础设施）
       ↓
解析分析结果
       ↓
保存分析报告到 portfolio_analysis_reports
       ↓
返回分析结果
```

---

## 4. 前端设计

### 4.1 页面结构

```
frontend/src/views/Portfolio/
├── index.vue              # 持仓总览页面
├── PositionList.vue       # 持仓列表组件
├── AddPosition.vue        # 添加持仓对话框
├── ImportPosition.vue     # 导入持仓对话框
├── PortfolioAnalysis.vue  # 持仓分析页面
└── AnalysisReport.vue     # 分析报告详情
```

### 4.2 页面功能

#### 4.2.1 持仓总览页 (`index.vue`)
- **顶部统计卡片**: 总市值、总盈亏、盈亏比例、持仓数量
- **行业分布饼图**: 按行业显示持仓分布
- **持仓列表**: 股票名称、代码、数量、成本价、现价、盈亏、操作
- **操作按钮**: 添加持仓、导入持仓、发起分析

#### 4.2.2 持仓分析页 (`PortfolioAnalysis.vue`)
- **分析参数设置**: 分析深度选择
- **分析进度展示**: 实时显示分析进度
- **分析结果展示**:
  - 健康度评分（仪表盘）
  - 风险等级
  - AI分析摘要
  - 详细建议列表
  - 完整分析报告

### 4.3 路由配置

```typescript
// router/index.ts 新增
{
  path: '/portfolio',
  name: 'Portfolio',
  component: () => import('@/views/Portfolio/index.vue'),
  meta: { requiresAuth: true, requiresPro: true }  // 专业版功能
},
{
  path: '/portfolio/analysis',
  name: 'PortfolioAnalysis',
  component: () => import('@/views/Portfolio/PortfolioAnalysis.vue'),
  meta: { requiresAuth: true, requiresPro: true }
},
{
  path: '/portfolio/analysis/:id',
  name: 'PortfolioAnalysisReport',
  component: () => import('@/views/Portfolio/AnalysisReport.vue'),
  meta: { requiresAuth: true, requiresPro: true }
}
```

---

## 5. 提示词设计

### 5.1 持仓分析提示词模板

```markdown
# 持仓组合分析任务

## 用户持仓概况
- 持仓总市值: {total_value} 元
- 持仓成本: {total_cost} 元
- 浮动盈亏: {unrealized_pnl} 元 ({unrealized_pnl_pct}%)
- 持仓股票数: {position_count} 只

## 持仓明细
{position_details}
| 股票代码 | 股票名称 | 行业 | 持仓数量 | 成本价 | 现价 | 市值 | 盈亏% |
|---------|---------|-----|---------|-------|-----|-----|------|
| ...     | ...     | ... | ...     | ...   | ... | ... | ...  |

## 行业分布
{industry_distribution}

## 分析要求
请从以下维度分析该持仓组合：

1. **持仓健康度评估** (0-100分)
   - 分散程度是否合理
   - 行业配置是否均衡
   - 单一股票集中度风险

2. **风险评估**
   - 整体风险等级 (低/中/高)
   - 主要风险点识别
   - 潜在的系统性风险

3. **持仓建议**
   - 是否需要调整持仓结构
   - 具体的加仓/减仓建议
   - 需要关注的股票

4. **综合评价**
   - 组合优势
   - 组合劣势
   - 改进建议

请以JSON格式输出分析结果。
```

---

## 6. 实现计划

### Phase 1: 后端基础 (Week 1)
- [ ] 创建数据模型 `app/models/portfolio.py`
- [ ] 创建服务层 `app/services/portfolio_service.py`
- [ ] 创建API路由 `app/routers/portfolio.py`
- [ ] 数据库索引初始化

### Phase 2: 持仓管理 (Week 2)
- [ ] 实现持仓CRUD接口
- [ ] 实现持仓导入功能
- [ ] 实现持仓统计接口
- [ ] 集成模拟交易持仓数据

### Phase 3: AI分析功能 (Week 3)
- [ ] 设计分析提示词
- [ ] 实现持仓分析服务
- [ ] 集成现有LLM基础设施
- [ ] 实现分析报告保存

### Phase 4: 前端开发 (Week 4)
- [ ] 持仓总览页面
- [ ] 持仓管理功能
- [ ] 持仓分析页面
- [ ] 分析报告展示

### Phase 5: 测试与优化 (Week 5)
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化
- [ ] 文档完善

---

## 7. 与现有功能的集成

### 7.1 与模拟交易集成
- 可选择将模拟交易持仓同步到用户持仓分析
- 共享股票行情数据获取逻辑

### 7.2 与单股分析集成
- 持仓分析中可快速跳转到单股详细分析
- 复用现有的分析报告展示组件

### 7.3 与学习中心集成
- 持仓分析结果可作为学习案例
- 提供"如何解读持仓分析报告"课程

---

## 8. 单股持仓分析

### 8.1 功能说明

单股持仓分析是针对用户持有的**某一只股票**，结合用户的**持仓成本**进行个性化分析，给出针对性的操作建议。

**与普通单股分析的区别**：
| 维度 | 普通单股分析 | 单股持仓分析 |
|------|-------------|-------------|
| 分析对象 | 任意股票 | 用户持有的股票 |
| 成本信息 | 无 | 有（成本价、持仓数量） |
| 建议类型 | 通用买卖建议 | 个性化操作建议（加仓/减仓/持有/清仓） |
| 目标价 | 一般预测 | 基于成本的止盈/止损价 |
| 收益计算 | 无 | 有（预期收益率、回本价位） |

### 8.2 核心功能

1. **持仓状态分析**
   - 当前盈亏状态（盈利/亏损/持平）
   - 盈亏比例计算
   - 持仓时间评估

2. **操作建议**（基于持仓成本）
   - **加仓建议**：当前价位是否适合加仓摊低成本
   - **减仓建议**：是否应该获利了结部分仓位
   - **持有建议**：继续持有的理由和风险
   - **清仓建议**：是否应该止损或获利清仓

3. **价位分析**
   - 止盈价位建议（基于成本的目标收益率）
   - 止损价位建议（基于成本的最大亏损容忍）
   - 回本价位计算
   - 关键支撑/阻力位与成本价的关系

4. **风险评估**
   - 继续持有的风险等级
   - 加仓的风险评估
   - 市场环境对持仓的影响

### 8.3 API 设计

```
/api/portfolio/positions/:id/analysis   # 单股持仓分析
├── POST  /                             # 发起分析
├── GET   /history                      # 该股票的分析历史
└── GET   /:analysis_id                 # 分析详情
```

**请求参数**：
```python
class PositionAnalysisRequest(BaseModel):
    research_depth: str = "标准"    # 分析深度
    include_add_position: bool = True   # 是否分析加仓建议
    target_profit_pct: float = 20.0     # 目标收益率(%)
    max_loss_pct: float = 10.0          # 最大亏损容忍(%)
```

### 8.4 数据模型

**单股持仓分析报告** `position_analysis_reports`
```python
{
    "_id": ObjectId,
    "analysis_id": str,
    "user_id": str,
    "position_id": str,        # 关联的持仓ID

    # 持仓信息快照
    "position_snapshot": {
        "code": str,
        "name": str,
        "quantity": int,
        "cost_price": float,
        "current_price": float,
        "market_value": float,
        "unrealized_pnl": float,
        "unrealized_pnl_pct": float,
        "holding_days": int        # 持仓天数
    },

    # 分析结果
    "analysis_result": {
        "action": str,             # add/reduce/hold/clear
        "action_reason": str,
        "confidence": float,       # 0-100

        # 价位建议
        "price_targets": {
            "take_profit_price": float,   # 止盈价
            "stop_loss_price": float,     # 止损价
            "add_position_price": float,  # 加仓价位
            "break_even_price": float     # 回本价
        },

        # 收益预测
        "profit_scenarios": {
            "best_case": {"price": float, "pnl_pct": float},
            "base_case": {"price": float, "pnl_pct": float},
            "worst_case": {"price": float, "pnl_pct": float}
        },

        # 风险评估
        "risk_assessment": {
            "hold_risk": str,      # 低/中/高
            "add_risk": str,
            "key_risks": list
        }
    },

    # AI详细分析
    "ai_analysis": {
        "summary": str,
        "detailed_report": str,
        "key_points": list
    },

    "created_at": datetime
}
```

### 8.5 提示词模板

```markdown
# 单股持仓分析任务

## 持仓信息
- 股票代码: {code}
- 股票名称: {name}
- 持仓数量: {quantity} 股
- 成本价: {cost_price} 元
- 当前价: {current_price} 元
- 持仓市值: {market_value} 元
- 浮动盈亏: {unrealized_pnl} 元 ({unrealized_pnl_pct}%)
- 持仓天数: {holding_days} 天

## 用户设置
- 目标收益率: {target_profit_pct}%
- 最大亏损容忍: {max_loss_pct}%

## 市场数据
{market_data}

## 分析要求

请基于用户的持仓成本，提供个性化的操作建议：

1. **操作建议** (四选一)
   - 加仓：建议在什么价位加仓，加仓后的平均成本
   - 减仓：建议减仓比例，锁定收益
   - 持有：继续持有的理由
   - 清仓：建议清仓的理由

2. **价位建议**
   - 止盈价位（基于成本价 {cost_price} 元）
   - 止损价位（基于最大亏损 {max_loss_pct}%）
   - 如建议加仓，给出合适的加仓价位

3. **风险评估**
   - 当前持仓风险等级
   - 主要风险因素
   - 需要关注的信号

4. **收益预测**
   - 乐观情况：预期价格和收益率
   - 基准情况：预期价格和收益率
   - 悲观情况：预期价格和收益率

请以JSON格式输出。
```

### 8.6 前端入口

**入口1**: 持仓列表页面
- 每只持仓股票后面增加"分析"按钮
- 点击后跳转到单股持仓分析页面

**入口2**: 模拟交易持仓列表
- 同样增加"AI分析"按钮

**入口3**: 单股分析结果页
- 如果该股票在用户持仓中，显示"结合持仓分析"入口

### 8.7 实现优先级

由于单股持仓分析可以复用现有的单股分析框架，建议：

1. **Phase 1**: 先完成整体持仓分析（Week 1-3）
2. **Phase 2**: 再实现单股持仓分析（Week 4）
   - 复用现有单股分析的 LLM 调用逻辑
   - 增加持仓信息注入
   - 调整提示词模板
   - 新增结果解析逻辑

---

## 9. 与分析引擎和模板系统集成

> **详细设计请参考**: [持仓分析与复盘分析引擎集成设计](../v2.0/portfolio-trade-review-engine-integration.md)

### 9.1 集成目标

将持仓分析与 v2.0 版本的以下系统集成：

1. **StockAnalysisEngine** - 复用多阶段分析引擎的单股分析结果
2. **提示词模板系统** - 使用统一的模板管理替代硬编码提示词

### 9.2 关键改造点

| 改造点 | 现状 | 目标 |
|--------|------|------|
| 单股分析数据来源 | `simple_analysis_service` | `StockAnalysisEngine.analyze()` |
| 持仓分析提示词 | 硬编码在 `_build_position_analysis_prompt_v2` | `get_agent_prompt("trader", "position_advisor", ...)` |
| 风格支持 | 不支持 | neutral/conservative/aggressive 三档 |
| 输出格式 | 自定义 | 统一 JSON 规范 |

### 9.3 新增模板

- `trader/position_advisor` - 单股持仓分析建议模板
- `managers/portfolio_analyst` - 组合层分析模板（预留）

### 9.4 特性开关

```bash
# 环境变量控制
USE_TEMPLATE_PROMPTS=true/false  # 是否使用模板系统
USE_STOCK_ENGINE=true/false      # 是否使用新分析引擎
```

