#!/usr/bin/env python3
"""
数据验证服务测试程序

用于测试和验证 DataValidationService 的功能，检查数据完整性检查服务是否正常工作。

使用方法:
    python scripts/test_data_validation_service.py [股票代码] [分析日期]
    
示例:
    python scripts/test_data_validation_service.py 000001 2025-01-24
    python scripts/test_data_validation_service.py 600519  # 使用当前日期
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量（如果需要）
if not os.getenv("MONGO_URI"):
    try:
        from dotenv import load_dotenv
        load_dotenv(project_root / ".env")
    except ImportError:
        # dotenv 未安装，尝试直接读取 .env 文件
        env_file = project_root / ".env"
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

import logging
from app.services.data_validation_service import get_data_validation_service, DataValidationResult
from app.core.database import init_database, get_mongo_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DataValidationTester:
    """数据验证服务测试器"""
    
    def __init__(self):
        self.validation_service = get_data_validation_service()
        self.db = None
    
    async def setup(self):
        """初始化数据库连接"""
        logger.info("🔄 正在初始化数据库连接...")
        try:
            await init_database()
            self.db = get_mongo_db()
            logger.info("✅ 数据库连接成功")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise
    
    async def test_basic_info_check(
        self,
        symbol: str,
        market_type: str = "cn"
    ) -> DataValidationResult:
        """测试基础信息检查"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 测试1: 基础信息检查")
        logger.info(f"{'='*60}")
        logger.info(f"股票代码: {symbol}")
        logger.info(f"市场类型: {market_type}")
        
        result = await self.validation_service.validate_stock_data(
            symbol=symbol,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            market_type=market_type,
            check_basic_info=True,
            check_historical_data=False,
            check_financial_data=False,
            check_realtime_quotes=False
        )
        
        self._print_result(result, "基础信息")
        return result
    
    async def test_historical_data_check(
        self,
        symbol: str,
        analysis_date: str,
        market_type: str = "cn",
        historical_days: int = 365
    ) -> DataValidationResult:
        """测试历史数据检查"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 测试2: 历史数据检查")
        logger.info(f"{'='*60}")
        logger.info(f"股票代码: {symbol}")
        logger.info(f"分析日期: {analysis_date}")
        logger.info(f"市场类型: {market_type}")
        logger.info(f"检查天数: {historical_days} 天")
        
        result = await self.validation_service.validate_stock_data(
            symbol=symbol,
            analysis_date=analysis_date,
            market_type=market_type,
            check_basic_info=True,
            check_historical_data=True,
            check_financial_data=False,
            check_realtime_quotes=False,
            historical_days=historical_days
        )
        
        self._print_result(result, "历史数据")
        
        # 打印详细信息
        if "historical_data" in result.details:
            hist_details = result.details["historical_data"]
            logger.info(f"\n📊 历史数据详情:")
            logger.info(f"  - 数据存在: {hist_details.get('exists', 'N/A')}")
            logger.info(f"  - 数据条数: {hist_details.get('count', 'N/A')}")
            logger.info(f"  - 最早日期: {hist_details.get('earliest_date', 'N/A')}")
            logger.info(f"  - 最晚日期: {hist_details.get('latest_date', 'N/A')}")
            analysis_date_exists = hist_details.get('analysis_date_exists', False)
            logger.info(f"  - 分析日期数据存在: {analysis_date_exists}")
            if not analysis_date_exists:
                logger.warning(f"  ⚠️  警告: 分析日期（{analysis_date}）当天的数据不存在！")
                if hist_details.get('latest_date'):
                    logger.warning(f"     最新数据日期: {hist_details.get('latest_date')}")
            logger.info(f"  - 日期范围: {hist_details.get('date_range', 'N/A')}")
            if "collections_checked" in hist_details:
                logger.info(f"  - 检查的集合: {hist_details['collections_checked']}")
            if hist_details.get('warning'):
                logger.warning(f"  ⚠️  数据完整性警告: 分析日期当天的数据不存在")
        
        return result
    
    async def test_financial_data_check(
        self,
        symbol: str,
        analysis_date: str,
        market_type: str = "cn"
    ) -> DataValidationResult:
        """测试财务数据检查"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 测试3: 财务数据检查")
        logger.info(f"{'='*60}")
        logger.info(f"股票代码: {symbol}")
        logger.info(f"分析日期: {analysis_date}")
        logger.info(f"市场类型: {market_type}")
        
        result = await self.validation_service.validate_stock_data(
            symbol=symbol,
            analysis_date=analysis_date,
            market_type=market_type,
            check_basic_info=True,
            check_historical_data=False,
            check_financial_data=True,
            check_realtime_quotes=False
        )
        
        self._print_result(result, "财务数据")
        
        # 打印详细信息
        if "financial_data" in result.details:
            fin_details = result.details["financial_data"]
            logger.info(f"\n📊 财务数据详情:")
            logger.info(f"  - 数据存在: {fin_details.get('exists', 'N/A')}")
            if fin_details.get('exists'):
                logger.info(f"  - 最新报告期: {fin_details.get('latest_report_period', 'N/A')}")
                logger.info(f"  - 报告类型: {fin_details.get('report_type', 'N/A')}")
        
        return result
    
    async def test_realtime_quotes_check(
        self,
        symbol: str,
        market_type: str = "cn"
    ) -> DataValidationResult:
        """测试实时行情检查"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 测试4: 实时行情检查")
        logger.info(f"{'='*60}")
        logger.info(f"股票代码: {symbol}")
        logger.info(f"市场类型: {market_type}")
        
        result = await self.validation_service.validate_stock_data(
            symbol=symbol,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            market_type=market_type,
            check_basic_info=True,
            check_historical_data=False,
            check_financial_data=False,
            check_realtime_quotes=True
        )
        
        self._print_result(result, "实时行情")
        
        # 打印详细信息
        if "realtime_quotes" in result.details:
            quote_details = result.details["realtime_quotes"]
            logger.info(f"\n📊 实时行情详情:")
            logger.info(f"  - 数据存在: {quote_details.get('exists', 'N/A')}")
            if quote_details.get('exists'):
                logger.info(f"  - 当前价格: {quote_details.get('current_price', 'N/A')}")
                logger.info(f"  - 更新时间: {quote_details.get('update_time', 'N/A')}")
        
        return result
    
    async def test_full_validation(
        self,
        symbol: str,
        analysis_date: str,
        market_type: str = "cn",
        historical_days: int = 365
    ) -> DataValidationResult:
        """测试完整验证（所有检查项）"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 测试5: 完整数据验证（所有检查项）")
        logger.info(f"{'='*60}")
        logger.info(f"股票代码: {symbol}")
        logger.info(f"分析日期: {analysis_date}")
        logger.info(f"市场类型: {market_type}")
        logger.info(f"历史数据天数: {historical_days}")
        
        result = await self.validation_service.validate_stock_data(
            symbol=symbol,
            analysis_date=analysis_date,
            market_type=market_type,
            check_basic_info=True,
            check_historical_data=True,
            check_financial_data=True,
            check_realtime_quotes=True,
            historical_days=historical_days
        )
        
        self._print_result(result, "完整验证")
        self._print_all_details(result)
        
        return result
    
    async def test_multiple_stocks(
        self,
        symbols: list[str],
        analysis_date: str,
        market_type: str = "cn"
    ):
        """测试多个股票的数据验证"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 测试6: 批量股票验证")
        logger.info(f"{'='*60}")
        logger.info(f"股票列表: {', '.join(symbols)}")
        logger.info(f"分析日期: {analysis_date}")
        
        results = []
        for symbol in symbols:
            logger.info(f"\n--- 验证股票: {symbol} ---")
            result = await self.validation_service.validate_stock_data(
                symbol=symbol,
                analysis_date=analysis_date,
                market_type=market_type,
                check_basic_info=True,
                check_historical_data=True,
                check_financial_data=False,
                check_realtime_quotes=False,
                historical_days=365
            )
            results.append((symbol, result))
            self._print_result(result, f"股票 {symbol}")
        
        # 统计结果
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 批量验证统计")
        logger.info(f"{'='*60}")
        valid_count = sum(1 for _, r in results if r.is_valid)
        total_count = len(results)
        logger.info(f"总计: {total_count} 个股票")
        logger.info(f"验证通过: {valid_count} 个")
        logger.info(f"验证失败: {total_count - valid_count} 个")
        
        # 列出失败的股票
        failed_stocks = [symbol for symbol, r in results if not r.is_valid]
        if failed_stocks:
            logger.info(f"\n❌ 验证失败的股票:")
            for symbol in failed_stocks:
                result = next(r for s, r in results if s == symbol)
                logger.info(f"  - {symbol}: {result.message}")
        
        return results
    
    def _print_result(self, result: DataValidationResult, test_name: str):
        """打印验证结果"""
        status = "✅ 通过" if result.is_valid else "❌ 失败"
        logger.info(f"\n{status} [{test_name}]")
        logger.info(f"消息: {result.message}")
        
        # 检查是否有警告
        if result.is_valid:
            has_warning = False
            if "historical_data" in result.details:
                hist_details = result.details["historical_data"]
                if hist_details.get("warning") or not hist_details.get("analysis_date_exists", True):
                    has_warning = True
            if has_warning:
                logger.warning("⚠️  注意: 验证通过但存在警告，请查看详细信息")
        
        if result.missing_data:
            logger.info(f"缺失数据: {', '.join(result.missing_data)}")
    
    def _print_all_details(self, result: DataValidationResult):
        """打印所有详细信息"""
        logger.info(f"\n📋 详细信息:")
        for key, value in result.details.items():
            # 使用 json.dumps 格式化字典，确保正确显示
            if isinstance(value, dict):
                logger.info(f"  {key}: {json.dumps(value, ensure_ascii=False, indent=2)}")
            else:
                logger.info(f"  {key}: {value}")
    
    async def inspect_database_collections(self, symbol: str, market_type: str = "cn"):
        """检查数据库中实际存在的数据"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 数据库数据检查")
        logger.info(f"{'='*60}")
        logger.info(f"股票代码: {symbol}")
        logger.info(f"市场类型: {market_type}")
        
        if self.db is None:
            logger.error("数据库未初始化")
            return
        
        symbol6 = str(symbol).zfill(6)
        
        # 检查基础信息集合
        collections_to_check = {
            "cn": {
                "basic_info": "stock_basic_info",
                "historical": ["stock_daily_quotes", "stock_daily_history"],
                "financial": "stock_financial_data",
                "quotes": "market_quotes"
            },
            "hk": {
                "basic_info": "stock_basic_info_hk",
                "historical": ["stock_daily_quotes_hk"],
                "financial": "stock_financial_data_hk",
                "quotes": "market_quotes_hk"
            },
            "us": {
                "basic_info": "stock_basic_info_us",
                "historical": ["stock_daily_quotes_us"],
                "financial": "stock_financial_data_us",
                "quotes": "market_quotes_us"
            }
        }
        
        config = collections_to_check.get(market_type, collections_to_check["cn"])
        
        # 检查基础信息
        logger.info(f"\n1. 基础信息 ({config['basic_info']}):")
        basic_doc = await self.db[config['basic_info']].find_one(
            {"$or": [{"symbol": symbol6}, {"code": symbol6}]},
            {"_id": 0, "symbol": 1, "code": 1, "name": 1, "list_date": 1}
        )
        if basic_doc:
            logger.info(f"   ✅ 存在: {basic_doc}")
        else:
            logger.info(f"   ❌ 不存在")
        
        # 检查历史数据
        logger.info(f"\n2. 历史数据:")
        for coll_name in config['historical']:
            collection_names = await self.db.list_collection_names()
            if coll_name not in collection_names:
                logger.info(f"   ⚠️  集合 {coll_name} 不存在")
                continue
            
            count = await self.db[coll_name].count_documents({
                "$or": [{"symbol": symbol6}, {"code": symbol6}]
            })
            if count > 0:
                # 获取日期范围
                earliest = await self.db[coll_name].find_one(
                    {"$or": [{"symbol": symbol6}, {"code": symbol6}]},
                    sort=[("trade_date", 1)]
                )
                latest = await self.db[coll_name].find_one(
                    {"$or": [{"symbol": symbol6}, {"code": symbol6}]},
                    sort=[("trade_date", -1)]
                )
                logger.info(f"   ✅ {coll_name}: {count} 条记录")
                if earliest:
                    logger.info(f"      最早日期: {earliest.get('trade_date')}")
                if latest:
                    logger.info(f"      最晚日期: {latest.get('trade_date')}")
            else:
                logger.info(f"   ❌ {coll_name}: 无数据")
        
        # 检查财务数据
        logger.info(f"\n3. 财务数据 ({config['financial']}):")
        collection_names = await self.db.list_collection_names()
        if config['financial'] not in collection_names:
            logger.info(f"   ⚠️  集合 {config['financial']} 不存在")
        else:
            count = await self.db[config['financial']].count_documents({
                "$or": [{"symbol": symbol6}, {"code": symbol6}]
            })
            if count > 0:
                latest_fin = await self.db[config['financial']].find_one(
                    {"$or": [{"symbol": symbol6}, {"code": symbol6}]},
                    sort=[("report_period", -1)],
                    projection={"_id": 0, "report_period": 1, "report_type": 1}
                )
                logger.info(f"   ✅ {count} 条记录")
                if latest_fin:
                    logger.info(f"      最新报告期: {latest_fin.get('report_period')}")
            else:
                logger.info(f"   ❌ 无数据")
        
        # 检查实时行情
        logger.info(f"\n4. 实时行情 ({config['quotes']}):")
        collection_names = await self.db.list_collection_names()
        if config['quotes'] not in collection_names:
            logger.info(f"   ⚠️  集合 {config['quotes']} 不存在")
        else:
            quote_doc = await self.db[config['quotes']].find_one(
                {"$or": [{"symbol": symbol6}, {"code": symbol6}]},
                {"_id": 0, "symbol": 1, "code": 1, "close": 1, "update_time": 1}
            )
            if quote_doc:
                logger.info(f"   ✅ 存在: {quote_doc}")
            else:
                logger.info(f"   ❌ 不存在")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="数据验证服务测试程序")
    parser.add_argument("symbol", nargs="?", help="股票代码（如：000001）")
    parser.add_argument("date", nargs="?", help="分析日期（YYYY-MM-DD格式，默认为今天）")
    parser.add_argument("--market", default="cn", choices=["cn", "hk", "us"], help="市场类型（默认：cn）")
    parser.add_argument("--days", type=int, default=365, help="历史数据检查天数（默认：365）")
    parser.add_argument("--test-all", action="store_true", help="运行所有测试")
    parser.add_argument("--batch", nargs="+", help="批量测试多个股票代码")
    parser.add_argument("--inspect", action="store_true", help="检查数据库中的实际数据")
    
    args = parser.parse_args()
    
    # 如果没有提供股票代码，使用默认值
    if not args.symbol and not args.batch:
        logger.warning("⚠️  未提供股票代码，使用默认测试股票: 000001")
        args.symbol = "000001"
    
    # 如果没有提供日期，使用今天
    analysis_date = args.date or datetime.now().strftime('%Y-%m-%d')
    
    tester = DataValidationTester()
    
    try:
        await tester.setup()
        
        if args.batch:
            # 批量测试
            await tester.test_multiple_stocks(args.batch, analysis_date, args.market)
        elif args.test_all:
            # 运行所有测试
            symbol = args.symbol
            logger.info(f"\n{'='*80}")
            logger.info(f"🚀 开始完整测试套件")
            logger.info(f"{'='*80}")
            
            await tester.test_basic_info_check(symbol, args.market)
            await tester.test_historical_data_check(symbol, analysis_date, args.market, args.days)
            await tester.test_financial_data_check(symbol, analysis_date, args.market)
            await tester.test_realtime_quotes_check(symbol, args.market)
            await tester.test_full_validation(symbol, analysis_date, args.market, args.days)
            
            if args.inspect:
                await tester.inspect_database_collections(symbol, args.market)
        else:
            # 单个股票测试
            symbol = args.symbol
            logger.info(f"\n{'='*80}")
            logger.info(f"🚀 开始数据验证测试")
            logger.info(f"{'='*80}")
            
            # 运行完整验证
            await tester.test_full_validation(symbol, analysis_date, args.market, args.days)
            
            if args.inspect:
                await tester.inspect_database_collections(symbol, args.market)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ 测试完成")
        logger.info(f"{'='*80}")
        
    except Exception as e:
        logger.error(f"❌ 测试过程中出错: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
