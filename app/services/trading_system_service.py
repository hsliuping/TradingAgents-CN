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
    TradingSystemUpdate,
    TradingSystemVersion,
    TradingSystemVersionCreate,
    TradingSystemPublish,
    TradingSystemStatus
)

logger = logging.getLogger(__name__)


class TradingSystemService:
    """交易计划服务类"""

    def __init__(self):
        self.db = get_mongo_db_sync()
        self.collection: Collection = self.db["trading_systems"]
        self.version_collection: Collection = self.db["trading_system_versions"]
        # 创建索引
        self._ensure_indexes()

    def _ensure_indexes(self):
        """确保必要的索引存在"""
        try:
            self.collection.create_index("user_id")
            self.collection.create_index([("user_id", 1), ("is_active", 1)])
            self.collection.create_index("created_at")
            # 版本表索引
            self.version_collection.create_index("system_id")
            self.version_collection.create_index([("system_id", 1), ("version", 1)])
            self.version_collection.create_index("created_at")
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
        system_dict["status"] = TradingSystemStatus.DRAFT.value  # 默认创建为草稿
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
        update_data: TradingSystemUpdate,
        save_as_draft: bool = False
    ) -> Optional[TradingSystem]:
        """更新交易计划
        
        Args:
            system_id: 系统ID
            user_id: 用户ID
            update_data: 更新数据
            save_as_draft: 是否保存为草稿（如果系统已发布，草稿数据不会影响正式版本）
            
        Returns:
            更新后的交易计划，如果不存在返回None
        """
        # 获取当前系统
        current_system = self.get_system(system_id, user_id)
        if not current_system:
            return None
        
        # 构建更新数据
        update_dict = update_data.dict(exclude_unset=True)
        if not update_dict:
            return current_system

        # 如果系统已发布且保存为草稿，只更新草稿数据
        if save_as_draft and current_system.status == TradingSystemStatus.PUBLISHED.value:
            # 将更新数据保存到 draft_data（不包含元数据字段）
            draft_data = update_dict.copy()
            # 移除不应该在草稿中的字段
            draft_data.pop("status", None)
            draft_data.pop("is_active", None)
            draft_data.pop("version", None)
            draft_data.pop("updated_at", None)
            draft_data.pop("created_at", None)
            
            result = self.collection.update_one(
                {"_id": ObjectId(system_id), "user_id": user_id},
                {"$set": {"draft_data": draft_data, "draft_updated_at": datetime.utcnow()}}
            )
            
            if result.matched_count == 0:
                return None
            
            logger.info(f"保存草稿成功: system_id={system_id}")
            return self.get_system(system_id, user_id)
        
        # 否则，正常更新（草稿状态或直接更新）
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

    def create_version(
        self,
        system_id: str,
        user_id: str,
        version_data: TradingSystemVersionCreate
    ) -> Optional[TradingSystemVersion]:
        """创建交易计划新版本
        
        Args:
            system_id: 系统ID
            user_id: 用户ID
            version_data: 版本数据
            
        Returns:
            创建的版本，如果系统不存在返回None
        """
        # 获取当前系统
        current_system = self.get_system(system_id, user_id)
        if not current_system:
            return None
        
        # 确定新版本号
        if version_data.new_version:
            new_version = version_data.new_version
        else:
            # 自动递增版本号
            current_version = current_system.version
            try:
                # 解析版本号，如 "1.0.0" -> [1, 0, 0]
                version_parts = [int(x) for x in current_version.split(".")]
                # 主版本号递增
                version_parts[0] += 1
                # 次版本号和修订号归零
                version_parts[1] = 0
                version_parts[2] = 0
                new_version = ".".join(str(x) for x in version_parts)
            except Exception:
                # 如果版本号格式不正确，使用默认递增
                new_version = f"{current_version}.1"
        
        # 创建版本快照
        version_dict = {
            "system_id": system_id,
            "version": new_version,
            "improvement_summary": version_data.improvement_summary,
            "snapshot": current_system.dict(),
            "created_at": datetime.utcnow(),
            "created_by": user_id
        }
        
        # 插入版本记录
        result = self.version_collection.insert_one(version_dict)
        version_dict["id"] = str(result.inserted_id)
        if "_id" in version_dict:
            del version_dict["_id"]
        
        # 更新主系统的版本号
        self.collection.update_one(
            {"_id": ObjectId(system_id), "user_id": user_id},
            {"$set": {"version": new_version, "updated_at": datetime.utcnow()}}
        )
        
        logger.info(f"创建交易计划版本成功: system_id={system_id}, version={new_version}")
        return TradingSystemVersion(**version_dict)

    def list_versions(
        self,
        system_id: str,
        user_id: str
    ) -> List[TradingSystemVersion]:
        """获取交易计划的所有版本
        
        Args:
            system_id: 系统ID
            user_id: 用户ID
            
        Returns:
            版本列表，按创建时间倒序
        """
        # 验证系统属于该用户
        system = self.get_system(system_id, user_id)
        if not system:
            return []
        
        versions = []
        for version_doc in self.version_collection.find(
            {"system_id": system_id}
        ).sort("created_at", -1):
            version_doc["id"] = str(version_doc["_id"])
            del version_doc["_id"]
            # 处理快照中的 _id
            if "snapshot" in version_doc and "_id" in version_doc["snapshot"]:
                version_doc["snapshot"]["id"] = str(version_doc["snapshot"]["_id"])
                del version_doc["snapshot"]["_id"]
            versions.append(TradingSystemVersion(**version_doc))
        
        return versions

    def get_version(
        self,
        version_id: str,
        user_id: str
    ) -> Optional[TradingSystemVersion]:
        """获取版本详情
        
        Args:
            version_id: 版本ID
            user_id: 用户ID
            
        Returns:
            版本详情，如果不存在返回None
        """
        try:
            version_doc = self.version_collection.find_one({
                "_id": ObjectId(version_id),
                "created_by": user_id
            })
            if version_doc:
                version_doc["id"] = str(version_doc["_id"])
                del version_doc["_id"]
                # 处理快照中的 _id
                if "snapshot" in version_doc and "_id" in version_doc["snapshot"]:
                    version_doc["snapshot"]["id"] = str(version_doc["snapshot"]["_id"])
                    del version_doc["snapshot"]["_id"]
                return TradingSystemVersion(**version_doc)
            return None
        except Exception as e:
            logger.error(f"获取版本详情失败: {e}")
            return None

    def update_system_with_version(
        self,
        system_id: str,
        user_id: str,
        update_data: TradingSystemUpdate,
        create_version: bool = False,
        improvement_summary: Optional[str] = None
    ) -> Optional[TradingSystem]:
        """更新交易计划（可选择是否创建新版本）
        
        Args:
            system_id: 系统ID
            user_id: 用户ID
            update_data: 更新数据
            create_version: 是否创建新版本
            improvement_summary: 改进总结（如果创建版本）
            
        Returns:
            更新后的交易计划
        """
        # 如果需要创建版本，先创建版本
        if create_version and improvement_summary:
            version_data = TradingSystemVersionCreate(
                improvement_summary=improvement_summary
            )
            self.create_version(system_id, user_id, version_data)
        
        # 执行更新
        return self.update_system(system_id, user_id, update_data)

    def publish_system(
        self,
        system_id: str,
        user_id: str,
        publish_data: TradingSystemPublish,
        update_data: Optional[TradingSystemUpdate] = None
    ) -> Optional[TradingSystem]:
        """发布交易计划（创建新版本并更新状态为已发布）
        
        Args:
            system_id: 系统ID
            user_id: 用户ID
            publish_data: 发布数据（包含改进总结）
            update_data: 可选的更新数据（如果有修改）
            
        Returns:
            发布后的交易计划
        """
        # 获取当前系统
        current_system = self.get_system(system_id, user_id)
        if not current_system:
            return None
        
        # 准备要更新的数据
        final_update_dict = {}
        
        # 如果有草稿数据，合并草稿数据到正式版本
        if current_system.draft_data:
            draft_dict = current_system.draft_data.copy()
            # 移除草稿特有的字段
            draft_dict.pop("draft_updated_at", None)
            final_update_dict.update(draft_dict)
            logger.info(f"合并草稿数据到正式版本: system_id={system_id}")
        
        # 如果有额外的更新数据，也合并进去
        if update_data:
            update_dict = update_data.dict(exclude_unset=True)
            final_update_dict.update(update_dict)
        
        # 如果有需要更新的数据，先更新系统
        if final_update_dict:
            # 移除不应该在发布时更新的字段
            final_update_dict.pop("status", None)
            final_update_dict.pop("version", None)
            final_update_dict["updated_at"] = datetime.utcnow()
            
            self.collection.update_one(
                {"_id": ObjectId(system_id), "user_id": user_id},
                {"$set": final_update_dict}
            )
            
            # 重新获取系统，确保使用最新数据创建版本
            current_system = self.get_system(system_id, user_id)
            if not current_system:
                return None
        
        # 创建新版本（使用更新后的系统数据）
        version_data = TradingSystemVersionCreate(
            improvement_summary=publish_data.improvement_summary,
            new_version=publish_data.new_version
        )
        version = self.create_version(system_id, user_id, version_data)
        
        if not version:
            return None
        
        # 更新系统状态为已发布，并清空草稿数据
        update_dict = {
            "status": TradingSystemStatus.PUBLISHED.value,
            "version": version.version,
            "updated_at": datetime.utcnow()
        }
        
        result = self.collection.update_one(
            {"_id": ObjectId(system_id), "user_id": user_id},
            {
                "$set": update_dict,
                "$unset": {"draft_data": "", "draft_updated_at": ""}
            }
        )
        
        if result.matched_count == 0:
            return None
        
        logger.info(f"发布交易计划成功: system_id={system_id}, version={version.version}")
        return self.get_system(system_id, user_id)


# 全局服务实例
_trading_system_service = None


def get_trading_system_service() -> TradingSystemService:
    """获取交易计划服务实例"""
    global _trading_system_service
    if _trading_system_service is None:
        _trading_system_service = TradingSystemService()
    return _trading_system_service


