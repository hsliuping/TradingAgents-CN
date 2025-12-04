# 模拟交易系统多市场支持设计方案

## 一、现状分析

### 当前系统特点
1. **仅支持A股**：代码使用 `_zfill_code()` 强制补齐6位数字
2. **简单的市价单**：即时成交，无订单簿
3. **数据库集合**：
   - `paper_accounts` - 账户（现金、已实现盈亏）
   - `paper_positions` - 持仓（代码、数量、成本）
   - `paper_orders` - 订单历史
   - `paper_trades` - 成交记录
4. **价格获取**：从 `stock_basic_info` 获取最新价

### 主要限制
- ❌ 不支持港股/美股代码格式
- ❌ 没有市场类型区分
- ❌ 没有货币转换
- ❌ 没有市场规则差异（T+0/T+1、涨跌停等）
- ❌ 没有交易时间检查

---

## 二、设计方案

### 方案A：最小改动方案（推荐用于MVP）

**核心思路**：在现有架构上扩展，保持向后兼容

#### 1. 数据库模型扩展

##### 1.1 账户表 (paper_accounts)
```javascript
{
  "_id": ObjectId("..."),
  "user_id": "user123",
  
  // 多货币账户
  "cash": {
    "CNY": 1000000.0,    // 人民币账户（A股）
    "HKD": 0.0,          // 港币账户（港股）
    "USD": 0.0           // 美元账户（美股）
  },
  
  // 已实现盈亏（按货币）
  "realized_pnl": {
    "CNY": 0.0,
    "HKD": 0.0,
    "USD": 0.0
  },
  
  // 账户设置
  "settings": {
    "auto_currency_conversion": false,  // 是否自动货币转换
    "default_market": "CN"              // 默认市场
  },
  
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

##### 1.2 持仓表 (paper_positions)
```javascript
{
  "_id": ObjectId("..."),
  "user_id": "user123",
  "code": "AAPL",              // 原始代码
  "market": "US",              // 市场类型 (CN/HK/US)
  "currency": "USD",           // 交易货币
  "quantity": 100,             // 持仓数量
  "avg_cost": 150.50,          // 平均成本（原币种）
  "available_qty": 100,        // 可用数量（考虑T+1限制）
  "frozen_qty": 0,             // 冻结数量（挂单中）
  "updated_at": "2024-01-01T00:00:00Z"
}
```

##### 1.3 订单表 (paper_orders)
```javascript
{
  "_id": ObjectId("..."),
  "user_id": "user123",
  "code": "AAPL",
  "market": "US",
  "currency": "USD",
  "side": "buy",               // buy/sell
  "quantity": 100,
  "price": 150.50,             // 成交价格
  "amount": 15050.0,           // 成交金额
  "commission": 1.0,           // 手续费
  "status": "filled",          // filled/rejected/cancelled
  "created_at": "2024-01-01T10:00:00Z",
  "filled_at": "2024-01-01T10:00:01Z",
  "analysis_id": "abc123"      // 关联的分析ID
}
```

##### 1.4 成交记录表 (paper_trades)
```javascript
{
  "_id": ObjectId("..."),
  "user_id": "user123",
  "code": "AAPL",
  "market": "US",
  "currency": "USD",
  "side": "buy",
  "quantity": 100,
  "price": 150.50,
  "amount": 15050.0,
  "commission": 1.0,
  "pnl": 0.0,                  // 已实现盈亏（卖出时计算）
  "timestamp": "2024-01-01T10:00:01Z",
  "analysis_id": "abc123"
}
```

#### 2. 市场规则配置

##### 2.1 市场规则表 (paper_market_rules)
```javascript
{
  "_id": ObjectId("..."),
  "market": "CN",
  "currency": "CNY",
  "rules": {
    "t_plus": 1,                    // T+1交易
    "price_limit": {
      "enabled": true,
      "up_limit": 10.0,             // 涨停 10%
      "down_limit": -10.0,          // 跌停 -10%
      "st_up_limit": 5.0,           // ST股涨停 5%
      "st_down_limit": -5.0         // ST股跌停 -5%
    },
    "lot_size": 100,                // 最小交易单位（手）
    "min_price_tick": 0.01,         // 最小报价单位
    "commission": {
      "rate": 0.0003,               // 佣金费率 0.03%
      "min": 5.0,                   // 最低佣金 5元
      "stamp_duty": 0.001           // 印花税 0.1%（仅卖出）
    },
    "trading_hours": {
      "timezone": "Asia/Shanghai",
      "sessions": [
        {"open": "09:30", "close": "11:30"},
        {"open": "13:00", "close": "15:00"}
      ]
    },
    "short_selling": {
      "enabled": false              // 不支持做空
    }
  }
}

{
  "_id": ObjectId("..."),
  "market": "HK",
  "currency": "HKD",
  "rules": {
    "t_plus": 0,                    // T+0交易
    "price_limit": {
      "enabled": false              // 无涨跌停限制
    },
    "lot_size": null,               // 每只股票不同，需查询
    "min_price_tick": 0.01,
    "commission": {
      "rate": 0.0003,
      "min": 3.0,
      "stamp_duty": 0.0013,         // 印花税 0.13%
      "transaction_levy": 0.00005,  // 交易征费 0.005%
      "trading_fee": 0.00005        // 交易费 0.005%
    },
    "trading_hours": {
      "timezone": "Asia/Hong_Kong",
      "sessions": [
        {"open": "09:30", "close": "12:00"},
        {"open": "13:00", "close": "16:00"}
      ]
    },
    "short_selling": {
      "enabled": true,
      "margin_requirement": 1.4     // 保证金要求 140%
    }
  }
}

{
  "_id": ObjectId("..."),
  "market": "US",
  "currency": "USD",
  "rules": {
    "t_plus": 0,                    // T+0交易
    "price_limit": {
      "enabled": false
    },
    "lot_size": 1,                  // 1股起
    "min_price_tick": 0.01,
    "commission": {
      "rate": 0.0,
      "min": 0.0,                   // 零佣金
      "sec_fee": 0.0000278          // SEC费用
    },
    "trading_hours": {
      "timezone": "America/New_York",
      "sessions": [
        {"open": "09:30", "close": "16:00"}
      ],
      "extended_hours": {
        "pre_market": {"open": "04:00", "close": "09:30"},
        "after_hours": {"open": "16:00", "close": "20:00"}
      }
    },
    "short_selling": {
      "enabled": true,
      "pdt_rule": true,             // Pattern Day Trader规则
      "min_account_equity": 25000   // PDT最低账户净值
    }
  }
}
```

#### 3. 后端API修改

##### 3.1 修改下单接口

**文件**: `app/routers/paper.py`

**修改点**:
1. ✅ 支持市场类型参数
2. ✅ 使用 `_detect_market_and_code()` 识别市场
3. ✅ 根据市场规则验证订单
4. ✅ 使用 `ForeignStockService` 获取港股/美股价格
5. ✅ 计算手续费
6. ✅ 检查T+1可用数量

**新的请求模型**:
```python
class PlaceOrderRequest(BaseModel):
    code: str = Field(..., description="股票代码（支持A股/港股/美股）")
    side: Literal["buy", "sell"]
    quantity: int = Field(..., gt=0)
    market: Optional[str] = Field(None, description="市场类型 (CN/HK/US)，不传则自动识别")
    analysis_id: Optional[str] = None
```

##### 3.2 新增货币转换接口

```python
@router.post("/account/currency/convert", response_model=dict)
async def convert_currency(
    from_currency: str,
    to_currency: str,
    amount: float,
    current_user: dict = Depends(get_current_user)
):
    """货币转换（使用实时汇率）"""
    # 实现货币转换逻辑
    pass
```

##### 3.3 修改账户查询接口

```python
@router.get("/account", response_model=dict)
async def get_account(current_user: dict = Depends(get_current_user)):
    """获取账户信息（支持多货币）"""
    # 返回多货币账户信息
    # 计算总资产（按基准货币）
    pass
```

#### 4. 前端修改

##### 4.1 下单对话框增强

**文件**: `frontend/src/views/PaperTrading/index.vue`

**修改点**:
1. ✅ 自动识别股票市场类型
2. ✅ 显示对应货币
3. ✅ 显示市场规则提示（T+0/T+1、手数等）
4. ✅ 计算预估手续费

**UI示例**:
```vue
<el-form-item label="股票代码">
  <el-input v-model="order.code" placeholder="输入代码（如：AAPL、0700、000001）">
    <template #append>
      <el-tag v-if="detectedMarket">{{ detectedMarket }}</el-tag>
    </template>
  </el-input>
</el-form-item>

<el-alert v-if="marketRules" type="info" :closable="false">
  <template #title>
    <div>
      <span>市场规则：</span>
      <el-tag size="small">{{ marketRules.t_plus === 0 ? 'T+0' : 'T+1' }}</el-tag>
      <el-tag size="small">{{ marketRules.currency }}</el-tag>
      <el-tag size="small" v-if="marketRules.lot_size > 1">
        {{ marketRules.lot_size }}股/手
      </el-tag>
    </div>
  </template>
</el-alert>
```

##### 4.2 账户页面多货币显示

```vue
<el-descriptions title="账户资产" :column="3">
  <el-descriptions-item label="人民币账户">
    ¥{{ formatAmount(account.cash.CNY) }}
  </el-descriptions-item>
  <el-descriptions-item label="港币账户">
    HK${{ formatAmount(account.cash.HKD) }}
  </el-descriptions-item>
  <el-descriptions-item label="美元账户">
    ${{ formatAmount(account.cash.USD) }}
  </el-descriptions-item>
</el-descriptions>

<el-descriptions-item label="总资产（人民币）">
  ¥{{ formatAmount(account.total_equity_cny) }}
</el-descriptions-item>
```

---

### 方案B：完整重构方案（长期规划）

**核心思路**：构建专业的模拟交易引擎

#### 1. 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Paper Trading API                     │
│  /api/paper/account, /order, /positions, /trades        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│              Paper Trading Service                       │
│  - Order Management System (OMS)                         │
│  - Position Manager                                      │
│  - Risk Manager                                          │
│  - Commission Calculator                                 │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│              Market Data Service                         │
│  - Real-time Quotes (CN/HK/US)                          │
│  - Market Rules Engine                                   │
│  - Trading Calendar                                      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│                   Database Layer                         │
│  MongoDB: accounts, positions, orders, trades, rules    │
└─────────────────────────────────────────────────────────┘
```

#### 2. 核心组件

##### 2.1 订单管理系统 (OMS)
- 订单验证（资金、持仓、市场规则）
- 订单路由（按市场分发）
- 订单状态管理
- 订单撮合（模拟）

##### 2.2 持仓管理器
- 多市场持仓跟踪
- T+1可用数量计算
- 盈亏计算（已实现/未实现）
- 持仓风险监控

##### 2.3 风险管理器
- 资金检查
- 持仓限制
- 集中度控制
- 杠杆检查（融资融券）

##### 2.4 手续费计算器
- 按市场规则计算佣金
- 印花税、交易征费等
- 滑点模拟（可选）

---

## 三、实施计划

### Phase 1: 基础多市场支持（1-2周）

#### Week 1: 数据库和后端
- [ ] 数据库模型迁移脚本
- [ ] 修改 `paper.py` 支持市场识别
- [ ] 集成 `ForeignStockService` 获取价格
- [ ] 基础手续费计算

#### Week 2: 前端和测试
- [ ] 前端下单对话框增强
- [ ] 账户页面多货币显示
- [ ] 持仓列表显示市场类型
- [ ] 端到端测试

### Phase 2: 市场规则引擎（2-3周）

- [ ] 市场规则配置表
- [ ] T+1可用数量计算
- [ ] 涨跌停检查
- [ ] 交易时间检查
- [ ] 手数/最小报价单位验证

### Phase 3: 高级功能（3-4周）

- [ ] 货币转换功能
- [ ] 限价单支持
- [ ] 止损止盈单
- [ ] 持仓分析报表
- [ ] 交易日志和回放

---

## 四、技术要点

### 1. 价格获取

```python
async def _get_last_price(code: str, market: str) -> Optional[float]:
    """获取最新价格（支持多市场）"""
    if market == 'CN':
        # A股：从 stock_basic_info 获取
        db = get_mongo_db()
        info = await db["stock_basic_info"].find_one({"code": code})
        return info.get("close") if info else None
    elif market in ['HK', 'US']:
        # 港股/美股：使用 ForeignStockService
        service = ForeignStockService()
        if market == 'HK':
            quote = await service.get_hk_quote(code)
        else:
            quote = await service.get_us_quote(code)
        return quote.get("current_price") if quote else None
    return None
```

### 2. 手续费计算

```python
def calculate_commission(market: str, side: str, amount: float, rules: dict) -> float:
    """计算手续费"""
    commission = 0.0
    
    # 佣金
    comm_rate = rules["commission"]["rate"]
    comm_min = rules["commission"]["min"]
    commission += max(amount * comm_rate, comm_min)
    
    # 印花税（仅卖出）
    if side == "sell" and "stamp_duty" in rules["commission"]:
        commission += amount * rules["commission"]["stamp_duty"]
    
    # 其他费用（港股）
    if market == "HK":
        if "transaction_levy" in rules["commission"]:
            commission += amount * rules["commission"]["transaction_levy"]
        if "trading_fee" in rules["commission"]:
            commission += amount * rules["commission"]["trading_fee"]
    
    return round(commission, 2)
```

### 3. T+1可用数量

```python
async def get_available_quantity(user_id: str, code: str, market: str) -> int:
    """获取可用数量（考虑T+1）"""
    db = get_mongo_db()
    pos = await db["paper_positions"].find_one({"user_id": user_id, "code": code})
    
    if not pos:
        return 0
    
    total_qty = pos.get("quantity", 0)
    
    # A股T+1：今天买入的不能卖出
    if market == "CN":
        today = datetime.utcnow().date().isoformat()
        today_buy = await db["paper_trades"].aggregate([
            {"$match": {
                "user_id": user_id,
                "code": code,
                "side": "buy",
                "timestamp": {"$gte": today}
            }},
            {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
        ]).to_list(1)
        
        today_buy_qty = today_buy[0]["total"] if today_buy else 0
        return total_qty - today_buy_qty
    
    # 港股/美股T+0：全部可用
    return total_qty
```

---

## 五、数据库迁移脚本

```python
# scripts/migrate_paper_trading_multi_market.py

async def migrate_accounts():
    """迁移账户表：单一现金 -> 多货币"""
    db = get_mongo_db()
    accounts = await db["paper_accounts"].find({}).to_list(None)
    
    for acc in accounts:
        # 将旧的 cash 字段转换为多货币格式
        old_cash = acc.get("cash", 0.0)
        new_cash = {
            "CNY": old_cash,
            "HKD": 0.0,
            "USD": 0.0
        }
        
        old_pnl = acc.get("realized_pnl", 0.0)
        new_pnl = {
            "CNY": old_pnl,
            "HKD": 0.0,
            "USD": 0.0
        }
        
        await db["paper_accounts"].update_one(
            {"_id": acc["_id"]},
            {"$set": {
                "cash": new_cash,
                "realized_pnl": new_pnl,
                "settings": {
                    "auto_currency_conversion": False,
                    "default_market": "CN"
                }
            }}
        )

async def migrate_positions():
    """迁移持仓表：添加市场和货币字段"""
    db = get_mongo_db()
    positions = await db["paper_positions"].find({}).to_list(None)
    
    for pos in positions:
        code = pos.get("code")
        # 假设旧数据都是A股
        await db["paper_positions"].update_one(
            {"_id": pos["_id"]},
            {"$set": {
                "market": "CN",
                "currency": "CNY",
                "available_qty": pos.get("quantity", 0),
                "frozen_qty": 0
            }}
        )
```

---

## 六、推荐实施路径

### 🎯 推荐：方案A（最小改动）

**理由**:
1. ✅ 快速上线（1-2周）
2. ✅ 向后兼容
3. ✅ 满足基本需求
4. ✅ 可逐步演进到方案B

**实施步骤**:
1. 数据库模型扩展（添加字段，不删除旧字段）
2. 后端API修改（支持市场识别和多货币）
3. 前端UI增强（显示市场类型和货币）
4. 数据迁移脚本（将现有数据迁移到新格式）
5. 测试和上线

**后续演进**:
- Phase 2: 添加市场规则引擎
- Phase 3: 添加高级订单类型
- Phase 4: 完整重构为方案B

---

## 七、风险和注意事项

### 1. 数据一致性
- ⚠️ 迁移过程中确保数据完整性
- ⚠️ 多货币账户的余额计算
- ⚠️ 持仓和订单的关联关系

### 2. 汇率问题
- ⚠️ 实时汇率获取（可使用 Alpha Vantage FX API）
- ⚠️ 汇率缓存策略
- ⚠️ 历史汇率记录（用于盈亏计算）

### 3. 市场规则
- ⚠️ 不同市场的交易规则差异
- ⚠️ 节假日和交易日历
- ⚠️ 特殊股票的规则（ST、创业板等）

### 4. 性能考虑
- ⚠️ 多市场价格获取的并发性能
- ⚠️ 持仓估值计算的效率
- ⚠️ 数据库查询优化

---

## 八、测试计划

### 1. 单元测试
- [ ] 市场识别函数
- [ ] 手续费计算
- [ ] T+1可用数量计算
- [ ] 货币转换

### 2. 集成测试
- [ ] A股下单流程
- [ ] 港股下单流程
- [ ] 美股下单流程
- [ ] 多市场持仓查询

### 3. 端到端测试
- [ ] 完整交易流程（下单-成交-持仓-卖出）
- [ ] 账户资产计算
- [ ] 盈亏计算
- [ ] 数据迁移验证

---

## 九、参考资料

- [A股交易规则](https://www.sse.com.cn/)
- [港股交易规则](https://www.hkex.com.hk/)
- [美股交易规则](https://www.sec.gov/)
- [Backtrader文档](https://www.backtrader.com/)
- [QuantConnect文档](https://www.quantconnect.com/)

