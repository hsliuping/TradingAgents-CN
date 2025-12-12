#!/usr/bin/env python3
"""
智能交易回测系统启动脚本
Smart Trading Backtest System Launcher

使用方法:
python run_backtest.py --stock 000001 000002 --start 2023-01-01 --end 2023-12-31

作者: TradingAgents-CN
版本: 1.0.0
"""

import argparse
import logging
import sys
import os
from datetime import datetime
from typing import List, Optional
import time

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backtest_system.core.backtest_engine import BacktestEngine, BacktestConfig
from backtest_system.core.performance_analyzer import PerformanceAnalyzer

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """设置日志"""

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers,
        force=True
    )

def parse_arguments():
    """解析命令行参数"""

    parser = argparse.ArgumentParser(
        description="智能交易回测系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_backtest.py --stock 000001 000002 --start 2023-01-01 --end 2023-12-31
  python run_backtest.py --stock 000001 --start 2022-01-01 --end 2023-12-31 --capital 1000000
  python run_backtest.py --config config.json --output-dir results
        """
    )

    # 股票代码
    parser.add_argument(
        '--stock', '-s',
        nargs='+',
        required=False,
        help='股票代码列表 (例如: 000001 000002)'
    )

    # 时间范围
    parser.add_argument(
        '--start', '-b',
        type=str,
        help='开始日期 (YYYY-MM-DD 格式)'
    )

    parser.add_argument(
        '--end', '-e',
        type=str,
        help='结束日期 (YYYY-MM-DD 格式)'
    )

    # 资金配置
    parser.add_argument(
        '--capital', '-c',
        type=float,
        default=100000.0,
        help='初始资金 (默认: 100000)'
    )

    parser.add_argument(
        '--commission',
        type=float,
        default=0.0003,
        help='手续费率 (默认: 0.0003)'
    )

    parser.add_argument(
        '--slippage',
        type=float,
        default=0.0001,
        help='滑点率 (默认: 0.0001)'
    )

    # 基准设置
    parser.add_argument(
        '--benchmark',
        type=str,
        default='399300',
        help='基准指数代码 (默认: 399300)'
    )

    # 输出设置
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='backtest_results',
        help='输出目录 (默认: backtest_results)'
    )

    
    parser.add_argument(
        '--no-reports',
        action='store_true',
        help='不生成报告'
    )

    # 其他选项
    parser.add_argument(
        '--config',
        type=str,
        help='配置文件路径 (JSON格式)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别 (默认: INFO)'
    )

    parser.add_argument(
        '--log-file',
        type=str,
        help='日志文件路径'
    )

    parser.add_argument(
        '--progress',
        action='store_true',
        help='显示进度条'
    )

    # 演示模式
    parser.add_argument(
        '--demo',
        action='store_true',
        help='演示模式，使用默认参数'
    )

    return parser.parse_args()

def load_config(config_file: str) -> dict:
    """加载配置文件"""

    try:
        import json
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}

def validate_arguments(args) -> bool:
    """验证参数"""

    # 演示模式跳过验证
    if args.demo:
        return True

    # 检查必需参数
    if not args.stock:
        print("错误: 请指定股票代码 (--stock)")
        return False

    if not args.start or not args.end:
        print("错误: 请指定开始和结束日期 (--start, --end)")
        return False

    # 验证日期格式
    try:
        datetime.strptime(args.start, '%Y-%m-%d')
        datetime.strptime(args.end, '%Y-%m-%d')
    except ValueError:
        print("错误: 日期格式不正确，请使用 YYYY-MM-DD 格式")
        return False

    # 验证日期范围
    if args.start >= args.end:
        print("错误: 开始日期必须早于结束日期")
        return False

    # 验证资金
    if args.capital <= 0:
        print("错误: 初始资金必须大于0")
        return False

    return True

def progress_callback(progress: float, current_date: str, current_day: int, total_days: int):
    """进度回调函数"""

    if progress <= 1.0:
        bar_length = 40
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)

        print(f'\r进度: |{bar}| {progress:.1%} ({current_day}/{total_days}) {current_date}', end='', flush=True)

    if progress >= 1.0:
        print()  # 换行

def run_demo():
    """运行演示模式"""

    print("🚀 启动演示模式...")
    print("使用演示参数: 股票000001, 时间范围2023年")

    # 演示参数
    demo_config = BacktestConfig(
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=100000.0,
        commission_rate=0.0003,
        slippage_rate=0.0001,
        benchmark="399300"
    )

    demo_stocks = ["000001"]  # 平安银行

    return demo_config, demo_stocks

def main():
    """主函数"""

    # 解析参数
    args = parse_arguments()

    # 设置日志
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)

    print("🎯 智能交易回测系统 v1.0.0")
    print("=" * 50)

    # 演示模式
    if args.demo:
        config, stock_codes = run_demo()
    else:
        # 验证参数
        if not validate_arguments(args):
            sys.exit(1)

        # 加载配置文件
        config_dict = {}
        if args.config:
            config_dict = load_config(args.config)

        # 创建回测配置
        config = BacktestConfig(
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital,
            commission_rate=args.commission,
            slippage_rate=args.slippage,
            benchmark=args.benchmark
        )

        stock_codes = args.stock

    # 显示配置信息
    print(f"📊 回测配置:")
    print(f"   股票代码: {', '.join(stock_codes)}")
    print(f"   回测期间: {config.start_date} 至 {config.end_date}")
    print(f"   初始资金: {config.initial_capital:,.2f} 元")
    print(f"   手续费率: {config.commission_rate:.4f}")
    print(f"   滑点率: {config.slippage_rate:.4f}")
    print(f"   基准指数: {config.benchmark}")
    # 修改输出目录为 backtest_system/result
    output_dir = os.path.join(args.output_dir, "result")
    print(f"   输出目录: {output_dir}")
    print()

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    try:
        # 初始化回测引擎
        logger.info("初始化回测引擎...")
        engine = BacktestEngine(config)

        # 执行回测
        logger.info("开始执行回测...")
        start_time = time.time()

        progress_callback_func = progress_callback if args.progress else None

        result = engine.run_backtest(
            stock_codes=stock_codes,
            progress_callback=progress_callback_func
        )

        end_time = time.time()
        execution_time = end_time - start_time

        print(f"\n⏱️  回测完成，耗时: {execution_time:.2f} 秒")

        # 检查结果
        if not result.success:
            print(f"❌ 回测失败: {result.error_message}")
            sys.exit(1)

        # 性能分析
        print("📈 进行性能分析...")
        analyzer = PerformanceAnalyzer()
        performance_analysis = analyzer.analyze_performance(
            portfolio_history=result.portfolio_history,
            trade_history=result.trade_history,
            daily_analysis=result.daily_analysis
        )

        # 显示关键结果
        print("\n📊 回测结果摘要:")
        print("-" * 30)

        if "returns" in performance_analysis:
            returns = performance_analysis["returns"]
            print(f"💰 总收益率: {returns.get('total_return', 0):.2%}")
            print(f"📈 年化收益率: {returns.get('annualized_return', 0):.2%}")
            print(f"🎯 胜率: {returns.get('win_rate', 0):.2%}")
            print(f"📊 夏普比率: {returns.get('sharpe_ratio', 0):.3f}")

        if "risk" in performance_analysis:
            risk = performance_analysis["risk"]
            print(f"⚠️  最大回撤: {risk.get('max_drawdown', 0):.2%}")
            print(f"📊 年化波动率: {risk.get('volatility', 0):.2%}")

        if "trading" in performance_analysis:
            trading = performance_analysis["trading"]
            print(f"🔄 总交易次数: {trading.get('total_trades', 0)}")
            print(f"📅 交易天数: {trading.get('trading_days', 0)}")

        if "overall_score" in performance_analysis:
            score = performance_analysis["overall_score"]
            print(f"🏆 综合评级: {score.get('grade', 'N/A')} ({score.get('total_score', 0):.1f}/{score.get('max_score', 100)})")

        # 生成基础报告文件（增强分析需要）
        print("\n📋 生成基础报告文件...")
        try:
            from backtest_system.reports import ReportGenerator
            report_generator = ReportGenerator(output_dir)
            report_generator.generate_comprehensive_report(
                backtest_result=result,
                stock_codes=stock_codes,
                performance_analysis=performance_analysis,
                save_to_file=True
            )
        except Exception as e:
            print(f"   ⚠️ 基础报告生成失败: {e}")

        # 生成增强综合分析
        print("\n📋 生成增强综合分析...")
        try:
            from create_enhanced_comprehensive_analysis import main as enhanced_main
            enhanced_main()
        except ImportError:
            print("   ⚠️ 无法导入增强分析模块，跳过生成")
        except Exception as e:
            print(f"   ⚠️ 增强分析生成失败: {e}")

        print("\n✅ 回测系统执行完成!")
        print(f"📁 所有结果已保存到: {output_dir}")

    except KeyboardInterrupt:
        print("\n⏹️  用户中断回测")
        sys.exit(1)
    except Exception as e:
        logger.error(f"回测执行过程中发生错误: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        print(f"\n❌ 回测执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()