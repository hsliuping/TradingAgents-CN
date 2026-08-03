#!/usr/bin/env python3
"""
使用 AKShare 补充 BaoStock 同步的股票的行业信息

功能：
1. 查询 stock_basic_info 集合中 industry="未知" 的股票
2. 使用 AKShare 的 stock_individual_info_em 接口获取行业信息
3. 更新数据库中的 industry 和 area 字段

使用方法：
    python scripts/补充行业信息_akshare.py  # 默认仅安全预览
    python scripts/补充行业信息_akshare.py --execute
    python scripts/补充行业信息_akshare.py --execute --limit 100
    python scripts/补充行业信息_akshare.py --execute --batch-size 10
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import argparse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def positive_int(value: str) -> int:
    """解析必须大于 0 的整数参数。"""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return parsed


def non_negative_float(value: str) -> float:
    """解析必须大于等于 0 的浮点参数。"""
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("必须是大于等于 0 的数值")
    return parsed


async def get_stock_industry_from_akshare(code: str) -> Dict[str, str]:
    """
    使用 AKShare 获取股票的行业和地区信息
    
    Args:
        code: 6位股票代码
        
    Returns:
        包含 industry 和 area 的字典
    """
    try:
        import akshare as ak
        
        def fetch_info():
            return ak.stock_individual_info_em(symbol=code)
        
        # 异步执行
        stock_info = await asyncio.to_thread(fetch_info)
        
        if stock_info is None or stock_info.empty:
            return {"industry": "未知", "area": "未知"}
        
        result = {"industry": "未知", "area": "未知"}
        
        # 提取行业信息
        industry_row = stock_info[stock_info['item'] == '所属行业']
        if not industry_row.empty:
            result['industry'] = str(industry_row['value'].iloc[0])
        
        # 提取地区信息
        area_row = stock_info[stock_info['item'] == '所属地区']
        if not area_row.empty:
            result['area'] = str(area_row['value'].iloc[0])
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 获取 {code} 行业信息失败: {e}")
        return {"industry": "未知", "area": "未知"}


async def 补充行业信息(
    limit: int = None,
    batch_size: int = 50,
    delay: float = 0.5,
    execute: bool = False,
):
    """
    补充行业信息主函数
    
    Args:
        limit: 限制处理的股票数量（None=全部）
        batch_size: 每批处理的股票数量
        delay: 每只股票之间的延迟（秒），避免API限流
        execute: 是否显式允许连接MongoDB、访问AKShare并写入数据
    """
    logger.info("=" * 80)
    logger.info("🚀 开始补充行业信息")
    logger.info("=" * 80)

    if not execute:
        planned_limit = limit if limit is not None else "全部待补充记录"
        logger.info("DRY-RUN：不会访问AKShare、连接MongoDB或写入数据")
        logger.info(
            "计划参数: limit=%s, batch_size=%s, delay=%s秒",
            planned_limit,
            batch_size,
            delay,
        )
        logger.info(
            "计划动作: 查询缺失行业信息的股票，逐只读取AKShare并更新industry/area"
        )
        logger.info("实际动作: MongoDB连接=0, 网络请求=0, 数据库写入=0")
        logger.info("使用 --execute 显式允许上述真实动作")
        return {
            "mode": "DRY_RUN",
            "planned_limit": limit,
            "batch_size": batch_size,
            "delay": delay,
            "database_connections": 0,
            "writes": 0,
            "network_requests": 0,
        }
    
    # 连接 MongoDB
    logger.info(f"🔌 连接 MongoDB: {settings.MONGO_URI}")
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    collection = db["stock_basic_info"]
    
    try:
        # 1. 查询需要补充行业信息的股票
        query = {
            "$or": [
                {"industry": "未知"},
                {"industry": {"$exists": False}},
                {"industry": None},
                {"industry": ""}
            ]
        }
        
        total_count = await collection.count_documents(query)
        logger.info(f"📊 找到 {total_count} 只需要补充行业信息的股票")
        
        if total_count == 0:
            logger.info("✅ 所有股票都已有行业信息，无需补充")
            return
        
        # 限制处理数量
        if limit:
            logger.info(f"⚠️  限制处理数量: {limit}")
            total_count = min(total_count, limit)
        
        # 2. 批量处理
        cursor = collection.find(query, {"code": 1, "symbol": 1, "name": 1, "_id": 0})
        if limit:
            cursor = cursor.limit(limit)
        
        stocks = await cursor.to_list(length=None)
        
        logger.info(f"\n🔄 开始处理 {len(stocks)} 只股票...")
        logger.info(f"   批次大小: {batch_size}")
        logger.info(f"   延迟时间: {delay}秒/股票")
        logger.info("")
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i, stock in enumerate(stocks, 1):
            code = stock.get("code") or stock.get("symbol")
            name = stock.get("name", "")
            
            if not code:
                logger.warning(f"⚠️  [{i}/{len(stocks)}] 跳过: 缺少股票代码")
                skipped_count += 1
                continue
            
            try:
                # 获取行业信息
                logger.info(f"🔍 [{i}/{len(stocks)}] 获取 {code} ({name}) 的行业信息...")
                info = await get_stock_industry_from_akshare(code)
                
                if info["industry"] != "未知" or info["area"] != "未知":
                    # 更新数据库
                    update_data = {
                        "industry": info["industry"],
                        "area": info["area"],
                        "updated_at": datetime.utcnow()
                    }
                    
                    result = await collection.update_one(
                        {"$or": [{"code": code}, {"symbol": code}]},
                        {"$set": update_data}
                    )
                    
                    if result.modified_count > 0:
                        logger.info(f"   ✅ 更新成功: 行业={info['industry']}, 地区={info['area']}")
                        success_count += 1
                    else:
                        logger.warning(f"   ⚠️  未更新: 可能已存在相同数据")
                        skipped_count += 1
                else:
                    logger.warning(f"   ⚠️  未获取到有效信息")
                    failed_count += 1
                
                # 延迟，避免API限流
                if i < len(stocks):
                    await asyncio.sleep(delay)
                
                # 每批次输出进度
                if i % batch_size == 0:
                    logger.info(f"\n📈 进度: {i}/{len(stocks)} ({i*100//len(stocks)}%)")
                    logger.info(f"   成功: {success_count}, 失败: {failed_count}, 跳过: {skipped_count}\n")
                
            except Exception as e:
                logger.error(f"   ❌ 处理失败: {e}")
                failed_count += 1
        
        # 3. 输出统计
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 补充完成统计")
        logger.info("=" * 80)
        logger.info(f"   总计: {len(stocks)} 只股票")
        logger.info(f"   成功: {success_count} 只")
        logger.info(f"   失败: {failed_count} 只")
        logger.info(f"   跳过: {skipped_count} 只")
        logger.info(f"   成功率: {success_count*100//len(stocks) if len(stocks) > 0 else 0}%")
        logger.info("=" * 80)
        
        # 4. 验证结果
        remaining_count = await collection.count_documents(query)
        logger.info(f"\n✅ 剩余需要补充的股票: {remaining_count} 只")
        
        if remaining_count > 0:
            logger.info(f"💡 提示: 可以再次运行此脚本继续补充")
        else:
            logger.info(f"🎉 所有股票的行业信息已补充完成！")
        
    finally:
        client.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="使用 AKShare 补充股票行业信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 安全预览：不联网、不连接MongoDB、不写入数据
  python scripts/补充行业信息_akshare.py

  # 补充所有股票的行业信息
  python scripts/补充行业信息_akshare.py --execute

  # 只处理前100只股票
  python scripts/补充行业信息_akshare.py --execute --limit 100

  # 调整批次大小和延迟
  python scripts/补充行业信息_akshare.py --execute --batch-size 10 --delay 1.0
        """
    )
    
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="限制处理的股票数量（默认：全部）"
    )
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=50,
        help="每批处理的股票数量（默认：50）"
    )
    parser.add_argument(
        "--delay",
        type=non_negative_float,
        default=0.5,
        help="每只股票之间的延迟（秒）（默认：0.5）"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="显式允许访问AKShare并更新数据库；默认仅dry-run",
    )
    
    args = parser.parse_args()
    
    # 运行异步任务
    asyncio.run(补充行业信息(
        limit=args.limit,
        batch_size=args.batch_size,
        delay=args.delay,
        execute=args.execute,
    ))


if __name__ == "__main__":
    main()
