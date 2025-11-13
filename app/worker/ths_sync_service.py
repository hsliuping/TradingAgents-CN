"""
同花顺题材同步服务
负责同步同花顺题材数据到MongoDB
- limit_cpt_list: 最强板块统计
- ths_member: 同花顺概念板块成分
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from tradingagents.dataflows.providers.china.tushare import TushareProvider
from app.core.database import get_mongo_db
from app.core.config import settings
from app.core.rate_limiter import get_tushare_rate_limiter
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

logger = logging.getLogger(__name__)


class THSSyncService:
    """
    同花顺题材同步服务
    负责将同花顺题材数据同步到MongoDB
    """
    
    def __init__(self):
        self.provider = TushareProvider()
        self.db = get_mongo_db()
        self.settings = settings
        
        # 速率限制器
        tushare_tier = getattr(settings, "TUSHARE_TIER", "standard")
        safety_margin = float(getattr(settings, "TUSHARE_RATE_LIMIT_SAFETY_MARGIN", "0.8"))
        self.rate_limiter = get_tushare_rate_limiter(tier=tushare_tier, safety_margin=safety_margin)
        
        # 批量处理配置
        self.batch_size = 500
        self._indexes_ensured = {
            "ths_limit_cpt_list": False,
            "ths_member": False,
            "ths_hot": False
        }
    
    async def initialize(self):
        """初始化同步服务"""
        success = await self.provider.connect()
        if not success:
            raise RuntimeError("❌ Tushare连接失败，无法启动同花顺题材同步服务")
        logger.info("✅ 同花顺题材同步服务初始化完成")
    
    # ==================== 索引管理 ====================
    
    async def _ensure_indexes(self, collection_name: str):
        """确保必要的索引存在"""
        if self._indexes_ensured.get(collection_name, False):
            return
        
        try:
            collection = self.db[collection_name]
            existing_indexes = await collection.list_indexes().to_list(length=None)
            existing_index_names = [idx["name"] for idx in existing_indexes]
            
            if collection_name == "ths_limit_cpt_list":
                # 复合唯一索引：trade_date + ts_code
                if "trade_date_ts_code_unique" not in existing_index_names:
                    await collection.create_index(
                        [("trade_date", 1), ("ts_code", 1)],
                        unique=True,
                        name="trade_date_ts_code_unique"
                    )
                
                # 交易日期索引（降序）
                if "trade_date_desc" not in existing_index_names:
                    await collection.create_index(
                        [("trade_date", -1)],
                        name="trade_date_desc"
                    )
                
                # 板块代码索引
                if "ts_code_index" not in existing_index_names:
                    await collection.create_index(
                        [("ts_code", 1)],
                        name="ts_code_index"
                    )
                
                # 排名索引（用于排序）
                if "rank_index" not in existing_index_names:
                    await collection.create_index(
                        [("rank", 1)],
                        name="rank_index"
                    )
                
                # 涨停家数索引（降序）
                if "up_nums_desc" not in existing_index_names:
                    await collection.create_index(
                        [("up_nums", -1)],
                        name="up_nums_desc"
                    )
            
            elif collection_name == "ths_member":
                # 复合唯一索引：ts_code + con_code
                if "ts_code_con_code_unique" not in existing_index_names:
                    await collection.create_index(
                        [("ts_code", 1), ("con_code", 1)],
                        unique=True,
                        name="ts_code_con_code_unique"
                    )
                
                # 板块代码索引
                if "ts_code_index" not in existing_index_names:
                    await collection.create_index(
                        [("ts_code", 1)],
                        name="ts_code_index"
                    )
                
                # 股票代码索引
                if "con_code_index" not in existing_index_names:
                    await collection.create_index(
                        [("con_code", 1)],
                        name="con_code_index"
                    )
                
                # 是否最新索引
                if "is_new_index" not in existing_index_names:
                    await collection.create_index(
                        [("is_new", 1)],
                        name="is_new_index"
                    )
            
            elif collection_name == "ths_hot":
                # 复合唯一索引：trade_date + market + ts_code + rank_time
                if "trade_date_market_ts_code_rank_time_unique" not in existing_index_names:
                    await collection.create_index(
                        [("trade_date", 1), ("market", 1), ("ts_code", 1), ("rank_time", 1)],
                        unique=True,
                        name="trade_date_market_ts_code_rank_time_unique"
                    )
                
                # 交易日期索引（降序）
                if "trade_date_desc" not in existing_index_names:
                    await collection.create_index(
                        [("trade_date", -1)],
                        name="trade_date_desc"
                    )
                
                # 热榜类型索引
                if "market_index" not in existing_index_names:
                    await collection.create_index(
                        [("market", 1)],
                        name="market_index"
                    )
                
                # 数据类型索引
                if "data_type_index" not in existing_index_names:
                    await collection.create_index(
                        [("data_type", 1)],
                        name="data_type_index"
                    )
                
                # 排行索引（用于排序）
                if "rank_index" not in existing_index_names:
                    await collection.create_index(
                        [("rank", 1)],
                        name="rank_index"
                    )
                
                # 热度值索引（降序）
                if "hot_desc" not in existing_index_names:
                    await collection.create_index(
                        [("hot", -1)],
                        name="hot_desc"
                    )
                
                # 是否最新索引
                if "is_new_index" not in existing_index_names:
                    await collection.create_index(
                        [("is_new", 1)],
                        name="is_new_index"
                    )
            
            self._indexes_ensured[collection_name] = True
            logger.debug(f"✅ {collection_name} 索引检查完成")
            
        except Exception as e:
            logger.warning(f"⚠️ 创建 {collection_name} 索引时出错: {e}")
    
    # ==================== 最强板块统计同步 ====================
    
    async def sync_limit_cpt_list(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步最强板块统计数据
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），如果为None则使用最新交易日
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步同花顺最强板块统计...")
        
        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "start_time": datetime.utcnow(),
            "errors_list": []
        }
        
        try:
            # 确保索引存在
            await self._ensure_indexes("ths_limit_cpt_list")
            
            # 如果没有指定日期，使用最新交易日
            if not trade_date:
                trade_date = await self._get_latest_trade_date()
            
            logger.info(f"📅 同步日期: {trade_date}")
            
            # 等待速率限制
            await self.rate_limiter.acquire()
            
            # 调用Tushare API获取最强板块统计
            df = await asyncio.to_thread(
                self.provider.api.limit_cpt_list,
                trade_date=trade_date
            )
            
            if df is None or df.empty:
                logger.warning(f"⚠️ 日期 {trade_date} 无最强板块统计数据")
                stats["errors"] = 1
                stats["errors_list"].append(f"日期 {trade_date} 无数据")
                return stats
            
            # 转换为字典列表
            records = df.to_dict('records')
            stats["total_processed"] = len(records)
            
            # 批量写入MongoDB
            operations = []
            now_iso = datetime.utcnow().isoformat()
            
            for record in records:
                # 验证必需字段
                ts_code = str(record.get("ts_code", "")).strip()
                if not ts_code:
                    logger.warning(f"⚠️ 跳过无效记录（ts_code为空）: {record}")
                    continue
                
                # 存储所有字段
                doc = {
                    "trade_date": str(record.get("trade_date", trade_date)),
                    "ts_code": ts_code,  # 板块代码
                    "name": str(record.get("name", "")),  # 板块名称
                    "days": record.get("days"),  # 上榜天数
                    "up_stat": str(record.get("up_stat", "")),  # 连板高度
                    "cons_nums": record.get("cons_nums"),  # 连板家数
                    "up_nums": str(record.get("up_nums", "")),  # 涨停家数
                    "pct_chg": record.get("pct_chg"),  # 涨跌幅%
                    "rank": str(record.get("rank", "")),  # 板块热点排名
                    "data_source": "tushare",
                    "updated_at": now_iso
                }
                
                # 保留所有原始字段（用于调试和扩展）
                for key, value in record.items():
                    if key not in doc and value is not None:
                        doc[key] = value
                
                # 使用 trade_date + ts_code 作为唯一键
                operations.append(
                    UpdateOne(
                        {
                            "trade_date": doc["trade_date"],
                            "ts_code": doc["ts_code"]
                        },
                        {"$set": doc},
                        upsert=True
                    )
                )
            
            # 批量写入
            if operations:
                try:
                    result = await self.db["ths_limit_cpt_list"].bulk_write(operations, ordered=False)
                    stats["inserted"] = result.upserted_count
                    stats["updated"] = result.modified_count
                    logger.info(
                        f"✅ 最强板块统计数据同步完成: "
                        f"新增 {result.upserted_count} 条, "
                        f"更新 {result.modified_count} 条, "
                        f"总计 {stats['total_processed']} 条"
                    )
                except BulkWriteError as e:
                    # 记录部分成功的写入
                    stats["inserted"] = e.details.get("nInserted", 0)
                    stats["updated"] = e.details.get("nModified", 0)
                    stats["errors"] = len(e.details.get("writeErrors", []))
                    logger.error(f"❌ 批量写入最强板块统计数据时出现错误: {e.details}")
                    stats["errors_list"].append(f"批量写入错误: {str(e)}")
            else:
                logger.warning("⚠️ 未生成任何最强板块统计数据")
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
        except Exception as e:
            logger.exception(f"❌ 同步最强板块统计数据失败: {e}")
            stats["errors"] = 1
            stats["errors_list"].append(str(e))
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds() if stats.get("end_time") else 0
        
        return stats
    
    # ==================== 同花顺概念板块成分同步 ====================
    
    async def sync_ths_member(self, ts_codes: Optional[List[str]] = None, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步同花顺概念板块成分数据
        
        Args:
            ts_codes: 板块代码列表，如果为None则从 limit_cpt_list 获取
            trade_date: 交易日期（用于从 limit_cpt_list 获取板块代码）
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步同花顺概念板块成分...")
        
        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "concepts_processed": 0,
            "concepts_failed": 0,
            "start_time": datetime.utcnow(),
            "errors_list": []
        }
        
        try:
            # 确保索引存在
            await self._ensure_indexes("ths_member")
            
            # 如果没有提供板块代码列表，从 limit_cpt_list 获取
            if not ts_codes:
                if not trade_date:
                    trade_date = await self._get_latest_trade_date()
                
                logger.info(f"📅 从 limit_cpt_list 获取板块代码（日期: {trade_date}）")
                
                # 从 limit_cpt_list 获取板块代码列表
                cursor = self.db["ths_limit_cpt_list"].find(
                    {"trade_date": trade_date},
                    {"ts_code": 1}
                )
                limit_cpt_records = await cursor.to_list(length=None)
                
                if not limit_cpt_records:
                    # 尝试查找最近有数据的交易日
                    logger.warning(f"⚠️ 未找到日期 {trade_date} 的最强板块数据，尝试查找最近有数据的交易日...")
                    
                    # 查找最近30天内有数据的交易日
                    recent_cursor = self.db["ths_limit_cpt_list"].find(
                        {},
                        {"trade_date": 1, "ts_code": 1}
                    ).sort("trade_date", -1).limit(1)
                    
                    recent_record = await recent_cursor.to_list(length=1)
                    
                    if recent_record:
                        latest_available_date = recent_record[0].get("trade_date")
                        logger.info(f"📅 找到最近有数据的交易日: {latest_available_date}，使用该日期的板块代码")
                        
                        # 使用最近有数据的交易日获取板块代码
                        latest_cursor = self.db["ths_limit_cpt_list"].find(
                            {"trade_date": latest_available_date},
                            {"ts_code": 1}
                        )
                        limit_cpt_records = await latest_cursor.to_list(length=None)
                    else:
                        logger.error(f"❌ 数据库中没有任何 limit_cpt_list 数据，请先同步 limit_cpt_list")
                        stats["errors"] = 1
                        stats["errors_list"].append(f"数据库中没有任何 limit_cpt_list 数据")
                        return stats
                
                if not limit_cpt_records:
                    logger.error(f"❌ 无法获取板块代码列表")
                    stats["errors"] = 1
                    stats["errors_list"].append(f"无法获取板块代码列表")
                    return stats
                
                ts_codes = [record.get("ts_code", "") for record in limit_cpt_records if record.get("ts_code")]
                logger.info(f"📊 找到 {len(ts_codes)} 个板块代码，开始同步成分股...")
            
            # 批量写入操作
            all_operations = []
            now_iso = datetime.utcnow().isoformat()
            
            # 循环每个板块代码，调用 ths_member 接口
            for ts_code in ts_codes:
                if not ts_code:
                    continue
                
                try:
                    # 等待速率限制
                    await self.rate_limiter.acquire()
                    
                    # 调用Tushare API获取该板块的成分股
                    df = await asyncio.to_thread(
                        self.provider.api.ths_member,
                        ts_code=ts_code
                    )
                    
                    if df is None or df.empty:
                        logger.debug(f"⚠️ 板块 {ts_code} 无成分股数据")
                        stats["concepts_failed"] += 1
                        continue
                    
                    # 转换为字典列表
                    records = df.to_dict('records')
                    stats["total_processed"] += len(records)
                    
                    # 处理每条记录
                    for record in records:
                        # 验证必需字段
                        con_code = str(record.get("con_code", "")).strip()
                        if not con_code:
                            logger.warning(f"⚠️ 跳过无效记录（con_code为空）: {record}")
                            continue
                        
                        # 存储所有字段
                        doc = {
                            "ts_code": str(record.get("ts_code", ts_code)),  # 板块代码
                            "con_code": con_code,  # 股票代码
                            "con_name": str(record.get("con_name", "")),  # 股票名称
                            "weight": record.get("weight"),  # 权重
                            "in_date": str(record.get("in_date", "")) if record.get("in_date") else None,  # 纳入日期
                            "out_date": str(record.get("out_date", "")) if record.get("out_date") else None,  # 剔除日期
                            "is_new": str(record.get("is_new", "")),  # 是否最新Y是N否
                            "data_source": "tushare",
                            "updated_at": now_iso
                        }
                        
                        # 保留所有原始字段（用于调试和扩展）
                        for key, value in record.items():
                            if key not in doc and value is not None:
                                doc[key] = value
                        
                        # 使用 ts_code + con_code 作为唯一键
                        all_operations.append(
                            UpdateOne(
                                {
                                    "ts_code": doc["ts_code"],
                                    "con_code": doc["con_code"]
                                },
                                {"$set": doc},
                                upsert=True
                            )
                        )
                    
                    stats["concepts_processed"] += 1
                    logger.info(f"✅ 板块 {ts_code} 获取完成: {len(records)} 条成分股数据")
                    
                except Exception as e:
                    logger.error(f"❌ 获取板块 {ts_code} 成分股失败: {e}")
                    stats["concepts_failed"] += 1
                    stats["errors_list"].append(f"板块 {ts_code}: {str(e)}")
                    continue
            
            # 批量写入MongoDB（分批写入，避免单次操作过大）
            if all_operations:
                total_ops = len(all_operations)
                for i in range(0, total_ops, self.batch_size):
                    batch_ops = all_operations[i:i + self.batch_size]
                    try:
                        result = await self.db["ths_member"].bulk_write(batch_ops, ordered=False)
                        stats["inserted"] += result.upserted_count
                        stats["updated"] += result.modified_count
                        logger.debug(f"📝 批量写入进度: {min(i + self.batch_size, total_ops)}/{total_ops}")
                    except BulkWriteError as e:
                        # 记录部分成功的写入
                        stats["inserted"] += e.details.get("nInserted", 0)
                        stats["updated"] += e.details.get("nModified", 0)
                        stats["errors"] += len(e.details.get("writeErrors", []))
                        logger.error(f"❌ 批量写入成分股数据时出现错误: {e.details}")
                        stats["errors_list"].append(f"批量写入错误: {str(e)}")
                
                logger.info(
                    f"✅ 同花顺概念板块成分同步完成: "
                    f"处理 {stats['concepts_processed']} 个板块, "
                    f"失败 {stats['concepts_failed']} 个板块, "
                    f"新增 {stats['inserted']} 条, "
                    f"更新 {stats['updated']} 条, "
                    f"总计 {stats['total_processed']} 条成分股数据"
                )
            else:
                logger.warning("⚠️ 未生成任何成分股数据")
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
        except Exception as e:
            logger.exception(f"❌ 同步同花顺概念板块成分失败: {e}")
            stats["errors"] = 1
            stats["errors_list"].append(str(e))
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds() if stats.get("end_time") else 0
        
        return stats
    
    # ==================== 同花顺热榜同步 ====================
    
    def _is_valid_hot_record(self, record: Dict[str, Any]) -> bool:
        """
        验证热榜记录是否有效
        
        Args:
            record: 热榜记录字典
        
        Returns:
            如果记录有效返回True，否则返回False
        """
        # 检查关键字段
        ts_code = str(record.get("ts_code", "")).strip()
        rank_time = str(record.get("rank_time", "")).strip()
        
        # ts_code 必须存在且不为空，且不能是 "{}"
        if not ts_code or ts_code == "{}" or ts_code.lower() == "none":
            return False
        
        # rank_time 应该存在且不为空，且不能是 "{}"
        if not rank_time or rank_time == "{}" or rank_time.lower() == "none":
            return False
        
        # 检查其他关键字段是否都是空值或占位符
        # 如果所有业务字段都是空的，视为无效
        key_fields = ["ts_name", "rank", "hot"]
        all_empty = True
        for field in key_fields:
            value = record.get(field)
            if value is not None:
                value_str = str(value).strip()
                if value_str and value_str != "{}" and value_str.lower() != "none":
                    all_empty = False
                    break
        
        # 如果所有关键业务字段都是空的，视为无效
        if all_empty:
            return False
        
        return True
    
    def _filter_valid_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤出有效的热榜记录
        
        Args:
            records: 记录列表
        
        Returns:
            过滤后的有效记录列表
        """
        valid_records = []
        for record in records:
            if self._is_valid_hot_record(record):
                valid_records.append(record)
            else:
                logger.debug(f"⚠️ 跳过无效记录: ts_code={record.get('ts_code')}, rank_time={record.get('rank_time')}")
        return valid_records
    
    async def sync_ths_hot(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步同花顺热榜数据
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），如果为None则使用最新交易日
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步同花顺热榜数据...")
        
        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "markets_processed": 0,
            "markets_failed": 0,
            "concept_codes_found": [],  # 记录找到的概念板块代码
            "start_time": datetime.utcnow(),
            "errors_list": []
        }
        
        try:
            # 确保索引存在
            await self._ensure_indexes("ths_hot")
            
            # 如果没有指定日期，使用最新交易日
            if not trade_date:
                trade_date = await self._get_latest_trade_date()
            
            logger.info(f"📅 同步日期: {trade_date}")
            
            # 定义需要同步的热榜类型
            markets = ['热股', '概念板块']
            logger.info(f"📊 开始循环获取热榜数据，类型: {markets}")
            
            # 批量写入操作
            all_operations = []
            now_iso = datetime.utcnow().isoformat()
            
            # 循环每个热榜类型
            for market in markets:
                try:
                    # 等待速率限制
                    await self.rate_limiter.acquire()
                    
                    # 调用Tushare API获取该类型的热榜数据
                    # 默认获取最新数据（is_new='Y'）
                    df = await asyncio.to_thread(
                        self.provider.api.ths_hot,
                        trade_date=trade_date,
                        market=market,
                        is_new='Y'
                    )
                    
                    is_new_value = 'Y'
                    records = []
                    
                    # 转换为字典列表并过滤无效记录
                    if df is not None and not df.empty:
                        records = df.to_dict('records')
                        records = self._filter_valid_records(records)
                    
                    # 如果没有获取到有效数据，尝试使用 is_new='N' 获取数据
                    if not records:
                        logger.debug(f"⚠️ 热榜类型 {market} is_new='Y' 无有效数据，尝试使用 is_new='N' 获取（日期: {trade_date}）")
                        await self.rate_limiter.acquire()
                        df = await asyncio.to_thread(
                            self.provider.api.ths_hot,
                            trade_date=trade_date,
                            market=market,
                            is_new='N'
                        )
                        is_new_value = 'N'
                        
                        # 转换为字典列表并过滤无效记录
                        if df is not None and not df.empty:
                            records = df.to_dict('records')
                            records = self._filter_valid_records(records)
                    
                    if not records:
                        logger.debug(f"⚠️ 热榜类型 {market} 无有效数据（日期: {trade_date}）")
                        stats["markets_failed"] += 1
                        continue
                    
                    # 如果使用 is_new='N' 获取数据，需要根据 rank_time 取最新的数据
                    if is_new_value == 'N':
                        # 按 ts_code 分组，每组只保留 rank_time 最新的记录
                        records_by_code = {}
                        for record in records:
                            # 再次验证记录有效性（双重保险）
                            if not self._is_valid_hot_record(record):
                                continue
                            
                            ts_code = str(record.get("ts_code", "")).strip()
                            rank_time = str(record.get("rank_time", ""))
                            
                            if ts_code not in records_by_code:
                                records_by_code[ts_code] = record
                            else:
                                # 比较 rank_time，保留最新的
                                existing_rank_time = str(records_by_code[ts_code].get("rank_time", ""))
                                if rank_time > existing_rank_time:
                                    records_by_code[ts_code] = record
                        
                        # 只保留每个 ts_code 最新的记录
                        records = list(records_by_code.values())
                        logger.debug(f"📊 热榜类型 {market} 使用 is_new='N'，根据 rank_time 筛选后保留 {len(records)} 条最新数据")
                    
                    stats["total_processed"] += len(records)
                    
                    # 处理每条记录
                    for record in records:
                        # 再次验证记录有效性（双重保险）
                        if not self._is_valid_hot_record(record):
                            logger.warning(f"⚠️ 跳过无效记录: {record}")
                            continue
                        
                        ts_code = str(record.get("ts_code", "")).strip()
                        
                        # 获取 is_new 字段，如果没有则使用默认值
                        record_is_new = str(record.get("is_new", is_new_value)).strip()
                        if not record_is_new:
                            record_is_new = is_new_value
                        
                        # 存储所有字段
                        doc = {
                            "trade_date": str(record.get("trade_date", trade_date)),
                            "market": market,  # 热榜类型
                            "data_type": str(record.get("data_type", "")),  # 数据类型
                            "ts_code": ts_code,  # 股票/板块代码
                            "ts_name": str(record.get("ts_name", "")),  # 股票/板块名称
                            "rank": record.get("rank"),  # 排行
                            "pct_change": record.get("pct_change"),  # 涨跌幅%
                            "current_price": record.get("current_price"),  # 当前价格
                            "concept": str(record.get("concept", "")),  # 标签
                            "rank_reason": str(record.get("rank_reason", "")),  # 上榜解读
                            "hot": record.get("hot"),  # 热度值
                            "rank_time": str(record.get("rank_time", "")),  # 排行榜获取时间
                            "is_new": record_is_new,  # 是否最新（Y是N否）
                            "data_source": "tushare",
                            "updated_at": now_iso
                        }
                        
                        # 如果是概念板块，记录板块代码用于后续同步 ths_member
                        if market == "概念板块" and ts_code:
                            if ts_code not in stats["concept_codes_found"]:
                                stats["concept_codes_found"].append(ts_code)
                        
                        # 保留所有原始字段（用于调试和扩展）
                        for key, value in record.items():
                            if key not in doc and value is not None:
                                doc[key] = value
                        
                        # 使用 trade_date + market + ts_code + rank_time 作为唯一键
                        all_operations.append(
                            UpdateOne(
                                {
                                    "trade_date": doc["trade_date"],
                                    "market": doc["market"],
                                    "ts_code": doc["ts_code"],
                                    "rank_time": doc["rank_time"]
                                },
                                {"$set": doc},
                                upsert=True
                            )
                        )
                    
                    stats["markets_processed"] += 1
                    logger.info(f"✅ 热榜类型 {market} 获取完成: {len(records)} 条数据 (is_new={is_new_value})")
                    
                except Exception as e:
                    logger.error(f"❌ 获取热榜类型 {market} 失败: {e}")
                    stats["markets_failed"] += 1
                    stats["errors_list"].append(f"热榜类型 {market}: {str(e)}")
                    continue
            
            # 批量写入MongoDB（分批写入，避免单次操作过大）
            if all_operations:
                total_ops = len(all_operations)
                for i in range(0, total_ops, self.batch_size):
                    batch_ops = all_operations[i:i + self.batch_size]
                    try:
                        result = await self.db["ths_hot"].bulk_write(batch_ops, ordered=False)
                        stats["inserted"] += result.upserted_count
                        stats["updated"] += result.modified_count
                        logger.debug(f"📝 批量写入进度: {min(i + self.batch_size, total_ops)}/{total_ops}")
                    except BulkWriteError as e:
                        # 记录部分成功的写入
                        stats["inserted"] += e.details.get("nInserted", 0)
                        stats["updated"] += e.details.get("nModified", 0)
                        stats["errors"] += len(e.details.get("writeErrors", []))
                        logger.error(f"❌ 批量写入热榜数据时出现错误: {e.details}")
                        stats["errors_list"].append(f"批量写入错误: {str(e)}")
                
                logger.info(
                    f"✅ 同花顺热榜数据同步完成: "
                    f"处理 {stats['markets_processed']} 个类型, "
                    f"失败 {stats['markets_failed']} 个类型, "
                    f"新增 {stats['inserted']} 条, "
                    f"更新 {stats['updated']} 条, "
                    f"总计 {stats['total_processed']} 条热榜数据"
                )
                
                # 如果找到概念板块代码，记录日志
                if stats["concept_codes_found"]:
                    logger.info(f"📊 找到 {len(stats['concept_codes_found'])} 个概念板块代码: {stats['concept_codes_found'][:10]}...")
            else:
                logger.warning("⚠️ 未生成任何热榜数据")
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
        except Exception as e:
            logger.exception(f"❌ 同步同花顺热榜数据失败: {e}")
            stats["errors"] = 1
            stats["errors_list"].append(str(e))
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds() if stats.get("end_time") else 0
        
        return stats
    
    # ==================== 统一同步入口 ====================
    
    async def sync_all(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步所有同花顺题材数据
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），如果为None则使用最新交易日
        
        Returns:
            同步结果统计
        """
        logger.info("🚀 开始同步所有同花顺题材数据...")
        start_time = datetime.utcnow()
        
        # 如果没有指定日期，获取最新交易日
        if not trade_date:
            trade_date = await self._get_latest_trade_date()
        
        # 1. 同步最强板块统计
        limit_cpt_stats = await self.sync_limit_cpt_list(trade_date=trade_date)
        
        # 2. 同步同花顺热榜数据
        ths_hot_stats = await self.sync_ths_hot(trade_date=trade_date)
        
        # 3. 收集需要同步成分股的板块代码
        concept_codes_to_sync = []
        
        # 从 limit_cpt_list 获取板块代码
        if limit_cpt_stats.get("inserted", 0) > 0 or limit_cpt_stats.get("updated", 0) > 0 or limit_cpt_stats.get("total_processed", 0) > 0:
            logger.info(f"📊 从 limit_cpt_list 获取板块代码...")
            cursor = self.db["ths_limit_cpt_list"].find(
                {"trade_date": trade_date},
                {"ts_code": 1}
            )
            limit_cpt_records = await cursor.to_list(length=None)
            limit_cpt_codes = [r.get("ts_code", "") for r in limit_cpt_records if r.get("ts_code")]
            concept_codes_to_sync.extend(limit_cpt_codes)
            logger.info(f"📊 从 limit_cpt_list 获取到 {len(limit_cpt_codes)} 个板块代码")
        
        # 从 ths_hot 的概念板块数据中获取板块代码
        if ths_hot_stats.get("concept_codes_found"):
            concept_codes_from_hot = ths_hot_stats.get("concept_codes_found", [])
            concept_codes_to_sync.extend(concept_codes_from_hot)
            logger.info(f"📊 从 ths_hot 获取到 {len(concept_codes_from_hot)} 个概念板块代码")
        
        # 去重
        concept_codes_to_sync = list(set(concept_codes_to_sync))
        
        # 4. 同步同花顺概念板块成分
        if concept_codes_to_sync:
            logger.info(f"📊 开始同步板块成分，共 {len(concept_codes_to_sync)} 个板块代码")
            ths_member_stats = await self.sync_ths_member(ts_codes=concept_codes_to_sync, trade_date=trade_date)
        elif limit_cpt_stats.get("total_processed", 0) > 0:
            # 即使没有新增或更新，如果有处理的数据，也可以同步成分股
            logger.info(f"📊 limit_cpt_list 已有数据，开始同步板块成分...")
            ths_member_stats = await self.sync_ths_member(trade_date=trade_date)
        else:
            # limit_cpt_list 同步失败或没有数据
            logger.warning(f"⚠️ 未找到板块代码，跳过板块成分同步")
            ths_member_stats = {
                "total_processed": 0,
                "inserted": 0,
                "updated": 0,
                "errors": 1,
                "concepts_processed": 0,
                "concepts_failed": 0,
                "start_time": datetime.utcnow(),
                "errors_list": ["未找到板块代码，无法同步成分股"],
                "end_time": datetime.utcnow(),
                "duration": 0
            }
        
        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()
        
        result = {
            "limit_cpt_list": limit_cpt_stats,
            "ths_hot": ths_hot_stats,
            "ths_member": ths_member_stats,
            "total_duration": total_duration
        }
        
        logger.info(
            f"✅ 所有同花顺题材数据同步完成: "
            f"最强板块-新增{limit_cpt_stats.get('inserted', 0)}条, "
            f"热榜-新增{ths_hot_stats.get('inserted', 0)}条, "
            f"板块成分-新增{ths_member_stats.get('inserted', 0)}条, "
            f"总耗时: {total_duration:.2f}秒"
        )
        
        return result
    
    # ==================== 工具方法 ====================
    
    async def _get_latest_trade_date(self) -> str:
        """
        获取最新交易日（is_open=1）
        如果今天不是交易日，返回最近一个交易日
        """
        try:
            # 使用Tushare API获取交易日历
            # 查询最近30天的交易日历，筛选出交易日（is_open=1）
            await self.rate_limiter.acquire()
            today_str = datetime.now().strftime('%Y%m%d')
            start_date_str = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            
            logger.debug(f"🔍 查询交易日历: {start_date_str} 到 {today_str}")
            
            cal_df = await asyncio.to_thread(
                self.provider.api.trade_cal,
                exchange='SSE',
                start_date=start_date_str,
                end_date=today_str
            )
            
            if cal_df is not None and not cal_df.empty:
                logger.debug(f"📊 获取到 {len(cal_df)} 条交易日历数据")
                
                # is_open 可能是字符串 '1' 或数字 1，需要兼容处理
                # 先转换为字符串进行比较，或者转换为数字
                if 'is_open' in cal_df.columns:
                    # 尝试转换为数字类型
                    cal_df['is_open'] = cal_df['is_open'].astype(str).str.strip()
                    # 筛选出交易日（is_open='1'）
                    trade_days = cal_df[cal_df['is_open'] == '1']
                else:
                    logger.warning("⚠️ 交易日历数据中缺少 is_open 字段")
                    trade_days = cal_df
                
                if not trade_days.empty:
                    # 按日期排序，确保获取最新的交易日
                    trade_days = trade_days.sort_values('cal_date', ascending=True)
                    # 获取最新的交易日（最后一行）
                    latest_date = trade_days.iloc[-1]['cal_date']
                    latest_date_str = str(latest_date)
                    logger.info(f"📅 获取到最新交易日: {latest_date_str} (共 {len(trade_days)} 个交易日)")
                    return latest_date_str
                else:
                    logger.warning(f"⚠️ 最近30天无交易日，扩大查询范围...")
                    # 如果最近30天都没有交易日，扩大查询范围
                    await self.rate_limiter.acquire()
                    start_date_extended = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
                    cal_df_extended = await asyncio.to_thread(
                        self.provider.api.trade_cal,
                        exchange='SSE',
                        start_date=start_date_extended,
                        end_date=today_str
                    )
                    
                    if cal_df_extended is not None and not cal_df_extended.empty:
                        if 'is_open' in cal_df_extended.columns:
                            cal_df_extended['is_open'] = cal_df_extended['is_open'].astype(str).str.strip()
                            trade_days_extended = cal_df_extended[cal_df_extended['is_open'] == '1']
                        else:
                            trade_days_extended = cal_df_extended
                        
                        if not trade_days_extended.empty:
                            trade_days_extended = trade_days_extended.sort_values('cal_date', ascending=True)
                            latest_date = trade_days_extended.iloc[-1]['cal_date']
                            latest_date_str = str(latest_date)
                            logger.info(f"📅 获取到最新交易日（扩展查询）: {latest_date_str} (共 {len(trade_days_extended)} 个交易日)")
                            return latest_date_str
            
            # 如果API调用失败，尝试使用昨天作为默认值
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            logger.warning(f"⚠️ 无法获取最新交易日，使用默认值: {yesterday}")
            return yesterday
            
        except Exception as e:
            logger.exception(f"⚠️ 获取最新交易日失败: {e}，使用默认值")
            # 尝试使用昨天作为默认值
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            return yesterday


# 单例模式
_ths_sync_service: Optional[THSSyncService] = None


async def get_ths_sync_service() -> THSSyncService:
    """获取同花顺题材同步服务单例"""
    global _ths_sync_service
    if _ths_sync_service is None:
        _ths_sync_service = THSSyncService()
        await _ths_sync_service.initialize()
    return _ths_sync_service

