# 服务层设计

> 本文档定义个人交易计划模块的业务逻辑层

---

## 1. 服务概览

### 1.1 文件位置

```
app/services/trading_system_service.py
```

### 1.2 核心职责

```
TradingSystemService
├── CRUD 操作
│   ├── 创建交易计划
│   ├── 查询交易计划
│   ├── 更新交易计划
│   └── 删除交易计划
│
├── 版本管理
│   ├── 保存版本快照
│   ├── 版本号递增
│   └── 版本历史查询
│
├── 规则读取（供其他模块调用）
│   ├── 获取激活系统
│   ├── 获取特定规则模块
│   └── 规则解析
│
└── 合规检查
    ├── 检查操作是否符合系统
    └── 生成违规报告
```

---

## 2. 服务类设计

### 2.1 主服务类

```python
# app/services/trading_system_service.py

from typing import Optional, List, Dict, Any
from datetime import datetime
from app.core.database import get_mongo_db
from app.models.trading_system import (
    TradingSystem, TradingSystemCreate, TradingSystemUpdate,
    TradingStyle, RiskProfile, ComplianceResult
)

class TradingSystemService:
    """个人交易计划服务"""
    
    def __init__(self):
        self.collection_name = "trading_systems"
        self.versions_collection = "trading_system_versions"
    
    # ==================== CRUD 操作 ====================
    
    async def create_system(
        self, 
        user_id: str, 
        data: TradingSystemCreate
    ) -> TradingSystem:
        """创建新的交易计划"""
        db = get_mongo_db()
        
        # 如果是用户的第一个系统，自动激活
        existing_count = await db[self.collection_name].count_documents(
            {"user_id": user_id}
        )
        is_active = existing_count == 0
        
        system = TradingSystem(
            user_id=user_id,
            name=data.name,
            description=data.description,
            style=data.style,
            risk_profile=data.risk_profile,
            version="1.0.0",
            is_active=is_active,
            stock_selection=data.stock_selection,
            timing=data.timing,
            position=data.position,
            holding=data.holding,
            risk_management=data.risk_management,
            review=data.review,
            discipline=data.discipline
        )
        
        result = await db[self.collection_name].insert_one(
            system.model_dump(by_alias=True)
        )
        system.id = str(result.inserted_id)
        
        return system
    
    async def get_system(
        self, 
        user_id: str, 
        system_id: str
    ) -> Optional[TradingSystem]:
        """获取交易计划详情"""
        db = get_mongo_db()
        doc = await db[self.collection_name].find_one({
            "_id": ObjectId(system_id),
            "user_id": user_id
        })
        if doc:
            return TradingSystem(**doc)
        return None
    
    async def list_systems(self, user_id: str) -> List[TradingSystem]:
        """获取用户的所有交易计划"""
        db = get_mongo_db()
        cursor = db[self.collection_name].find({"user_id": user_id})
        systems = []
        async for doc in cursor:
            systems.append(TradingSystem(**doc))
        return systems
    
    async def update_system(
        self,
        user_id: str,
        system_id: str,
        data: TradingSystemUpdate,
        save_version: bool = True
    ) -> Optional[TradingSystem]:
        """更新交易计划"""
        db = get_mongo_db()
        
        # 获取当前系统
        current = await self.get_system(user_id, system_id)
        if not current:
            return None
        
        # 保存版本历史
        if save_version:
            await self._save_version(current, data.change_summary)
        
        # 递增版本号
        new_version = self._increment_version(current.version)
        
        # 构建更新数据
        update_data = data.model_dump(exclude_unset=True)
        update_data["version"] = new_version
        update_data["updated_at"] = datetime.utcnow()
        
        await db[self.collection_name].update_one(
            {"_id": ObjectId(system_id)},
            {"$set": update_data}
        )
        
        return await self.get_system(user_id, system_id)
    
    async def delete_system(self, user_id: str, system_id: str) -> bool:
        """删除交易计划"""
        db = get_mongo_db()
        result = await db[self.collection_name].delete_one({
            "_id": ObjectId(system_id),
            "user_id": user_id
        })
        return result.deleted_count > 0
    
    async def activate_system(self, user_id: str, system_id: str) -> bool:
        """激活交易计划"""
        db = get_mongo_db()

        # 先将所有系统设为非激活
        await db[self.collection_name].update_many(
            {"user_id": user_id},
            {"$set": {"is_active": False}}
        )

        # 激活指定系统
        result = await db[self.collection_name].update_one(
            {"_id": ObjectId(system_id), "user_id": user_id},
            {"$set": {"is_active": True}}
        )

        return result.modified_count > 0

    # ==================== 规则读取（供其他模块调用） ====================

    async def get_active_system(self, user_id: str) -> Optional[TradingSystem]:
        """获取用户当前激活的交易计划"""
        db = get_mongo_db()
        doc = await db[self.collection_name].find_one({
            "user_id": user_id,
            "is_active": True
        })
        if doc:
            return TradingSystem(**doc)
        return None

    async def get_position_rules(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户的仓位规则"""
        system = await self.get_active_system(user_id)
        if system:
            return system.position.model_dump() if system.position else None
        return None

    async def get_risk_rules(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户的风控规则"""
        system = await self.get_active_system(user_id)
        if system:
            return system.risk_management
        return None

    async def get_stock_selection_rules(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户的选股规则"""
        system = await self.get_active_system(user_id)
        if system:
            return system.stock_selection.model_dump() if system.stock_selection else None
        return None

    async def get_discipline_rules(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户的纪律规则"""
        system = await self.get_active_system(user_id)
        if system:
            return system.discipline
        return None

    # ==================== 合规检查 ====================

    async def check_compliance(
        self,
        user_id: str,
        action_type: str,
        action_details: Dict[str, Any]
    ) -> ComplianceResult:
        """
        检查操作是否符合交易计划规则

        Args:
            user_id: 用户ID
            action_type: 操作类型 (buy/sell/add_position/etc)
            action_details: 操作详情

        Returns:
            ComplianceResult: 合规检查结果
        """
        system = await self.get_active_system(user_id)

        if not system:
            return ComplianceResult(
                is_compliant=True,
                has_system=False,
                message="用户未设置交易计划，跳过合规检查"
            )

        violations = []
        warnings = []

        # 根据操作类型进行不同的检查
        if action_type == "buy":
            violations, warnings = await self._check_buy_compliance(
                system, action_details
            )
        elif action_type == "sell":
            violations, warnings = await self._check_sell_compliance(
                system, action_details
            )

        return ComplianceResult(
            is_compliant=len(violations) == 0,
            has_system=True,
            violations=violations,
            warnings=warnings,
            system_name=system.name,
            system_version=system.version
        )

    async def _check_buy_compliance(
        self,
        system: TradingSystem,
        details: Dict[str, Any]
    ) -> tuple:
        """检查买入操作的合规性"""
        violations = []
        warnings = []

        position_rules = system.position
        discipline = system.discipline or {}

        # 检查仓位限制
        if position_rules:
            position_pct = details.get("position_pct", 0)
            max_per_stock = position_rules.max_per_stock * 100

            if position_pct > max_per_stock:
                violations.append({
                    "rule": "单股仓位上限",
                    "limit": f"{max_per_stock}%",
                    "actual": f"{position_pct}%",
                    "message": f"单股仓位 {position_pct}% 超过系统设定的 {max_per_stock}%"
                })

        # 检查纪律规则 - must_not
        must_not_rules = discipline.get("must_not", [])
        for rule in must_not_rules:
            if rule.get("rule") == "不追涨停":
                if details.get("is_limit_up", False):
                    violations.append({
                        "rule": "不追涨停",
                        "message": "该股票当天涨停，系统规则禁止追涨停"
                    })

        return violations, warnings

    # ==================== 版本管理 ====================

    async def _save_version(
        self,
        system: TradingSystem,
        change_summary: str = ""
    ):
        """保存版本快照"""
        db = get_mongo_db()

        version_doc = {
            "system_id": str(system.id),
            "version": system.version,
            "snapshot": system.model_dump(),
            "change_summary": change_summary,
            "created_at": datetime.utcnow()
        }

        await db[self.versions_collection].insert_one(version_doc)

    def _increment_version(self, version: str) -> str:
        """递增版本号（补丁版本）"""
        parts = version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
        return ".".join(parts)


# ==================== 服务实例获取 ====================

_trading_system_service = None

def get_trading_system_service() -> TradingSystemService:
    """获取交易计划服务实例"""
    global _trading_system_service
    if _trading_system_service is None:
        _trading_system_service = TradingSystemService()
    return _trading_system_service
```

---

## 3. 合规检查结果模型

```python
# app/models/trading_system.py

class ComplianceResult(BaseModel):
    """合规检查结果"""
    is_compliant: bool = True              # 是否合规
    has_system: bool = False               # 用户是否有交易计划
    violations: List[Dict] = []            # 违规项
    warnings: List[Dict] = []              # 警告项
    system_name: str = ""                  # 交易计划名称
    system_version: str = ""               # 交易计划版本
    message: str = ""                      # 附加消息
```

---

## 4. 与其他服务的集成示例

### 4.1 模拟交易集成

```python
# app/services/paper_trading_service.py

from app.services.trading_system_service import get_trading_system_service

class PaperTradingService:

    async def create_buy_order(self, user_id: str, order_data: dict):
        ts_service = get_trading_system_service()

        # 获取仓位规则，计算推荐仓位
        position_rules = await ts_service.get_position_rules(user_id)
        if position_rules:
            suggested_position = self._calculate_position(
                position_rules,
                order_data
            )
            order_data["suggested_position"] = suggested_position

        # 获取风控规则，计算止损价
        risk_rules = await ts_service.get_risk_rules(user_id)
        if risk_rules:
            stop_loss = risk_rules.get("stop_loss", {})
            if stop_loss.get("type") == "fixed":
                pct = stop_loss.get("percentage", 0.05)
                order_data["suggested_stop_loss"] = order_data["price"] * (1 - pct)

        # 合规检查
        compliance = await ts_service.check_compliance(
            user_id, "buy", order_data
        )
        if not compliance.is_compliant:
            order_data["compliance_warnings"] = compliance.violations

        # 继续创建订单...
```

### 4.2 复盘分析集成

```python
# app/services/trade_review_service.py

class TradeReviewService:

    async def analyze_trade(self, user_id: str, trade_record: dict):
        ts_service = get_trading_system_service()

        # 检查交易是否符合系统规则
        compliance = await ts_service.check_compliance(
            user_id,
            trade_record["action"],
            trade_record
        )

        # 在复盘报告中标记违规情况
        review_report = {
            "trade_id": trade_record["id"],
            "compliance": {
                "is_compliant": compliance.is_compliant,
                "violations": compliance.violations,
                "system_name": compliance.system_name
            }
        }

        return review_report
```
```

