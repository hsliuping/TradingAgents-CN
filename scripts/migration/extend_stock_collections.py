#!/usr/bin/env python3
"""
⚠️ 已废弃 - 请勿使用此脚本 ⚠️

此脚本已被废弃，因为它创建了与多数据源架构冲突的 full_symbol 唯一索引。

新的多数据源架构使用 (code, source) 联合唯一索引，允许同一股票有多个数据源的记录。

如需初始化数据库索引，请使用：
- scripts/setup/init_mongodb_indexes.py
- scripts/migrations/migrate_stock_basic_info_add_source_index.py

---

原功能（已废弃）:
1. 为现有 stock_basic_info 集合添加标准化字段
2. 为现有 market_quotes 集合添加标准化字段
3. 创建新的索引以支持多市场查询
4. 数据验证和完整性检查
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockCollectionExtender:
    """股票集合字段扩展器"""
    
    def __init__(self):
        self.client = None
        self.db = None
        
    async def connect(self):
        """连接MongoDB"""
        try:
            self.client = AsyncIOMotorClient(settings.MONGO_URI)
            self.db = self.client[settings.MONGO_DB]
            
            # 测试连接
            await self.client.admin.command('ping')
            logger.info(f"✅ 连接MongoDB成功: {settings.MONGO_DB}")
            
        except Exception as e:
            logger.error(f"❌ 连接MongoDB失败: {e}")
            raise
    
    async def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
    
    async def extend_stock_basic_info(self):
        """扩展 stock_basic_info 集合字段"""
        logger.info("🔄 开始扩展 stock_basic_info 集合...")
        
        collection = self.db.stock_basic_info
        
        # 统计现有记录
        total_count = await collection.count_documents({})
        logger.info(f"📊 现有记录数: {total_count}")
        
        if total_count == 0:
            logger.warning("⚠️ 集合为空，跳过扩展")
            return
        
        # 批量更新记录
        updated_count = 0
        batch_size = 1000
        
        async for doc in collection.find({}):
            try:
                code = doc.get("code", "")
                if not code or len(code) != 6:
                    continue
                
                # 准备扩展字段
                update_fields = self._prepare_basic_info_extensions(doc)
                
                if update_fields:
                    await collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": update_fields}
                    )
                    updated_count += 1
                    
                    if updated_count % batch_size == 0:
                        logger.info(f"📈 已更新 {updated_count}/{total_count} 条记录")
                        
            except Exception as e:
                logger.error(f"❌ 更新记录失败 {doc.get('code', 'N/A')}: {e}")
                continue
        
        logger.info(f"✅ stock_basic_info 扩展完成，共更新 {updated_count} 条记录")
    
    async def extend_market_quotes(self):
        """扩展 market_quotes 集合字段"""
        logger.info("🔄 开始扩展 market_quotes 集合...")
        
        collection = self.db.market_quotes
        
        # 统计现有记录
        total_count = await collection.count_documents({})
        logger.info(f"📊 现有记录数: {total_count}")
        
        if total_count == 0:
            logger.warning("⚠️ 集合为空，跳过扩展")
            return
        
        # 批量更新记录
        updated_count = 0
        batch_size = 1000
        
        async for doc in collection.find({}):
            try:
                code = doc.get("code", "")
                if not code or len(code) != 6:
                    continue
                
                # 准备扩展字段
                update_fields = self._prepare_quotes_extensions(doc)
                
                if update_fields:
                    await collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": update_fields}
                    )
                    updated_count += 1
                    
                    if updated_count % batch_size == 0:
                        logger.info(f"📈 已更新 {updated_count}/{total_count} 条记录")
                        
            except Exception as e:
                logger.error(f"❌ 更新记录失败 {doc.get('code', 'N/A')}: {e}")
                continue
        
        logger.info(f"✅ market_quotes 扩展完成，共更新 {updated_count} 条记录")
    
    async def create_extended_indexes(self):
        """创建扩展索引"""
        logger.info("🔄 创建扩展索引...")
        
        try:
            # stock_basic_info 扩展索引
            basic_collection = self.db.stock_basic_info
            
            # 标准化字段索引
            await basic_collection.create_index("symbol")
            await basic_collection.create_index("full_symbol", unique=True)
            await basic_collection.create_index("market_info.market")
            await basic_collection.create_index("market_info.exchange")
            await basic_collection.create_index([("market_info.market", 1), ("status", 1)])
            
            logger.info("✅ stock_basic_info 扩展索引创建完成")
            
            # market_quotes 扩展索引
            quotes_collection = self.db.market_quotes
            
            await quotes_collection.create_index("symbol")
            await quotes_collection.create_index("full_symbol")
            await quotes_collection.create_index("market")
            await quotes_collection.create_index([("market", 1), ("updated_at", -1)])
            
            logger.info("✅ market_quotes 扩展索引创建完成")
            
        except Exception as e:
            logger.error(f"❌ 创建索引失败: {e}")
            raise
    
    async def validate_extensions(self):
        """验证扩展结果"""
        logger.info("🔍 验证扩展结果...")
        
        # 验证 stock_basic_info
        basic_collection = self.db.stock_basic_info
        
        total_basic = await basic_collection.count_documents({})
        with_symbol = await basic_collection.count_documents({"symbol": {"$exists": True}})
        with_full_symbol = await basic_collection.count_documents({"full_symbol": {"$exists": True}})
        with_market_info = await basic_collection.count_documents({"market_info": {"$exists": True}})
        
        logger.info(f"📊 stock_basic_info 验证结果:")
        logger.info(f"   总记录数: {total_basic}")
        logger.info(f"   有symbol字段: {with_symbol} ({with_symbol/total_basic*100:.1f}%)")
        logger.info(f"   有full_symbol字段: {with_full_symbol} ({with_full_symbol/total_basic*100:.1f}%)")
        logger.info(f"   有market_info字段: {with_market_info} ({with_market_info/total_basic*100:.1f}%)")
        
        # 验证 market_quotes
        quotes_collection = self.db.market_quotes
        
        total_quotes = await quotes_collection.count_documents({})
        if total_quotes > 0:
            with_symbol_q = await quotes_collection.count_documents({"symbol": {"$exists": True}})
            with_full_symbol_q = await quotes_collection.count_documents({"full_symbol": {"$exists": True}})
            with_market_q = await quotes_collection.count_documents({"market": {"$exists": True}})
            
            logger.info(f"📊 market_quotes 验证结果:")
            logger.info(f"   总记录数: {total_quotes}")
            logger.info(f"   有symbol字段: {with_symbol_q} ({with_symbol_q/total_quotes*100:.1f}%)")
            logger.info(f"   有full_symbol字段: {with_full_symbol_q} ({with_full_symbol_q/total_quotes*100:.1f}%)")
            logger.info(f"   有market字段: {with_market_q} ({with_market_q/total_quotes*100:.1f}%)")
        else:
            logger.info("📊 market_quotes 集合为空")
    
    def _prepare_basic_info_extensions(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """准备基础信息扩展字段"""
        code = doc.get("code", "")
        if not code or len(code) != 6:
            return {}
        
        extensions = {}
        
        # 标准化字段
        extensions["symbol"] = code
        
        # 生成完整代码和市场信息
        if code.startswith(('60', '68', '90')):
            extensions["full_symbol"] = f"{code}.SS"
            exchange = "SSE"
            exchange_name = "上海证券交易所"
        elif code.startswith(('00', '30', '20')):
            extensions["full_symbol"] = f"{code}.SZ"
            exchange = "SZSE"
            exchange_name = "深圳证券交易所"
        else:
            extensions["full_symbol"] = f"{code}.SZ"
            exchange = "SZSE"
            exchange_name = "深圳证券交易所"
        
        # 市场信息
        extensions["market_info"] = {
            "market": "CN",
            "exchange": exchange,
            "exchange_name": exchange_name,
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
            "trading_hours": {
                "open": "09:30",
                "close": "15:00",
                "lunch_break": ["11:30", "13:00"]
            }
        }
        
        # 其他标准化字段
        extensions["board"] = doc.get("sse")
        extensions["sector"] = doc.get("sec")
        extensions["status"] = "L"  # 默认上市状态
        extensions["data_version"] = 1
        extensions["extended_at"] = datetime.utcnow()
        
        return extensions
    
    def _prepare_quotes_extensions(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """准备行情扩展字段"""
        code = doc.get("code", "")
        if not code or len(code) != 6:
            return {}
        
        extensions = {}
        
        # 标准化字段
        extensions["symbol"] = code
        
        # 生成完整代码
        if code.startswith(('60', '68', '90')):
            extensions["full_symbol"] = f"{code}.SS"
        else:
            extensions["full_symbol"] = f"{code}.SZ"
        
        extensions["market"] = "CN"
        
        # 字段映射
        extensions["current_price"] = doc.get("close")
        
        # 计算涨跌额
        if doc.get("close") and doc.get("pre_close"):
            try:
                extensions["change"] = float(doc["close"]) - float(doc["pre_close"])
            except (ValueError, TypeError):
                extensions["change"] = None
        
        extensions["data_source"] = "market_quotes"
        extensions["data_version"] = 1
        extensions["extended_at"] = datetime.utcnow()
        
        return extensions


async def main():
    """主函数"""
    logger.error("=" * 80)
    logger.error("⚠️  此脚本已废弃，请勿使用！")
    logger.error("=" * 80)
    logger.error("")
    logger.error("原因：此脚本创建的 full_symbol 唯一索引与多数据源架构冲突")
    logger.error("")
    logger.error("请使用以下脚本代替：")
    logger.error("  - scripts/setup/init_mongodb_indexes.py")
    logger.error("  - scripts/migrations/migrate_stock_basic_info_add_source_index.py")
    logger.error("")
    logger.error("=" * 80)
    sys.exit(1)

    # 以下代码已废弃，不会执行
    logger.info("🚀 开始股票数据集合字段扩展...")

    extender = StockCollectionExtender()
    
    try:
        # 连接数据库
        await extender.connect()
        
        # 扩展集合字段
        await extender.extend_stock_basic_info()
        await extender.extend_market_quotes()
        
        # 创建扩展索引
        await extender.create_extended_indexes()
        
        # 验证扩展结果
        await extender.validate_extensions()
        
        logger.info("🎉 股票数据集合字段扩展完成！")
        
    except Exception as e:
        logger.error(f"❌ 扩展过程失败: {e}")
        sys.exit(1)
        
    finally:
        await extender.close()


if __name__ == "__main__":
    asyncio.run(main())
