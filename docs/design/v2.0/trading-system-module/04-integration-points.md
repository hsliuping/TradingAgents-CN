# 功能联动设计

> 本文档定义个人交易系统与现有功能模块的联动方案

---

## 1. 联动策略

### 1.1 当前版本：保守渐进

> **设计原则**：用户的交易系统在初期可能不够完善，直接用来指导分析和交易决策过于激进。
> 当前版本采用**静态保存 + 复盘对照**的方式，不干预用户的实际交易决策。

```
                        ┌─────────────────────────────────────┐
                        │       个人交易系统模块              │
                        │      TradingSystemService           │
                        └───────────┬─────────────────────────┘
                                    │
                                    │ 当前版本只联动复盘
                                    │
                                    ▼
                            ┌──────────────┐
                            │   操作分析    │
                            │   复盘报告    │
                            └──────────────┘
                                    │
                            读取系统规则
                            对照检查执行情况
                            标记违规操作
```

### 1.2 联动范围

| 功能模块 | 当前版本 | 未来版本（可选开启） |
|---------|---------|---------|
| 单股分析/批量分析 | ❌ 不联动 | 显示系统匹配度参考 |
| 模拟交易/下单 | ❌ 不联动 | 提示建议仓位/止损 |
| 持仓分析 | ❌ 不联动 | 对照持仓规则 |
| **操作分析/复盘** | ✅ 联动 | 对照系统规则检查 |

**不联动的原因**：
- 用户的交易系统需要时间打磨和验证
- 一开始就用不完善的系统指导交易，可能带来误导
- 复盘是事后检查，不影响实际决策，风险可控

---

## 2. 操作分析/复盘联动（当前版本）

### 2.1 联动目标

在用户复盘时，自动对照其交易系统规则，检查操作是否符合系统要求：
- 仓位是否超限
- 是否设置了止损
- 是否违反了纪律规则（如追涨停、扛单等）

### 2.2 联动方式

```python
# app/services/trade_review_service.py

from app.services.trading_system_service import get_trading_system_service

class TradeReviewService:

    async def generate_review_report(self, user_id: str, trade_id: str):
        ts_service = get_trading_system_service()

        # 获取交易记录
        trade = await self._get_trade(trade_id)

        # 获取用户交易系统
        system = await ts_service.get_active_system(user_id)

        report = {
            "trade": trade,
            "system_compliance": None
        }

        if system:
            # 检查合规性
            compliance = await ts_service.check_compliance(
                user_id,
                trade["action"],
                {
                    "position_pct": trade["position_percentage"],
                    "is_limit_up": trade.get("is_limit_up", False),
                    "has_stop_loss": trade.get("stop_loss_price") is not None
                }
            )

            report["system_compliance"] = {
                "system_name": system.name,
                "system_version": system.version,
                "is_compliant": compliance.is_compliant,
                "violations": compliance.violations,
                "warnings": compliance.warnings
            }

            # 如果有违规，记录到纪律违规统计
            if not compliance.is_compliant:
                await self._record_violation(user_id, trade_id, compliance.violations)

        return report
```

**前端展示**：

```
┌─────────────────────────────────────────────────────┐
│  📊 操作复盘 - 2024-12-20 买入 000001                │
├─────────────────────────────────────────────────────┤
│  操作详情：                                          │
│  • 买入价格：￥12.50                                 │
│  • 买入数量：4000股                                  │
│  • 仓位占比：50%                                     │
│                                                     │
│  📋 系统执行检查（我的短线系统 v1.2）                 │
│  ├── ✅ 仓位控制：50% ≤ 50%（符合）                  │
│  ├── ✅ 止损设置：已设置 ￥11.88                     │
│  ├── ❌ 追涨停：该股当天涨停（违反纪律）              │
│  └── ✅ 买入理由：已记录                             │
│                                                     │
│  ⚠️ 本次操作存在 1 项违规                            │
│  建议：复盘时重点反思为何违反"不追涨停"规则          │
└─────────────────────────────────────────────────────┘
```

### 2.3 合规检查服务

```python
# app/services/trading_system_service.py

async def check_compliance(
    self,
    user_id: str,
    action: str,
    trade_context: dict
) -> ComplianceResult:
    """
    检查交易操作是否符合用户的交易系统规则

    Args:
        user_id: 用户ID
        action: 操作类型 (buy/sell)
        trade_context: 交易上下文信息
            - position_pct: 仓位百分比
            - is_limit_up: 是否涨停
            - has_stop_loss: 是否设置止损
            - stock_code: 股票代码
            - market_condition: 市场环境

    Returns:
        ComplianceResult: 合规检查结果
    """
    system = await self.get_active_system(user_id)

    if not system:
        return ComplianceResult(
            is_compliant=True,
            has_system=False,
            message="未设置交易系统，跳过合规检查"
        )

    violations = []
    warnings = []

    # 检查仓位规则
    if action == "buy":
        max_per_stock = system.position.max_per_stock
        if trade_context.get("position_pct", 0) > max_per_stock * 100:
            violations.append({
                "rule": "单股仓位上限",
                "expected": f"≤ {max_per_stock * 100}%",
                "actual": f"{trade_context['position_pct']}%",
                "severity": "high"
            })

    # 检查纪律规则
    if system.discipline:
        discipline = system.discipline

        # 检查追涨停
        if discipline.get("no_limit_up") and trade_context.get("is_limit_up"):
            violations.append({
                "rule": "不追涨停",
                "expected": "不买入涨停股",
                "actual": "买入了涨停股",
                "severity": "high"
            })

        # 检查止损设置
        if discipline.get("must_set_stop_loss") and not trade_context.get("has_stop_loss"):
            violations.append({
                "rule": "必须设置止损",
                "expected": "设置止损价",
                "actual": "未设置止损",
                "severity": "medium"
            })

    return ComplianceResult(
        is_compliant=len(violations) == 0,
        has_system=True,
        system_name=system.name,
        system_version=system.version,
        violations=violations,
        warnings=warnings
    )
```

---

## 3. 降级策略

当用户没有设置交易系统时：

1. **不阻断功能**：操作分析/复盘功能正常使用
2. **显示引导**：在复盘页面显示提示："设置您的交易系统后，可自动检查操作是否符合系统规则"
3. **跳过检查**：合规检查返回 `has_system=False`，前端不显示合规检查模块

```python
# 前端处理示例
if report.system_compliance is None or not report.system_compliance.has_system:
    # 显示引导卡片
    show_trading_system_guide()
else:
    # 显示合规检查结果
    show_compliance_result(report.system_compliance)
```

---

## 4. 未来版本联动规划（暂不实现）

> 以下联动功能将在用户的交易系统经过一段时间验证后，在未来版本中考虑实现。
> 这些功能应作为"可选参考"，需要用户主动开启，而非强制指导。

### 4.1 单股分析联动（未来）

- 分析结果显示"系统匹配度"
- 按用户的选股条件给出匹配评估
- 用户可选择是否开启此功能

### 4.2 模拟交易联动（未来）

- 下单时显示"系统建议仓位/止损"
- 仅作为参考，不强制执行
- 用户可选择是否采纳建议

### 4.3 持仓分析联动（未来）

- 对照持仓规则检查当前持仓
- 提示是否超出持股数量/仓位上限
- 仅作为警示，不阻断操作

