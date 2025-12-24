# 数据模型设计

> 本文档定义个人交易系统模块的数据结构

---

## 1. MongoDB 集合设计

### 1.1 集合概览

| 集合名 | 说明 | 索引 |
|-------|------|------|
| `trading_systems` | 交易系统主表 | `user_id`, `is_active`, `created_at` |
| `trading_system_versions` | 交易系统版本历史 | `system_id`, `version`, `created_at` |

### 1.2 trading_systems 集合

```json
{
  "_id": ObjectId,
  "user_id": "string",           // 所属用户
  "name": "string",              // 系统名称，如 "我的短线系统"
  "description": "string",       // 系统描述
  "style": "string",             // 交易风格: short_term/medium_term/long_term
  "risk_profile": "string",      // 风险偏好: conservative/balanced/aggressive
  "version": "string",           // 当前版本号，如 "1.0.0"
  "is_active": true,             // 是否为当前激活系统
  
  // 六大模块规则
  "stock_selection": { ... },    // 选股规则
  "timing": { ... },             // 择时规则
  "position": { ... },           // 仓位规则
  "holding": { ... },            // 持仓规则
  "risk_management": { ... },    // 止盈止损规则
  "review": { ... },             // 复盘规则
  "discipline": { ... },         // 纪律规则
  
  // 元数据
  "created_at": ISODate,
  "updated_at": ISODate
}
```

---

## 2. 规则模块详细结构

### 2.1 选股规则 (stock_selection)

```json
{
  "stock_selection": {
    // 分析配置
    "analysis_config": {
      "analysts": ["fundamentals", "market", "news", "social"],
      "weights": {
        "technical": 0.4,
        "fundamental": 0.2,
        "news": 0.2,
        "sentiment": 0.2
      }
    },
    
    // 必备条件（全部满足才考虑）
    "must_have": [
      {"type": "min_daily_turnover", "value": 50000000, "unit": "CNY"},
      {"type": "min_score", "value": 75},
      {"type": "risk_level", "value": ["low", "medium"]}
    ],
    
    // 排除条件（满足任一则排除）
    "exclude": [
      {"type": "st_stock", "value": true},
      {"type": "consecutive_limit_up_days", "value": 3},
      {"type": "ipo_days_within", "value": 30}
    ],
    
    // 加分条件（可选，提高评分）
    "bonus": [
      {"type": "hot_sector", "weight": 10},
      {"type": "volume_breakout", "weight": 5}
    ]
  }
}
```

### 2.2 择时规则 (timing)

```json
{
  "timing": {
    // 大盘条件
    "market_condition": {
      "allowed_states": ["bull", "range"],
      "not_allowed_ratings": ["strong_bearish"]
    },
    
    // 行业条件
    "sector_condition": {
      "prefer_hot_sector": true,
      "avoid_declining_sector": true
    },
    
    // 买入信号
    "entry_signals": [
      {"type": "breakout_high", "description": "突破前期高点，放量"},
      {"type": "pullback_support", "description": "回调到支撑位，缩量企稳"}
    ],
    
    // 确认条件
    "confirmation": [
      {"type": "close_above_breakout", "description": "收盘站稳突破位"},
      {"type": "no_breakdown_next_day", "description": "次日不跌破突破位"}
    ]
  }
}
```

### 2.3 仓位规则 (position)

```json
{
  "position": {
    // 总仓位控制（按市况）
    "total_position": {
      "bull": 0.8,
      "range": 0.5,
      "bear": 0.2
    },
    
    // 单只股票上限
    "max_per_stock": 0.5,
    
    // 持股数量
    "max_holdings": 3,
    "min_holdings": 1,
    
    // 分批策略
    "scaling": {
      "enabled": true,
      "batches": 2,
      "batch_ratios": [0.6, 0.4],
      "batch_conditions": [
        "突破确认时买入",
        "回调到支撑位时买入"
      ]
    }
  }
}
```

### 2.4 持仓规则 (holding)

```json
{
  "holding": {
    // 检视频率
    "review_frequency": "daily",

    // 加仓条件
    "add_conditions": [
      {"type": "price_above_cost", "description": "股价高于成本价"},
      {"type": "trend_intact", "description": "上涨趋势未破坏"},
      {"type": "position_below_max", "description": "仓位未达上限"}
    ],

    // 减仓条件
    "reduce_conditions": [
      {"type": "target_reached", "description": "达到止盈目标"},
      {"type": "trend_weakening", "description": "上涨动能减弱"}
    ],

    // 换股条件
    "switch_conditions": [
      {"type": "better_opportunity", "description": "发现更好机会"},
      {"type": "sector_rotation", "description": "板块轮动"}
    ]
  }
}
```

### 2.5 止盈止损规则 (risk_management)

```json
{
  "risk_management": {
    // 止损设置
    "stop_loss": {
      "type": "fixed",           // fixed/trailing/logical
      "percentage": 0.05,        // 5% 止损
      "trailing_distance": null  // 移动止损距离（如果是trailing类型）
    },

    // 止盈设置
    "take_profit": {
      "type": "scaled",          // fixed/scaled/trailing
      "targets": [
        {"percentage": 0.1, "sell_ratio": 0.5},   // 涨10%卖50%
        {"percentage": 0.2, "sell_ratio": 0.3},   // 涨20%再卖30%
        {"percentage": 0.3, "sell_ratio": 0.2}    // 涨30%卖剩余
      ]
    },

    // 时间止损（短线专用）
    "time_stop": {
      "enabled": true,
      "max_holding_days": 5,
      "action": "review"         // review/sell
    },

    // 逻辑止损
    "logical_stop": {
      "enabled": true,
      "conditions": [
        "买入逻辑不再成立",
        "基本面发生重大负面变化",
        "行业政策出现重大利空"
      ]
    }
  }
}
```

### 2.6 复盘规则 (review)

```json
{
  "review": {
    // 复盘频率
    "frequency": "weekly",

    // 复盘内容
    "checklist": [
      "检查持仓表现",
      "分析买卖决策",
      "评估系统执行",
      "总结经验教训"
    ],

    // 案例保存规则
    "case_save": {
      "save_profitable": true,
      "save_losing": true,
      "min_profit_pct": 0.1,      // 盈利超过10%保存
      "min_loss_pct": -0.05       // 亏损超过5%保存
    }
  }
}
```

### 2.7 纪律规则 (discipline)

```json
{
  "discipline": {
    // 绝对禁止
    "must_not": [
      {"rule": "不追涨停", "description": "不买当天涨停的股票"},
      {"rule": "不满仓单只", "description": "单只股票不超过设定仓位上限"},
      {"rule": "不扛单", "description": "到达止损位必须执行"}
    ],

    // 必须做到
    "must_do": [
      {"rule": "设置止损", "description": "买入前必须设定止损价"},
      {"rule": "记录买入理由", "description": "每次买入都要记录理由"},
      {"rule": "定期复盘", "description": "按设定频率进行复盘"}
    ],

    // 违规处理
    "violation_actions": [
      {"trigger": "single_violation", "action": "记录警告"},
      {"trigger": "three_violations_month", "action": "降低仓位上限至50%"},
      {"trigger": "five_violations_month", "action": "暂停交易一周"}
    ]
  }
}
```

---

## 3. Pydantic 模型定义

### 3.1 文件位置

```
app/models/trading_system.py
```

### 3.2 核心模型

```python
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class TradingStyle(str, Enum):
    SHORT_TERM = "short_term"      # 短线（1天-1周）
    MEDIUM_TERM = "medium_term"    # 中线（1周-1月）
    LONG_TERM = "long_term"        # 长线（1月-1年+）

class RiskProfile(str, Enum):
    CONSERVATIVE = "conservative"  # 保守
    BALANCED = "balanced"          # 稳健
    AGGRESSIVE = "aggressive"      # 激进

# 选股规则模型
class StockSelectionRule(BaseModel):
    analysis_config: Dict[str, Any] = Field(default_factory=dict)
    must_have: List[Dict[str, Any]] = Field(default_factory=list)
    exclude: List[Dict[str, Any]] = Field(default_factory=list)
    bonus: List[Dict[str, Any]] = Field(default_factory=list)

# 择时规则模型
class TimingRule(BaseModel):
    market_condition: Dict[str, Any] = Field(default_factory=dict)
    sector_condition: Dict[str, Any] = Field(default_factory=dict)
    entry_signals: List[Dict[str, Any]] = Field(default_factory=list)
    confirmation: List[Dict[str, Any]] = Field(default_factory=list)

# 仓位规则模型
class PositionRule(BaseModel):
    total_position: Dict[str, float] = Field(
        default_factory=lambda: {"bull": 0.8, "range": 0.5, "bear": 0.2}
    )
    max_per_stock: float = 0.3
    max_holdings: int = 5
    min_holdings: int = 1
    scaling: Dict[str, Any] = Field(default_factory=dict)

# 交易系统主模型
class TradingSystem(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    name: str
    description: str = ""
    style: TradingStyle = TradingStyle.MEDIUM_TERM
    risk_profile: RiskProfile = RiskProfile.BALANCED
    version: str = "1.0.0"
    is_active: bool = True

    # 六大模块
    stock_selection: StockSelectionRule = Field(default_factory=StockSelectionRule)
    timing: TimingRule = Field(default_factory=TimingRule)
    position: PositionRule = Field(default_factory=PositionRule)
    holding: Dict[str, Any] = Field(default_factory=dict)
    risk_management: Dict[str, Any] = Field(default_factory=dict)
    review: Dict[str, Any] = Field(default_factory=dict)
    discipline: Dict[str, Any] = Field(default_factory=dict)

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 4. 版本历史表

```json
{
  "_id": ObjectId,
  "system_id": "string",         // 关联的交易系统ID
  "version": "string",           // 版本号
  "snapshot": { ... },           // 完整的系统快照
  "change_summary": "string",    // 变更说明
  "created_at": ISODate
}
```
```

