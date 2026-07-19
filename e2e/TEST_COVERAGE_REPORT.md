# E2E 测试覆盖报告

## 产品定位

**基于日线、历史数据和基本面的深度分析平台**

---

## 测试文件结构

```
e2e/
├── auth.spec.ts              # 认证流程（5个测试）
├── navigation.spec.ts        # 页面导航（9个测试）
├── analysis.spec.ts          # 分析流程（4个测试）
├── analysis_core.spec.ts     # 核心分析流程（11个测试）
├── screening.spec.ts         # 智能选股（10个测试）
├── portfolio.spec.ts         # 持仓管理（14个测试）
├── reports.spec.ts           # 投资报告（6个测试）
├── trading_plan.spec.ts      # 交易计划（6个测试）
├── data_quality.spec.ts      # 数据质量监控（12个测试）
└── utils.ts                  # 工具函数
```

**总计：77个测试用例，9个测试文件**

---

## 测试场景分类

### P0 - 核心功能（必须通过）

#### 1. 认证流程（auth.spec.ts）
- ✅ 登录页加载
- ✅ 正确凭据登录
- ✅ 错误密码登录失败
- ✅ 未登录访问受保护路由
- ✅ 公开页面访问

#### 2. 核心分析流程（analysis_core.spec.ts）
- ✅ 单股深度分析触发
- ✅ 分析页面加载
- ✅ 历史分析结果查看
- ✅ 分析任务管理（列表/筛选/详情/重试/取消）
- ✅ 分析反馈评分
- ✅ 定时分析配置

#### 3. 智能选股（screening.spec.ts）
- ✅ PE/PB/ROE 多条件组合筛选
- ✅ 行业板块筛选
- ✅ 筛选结果排序
- ✅ 保存筛选条件
- ✅ 均线条件筛选
- ✅ 成交量条件筛选
- ✅ 股票关注列表管理（添加/列表/分组/发起分析）

#### 4. 持仓管理（portfolio.spec.ts）
- ✅ 持仓列表加载
- ✅ 持仓收益统计
- ✅ 持仓分布图表
- ✅ 从持仓发起分析
- ✅ 模拟交易（买入/卖出/交易记录/持仓明细/资产概览）
- ✅ 交易复盘（概览/交易明细/盈亏分析/胜率统计）

---

### P1 - 重要功能

#### 5. 投资报告（reports.spec.ts）
- ✅ 报告列表加载
- ✅ 查看报告详情
- ✅ 搜索报告
- ✅ 按时间筛选报告
- ✅ 导出报告
- ✅ Token 消耗统计

#### 6. 交易计划（trading_plan.spec.ts）
- ✅ 交易计划列表加载
- ✅ 创建新交易计划
- ✅ 编辑交易计划
- ✅ 激活/停用交易计划
- ✅ 设置止损止盈规则
- ✅ 查看交易计划详情

---

### P2 - 基础设施

#### 7. 数据质量监控（data_quality.spec.ts）
- ✅ 数据源质量统计页面加载
- ✅ 数据源成功率展示
- ✅ 数据源耗时统计
- ✅ QMT 诊断页面加载
- ✅ 运行 QMT 连接诊断
- ✅ 配置管理页面加载
- ✅ 设置首页加载
- ✅ 股票关注列表分组配置
- ✅ Agent 列表页面加载
- ✅ 查看 Agent 版本历史
- ✅ Agent 版本回滚

#### 8. 页面导航（navigation.spec.ts）
- ✅ Dashboard 页面加载
- ✅ 导航到单股分析页面
- ✅ 导航到筛选页面
- ✅ 导航到收藏页面
- ✅ 导航到报告页面
- ✅ 导航到持仓页面
- ✅ 导航到模拟交易页面
- ✅ 导航到交易复盘页面
- ✅ 导航到任务中心页面
- ✅ 导航到设置页面

---

## 测试覆盖矩阵

| 功能模块 | 测试文件 | 测试数量 | 优先级 |
|---------|---------|---------|-------|
| 认证流程 | auth.spec.ts | 5 | P0 |
| 页面导航 | navigation.spec.ts | 9 | P2 |
| 分析流程 | analysis.spec.ts | 4 | P0 |
| 核心分析流程 | analysis_core.spec.ts | 11 | P0 |
| 智能选股 | screening.spec.ts | 10 | P0 |
| 持仓管理 | portfolio.spec.ts | 14 | P0 |
| 投资报告 | reports.spec.ts | 6 | P1 |
| 交易计划 | trading_plan.spec.ts | 6 | P1 |
| 数据质量监控 | data_quality.spec.ts | 12 | P2 |
| **总计** | **9个文件** | **77个测试** | - |

---

## 运行测试

```bash
# 列出所有测试
npx playwright test --list

# 运行所有测试
npx playwright test

# 运行指定测试文件
npx playwright test analysis_core.spec.ts

# 运行指定测试
npx playwright test -g "单股深度分析"

# UI 模式运行
npx playwright test --ui

# 生成 HTML 报告
npx playwright test --reporter=html

# 查看报告
npx playwright show-report
```

---

## 测试设计原则

### 1. 聚焦核心分析能力
- 单股深度分析流程
- 多条件组合选股
- 持仓管理与分析联动
- 分析报告生成与查看

### 2. 保障数据质量
- 数据源质量监控
- QMT 连接诊断
- 数据源配置管理

### 3. 完整的用户旅程
- 认证 → 选股 → 分析 → 持仓 → 报告 → 复盘
- 覆盖投资人日常工作流程

### 4. 不测试实时行情
- 不包含分钟级实时数据测试
- 不包含集合竞价数据测试
- 聚焦日线级别和历史数据分析

---

## 测试辅助工具

### utils.ts 提供

- `login()` - 登录流程
- `ensureLoggedIn()` - 确保已登录
- `waitForLoadingDone()` - 等待加载完成
- `waitForTableLoaded()` - 等待表格加载
- `getElMessage()` - 获取 Element Plus 消息
- `selectStock()` - 选择股票
- `waitForModalClose()` - 等待模态框关闭
- `clickConfirm()` - 点击确认按钮
- `clickCancel()` - 点击取消按钮
- `waitForSidebarMenu()` - 等待侧边栏菜单
- `navigateBySidebar()` - 侧边栏导航
- `waitForTableData()` - 等待表格数据
- `verifyPageTitle()` - 验证页面标题
- `randomWait()` - 随机等待

---

## 持续集成

建议在 CI/CD 流程中：

1. **每次提交**：运行 P0 核心功能测试
2. **每日构建**：运行所有测试
3. **发布前**：运行完整测试套件并生成报告

```yaml
# GitHub Actions 示例
- name: Run E2E Tests
  run: |
    npm run build
    npm run test:e2e
    
- name: Upload Test Results
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: playwright-report/
```

---

## 下一步优化

1. **增加数据验证测试**
   - 验证分析结果数据完整性
   - 验证报告内容准确性

2. **性能测试**
   - 大批量选股性能
   - 复杂分析任务性能

3. **兼容性测试**
   - 不同浏览器兼容性
   - 不同屏幕尺寸适配

4. **回归测试**
   - 关键业务流程自动化回归
   - 数据一致性验证

---

**报告生成时间**：2026-06-22  
**测试框架版本**：Playwright  
**测试用例总数**：77个
