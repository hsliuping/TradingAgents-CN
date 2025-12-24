# API 接口设计

> 本文档定义个人交易系统模块的 RESTful API 接口

---

## 1. API 概览

### 1.1 基础路径

```
/api/trading-system
```

### 1.2 接口列表

| 方法 | 路径 | 说明 |
|-----|------|------|
| GET | `/` | 获取用户的交易系统列表 |
| POST | `/` | 创建新的交易系统 |
| GET | `/{system_id}` | 获取交易系统详情 |
| PUT | `/{system_id}` | 更新交易系统 |
| DELETE | `/{system_id}` | 删除交易系统 |
| POST | `/{system_id}/activate` | 激活交易系统 |
| GET | `/{system_id}/versions` | 获取版本历史 |
| POST | `/{system_id}/versions` | 保存新版本 |
| GET | `/active` | 获取当前激活的交易系统 |
| GET | `/templates` | 获取系统模板列表 |
| POST | `/from-template/{template_id}` | 从模板创建 |
| GET | `/export/{system_id}` | 导出为 Markdown |

---

## 2. 接口详细定义

### 2.1 获取交易系统列表

```
GET /api/trading-system
```

**请求头**
```
Authorization: Bearer {token}
```

**响应**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "system_001",
        "name": "我的短线系统",
        "style": "short_term",
        "risk_profile": "balanced",
        "version": "1.2.0",
        "is_active": true,
        "created_at": "2024-12-01T10:00:00Z",
        "updated_at": "2024-12-20T15:30:00Z"
      }
    ],
    "total": 1
  }
}
```

### 2.2 创建交易系统

```
POST /api/trading-system
```

**请求体**
```json
{
  "name": "我的短线系统",
  "description": "基于技术分析的短线交易系统",
  "style": "short_term",
  "risk_profile": "balanced",
  
  "stock_selection": {
    "analysis_config": {
      "analysts": ["market", "news", "social"],
      "weights": {"technical": 0.4, "news": 0.3, "sentiment": 0.3}
    },
    "must_have": [
      {"type": "min_daily_turnover", "value": 50000000}
    ],
    "exclude": [
      {"type": "st_stock", "value": true}
    ]
  },
  
  "position": {
    "total_position": {"bull": 0.8, "range": 0.5, "bear": 0.2},
    "max_per_stock": 0.5,
    "max_holdings": 3
  },
  
  "risk_management": {
    "stop_loss": {"type": "fixed", "percentage": 0.05},
    "take_profit": {"type": "fixed", "percentage": 0.15}
  }
}
```

**响应**
```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": "system_002",
    "name": "我的短线系统",
    "version": "1.0.0",
    "is_active": true
  }
}
```

### 2.3 获取交易系统详情

```
GET /api/trading-system/{system_id}
```

**响应**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "system_001",
    "name": "我的短线系统",
    "description": "...",
    "style": "short_term",
    "risk_profile": "balanced",
    "version": "1.2.0",
    "is_active": true,
    
    "stock_selection": { ... },
    "timing": { ... },
    "position": { ... },
    "holding": { ... },
    "risk_management": { ... },
    "review": { ... },
    "discipline": { ... },
    
    "created_at": "2024-12-01T10:00:00Z",
    "updated_at": "2024-12-20T15:30:00Z"
  }
}
```

### 2.4 更新交易系统

```
PUT /api/trading-system/{system_id}
```

**请求体**（部分更新）
```json
{
  "name": "我的短线系统 V2",
  "position": {
    "max_per_stock": 0.4
  },
  "change_summary": "调整单股仓位上限从50%到40%"
}
```

**说明**
- 更新时自动递增小版本号（如 1.2.0 → 1.2.1）
- 可选择是否保存版本历史

### 2.5 激活交易系统

```
POST /api/trading-system/{system_id}/activate
```

**说明**
- 将指定系统设为激活状态
- 同时将该用户的其他系统设为非激活

**响应**
```json
{
  "code": 0,
  "message": "已激活",
  "data": {
    "active_system_id": "system_001",
    "active_system_name": "我的短线系统"
  }
}
```

### 2.6 获取当前激活的交易系统

```
GET /api/trading-system/active
```

**响应**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "system_001",
    "name": "我的短线系统",
    "style": "short_term",
    "version": "1.2.0",

    // 完整规则（供其他模块读取）
    "stock_selection": { ... },
    "timing": { ... },
    "position": { ... },
    "holding": { ... },
    "risk_management": { ... },
    "review": { ... },
    "discipline": { ... }
  }
}
```

**特殊说明**
- 如果用户没有任何交易系统，返回 `data: null`
- 此接口是其他模块获取用户交易规则的主要入口

### 2.7 获取版本历史

```
GET /api/trading-system/{system_id}/versions
```

**查询参数**
- `limit`: 返回数量，默认 10
- `skip`: 跳过数量，默认 0

**响应**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "version": "1.2.0",
        "change_summary": "调整止损比例",
        "created_at": "2024-12-20T15:30:00Z"
      },
      {
        "version": "1.1.0",
        "change_summary": "增加分批买入策略",
        "created_at": "2024-12-15T10:00:00Z"
      }
    ],
    "total": 5
  }
}
```

### 2.8 导出为 Markdown

```
GET /api/trading-system/export/{system_id}
```

**查询参数**
- `format`: 导出格式，可选 `markdown`（默认）、`json`

**响应**（format=markdown）
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "filename": "我的短线系统_v1.2.0.md",
    "content": "# 我的短线系统\n\n## 基本信息\n..."
  }
}
```

---

## 3. 内部服务接口

供其他模块调用的内部接口（不暴露为 HTTP API）。

### 3.1 TradingSystemService

```python
class TradingSystemService:

    async def get_active_system(self, user_id: str) -> Optional[TradingSystem]:
        """获取用户当前激活的交易系统"""
        pass

    async def get_position_rules(self, user_id: str) -> Optional[PositionRule]:
        """获取用户的仓位规则（供下单模块使用）"""
        pass

    async def get_risk_rules(self, user_id: str) -> Optional[Dict]:
        """获取用户的风控规则（供止损模块使用）"""
        pass

    async def get_stock_selection_rules(self, user_id: str) -> Optional[Dict]:
        """获取用户的选股规则（供分析模块使用）"""
        pass

    async def check_compliance(
        self,
        user_id: str,
        action: str,
        details: Dict
    ) -> ComplianceResult:
        """检查操作是否符合交易系统规则"""
        pass
```

### 3.2 使用示例

```python
# 在模拟交易模块中
from app.services.trading_system_service import get_trading_system_service

async def create_order(user_id: str, stock_code: str, quantity: int):
    ts_service = get_trading_system_service()

    # 获取用户的仓位规则
    position_rules = await ts_service.get_position_rules(user_id)

    if position_rules:
        # 计算推荐仓位
        max_position = position_rules.max_per_stock
        # ... 应用规则
```

---

## 4. 错误码定义

| 错误码 | 说明 |
|-------|------|
| 40001 | 交易系统不存在 |
| 40002 | 无权访问该交易系统 |
| 40003 | 系统名称已存在 |
| 40004 | 规则格式错误 |
| 40005 | 版本号格式错误 |

---

## 5. 路由注册

```python
# app/routers/trading_system.py
from fastapi import APIRouter, Depends
from app.routers.auth_db import get_current_user

router = APIRouter(
    prefix="/trading-system",
    tags=["交易系统"]
)

# 在 app/main.py 中注册
from app.routers import trading_system
app.include_router(trading_system.router, prefix="/api", tags=["trading-system"])
```

