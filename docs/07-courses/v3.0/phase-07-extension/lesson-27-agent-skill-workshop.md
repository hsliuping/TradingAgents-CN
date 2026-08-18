# 第 27 课:Agent 工坊与 Skill 中心——自定义分析师 + 扩展平台能力

> **课时**: 25 分钟 | **难度**: ⭐⭐⭐ 进阶 | **前置**: 第 26 课

> ⚠️ **风险提示**:本课程内容仅为平台功能教学,AI 输出的研究报告不构成投资建议,最终决策由你自己负责。

## 🎯 学完后能做什么

- 理解 **Agent** 和 **Skill** 的区别
- 在 **Agent 工坊** 创建自定义分析师
- 在 **Skill 中心** 创建 Skill 扩展平台
- 把自定义 Agent 接入工作流(第 26 课)

## 🆚 Agent vs Skill

| 维度 | Agent | Skill |
|------|-------|-------|
| 是什么 | **AI 角色**(分析师/顾问) | **平台能力扩展**(工具/数据源) |
| 在哪 | 「分析流」→「Agent 工坊」 | 「分析流」→「Skill 中心」 |
| 输入 | 数据 + 提示词 | 工具调用 |
| 输出 | 报告/决策 | 数据/计算结果 |
| 例子 | "巴菲特分析师" | "Tushare 财务数据 Skill" |
| 谁用 | 工作流节点 | 平台底层 |

> 💡 **类比**:
> - **Agent** = 一个人(分析师)
> - **Skill** = 这个人会用的工具(Tushare API、计算器等)

## 📍 入口

- **Agent 工坊**: 「分析流」→「Agent 工坊」
- **Skill 中心**: 「分析流」→「Skill 中心」

## 🖱️ 操作步骤

### Agent 工坊

#### 步骤 1:进入 Agent 工坊

1. 侧边栏「分析流」→「Agent 工坊」
2. 看到已有 Agent 列表(内置 + 你的自定义)

#### 步骤 2:创建自定义 Agent

1. 点"创建 Agent"按钮
2. 填写:
   - **Agent ID**: 全小写 + 下划线(如 `buffett_analyst`)
   - **名称**: 中文显示名(如"巴菲特价值分析师")
   - **描述**: 这个 Agent 做什么
   - **角色定位**: 系统提示词(System Prompt)
   - **输入**: 接受什么数据(财务 / 行情 / 行业)
   - **输出**: 输出什么结构
3. 保存

#### 步骤 3:配置 Agent 的"系统提示词"

**系统提示词** 是 Agent 的"灵魂",决定它怎么思考。

**模板**:
```
你是 {角色定位},你的核心职责是 {核心职责}。

你的分析方法:
- {方法 1}
- {方法 2}
- {方法 3}

你的输出格式:
- {字段 1}
- {字段 2}

你的关注重点:
- {重点 1}
- {重点 2}

禁止:
- {不能做的事 1}
- {不能做的事 2}
```

#### 步骤 4:测试 Agent

- 点"测试"按钮
- 输入测试数据(模拟的财务数据)
- 看 Agent 输出是否符合预期
- 不满意调整提示词

#### 步骤 5:把 Agent 接入工作流

- 进入「分析流」→「流程管理」
- 找到工作流,在节点列表里**选择新创建的 Agent**
- 保存

### Skill 中心

#### 步骤 1:进入 Skill 中心

1. 侧边栏「分析流」→「Skill 中心」
2. 看到已有 Skill 列表(系统内置 + 你的自定义)

#### 步骤 2:创建自定义 Skill

1. 点"创建 Skill"按钮
2. 选择类型:
   - **API Skill**: 调用外部 API
   - **数据库 Skill**: 查询数据库
   - **计算 Skill**: 数学/统计计算
   - **文件 Skill**: 读/写文件
3. 填写配置

#### 步骤 3:测试 Skill

- 输入测试参数
- 看 Skill 返回是否符合预期
- 调整参数

#### 步骤 4:把 Skill 接入 Agent

- 进入 Agent 工坊
- 在 Agent 的"可用工具"列表里**勾选新 Skill**
- 保存

## 📊 内置 Agent 的分类

v3.0 内置 Agent 来自 `agent_configs` 集合,分 6 大类(数量随版本更新可能变化):

| 类别 | 例子 |
|------|------|
| **基础面分析师** | market_analyst, fundamentals_analyst |
| **辩论角色** | bull_researcher, bear_researcher, research_manager |
| **风险角色** | risky_analyst, safe_analyst, neutral_analyst |
| **决策角色** | risk_manager, research_manager |
| **持仓角色** | position_technical, position_fundamental, position_risk, position_advisor |
| **行业/市场** | sector_analyst, index_analyst |
| **其他** | 新闻/情绪/工具类 |

> 💡 **查看当前 Agent 列表**:进入「分析流」→「Agent 工坊」即可看到所有内置 Agent 和你的自定义 Agent。

## 🧠 Agent 设计的"4 个原则"

### 原则 1:单一职责

- 一个 Agent 只做**一件事**
- 例: "巴菲特分析师" 只看价值,不看短线

### 原则 2:可验证

- Agent 的输出**可被验证**(可以打分)
- 例: 巴菲特分析师的输出包含 "内在价值估算",可以对比真实价格

### 原则 3:数据驱动

- Agent 要**基于真实数据**判断
- 不能纯 LLM"自由发挥"

### 原则 4:可解释

- Agent 的结论要**能解释为什么**
- 输出包含**评估理由**(长文本说明依据)

## ⚠️ v3.0 重要变化

- ✅ **Agent 工坊**:v3.0 新增,可以自定义分析师
- ✅ **Skill 中心**:v3.0 新增,可以扩展平台能力
- ✅ **MCP 协议**:支持外部 MCP 工具(高级)
- ✅ **内置 Agent 覆盖大多数场景**(进入「分析流」→「Agent 工坊」查看完整列表)
- ⚠️ **Agent 创建需要权限**:普通用户可能受限
- ⚠️ **Skill 创建需要 API Key**(部分类型)
- ⚠️ **京东云版**:Agent/Skill 创建受平台限制
- ⚠️ **平台仅 A 股和 ETF**

## 🛠️ 实操作业

### 作业 1:创建 1 个自定义 Agent

1. 进入「分析流」→「Agent 工坊」
2. 创建:
   - ID: `value_investor_analyst`
   - 名称: "价值投资分析师"
   - 角色定位: "巴菲特式的价值投资者"
   - 系统提示词: 用上面的模板
3. 测试: 输入一只股票(600519)的模拟数据
4. 看输出

### 作业 2:把自定义 Agent 接入工作流

1. 进入 AI 工作流架构师（「分析流」→「流程管理」→ 点右上角「AI 智能创建」绿色按钮）
2. 描述: "做一个价值投资工作流,用 `value_investor_analyst`"
3. AI 生成工作流,包含你刚创建的 Agent
4. 保存
5. 在「通用研究」菜单跑一次,看报告

**做完这次作业**,你就有了**第一个**自定义 Agent。

## ❓ FAQ

**Q:Agent 创建失败,权限不足?**
A: 检查:
- 用户是否有「分析流」→「Agent 工坊」权限
- 京东云版可能关闭了 Agent 创建功能
- 联系平台管理员开通

**Q:Agent 的提示词怎么写才好?**
A: 经验:
- **明确角色**: "你是 XX 风格的分析师"
- **明确方法**: "用以下方法..."
- **明确输出**: "输出包括..."
- **明确禁止**: "不要..."

**Q:Skill 和 Agent 怎么配合?**
A:
- **Skill 提供数据/工具**: Agent 调 Skill 获取数据
- **Agent 用数据做决策**: Agent 拿到数据后分析
- **例**: "Tushare Skill" 提供财务数据 → "巴菲特 Agent" 用数据做价值评估

**Q:Agent 能复用吗?**
A: 可以。同一个 Agent 可用于多个工作流。

## 📚 延伸阅读

- [第 26 课:AI 工作流架构师](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-07-extension/lesson-26-ai-workflow-architect.md)
- [第 28 课:巴菲特工作流实战](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-07-extension/lesson-28-buffett-workflow-case.md)
- [附录 A:v3.0 平台能力速查表](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/appendices/A-platform-capabilities.md)
