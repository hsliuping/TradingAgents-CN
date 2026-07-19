# 持仓管理增强计划

> 版本：v3.0 / v3.1
> 创建日期：2026-07-19
> 状态：规划中

## 背景与问题

当前持仓管理存在以下不足：

1. **盈亏计算不准确**：`浮盈 = (现价 - 成本价) × 数量`，未扣除买入/卖出手续费
2. **佣金费率无法配置**：不同券商有万2.5、万1、免5等差异，用户无法自定义
3. **分红未计入收益**：持仓分析 AI 提示词中不包含分红收益信息
4. **手动录入效率低**：用户需逐条填写持仓，无法批量导入或截图识别
5. **无外部 API 接口**：第三方系统（交易机器人、QMT）无法通过 API 管理持仓

## 功能清单

### P0：提示词加入分红收益（0.5h）

**优先级**：⭐⭐⭐ 最高（改动最小，效果立竿见影）

**内容**：
- 修改 `_build_analysis_prompt`，查询 `position_changes` 中 DIVIDEND 类型记录
- 按股票汇总分红收益，注入提示词的"个股收益分析"部分
- 让 AI 分析时能考虑分红对总收益的贡献

**修改文件**：
- `app/services/portfolio_service.py` — `_build_analysis_prompt` 方法

---

### P1：佣金费率设置 + 手续费计算（2~3h）

**优先级**：⭐⭐⭐ 高（盈亏数字准确性基础）

**内容**：
- 新增 `real_market_rules` 配置集合（复用模拟交易的数据结构）
- `add_position` / `operate_position(ADD/REDUCE)` 计算并扣除手续费
- 手续费明细（佣金、印花税、过户费）存入持仓变动记录
- 盈亏计算考虑手续费：`实际成本 = 成交金额 + 手续费`

**佣金配置结构**（与 `paper_market_rules` 一致）：
```json
{
  "market": "CN",
  "rules": {
    "commission": {
      "rate": 0.00025,      // 佣金费率（万2.5）
      "min": 5.0,           // 最低佣金 5 元
      "stamp_duty_rate": 0.001,  // 印花税千1（仅卖出）
      "transfer_fee_rate": 0.00002  // 过户费万0.2
    }
  }
}
```

**修改文件**：
- `app/services/portfolio_service.py` — 加仓/减仓扣手续费
- `app/routers/portfolio.py` — 新增费率配置 API
- `app/models/portfolio.py` — PositionChange 增加手续费明细字段
- `frontend/src/views/Settings/` — 佣金费率设置页面

---

### P2：自动获取分红数据（2~3h）

**优先级**：⭐⭐ 中

**内容**：
- Tushare `dividend()` 接口查询分红记录（需 2000+ 积分）
- AKShare `stock_dividend_cninfo()` 兜底
- 持仓创建时自动查询买入日至今的分红记录
- 分红自动记入 `position_changes`（DIVIDEND 类型）
- 持仓分析中展示累计分红收益

**修改文件**：
- `app/services/portfolio_service.py` — 查询并记录分红
- `app/services/data_sources/tushare_adapter.py` — 分红接口
- `app/services/data_sources/akshare_adapter.py` — 分红接口
- `frontend/src/views/Portfolio/` — 分红展示

---

### P3：融资利息（3~4h）

**优先级**：⭐ 低（多数个人投资者不使用融资）

**内容**：
- 新增 `margin_position` 模型（融资买入的持仓）
- 融资利率配置（默认 6%~8%）
- 按日计息，月末结算
- 盈亏计算扣除融资利息

**计划**：推迟到 v4.0

---

### P4：Excel/CSV 批量导入持仓（2~3h）

**优先级**：⭐⭐⭐ 高（迁移已有持仓的刚需）

**内容**：
- 支持上传 Excel (.xlsx) / CSV 文件
- 智能识别券商导出格式（同花顺、东方财富、华泰等）
- 自定义字段映射（列名 → 系统字段）
- 预览表格 + 错误提示 + 批量校验
- 导入结果统计（成功/失败/跳过）

**支持的券商格式**：
| 券商 | 导出格式 | 关键字段 |
|------|---------|---------|
| 同花顺 | Excel | 股票代码、股票名称、持仓数量、成本价、买入日期 |
| 东方财富 | Excel | 同上 |
| 华泰证券 | CSV | 同上 |
| 通用 | CSV/Excel | 需用户手动映射列名 |

**修改文件**：
- `app/routers/portfolio.py` — 新增导入 API
- `app/services/portfolio_service.py` — `import_positions` 增强
- `frontend/src/views/Portfolio/` — 上传组件 + 预览

---

### P5：截图识别录入（3~4h）

**优先级**：⭐⭐⭐ 高（体验跃升最大）

**内容**：
- 用户上传/粘贴券商界面截图
- 调用 LLM Vision API（GLM-5.1 支持图片理解）解析截图
- Prompt 要求 LLM 返回结构化 JSON：`[{code, name, quantity, cost_price, buy_date}]`
- 前端展示识别结果，用户确认/编辑后提交

**截图识别 Prompt 设计**：
```
请识别这张券商持仓截图，提取每只股票的以下信息：
- 股票代码（6位数字）
- 股票名称
- 持仓数量
- 成本价（摊薄成本）
- 买入日期（如有）

返回 JSON 数组格式：
[{"code": "000001", "name": "平安银行", "quantity": 1000, "cost_price": 12.34, "buy_date": "2024-01-15"}]
```

**修改文件**：
- `app/routers/portfolio.py` — 新增截图识别 API
- `app/services/portfolio_service.py` — OCR 识别 + 解析
- `frontend/src/views/Portfolio/` — 截图上传/粘贴组件 + 结果确认表单

---

### P6：API Key 认证（1~2h）

**优先级**：⭐⭐ 中

**内容**：
- 生成 API Key（`ta_xxxxx` 格式），存入数据库
- 新增 `X-API-Key` 请求头认证中间件
- API Key 权限范围：`positions:read`、`positions:write`、`trades:read`
- 前端管理界面：生成/吊销/查看

**修改文件**：
- `app/core/auth.py` — API Key 认证中间件
- `app/routers/portfolio.py` — 支持 API Key 访问
- `app/models/` — APIKey 模型
- `frontend/src/views/Settings/` — API Key 管理

---

### P7：持仓 API 文档化 + 补齐端点（1~2h）

**优先级**：⭐⭐ 中

**内容**：
- 梳理现有端点，补齐缺失的 CRUD
- 按代码查询持仓 `GET /portfolio/positions/{code}`
- 批量操作 `POST /portfolio/positions/batch`
- OpenAPI 文档自动生成（FastAPI 自带 Swagger）

---

### P8：Webhook 通知（2~3h）

**优先级**：⭐ 低

**内容**：
- 持仓变动时推送事件到用户配置的回调 URL
- 事件类型：`position.added`、`position.reduced`、`dividend.recorded`
- 签名验证（HMAC-SHA256）
- 重试机制（3 次指数退避）

**计划**：推迟到 v3.1 / v4.0

---

## 实施计划

### v3.0 当前版本（立即实施）

| 顺序 | 功能 | 预估 |
|:---:|------|:---:|
| 1 | P0 提示词加入分红收益 | 0.5h |
| 2 | P1 佣金费率设置 + 手续费计算 | 2~3h |
| 3 | P4 Excel/CSV 批量导入 | 2~3h |
| 4 | P5 截图识别录入 | 3~4h |

**小计：约 8~10 小时**

### v3.1 下一版本

| 功能 | 预估 |
|------|:---:|
| P2 自动分红数据 | 2~3h |
| P6 API Key 认证 | 1~2h |
| P7 API 文档化 | 1~2h |

### v4.0 远期

| 功能 | 预估 |
|------|:---:|
| P3 融资利息 | 3~4h |
| P8 Webhook 通知 | 2~3h |
