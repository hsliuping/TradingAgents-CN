"""
个人交易计划服务层
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pymongo.collection import Collection

from app.core.database import get_mongo_db_sync
from app.models.trading_system import (
    TradingSystem,
    TradingSystemCreate,
    TradingSystemUpdate
)

logger = logging.getLogger(__name__)


class TradingSystemService:
    """交易计划服务类"""

    def __init__(self):
        self.db = get_mongo_db_sync()
        self.collection: Collection = self.db["trading_systems"]
        # 创建索引
        self._ensure_indexes()

    def _ensure_indexes(self):
        """确保必要的索引存在"""
        try:
            self.collection.create_index("user_id")
            self.collection.create_index([("user_id", 1), ("is_active", 1)])
            self.collection.create_index("created_at")
        except Exception as e:
            logger.warning(f"创建索引失败: {e}")

    def create_system(self, user_id: str, system_data: TradingSystemCreate) -> TradingSystem:
        """创建交易计划
        
        Args:
            user_id: 用户ID
            system_data: 交易计划数据
            
        Returns:
            创建的交易计划
        """
        # 如果设置为激活，先将该用户的其他系统设为非激活
        if system_data.dict().get("is_active", True):
            self.collection.update_many(
                {"user_id": user_id, "is_active": True},
                {"$set": {"is_active": False}}
            )

        # 构建系统数据
        system_dict = system_data.dict(exclude_unset=True)
        system_dict["user_id"] = user_id
        system_dict["version"] = "1.0.0"
        system_dict["is_active"] = True
        system_dict["created_at"] = datetime.utcnow()
        system_dict["updated_at"] = datetime.utcnow()

        # 插入数据库
        result = self.collection.insert_one(system_dict)
        system_dict["id"] = str(result.inserted_id)
        if "_id" in system_dict:
            del system_dict["_id"]

        logger.info(f"创建交易计划成功: user_id={user_id}, system_id={result.inserted_id}, name={system_data.name}")
        return TradingSystem(**system_dict)

    def get_system(self, system_id: str, user_id: str) -> Optional[TradingSystem]:
        """获取交易计划

        Args:
            system_id: 系统ID
            user_id: 用户ID

        Returns:
            交易计划，如果不存在返回None
        """
        try:
            system = self.collection.find_one({
                "_id": ObjectId(system_id),
                "user_id": user_id
            })
            if system:
                system["id"] = str(system["_id"])
                del system["_id"]
                return TradingSystem(**system)
            return None
        except Exception as e:
            logger.error(f"获取交易计划失败: {e}")
            return None

    def list_systems(self, user_id: str, is_active: Optional[bool] = None) -> List[TradingSystem]:
        """获取用户的交易计划列表

        Args:
            user_id: 用户ID
            is_active: 是否只获取激活的系统

        Returns:
            交易计划列表
        """
        query = {"user_id": user_id}
        if is_active is not None:
            query["is_active"] = is_active

        logger.info(f"查询交易计划列表: user_id={user_id}, query={query}")

        systems = []
        for idx, system in enumerate(self.collection.find(query).sort("created_at", -1)):
            logger.info(f"处理第 {idx+1} 个系统，原始数据键: {list(system.keys())}")
            try:
                system["id"] = str(system["_id"])
                del system["_id"]
                logger.info(f"转换后的数据键: {list(system.keys())}")
                trading_system = TradingSystem(**system)
                systems.append(trading_system)
                logger.info(f"成功创建 TradingSystem 对象: {trading_system.name}")
            except Exception as e:
                logger.error(f"处理第 {idx+1} 个系统时出错: {e}, 系统数据键: {list(system.keys())}")
                raise

        logger.info(f"成功获取 {len(systems)} 个交易计划")
        return systems

    def get_active_system(self, user_id: str) -> Optional[TradingSystem]:
        """获取用户当前激活的交易计划

        Args:
            user_id: 用户ID

        Returns:
            激活的交易计划，如果不存在返回None
        """
        system = self.collection.find_one({
            "user_id": user_id,
            "is_active": True
        })
        if system:
            system["id"] = str(system["_id"])
            del system["_id"]
            return TradingSystem(**system)
        return None

    def update_system(
        self,
        system_id: str,
        user_id: str,
        update_data: TradingSystemUpdate
    ) -> Optional[TradingSystem]:
        """更新交易计划
        
        Args:
            system_id: 系统ID
            user_id: 用户ID
            update_data: 更新数据
            
        Returns:
            更新后的交易计划，如果不存在返回None
        """
        # 构建更新数据
        update_dict = update_data.dict(exclude_unset=True)
        if not update_dict:
            return self.get_system(system_id, user_id)

        update_dict["updated_at"] = datetime.utcnow()

        # 如果要激活此系统，先将其他系统设为非激活
        if update_dict.get("is_active") is True:
            self.collection.update_many(
                {"user_id": user_id, "is_active": True, "_id": {"$ne": ObjectId(system_id)}},
                {"$set": {"is_active": False}}
            )

        # 更新系统
        result = self.collection.update_one(
            {"_id": ObjectId(system_id), "user_id": user_id},
            {"$set": update_dict}
        )

        if result.matched_count == 0:
            return None

        logger.info(f"更新交易计划成功: system_id={system_id}")
        return self.get_system(system_id, user_id)

    def delete_system(self, system_id: str, user_id: str) -> bool:
        """删除交易计划

        Args:
            system_id: 系统ID
            user_id: 用户ID

        Returns:
            是否删除成功
        """
        result = self.collection.delete_one({
            "_id": ObjectId(system_id),
            "user_id": user_id
        })

        if result.deleted_count > 0:
            logger.info(f"删除交易计划成功: system_id={system_id}")
            return True
        return False

    def activate_system(self, system_id: str, user_id: str) -> Optional[TradingSystem]:
        """激活交易计划

        Args:
            system_id: 系统ID
            user_id: 用户ID

        Returns:
            激活后的交易计划，如果不存在返回None
        """
        # 先将该用户的所有系统设为非激活
        self.collection.update_many(
            {"user_id": user_id, "is_active": True},
            {"$set": {"is_active": False}}
        )

        # 激活指定系统
        result = self.collection.update_one(
            {"_id": ObjectId(system_id), "user_id": user_id},
            {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
        )

        if result.matched_count == 0:
            return None

        logger.info(f"激活交易计划成功: system_id={system_id}")
        return self.get_system(system_id, user_id)

    def check_compliance(
        self,
        user_id: str,
        trade_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检查交易是否符合系统规则

        Args:
            user_id: 用户ID
            trade_data: 交易数据，包含：
                - action: 'buy' | 'sell'
                - symbol: 股票代码
                - price: 价格
                - quantity: 数量
                - position_ratio: 仓位比例
                - stop_loss: 止损价（可选）
                - reason: 交易理由（可选）

        Returns:
            合规检查结果：
            {
                "is_compliant": bool,
                "violations": List[str],
                "warnings": List[str],
                "suggestions": List[str]
            }
        """
        # 获取激活的交易计划
        system = self.get_active_system(user_id)
        if not system:
            return {
                "is_compliant": True,
                "violations": [],
                "warnings": ["未设置交易计划，无法进行合规检查"],
                "suggestions": ["建议创建个人交易计划以获得更好的交易指导"]
            }

        violations = []
        warnings = []
        suggestions = []

        # 检查纪律规则
        self._check_discipline_rules(system, trade_data, violations, warnings)

        # 检查仓位规则
        self._check_position_rules(system, trade_data, violations, warnings)

        # 检查风险管理规则
        self._check_risk_management_rules(system, trade_data, violations, warnings, suggestions)

        return {
            "is_compliant": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "suggestions": suggestions
        }

    def _check_discipline_rules(
        self,
        system: TradingSystem,
        trade_data: Dict[str, Any],
        violations: List[str],
        warnings: List[str]
    ):
        """检查纪律规则"""
        discipline = system.discipline

        # 检查必须做到的规则
        for rule in discipline.must_do:
            rule_type = rule.get("rule", "")
            if "设置止损" in rule_type and trade_data.get("action") == "buy":
                if not trade_data.get("stop_loss"):
                    violations.append(f"违反纪律规则：{rule_type} - {rule.get('description', '')}")

            if "记录买入理由" in rule_type and trade_data.get("action") == "buy":
                if not trade_data.get("reason"):
                    violations.append(f"违反纪律规则：{rule_type} - {rule.get('description', '')}")

        # 检查绝对禁止的规则
        for rule in discipline.must_not:
            rule_type = rule.get("rule", "")
            # 这里可以根据具体规则进行检查
            # 例如：检查是否追涨停、是否满仓单只等

    def _check_position_rules(
        self,
        system: TradingSystem,
        trade_data: Dict[str, Any],
        violations: List[str],
        warnings: List[str]
    ):
        """检查仓位规则"""
        position = system.position
        position_ratio = trade_data.get("position_ratio", 0)

        # 检查单只股票仓位上限
        if position_ratio > position.max_per_stock:
            violations.append(
                f"违反仓位规则：单只股票仓位 {position_ratio*100:.1f}% 超过上限 {position.max_per_stock*100:.1f}%"
            )

    def _check_risk_management_rules(
        self,
        system: TradingSystem,
        trade_data: Dict[str, Any],
        violations: List[str],
        warnings: List[str],
        suggestions: List[str]
    ):
        """检查风险管理规则"""
        risk_mgmt = system.risk_management

        if trade_data.get("action") == "buy":
            # 检查止损设置
            stop_loss_config = risk_mgmt.stop_loss
            if stop_loss_config.get("type") and not trade_data.get("stop_loss"):
                warnings.append("建议设置止损价格")

            # 如果有止损价格，检查止损幅度
            if trade_data.get("stop_loss") and stop_loss_config.get("percentage"):
                price = trade_data.get("price", 0)
                stop_loss = trade_data.get("stop_loss", 0)
                actual_stop_pct = abs(price - stop_loss) / price if price > 0 else 0
                expected_stop_pct = stop_loss_config.get("percentage", 0)

                if actual_stop_pct > expected_stop_pct * 1.5:  # 允许50%的偏差
                    warnings.append(
                        f"止损幅度 {actual_stop_pct*100:.1f}% 偏离系统设置 {expected_stop_pct*100:.1f}%"
                    )


# 全局服务实例
_trading_system_service = None


def get_trading_system_service() -> TradingSystemService:
    """获取交易计划服务实例"""
    global _trading_system_service
    if _trading_system_service is None:
        _trading_system_service = TradingSystemService()
    return _trading_system_service


