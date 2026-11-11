#!/usr/bin/env python3
"""
BaoStock数据初始化CLI工具
提供命令行界面进行BaoStock数据初始化和管理
"""
import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.worker.baostock_init_service import BaoStockInitService
from app.worker.baostock_sync_service import BaoStockSyncService

# 配置日志（共享初始化函数，日志治理 §5.3）
os.makedirs(os.path.join('data', 'logs'), exist_ok=True)
from core.utils.logging_setup import setup_cli_logging
setup_cli_logging(
    "INFO",
    fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    log_file=os.path.join('data', 'logs', 'baostock_init.log'),
)
logger = logging.getLogger(__name__)


def print_banner():
    """打印横幅"""
    print("🚀 BaoStock数据初始化工具")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def print_stats(stats):
    """打印统计信息"""
    print("\n📊 初始化统计:")
    print(f"   完成步骤: {stats.progress}")
    print(f"   基础信息: {stats.basic_info_count}条")
    print(f"   行情数据: {stats.quotes_count}条")
    print(f"   历史记录: {stats.historical_records}条")
    print(f"   财务记录: {stats.financial_records}条")
    print(f"   错误数量: {len(stats.errors)}")
    print(f"   总耗时: {stats.duration:.1f}秒")
    
    if stats.errors:
        print("\n❌ 错误详情:")
        for i, error in enumerate(stats.errors[:5], 1):  # 只显示前5个错误
            print(f"   {i}. {error}")
        if len(stats.errors) > 5:
            print(f"   ... 还有{len(stats.errors) - 5}个错误")


async def test_connection():
    """测试BaoStock连接"""
    print("🔗 测试BaoStock连接...")
    try:
        # 不需要数据库连接，仅测试BaoStock API
        service = BaoStockSyncService(require_db=False)
        connected = await service.provider.test_connection()

        if connected:
            print("✅ BaoStock连接成功")
            return True
        else:
            print("❌ BaoStock连接失败")
            return False

    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False


async def check_database_status():
    """检查数据库状态"""
    print("📋 检查数据库状态...")
    try:
        service = BaoStockInitService()
        status = await service.check_database_status()
        
        print(f"  📋 股票基础信息: {status.get('basic_info_count', 0)}条")
        if status.get('basic_info_latest'):
            print(f"     最新更新: {status['basic_info_latest']}")
        
        print(f"  📈 行情数据: {status.get('quotes_count', 0)}条")
        if status.get('quotes_latest'):
            print(f"     最新更新: {status['quotes_latest']}")
        
        print(f"  ✅ 数据库状态: {status.get('status', 'unknown')}")
        
        return status
        
    except Exception as e:
        print(f"❌ 检查数据库状态失败: {e}")
        return None


async def run_full_initialization(historical_days: int = 365, force: bool = False):
    """运行完整初始化"""
    print(f"🚀 开始完整初始化 (历史数据: {historical_days}天, 强制: {force})...")
    
    try:
        service = BaoStockInitService()
        stats = await service.full_initialization(historical_days=historical_days, force=force)
        
        if stats.completed_steps == stats.total_steps:
            print("✅ 完整初始化成功完成")
        else:
            print(f"⚠️ 初始化部分完成: {stats.progress}")
        
        print_stats(stats)
        return stats.completed_steps == stats.total_steps
        
    except Exception as e:
        print(f"❌ 完整初始化失败: {e}")
        return False


async def run_basic_initialization():
    """运行基础初始化"""
    print("🚀 开始基础初始化...")
    
    try:
        service = BaoStockInitService()
        stats = await service.basic_initialization()
        
        if stats.completed_steps == stats.total_steps:
            print("✅ 基础初始化成功完成")
        else:
            print(f"⚠️ 初始化部分完成: {stats.progress}")
        
        print_stats(stats)
        return stats.completed_steps == stats.total_steps
        
    except Exception as e:
        print(f"❌ 基础初始化失败: {e}")
        return False


def print_help_detail():
    """打印详细帮助信息"""
    help_text = """
🔧 BaoStock数据初始化工具详细说明

📋 主要功能:
  --full              完整初始化（推荐首次部署使用）
  --basic-only        仅基础初始化（股票列表和行情）
  --check-only        仅检查数据库状态
  --test-connection   测试BaoStock连接

⚙️ 配置选项:
  --historical-days   历史数据天数（默认365天）
  --force            强制重新初始化（忽略现有数据）

📊 使用示例:
  # 检查数据库状态
  python cli/baostock_init.py --check-only

  # 测试连接
  python cli/baostock_init.py --test-connection

  # 完整初始化（推荐，默认1年历史数据）
  python cli/baostock_init.py --full

  # 自定义历史数据范围（6个月）
  python cli/baostock_init.py --full --historical-days 180

  # 全历史数据初始化（从1990年至今，需要>=3650天）
  python cli/baostock_init.py --full --historical-days 10000

  # 全历史多周期初始化（推荐用于生产环境）
  python cli/baostock_init.py --full --multi-period --historical-days 10000

  # 强制重新初始化
  python cli/baostock_init.py --full --force

  # 仅基础初始化
  python cli/baostock_init.py --basic-only

📝 说明:
  - 完整初始化包含: 基础信息、历史数据、财务数据、实时行情
  - 基础初始化包含: 基础信息、实时行情
  - 首次部署建议使用完整初始化
  - 日常维护可使用基础初始化

⚠️ 注意事项:
  - 确保网络连接正常
  - 确保MongoDB数据库可访问
  - 完整初始化可能需要较长时间
  - 建议在非交易时间进行初始化
"""
    print(help_text)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="BaoStock数据初始化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 操作选项
    parser.add_argument('--full', action='store_true', help='完整初始化')
    parser.add_argument('--basic-only', action='store_true', help='仅基础初始化')
    parser.add_argument('--check-only', action='store_true', help='仅检查数据库状态')
    parser.add_argument('--test-connection', action='store_true', help='测试BaoStock连接')
    parser.add_argument('--help-detail', action='store_true', help='显示详细帮助')
    
    # 配置选项
    parser.add_argument('--historical-days', type=int, default=365, help='历史数据天数（默认365）')
    parser.add_argument('--force', action='store_true', help='强制重新初始化')
    
    args = parser.parse_args()
    
    # 显示详细帮助
    if args.help_detail:
        print_help_detail()
        return
    
    # 如果没有指定任何操作，显示帮助
    if not any([args.full, args.basic_only, args.check_only, args.test_connection]):
        parser.print_help()
        print("\n💡 使用 --help-detail 查看详细说明")
        return
    
    print_banner()
    
    try:
        success = True
        
        # 测试连接
        if args.test_connection:
            success = await test_connection()
        
        # 检查数据库状态
        elif args.check_only:
            status = await check_database_status()
            success = status is not None
        
        # 完整初始化
        elif args.full:
            success = await run_full_initialization(
                historical_days=args.historical_days,
                force=args.force
            )
        
        # 基础初始化
        elif args.basic_only:
            success = await run_basic_initialization()
        
        # 输出结果
        print("\n" + "=" * 50)
        if success:
            print("✅ 操作成功完成")
        else:
            print("❌ 操作失败，请检查日志文件")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ 操作被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 操作过程中发生错误: {e}")
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ 程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        sys.exit(1)
