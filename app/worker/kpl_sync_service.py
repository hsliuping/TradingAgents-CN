"""
开盘啦数据同步服务
负责同步开盘啦（KPL）三个接口的数据到MongoDB
- kpl_concept: 开盘啦题材库
- kpl_concept_cons: 开盘啦题材成分
- kpl_list: 开盘啦榜单数据
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


class KPLSyncService:
    """
    开盘啦数据同步服务
    负责将开盘啦数据同步到MongoDB
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
            "kpl_concept": False,
            "kpl_concept_cons": False,
            "kpl_list": False,
            "kpl_concept_stats": False
        }
    
    async def initialize(self):
        """初始化同步服务"""
        success = await self.provider.connect()
        if not success:
            raise RuntimeError("❌ Tushare连接失败，无法启动开盘啦同步服务")
        logger.info("✅ 开盘啦同步服务初始化完成")
    
    # ==================== 索引管理 ====================
    
    async def _ensure_indexes(self, collection_name: str):
        """确保必要的索引存在"""
        if self._indexes_ensured.get(collection_name, False):
            return
        
        try:
            collection = self.db[collection_name]
            
            if collection_name == "kpl_concept":
                # 开盘啦题材库索引
                await collection.create_index(
                    [("trade_date", 1), ("ts_code", 1)],
                    unique=True,
                    name="trade_date_ts_code_unique",
                    background=True
                )
                await collection.create_index([("trade_date", -1)], name="trade_date_desc", background=True)
                await collection.create_index([("ts_code", 1)], name="ts_code_index", background=True)
                await collection.create_index([("name", 1)], name="name_index", background=True)
                await collection.create_index([("z_t_num", -1)], name="z_t_num_desc", background=True)
                await collection.create_index([("up_num", 1)], name="up_num_index", background=True)
                
            elif collection_name == "kpl_concept_cons":
                # 开盘啦题材成分索引
                await collection.create_index(
                    [("trade_date", 1), ("concept_code", 1), ("ts_code", 1)],
                    unique=True,
                    name="trade_date_concept_cons_unique",
                    background=True
                )
                await collection.create_index([("trade_date", -1)], name="trade_date_desc", background=True)
                await collection.create_index([("concept_code", 1)], name="concept_code_index", background=True)
                await collection.create_index([("ts_code", 1)], name="ts_code_index", background=True)
                await collection.create_index([("concept_name", 1)], name="concept_name_index", background=True)
                
            elif collection_name == "kpl_list":
                # 开盘啦榜单数据索引
                # 先删除旧的索引（如果存在）
                try:
                    old_indexes = ["trade_date_rank_type_rank_unique", "rank_type_index", "rank_index"]
                    existing_indexes = await collection.list_indexes().to_list(length=None)
                    for idx in existing_indexes:
                        idx_name = idx.get('name', '')
                        if idx_name in old_indexes:
                            try:
                                await collection.drop_index(idx_name)
                                logger.info(f"🗑️ 删除旧索引: {idx_name}")
                            except Exception as e:
                                logger.debug(f"删除索引 {idx_name} 失败（可能不存在）: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ 检查旧索引时出错: {e}")
                
                # 创建新的唯一索引（先尝试删除，再创建）
                try:
                    # 如果新索引已存在，先删除
                    try:
                        await collection.drop_index("trade_date_tag_ts_code_unique")
                        logger.info("🗑️ 删除已存在的新索引，准备重新创建")
                    except:
                        pass  # 索引不存在，继续创建
                    
                    await collection.create_index(
                        [("trade_date", 1), ("tag", 1), ("ts_code", 1)],
                        unique=True,
                        name="trade_date_tag_ts_code_unique",
                        background=True
                    )
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"⚠️ 创建唯一索引失败: {e}")
                
                # 创建其他索引
                try:
                    await collection.create_index([("trade_date", -1)], name="trade_date_desc", background=True)
                except:
                    pass
                try:
                    await collection.create_index([("tag", 1)], name="tag_index", background=True)
                except:
                    pass
                try:
                    await collection.create_index([("ts_code", 1)], name="ts_code_index", background=True)
                except:
                    pass
                try:
                    await collection.create_index([("status", 1)], name="status_index", background=True)
                except:
                    pass
                try:
                    await collection.create_index([("theme", 1)], name="theme_index", background=True)
                except:
                    pass
            
            elif collection_name == "kpl_concept_stats":
                # 开盘啦题材统计数据索引
                await collection.create_index(
                    [("trade_date", 1), ("concept_code", 1)],
                    unique=True,
                    name="trade_date_concept_code_unique",
                    background=True
                )
                await collection.create_index([("trade_date", -1)], name="trade_date_desc", background=True)
                await collection.create_index([("concept_code", 1)], name="concept_code_index", background=True)
                await collection.create_index([("concept_name", 1)], name="concept_name_index", background=True)
                await collection.create_index([("limit_up_count", -1)], name="limit_up_count_desc", background=True)
            
            self._indexes_ensured[collection_name] = True
            logger.info(f"✅ {collection_name} 索引检查完成")
            
        except Exception as e:
            logger.warning(f"⚠️ 创建 {collection_name} 索引时出现警告（可能已存在）: {e}")
            self._indexes_ensured[collection_name] = True
    
    # ==================== 开盘啦题材库同步 ====================
    
    async def sync_kpl_concept(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步开盘啦题材库数据
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），为空则使用最新交易日
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步开盘啦题材库数据...")
        
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
            await self._ensure_indexes("kpl_concept")
            
            # 如果没有指定日期，使用最新交易日
            if not trade_date:
                trade_date = await self._get_latest_trade_date()
            
            # 等待速率限制
            await self.rate_limiter.acquire()
            
            # 调用Tushare API
            df = await asyncio.to_thread(
                self.provider.api.kpl_concept,
                trade_date=trade_date
            )
            
            if df is None or df.empty:
                logger.warning(f"⚠️ 开盘啦题材库数据为空（日期: {trade_date}）")
                stats["errors"] = 1
                stats["errors_list"].append(f"数据为空（日期: {trade_date}）")
                return stats
            
            # 转换为字典列表
            records = df.to_dict('records')
            stats["total_processed"] = len(records)
            
            # 批量写入MongoDB
            operations = []
            now_iso = datetime.utcnow().isoformat()
            
            for record in records:
                # 标准化数据
                doc = {
                    "trade_date": str(record.get("trade_date", trade_date)),
                    "ts_code": str(record.get("ts_code", "")),
                    "name": str(record.get("name", "")),
                    "z_t_num": record.get("z_t_num"),
                    "up_num": record.get("up_num"),
                    "data_source": "tushare",
                    "updated_at": now_iso
                }
                
                # 使用 trade_date + ts_code 作为唯一键
                operations.append(
                    UpdateOne(
                        {"trade_date": doc["trade_date"], "ts_code": doc["ts_code"]},
                        {"$set": doc},
                        upsert=True
                    )
                )
            
            # 执行批量写入
            if operations:
                try:
                    result = await self.db["kpl_concept"].bulk_write(operations, ordered=False)
                    stats["inserted"] = result.upserted_count
                    stats["updated"] = result.modified_count
                    logger.info(f"✅ 开盘啦题材库同步完成: 新增 {stats['inserted']} 条, 更新 {stats['updated']} 条")
                except BulkWriteError as e:
                    stats["errors"] = len(e.details.get('writeErrors', []))
                    logger.error(f"❌ 批量写入失败: {e}")
                    stats["errors_list"].append(str(e))
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            return stats
            
        except Exception as e:
            logger.exception(f"❌ 同步开盘啦题材库失败: {e}")
            stats["errors"] = 1
            stats["errors_list"].append(str(e))
            stats["end_time"] = datetime.utcnow()
            return stats
    
    # ==================== 开盘啦题材成分同步 ====================
    
    async def sync_kpl_concept_cons(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步开盘啦题材成分数据
        
        逻辑：先从 kpl_concept 集合获取该日期的所有题材代码，然后循环调用 kpl_concept_cons 接口
        获取每个题材的成分股数据
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），为空则使用最新交易日
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步开盘啦题材成分数据...")
        
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
            await self._ensure_indexes("kpl_concept_cons")
            
            # 如果没有指定日期，使用最新交易日
            if not trade_date:
                trade_date = await self._get_latest_trade_date()
            
            logger.info(f"📅 同步日期: {trade_date}")
            
            # 1. 从 kpl_concept 集合获取该日期的所有题材代码
            concept_cursor = self.db["kpl_concept"].find(
                {"trade_date": trade_date},
                {"ts_code": 1, "name": 1}
            )
            concepts = await concept_cursor.to_list(length=None)
            
            if not concepts:
                logger.warning(f"⚠️ 未找到日期 {trade_date} 的题材数据，请先同步 kpl_concept")
                stats["errors"] = 1
                stats["errors_list"].append(f"未找到日期 {trade_date} 的题材数据")
                return stats
            
            concept_list = [(c.get("ts_code"), c.get("name", "")) for c in concepts if c.get("ts_code")]
            logger.info(f"📊 找到 {len(concept_list)} 个题材，开始循环获取成分股...")
            
            # 2. 循环每个题材代码，调用 kpl_concept_cons 接口
            all_operations = []
            now_iso = datetime.utcnow().isoformat()
            
            for idx, (concept_code, concept_name) in enumerate(concept_list, 1):
                try:
                    # 等待速率限制
                    await self.rate_limiter.acquire()
                    
                    # 调用Tushare API获取该题材的成分股
                    df = await asyncio.to_thread(
                        self.provider.api.kpl_concept_cons,
                        trade_date=trade_date,
                        ts_code=concept_code
                    )
                    
                    if df is None or df.empty:
                        logger.debug(f"⚠️ 题材 {concept_code} ({concept_name}) 无成分股数据")
                        stats["concepts_failed"] += 1
                        continue
                    
                    # 转换为字典列表
                    records = df.to_dict('records')
                    stats["total_processed"] += len(records)
                    
                    # 处理每条记录
                    for record in records:
                        # 根据API文档，字段映射：
                        # ts_code -> concept_code (题材代码)
                        # name -> concept_name (题材名称)
                        # con_code -> ts_code (股票代码)
                        # con_name -> stock_name (股票名称)
                        doc = {
                            "trade_date": str(record.get("trade_date", trade_date)),
                            "concept_code": str(record.get("ts_code", concept_code)),  # 题材代码
                            "ts_code": str(record.get("con_code", "")),  # 股票代码
                            "concept_name": str(record.get("name", concept_name)),  # 题材名称
                            "stock_name": str(record.get("con_name", "")),  # 股票名称
                            "desc": str(record.get("desc", "")),  # 描述
                            "hot_num": record.get("hot_num"),  # 人气值
                            "data_source": "tushare",
                            "updated_at": now_iso
                        }
                        
                        # 保留所有原始字段（用于调试和扩展）
                        for key, value in record.items():
                            if key not in doc and value is not None:
                                doc[f"raw_{key}"] = value
                        
                        # 使用 trade_date + concept_code + ts_code 作为唯一键
                        all_operations.append(
                            UpdateOne(
                                {
                                    "trade_date": doc["trade_date"],
                                    "concept_code": doc["concept_code"],
                                    "ts_code": doc["ts_code"]
                                },
                                {"$set": doc},
                                upsert=True
                            )
                        )
                    
                    stats["concepts_processed"] += 1
                    
                    # 每处理10个题材输出一次进度
                    if idx % 10 == 0:
                        logger.info(f"📈 进度: {idx}/{len(concept_list)} 个题材已处理，已获取 {stats['total_processed']} 条成分股数据")
                    
                except Exception as e:
                    logger.error(f"❌ 获取题材 {concept_code} ({concept_name}) 成分股失败: {e}")
                    stats["concepts_failed"] += 1
                    stats["errors_list"].append(f"题材 {concept_code}: {str(e)}")
                    continue
            
            # 3. 批量写入MongoDB（分批写入，避免单次操作过大）
            if all_operations:
                batch_size = 1000
                total_inserted = 0
                total_updated = 0
                
                for i in range(0, len(all_operations), batch_size):
                    batch = all_operations[i:i + batch_size]
                    try:
                        result = await self.db["kpl_concept_cons"].bulk_write(batch, ordered=False)
                        total_inserted += result.upserted_count
                        total_updated += result.modified_count
                    except BulkWriteError as e:
                        write_errors = len(e.details.get('writeErrors', []))
                        stats["errors"] += write_errors
                        logger.error(f"❌ 批量写入失败（批次 {i//batch_size + 1}）: {write_errors} 条错误")
                        stats["errors_list"].append(f"批量写入批次 {i//batch_size + 1}: {str(e)}")
                
                stats["inserted"] = total_inserted
                stats["updated"] = total_updated
                logger.info(
                    f"✅ 开盘啦题材成分同步完成: "
                    f"处理 {stats['concepts_processed']} 个题材, "
                    f"失败 {stats['concepts_failed']} 个题材, "
                    f"新增 {stats['inserted']} 条, "
                    f"更新 {stats['updated']} 条, "
                    f"总计 {stats['total_processed']} 条成分股数据"
                )
            else:
                logger.warning(f"⚠️ 未获取到任何成分股数据")
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            return stats
            
        except Exception as e:
            logger.exception(f"❌ 同步开盘啦题材成分失败: {e}")
            stats["errors"] = 1
            stats["errors_list"].append(str(e))
            stats["end_time"] = datetime.utcnow()
            return stats
    
    # ==================== 开盘啦榜单数据同步 ====================
    
    async def sync_kpl_list(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步开盘啦榜单数据
        
        逻辑：从 kpl_concept 集合获取 trade_date，然后循环调用 kpl_list 接口
        分别使用 tag='涨停'、'跌停'、'炸板' 各调用一次
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），为空则使用最新交易日
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步开盘啦榜单数据...")
        
        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "tags_processed": 0,
            "tags_failed": 0,
            "start_time": datetime.utcnow(),
            "errors_list": []
        }
        
        try:
            # 确保索引存在
            await self._ensure_indexes("kpl_list")
            
            # 如果没有指定日期，使用最新交易日
            if not trade_date:
                trade_date = await self._get_latest_trade_date()
            
            logger.info(f"📅 同步日期: {trade_date}")
            
            # 1. 从 kpl_concept 集合获取该日期（验证数据是否存在）
            concept_count = await self.db["kpl_concept"].count_documents({"trade_date": trade_date})
            if concept_count == 0:
                logger.warning(f"⚠️ 未找到日期 {trade_date} 的题材数据，请先同步 kpl_concept")
                stats["errors"] = 1
                stats["errors_list"].append(f"未找到日期 {trade_date} 的题材数据")
                return stats
            
            # 2. 定义需要同步的榜单类型
            tags = ['涨停', '跌停', '炸板', '自然涨停', '竞价']            
            logger.info(f"📊 开始循环获取榜单数据，类型: {tags}")
            
            # 3. 循环每个榜单类型，调用 kpl_list 接口
            all_operations = []
            now_iso = datetime.utcnow().isoformat()
            
            for tag in tags:
                try:
                    # 等待速率限制
                    await self.rate_limiter.acquire()
                    
                    # 明确指定需要返回的字段，确保包含 pct_chg
                    fields = "ts_code,name,trade_date,lu_time,ld_time,open_time,last_time,lu_desc,tag,theme,net_change,bid_amount,status,bid_change,bid_turnover,lu_bid_vol,pct_chg,bid_pct_chg,rt_pct_chg,limit_order,amount,turnover_rate,free_float,lu_limit_order"
                    
                    # 调用Tushare API获取该类型的榜单数据
                    df = await asyncio.to_thread(
                        self.provider.api.kpl_list,
                        trade_date=trade_date,
                        tag=tag,
                        fields=fields
                    )
                    
                    if df is None or df.empty:
                        logger.debug(f"⚠️ 榜单类型 {tag} 无数据（日期: {trade_date}）")
                        stats["tags_failed"] += 1
                        continue
                    
                    # 转换为字典列表
                    records = df.to_dict('records')
                    stats["total_processed"] += len(records)
                    
                    # 处理每条记录
                    for record in records:
                        # 验证必需字段
                        ts_code = str(record.get("ts_code", "")).strip()
                        if not ts_code:
                            logger.warning(f"⚠️ 跳过无效记录（ts_code为空）: {record}")
                            continue
                        
                        # 根据API文档，存储所有字段
                        doc = {
                            "trade_date": str(record.get("trade_date", trade_date)),
                            "tag": str(record.get("tag", tag)),  # 榜单类型
                            "ts_code": ts_code,  # 股票代码（已验证非空）
                            "name": str(record.get("name", "")),  # 股票名称
                            "lu_time": str(record.get("lu_time", "")),  # 涨停时间
                            "ld_time": str(record.get("ld_time", "")),  # 跌停时间
                            "open_time": str(record.get("open_time", "")),  # 开板时间
                            "last_time": str(record.get("last_time", "")),  # 最后涨停时间
                            "lu_desc": str(record.get("lu_desc", "")),  # 涨停原因
                            "theme": str(record.get("theme", "")),  # 板块
                            "net_change": record.get("net_change"),  # 主力净额(元)
                            "bid_amount": record.get("bid_amount"),  # 竞价成交额(元)
                            "status": str(record.get("status", "")),  # 状态（N连板）
                            "bid_change": record.get("bid_change"),  # 竞价净额
                            "bid_turnover": record.get("bid_turnover"),  # 竞价换手%
                            "lu_bid_vol": record.get("lu_bid_vol"),  # 涨停委买额
                            "pct_chg": self._safe_float(record.get("pct_chg")),  # 涨跌幅%
                            "bid_pct_chg": self._safe_float(record.get("bid_pct_chg")),  # 竞价涨幅%
                            "rt_pct_chg": self._safe_float(record.get("rt_pct_chg")),  # 实时涨幅%
                            "limit_order": record.get("limit_order"),  # 封单
                            "amount": record.get("amount"),  # 成交额
                            "turnover_rate": record.get("turnover_rate"),  # 换手率%
                            "free_float": record.get("free_float"),  # 实际流通
                            "lu_limit_order": record.get("lu_limit_order"),  # 最大封单
                            "data_source": "tushare",
                            "updated_at": now_iso
                        }
                        
                        # 保留所有原始字段（用于调试和扩展）
                        for key, value in record.items():
                            if key not in doc and value is not None:
                                doc[key] = value
                        
                        # 使用 trade_date + tag + ts_code 作为唯一键
                        all_operations.append(
                            UpdateOne(
                                {
                                    "trade_date": doc["trade_date"],
                                    "tag": doc["tag"],
                                    "ts_code": doc["ts_code"]
                                },
                                {"$set": doc},
                                upsert=True
                            )
                        )
                    
                    stats["tags_processed"] += 1
                    logger.info(f"✅ 榜单类型 {tag} 获取完成: {len(records)} 条数据")
                    
                except Exception as e:
                    logger.error(f"❌ 获取榜单类型 {tag} 失败: {e}")
                    stats["tags_failed"] += 1
                    stats["errors_list"].append(f"榜单类型 {tag}: {str(e)}")
                    continue
            
            # 4. 批量写入MongoDB（分批写入，避免单次操作过大）
            if all_operations:
                batch_size = 1000
                total_inserted = 0
                total_updated = 0
                
                for i in range(0, len(all_operations), batch_size):
                    batch = all_operations[i:i + batch_size]
                    try:
                        result = await self.db["kpl_list"].bulk_write(batch, ordered=False)
                        total_inserted += result.upserted_count
                        total_updated += result.modified_count
                    except BulkWriteError as e:
                        write_errors = e.details.get('writeErrors', [])
                        error_count = len(write_errors)
                        stats["errors"] += error_count
                        
                        # 输出详细的错误信息
                        logger.error(f"❌ 批量写入失败（批次 {i//batch_size + 1}）: {error_count} 条错误")
                        
                        # 记录前5个错误的详细信息
                        for idx, error in enumerate(write_errors[:5], 1):
                            error_code = error.get('code', 'N/A')
                            error_msg = error.get('errmsg', 'Unknown error')
                            error_index = error.get('index', 'N/A')
                            logger.error(f"   错误 {idx}: [Code {error_code}] {error_msg} (索引: {error_index})")
                        
                        if error_count > 5:
                            logger.error(f"   ... 还有 {error_count - 5} 个错误未显示")
                        
                        # 统计成功写入的数量（即使有错误，部分数据可能已写入）
                        if hasattr(e, 'details'):
                            n_inserted = e.details.get('nInserted', 0)
                            n_modified = e.details.get('nModified', 0)
                            if n_inserted > 0 or n_modified > 0:
                                total_inserted += n_inserted
                                total_updated += n_modified
                                logger.info(f"   ℹ️ 部分成功: 新增 {n_inserted} 条, 更新 {n_modified} 条")
                        
                        stats["errors_list"].append(f"批量写入批次 {i//batch_size + 1}: {error_count} 条错误")
                
                stats["inserted"] = total_inserted
                stats["updated"] = total_updated
                logger.info(
                    f"✅ 开盘啦榜单数据同步完成: "
                    f"处理 {stats['tags_processed']} 个榜单类型, "
                    f"失败 {stats['tags_failed']} 个榜单类型, "
                    f"新增 {stats['inserted']} 条, "
                    f"更新 {stats['updated']} 条, "
                    f"总计 {stats['total_processed']} 条榜单数据"
                )
                
                # 5. 统计题材数据并写入新表
                concept_stats_result = await self._sync_concept_stats(trade_date)
                stats["concept_stats"] = concept_stats_result
            else:
                logger.warning(f"⚠️ 未获取到任何榜单数据")
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            return stats
            
        except Exception as e:
            logger.exception(f"❌ 同步开盘啦榜单数据失败: {e}")
            stats["errors"] = 1
            stats["errors_list"].append(str(e))
            stats["end_time"] = datetime.utcnow()
            return stats
    
    # ==================== 题材统计数据同步 ====================
    
    async def _sync_concept_stats(self, trade_date: str) -> Dict[str, Any]:
        """
        统计每个题材的涨停、跌停、炸板、涨幅超过9%的个数
        
        逻辑：
        1. 从 kpl_concept 获取该日期的所有题材
        2. 对每个题材，从 kpl_concept_cons 获取该题材包含的股票代码列表
        3. 从 kpl_list 中查找这些股票的涨跌停信息进行统计
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式）
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始统计题材数据...")
        
        try:
            # 确保索引存在
            await self._ensure_indexes("kpl_concept_stats")
            
            # 1. 从 kpl_concept 获取该日期的所有题材
            concept_cursor = self.db["kpl_concept"].find(
                {"trade_date": trade_date},
                {"ts_code": 1, "name": 1}
            )
            concepts = await concept_cursor.to_list(length=None)
            
            if not concepts:
                logger.warning(f"⚠️ 未找到日期 {trade_date} 的题材数据，请先同步 kpl_concept")
                return {"inserted": 0, "updated": 0}
            
            logger.info(f"📊 找到 {len(concepts)} 个题材，开始统计...")
            
            # 2. 从 kpl_list 获取该日期的所有股票涨跌停信息（建立索引）
            list_cursor = self.db["kpl_list"].find(
                {"trade_date": trade_date},
                {"ts_code": 1, "tag": 1, "pct_chg": 1}
            )
            list_records = await list_cursor.to_list(length=None)
            
            # 建立股票代码到涨跌停信息的映射（支持多种格式）
            stock_info_map = {}
            for record in list_records:
                ts_code = record.get("ts_code", "")
                if not ts_code:
                    continue
                
                # 标准化股票代码：提取6位数字代码
                # 处理格式：000001.SZ, 000001.SH, 000001, 600001 等
                code_6digit = self._normalize_stock_code(ts_code)
                if not code_6digit:
                    continue
                
                if code_6digit not in stock_info_map:
                    stock_info_map[code_6digit] = {
                        "limit_up": False,
                        "limit_down": False,
                        "zha_ban": False,
                        "high_gain": False
                    }
                
                # 记录涨跌停信息
                tag = record.get("tag", "")
                if tag == "涨停":
                    stock_info_map[code_6digit]["limit_up"] = True
                elif tag == "跌停":
                    stock_info_map[code_6digit]["limit_down"] = True
                elif tag == "炸板":
                    stock_info_map[code_6digit]["zha_ban"] = True
                
                # 检查涨幅（涨幅超过9%的统计）
                pct_chg = record.get("pct_chg")
                if pct_chg is not None and isinstance(pct_chg, (int, float)) and pct_chg > 9:
                    stock_info_map[code_6digit]["high_gain"] = True
            
            logger.info(f"📈 从 kpl_list 获取到 {len(stock_info_map)} 只股票的涨跌停信息")
            
            # 3. 对每个题材，统计其包含股票的涨跌停信息
            operations = []
            now_iso = datetime.utcnow().isoformat()
            concepts_processed = 0
            
            for concept in concepts:
                concept_code = concept.get("ts_code", "")
                concept_name = concept.get("name", "")
                
                if not concept_code:
                    continue
                
                # 从 kpl_concept_cons 获取该题材包含的股票代码列表
                cons_cursor = self.db["kpl_concept_cons"].find(
                    {
                        "trade_date": trade_date,
                        "concept_code": concept_code
                    },
                    {"ts_code": 1}
                )
                cons_stocks = await cons_cursor.to_list(length=None)
                
                if not cons_stocks:
                    continue
                
                # 统计该题材的涨跌停信息
                limit_up_count = 0
                limit_down_count = 0
                zha_ban_count = 0
                high_gain_count = 0
                
                for cons_stock in cons_stocks:
                    stock_code = cons_stock.get("ts_code", "")
                    if not stock_code:
                        continue
                    
                    # 标准化股票代码：提取6位数字代码
                    code_6digit = self._normalize_stock_code(stock_code)
                    if not code_6digit:
                        continue
                    
                    # 从映射中查找该股票的涨跌停信息
                    if code_6digit in stock_info_map:
                        stock_info = stock_info_map[code_6digit]
                        if stock_info["limit_up"]:
                            limit_up_count += 1
                        if stock_info["limit_down"]:
                            limit_down_count += 1
                        if stock_info["zha_ban"]:
                            zha_ban_count += 1
                        if stock_info["high_gain"]:
                            high_gain_count += 1
                
                # 准备写入数据
                doc = {
                    "trade_date": trade_date,
                    "concept_code": concept_code,
                    "concept_name": concept_name,
                    "limit_up_count": limit_up_count,
                    "limit_down_count": limit_down_count,
                    "zha_ban_count": zha_ban_count,
                    "high_gain_count": high_gain_count,
                    "total_stocks": len(cons_stocks),  # 该题材包含的股票总数
                    "data_source": "tushare",
                    "updated_at": now_iso
                }
                
                # 使用 trade_date + concept_code 作为唯一键
                operations.append(
                    UpdateOne(
                        {
                            "trade_date": doc["trade_date"],
                            "concept_code": doc["concept_code"]
                        },
                        {"$set": doc},
                        upsert=True
                    )
                )
                
                concepts_processed += 1
                
                # 每处理50个题材输出一次进度
                if concepts_processed % 50 == 0:
                    logger.info(f"📈 进度: {concepts_processed}/{len(concepts)} 个题材已统计")
            
            # 4. 批量写入
            if operations:
                try:
                    result = await self.db["kpl_concept_stats"].bulk_write(operations, ordered=False)
                    logger.info(
                        f"✅ 题材统计数据同步完成: "
                        f"新增 {result.upserted_count} 条, "
                        f"更新 {result.modified_count} 条, "
                        f"共 {concepts_processed} 个题材"
                    )
                    return {
                        "inserted": result.upserted_count,
                        "updated": result.modified_count,
                        "total": concepts_processed
                    }
                except BulkWriteError as e:
                    write_errors = len(e.details.get('writeErrors', []))
                    logger.error(f"❌ 题材统计数据批量写入失败: {write_errors} 条错误")
                    # 即使有错误，也返回部分成功的数据
                    n_inserted = e.details.get('nInserted', 0)
                    n_modified = e.details.get('nModified', 0)
                    if n_inserted > 0 or n_modified > 0:
                        logger.info(f"   ℹ️ 部分成功: 新增 {n_inserted} 条, 更新 {n_modified} 条")
                    return {
                        "inserted": n_inserted,
                        "updated": n_modified,
                        "errors": write_errors
                    }
            else:
                logger.warning(f"⚠️ 未生成任何题材统计数据")
                return {"inserted": 0, "updated": 0}
                
        except Exception as e:
            logger.exception(f"❌ 统计题材数据失败: {e}")
            return {"inserted": 0, "updated": 0, "error": str(e)}
    
    # ==================== 统一同步入口 ====================
    
    async def sync_all(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        同步所有开盘啦数据
        
        Args:
            trade_date: 交易日期（YYYYMMDD格式），为空则使用最新交易日
        
        Returns:
            同步结果统计
        """
        logger.info("🔄 开始同步所有开盘啦数据...")
        
        overall_stats = {
            "start_time": datetime.utcnow(),
            "concept": {},
            "concept_cons": {},
            "list": {},
            "total_duration": 0
        }
        
        # 同步题材库
        concept_stats = await self.sync_kpl_concept(trade_date)
        overall_stats["concept"] = concept_stats
        
        # 同步题材成分
        concept_cons_stats = await self.sync_kpl_concept_cons(trade_date)
        overall_stats["concept_cons"] = concept_cons_stats
        
        # 同步榜单数据
        list_stats = await self.sync_kpl_list(trade_date)
        overall_stats["list"] = list_stats
        
        overall_stats["end_time"] = datetime.utcnow()
        overall_stats["total_duration"] = (overall_stats["end_time"] - overall_stats["start_time"]).total_seconds()
        
        logger.info(f"✅ 所有开盘啦数据同步完成，总耗时: {overall_stats['total_duration']:.2f}秒")
        
        return overall_stats
    
    # ==================== 工具方法 ====================
    
    def _normalize_stock_code(self, code: str) -> str:
        """
        标准化股票代码为6位数字
        
        处理以下格式：
        - 000001.SZ -> 000001
        - 000001.SH -> 000001
        - 600001.SS -> 600001
        - 000001 -> 000001
        - 600001 -> 600001
        
        Args:
            code: 原始股票代码
        
        Returns:
            str: 标准化后的6位股票代码，如果无法提取则返回空字符串
        """
        if not code:
            return ""
        
        code_str = str(code).strip()
        
        # 如果包含点号，提取点号前的部分
        if "." in code_str:
            code_str = code_str.split(".")[0]
        
        # 提取所有数字字符
        code_digits = ''.join(filter(str.isdigit, code_str))
        
        if not code_digits:
            return ""
        
        # 如果是纯数字，补齐到6位
        if code_digits.isdigit():
            # 移除前导0，然后补齐到6位
            code_clean = code_digits.lstrip('0') or '0'
            return code_clean.zfill(6)
        
        return ""
    
    async def _get_latest_trade_date(self) -> str:
        """获取最新交易日"""
        try:
            # 使用Tushare API获取交易日历
            await self.rate_limiter.acquire()
            cal_df = await asyncio.to_thread(
                self.provider.api.trade_cal,
                exchange='SSE',
                start_date=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'),
                end_date=datetime.now().strftime('%Y%m%d'),
                is_open=1
            )
            
            if cal_df is not None and not cal_df.empty:
                # 获取最后一个交易日
                latest_date = cal_df.iloc[-1]['cal_date']
                return str(latest_date)
            
            # 如果获取失败，使用昨天作为默认值
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            logger.warning(f"⚠️ 无法获取最新交易日，使用默认值: {yesterday}")
            return yesterday
            
        except Exception as e:
            logger.warning(f"⚠️ 获取最新交易日失败: {e}，使用默认值")
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            return yesterday


# 单例模式
_kpl_sync_service: Optional[KPLSyncService] = None


async def get_kpl_sync_service() -> KPLSyncService:
    """获取开盘啦同步服务单例"""
    global _kpl_sync_service
    if _kpl_sync_service is None:
        _kpl_sync_service = KPLSyncService()
        await _kpl_sync_service.initialize()
    return _kpl_sync_service

