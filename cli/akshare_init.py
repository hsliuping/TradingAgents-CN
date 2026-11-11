#!/usr/bin/env python3
"""
AKShare数据初始化CLI工具
用于首次部署时的数据初始化和管理
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
import os

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_database, get_mongo_db, close_database
from app.worker.akshare_init_service import get_akshare_init_service
from app.worker.akshare_sync_service import get_akshare_sync_service

# 配置日志（共享初始化函数，日志治理 §5.3）
os.makedirs(os.path.join('data', 'logs'), exist_ok=True)
from core.utils.logging_setup import setup_cli_logging
setup_cli_logging(
    "INFO",
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_file=os.path.join('data', 'logs', 'akshare_init.log'),
)
logger = logging.getLogger(__name__)


async def check_database_status():
    """检查数据库状态"""
    print("=" * 50)
    print("📊 检查数据库状态...")
    
    try:
        db = get_mongo_db()
        
        # 检查基础信息
        basic_count = await db.stock_basic_info.count_documents({})
        extended_count = await db.stock_basic_info.count_documents({
            "full_symbol": {"$exists": True},
            "market_info": {"$exists": True}
        })
        
        # 获取最新更新时间
        latest_basic = await db.stock_basic_info.find_one(
            {}, sort=[("updated_at", -1)]
        )
        
        print(f"  📋 股票基础信息: {basic_count:,}条")
        if basic_count > 0:
            print(f"     扩展字段覆盖: {extended_count:,}条 ({extended_count/basic_count*100:.1f}%)")
            if latest_basic and latest_basic.get("updated_at"):
                print(f"     最新更新: {latest_basic['updated_at']}")
        
        # 检查行情数据
        quotes_count = await db.market_quotes.count_documents({})
        latest_quotes = await db.market_quotes.find_one(
            {}, sort=[("updated_at", -1)]
        )
        
        print(f"  📈 行情数据: {quotes_count:,}条")
        if quotes_count > 0 and latest_quotes and latest_quotes.get("updated_at"):
            print(f"     最新更新: {latest_quotes['updated_at']}")
        
        # 数据状态评估
        if basic_count == 0:
            print("  ❌ 数据库为空，需要运行完整初始化")
            return False
        elif extended_count / basic_count < 0.5:
            print("  ⚠️ 扩展字段覆盖率较低，建议重新初始化")
            return False
        else:
            print("  ✅ 数据库状态良好")
            return True
            
    except Exception as e:
        print(f"  ❌ 检查数据库状态失败: {e}")
        return False
    finally:
        print("📋 数据库状态检查完成")


async def run_full_initialization(
    historical_days: int,
    force: bool = False,
    multi_period: bool = False,
    sync_items: list = None
):
    """运行完整初始化"""
    print("=" * 50)
    print("🚀 开始AKShare数据完整初始化...")
    print(f"📅 历史数据范围: {historical_days}天")
    print(f"🔄 强制模式: {'是' if force else '否'}")
    if sync_items:
        print(f"📋 同步项目: {', '.join(sync_items)}")
    elif multi_period:
        print(f"📊 多周期模式: 日线、周线、月线")

    try:
        service = await get_akshare_init_service()

        result = await service.run_full_initialization(
            historical_days=historical_days,
            skip_if_exists=not force,
            enable_multi_period=multi_period,
            sync_items=sync_items
        )
        
        print("\n" + "=" * 50)
        print("📊 初始化结果统计:")
        print(f"  ✅ 成功: {'是' if result['success'] else '否'}")
        print(f"  ⏱️ 耗时: {result['duration']:.2f}秒")
        print(f"  📈 进度: {result['progress']}")
        
        data_summary = result.get('data_summary', {})
        print(f"  📋 基础信息: {data_summary.get('basic_info_count', 0):,}条")
        print(f"  📊 历史数据: {data_summary.get('daily_records', 0):,}条")
        if multi_period:
            print(f"     - 日线数据: {data_summary.get('daily_records', 0):,}条")
            print(f"     - 周线数据: {data_summary.get('weekly_records', 0):,}条")
            print(f"     - 月线数据: {data_summary.get('monthly_records', 0):,}条")
        print(f"  💰 财务数据: {data_summary.get('financial_records', 0):,}条")
        print(f"  📈 行情数据: {data_summary.get('quotes_count', 0):,}条")
        print(f"  📰 新闻数据: {data_summary.get('news_count', 0):,}条")
        
        if result.get('errors'):
            print(f"  ⚠️ 错误数量: {len(result['errors'])}")
            for error in result['errors'][:3]:  # 只显示前3个错误
                print(f"     - {error.get('step', 'Unknown')}: {error.get('error', 'Unknown error')}")
        
        return result['success']
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False


async def run_basic_sync_only():
    """仅运行基础信息同步"""
    print("=" * 50)
    print("📋 开始基础信息同步...")
    
    try:
        service = await get_akshare_sync_service()
        result = await service.sync_stock_basic_info(force_update=True)
        
        print(f"✅ 基础信息同步完成:")
        print(f"  📊 处理总数: {result.get('total_processed', 0):,}")
        print(f"  ✅ 成功数量: {result.get('success_count', 0):,}")
        print(f"  ❌ 错误数量: {result.get('error_count', 0):,}")
        print(f"  ⏱️ 耗时: {result.get('duration', 0):.2f}秒")
        
        return result.get('success_count', 0) > 0
        
    except Exception as e:
        print(f"❌ 基础信息同步失败: {e}")
        return False


async def test_akshare_connection():
    """测试AKShare连接"""
    print("=" * 50)
    print("🔗 测试AKShare连接...")
    
    try:
        service = await get_akshare_sync_service()
        connected = await service.provider.test_connection()
        
        if connected:
            print("✅ AKShare连接成功")
            
            # 测试获取股票列表
            stock_list = await service.provider.get_stock_list()
            if stock_list:
                print(f"📋 获取股票列表成功: {len(stock_list)}只股票")
                
                # 显示前5只股票
                print("  前5只股票:")
                for i, stock in enumerate(stock_list[:5]):
                    print(f"    {i+1}. {stock.get('code')} - {stock.get('name')}")
            else:
                print("⚠️ 获取股票列表失败")
                
            return True
        else:
            print("❌ AKShare连接失败")
            return False
            
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False


def print_help_detail():
    """打印详细帮助信息"""
    help_text = """
🔧 AKShare数据初始化工具详细说明

📋 主要功能:
  --check-only        仅检查数据库状态，不执行任何操作
  --test-connection   测试AKShare连接状态
  --basic-only        仅同步股票基础信息
  --full              运行完整的数据初始化流程
  
🔄 完整初始化流程包括:
  1. 检查数据库状态
  2. 同步股票基础信息
  3. 同步历史数据（可配置天数）
  4. 同步财务数据
  5. 同步最新行情数据
  6. 验证数据完整性

⚙️ 配置选项:
  --historical-days   历史数据天数 (默认365天)
  --force            强制重新初始化，忽略已有数据
  
📝 使用示例:
  # 检查数据库状态
  python cli/akshare_init.py --check-only

  # 测试连接
  python cli/akshare_init.py --test-connection

  # 仅同步基础信息
  python cli/akshare_init.py --basic-only

  # 完整初始化（推荐首次部署，默认1年历史数据）
  python cli/akshare_init.py --full

  # 自定义历史数据范围（6个月）
  python cli/akshare_init.py --full --historical-days 180

  # 全历史数据初始化（从1990年至今，需要>=3650天）
  python cli/akshare_init.py --full --historical-days 10000

  # 全历史多周期初始化（推荐用于生产环境）
  python cli/akshare_init.py --full --multi-period --historical-days 10000

  # 强制重新初始化
  python cli/akshare_init.py --full --force

📊 日志文件:
  所有操作日志会保存到 akshare_init.log 文件中
  
⚠️ 注意事项:
  - 首次初始化可能需要较长时间（30分钟-2小时）
  - 建议在网络状况良好时运行
  - AKShare有API调用频率限制，请耐心等待
  - 可以随时按Ctrl+C中断操作
"""
    print(help_text)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AKShare数据初始化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 操作选项
    parser.add_argument("--check-only", action="store_true", help="仅检查数据库状态")
    parser.add_argument("--test-connection", action="store_true", help="测试AKShare连接")
    parser.add_argument("--basic-only", action="store_true", help="仅同步基础信息")
    parser.add_argument("--full", action="store_true", help="运行完整初始化")
    
    # 配置选项
    parser.add_argument("--historical-days", type=int, default=365, help="历史数据天数（默认365）")
    parser.add_argument("--multi-period", action="store_true", help="同步多周期数据（日线、周线、月线）")
    parser.add_argument("--sync-items", type=str, help="指定要同步的数据类型（逗号分隔），可选: basic_info,historical,weekly,monthly,financial,quotes,news")
    parser.add_argument("--force", action="store_true", help="强制重新初始化")
    parser.add_argument("--help-detail", action="store_true", help="显示详细帮助信息")
    
    args = parser.parse_args()
    
    # 显示详细帮助
    if args.help_detail:
        print_help_detail()
        return
    
    # 如果没有指定任何操作，显示帮助
    if not any([args.check_only, args.test_connection, args.basic_only, args.full]):
        parser.print_help()
        print("\n💡 使用 --help-detail 查看详细说明")
        return
    
    print("🚀 AKShare数据初始化工具")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 初始化数据库连接
        print("🔄 初始化数据库连接...")
        await init_database()
        print("✅ 数据库连接成功")
        print()

        success = True

        # 检查数据库状态
        if args.check_only:
            await check_database_status()
        
        # 测试连接
        elif args.test_connection:
            success = await test_akshare_connection()
        
        # 仅基础信息同步
        elif args.basic_only:
            success = await run_basic_sync_only()
        
        # 完整初始化
        elif args.full:
            # 解析sync_items参数
            sync_items = None
            if args.sync_items:
                sync_items = [item.strip() for item in args.sync_items.split(',')]
                # 验证sync_items
                valid_items = ['basic_info', 'historical', 'weekly', 'monthly', 'financial', 'quotes', 'news']
                invalid_items = [item for item in sync_items if item not in valid_items]
                if invalid_items:
                    print(f"❌ 无效的同步项目: {', '.join(invalid_items)}")
                    print(f"   有效选项: {', '.join(valid_items)}")
                    return

            success = await run_full_initialization(
                args.historical_days,
                args.force,
                args.multi_period,
                sync_items
            )
        
        print("\n" + "=" * 50)
        if success:
            print("🎉 操作完成！")
        else:
            print("❌ 操作失败，请检查日志文件")

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 发生未预期错误: {e}")
        logger.exception("Unexpected error occurred")
    finally:
        # 关闭数据库连接
        try:
            await close_database()
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")

        # 根据成功状态退出
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
