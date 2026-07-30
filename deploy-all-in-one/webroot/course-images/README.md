# 课程截图目录

本目录存放《从散户到系统交易者：AI赋能的可进化投资法》课程的所有截图和图片资源。

## 当前状态

- 前端开发服务默认访问地址：`http://localhost:3000`
- 后端接口默认访问地址：`http://localhost:8000`
- 目前已存在的截图：通用截图 5 张、lesson-02 示意图 2 张
- 目前仍需补齐的重点：单股研究、批量分析、持仓研究、操作复盘、交易计划、分析流相关截图

## 核心页面路径速查

| 功能 | 路径 | 说明 |
|------|------|------|
| 登录页 | `/login` | 通用截图 |
| 仪表板 | `/dashboard` | 通用截图 |
| 学习中心 | `/learning` | 高级课程入口 |
| 高级课程列表 | `/learning/advanced` | 课程分类页 |
| 单股研究 | `/analysis/single` | 第3课主页面 |
| 批量分析 | `/analysis/batch` | 第4课主页面 |
| 任务中心 | `/tasks/unified` | 第4课任务结果页 |
| 分析流 | `/workflow` | 第2、17、20课相关 |
| 模拟交易 | `/paper` | 第10课主页面 |
| 持仓研究 | `/portfolio` | 第11-12课主页面 |
| 操作复盘 | `/review` | 第15-16课主页面 |
| 交易计划 | `/trading-system` | 第23-24课主页面 |

## 截图前置条件

为避免拍摄时频繁回填数据，建议先准备以下最小演示数据：

- 单股研究：准备一只可分析股票，例如 `000001`，用于展示输入区、分析深度和结果卡片
- 批量分析：准备 3-5 只股票代码，确保任务中心有至少 1 个已完成任务
- 模拟交易：准备至少 1 笔买入和 1 笔卖出记录，便于展示持仓与交易历史
- 持仓研究：准备至少 2 只持仓股票，最好覆盖不同行业，便于展示行业分布和研究入口
- 操作复盘：准备至少 1 条可复盘记录和 1 条历史复盘记录
- 交易计划：准备 1 个已创建的交易计划；如果没有，也需要保留 1 张空状态或创建向导截图
- 分析流：准备 1 个已保存的分析流，便于展示流程管理、节点配置和分析师选择

## 建议先拍的第一批

如果本轮目标是先把课程展示材料补齐，建议优先完成以下页面：

1. `common/common-03-left-menu.png`：左侧菜单完整展开，确保出现“单股研究 / 持仓研究 / 操作复盘 / 交易计划”
2. `lesson-03/03-single-01-page-overview.png`：单股研究页全貌
3. `lesson-03/03-single-06-report-overview.png`：单股研究结果概览
4. `lesson-04/04-batch-01-page-overview.png`：批量分析页全貌
5. `lesson-04/04-batch-05-task-center.png`：任务中心结果页
6. `lesson-10/10-mock-01-page-overview.png`：模拟交易页全貌
7. `lesson-11/11-holding-01-page-overview.png`：持仓研究页全貌
8. `lesson-15/15-review-01-page-overview.png`：操作复盘页全貌
9. `lesson-15/15-review-04-score-cards.png`：操作复盘评分卡片
10. `lesson-23/23-system-01-trade-plan-template.png`：交易计划列表或创建入口
11. `lesson-23/23-system-03-rule-setting.png`：交易计划创建向导中的规则设置步骤

## 📁 目录结构

```
images/
├── README.md                    # 本说明文件
├── common/                      # 通用截图（导航、登录等）
├── lesson-01/                   # 第1课截图
├── lesson-02/                   # 第2课截图
├── lesson-03/                   # 第3课截图
├── lesson-04/                   # 第4课截图
├── lesson-05/                   # 第5课截图
├── lesson-06/                   # 第6课截图
├── lesson-07/                   # 第7课截图
├── lesson-08/                   # 第8课截图
├── lesson-09/                   # 第9课截图
├── lesson-10/                   # 第10课截图
├── lesson-11/                   # 第11课截图
├── lesson-12/                   # 第12课截图
├── lesson-13/                   # 第13课截图
├── lesson-14/                   # 第14课截图
├── lesson-15/                   # 第15课截图
├── lesson-16/                   # 第16课截图
├── lesson-17/                   # 第17课截图
├── lesson-18/                   # 第18课截图
├── lesson-19/                   # 第19课截图
├── lesson-20/                   # 第20课截图
├── lesson-21/                   # 第21课截图
├── lesson-22/                   # 第22课截图
├── lesson-23/                   # 第23课截图
└── lesson-24/                   # 第24课截图
```

## 📝 命名规范

### 文件命名格式

```
[课程编号]-[功能模块]-[序号]-[描述].png
```

### 示例

```
03-single-analysis-01-page-overview.png     # 第3课-单股研究-01-页面概览
03-single-analysis-02-config-panel.png      # 第3课-单股研究-02-配置面板
15-trade-review-01-review-form.png          # 第15课-操作复盘-01-复盘表单
15-trade-review-02-score-display.png        # 第15课-操作复盘-02-评分展示
```

## 📐 截图规范

### 尺寸要求
- **推荐宽度**：1200px - 1600px
- **最小宽度**：800px
- **格式**：PNG（界面截图）/ GIF（操作演示）

### 内容要求
- 隐藏敏感信息（账户、密码等）
- 使用示例数据，不使用真实交易数据
- 确保界面元素清晰可见
- 必要时添加标注（箭头、框选）

### 标注规范
- 使用红色（#FF0000）或蓝色（#0066CC）进行标注
- 箭头粗细：3px
- 框选线条：2px 虚线

## 🔗 在课程中引用截图

### Markdown 引用格式

```markdown
![页面概览](./images/lesson-03/03-single-analysis-01-page-overview.png)
*图3-1：单股研究页面概览*
```

### 带说明的引用

```markdown
<figure>
  <img src="./images/lesson-03/03-single-analysis-01-page-overview.png" alt="单股研究页面概览">
  <figcaption>图3-1：单股研究页面概览，左侧为配置区域，右侧为结果展示区域</figcaption>
</figure>
```

## 📋 截图清单

详细的截图需求清单请参考：[截图需求清单.md](./截图需求清单.md)

---

**最后更新**：2026-04-29

