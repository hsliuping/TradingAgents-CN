"""
Worker 模块启动入口
支持使用 python -m app.worker 启动 Worker
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.worker.analysis_worker import AnalysisWorker


def setup_logging():
    """设置日志配置"""
    # 确保日志目录存在
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 创建文件处理器，强制刷新
    file_handler = logging.FileHandler('logs/worker.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 强制刷新输出
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
    sys.stderr.reconfigure(line_buffering=True) if hasattr(sys.stderr, 'reconfigure') else None


async def main():
    """主函数"""
    logger = None

    try:
        print("🚀 启动TradingAgents分析Worker...")
        sys.stdout.flush()

        # 设置日志
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("🚀 启动TradingAgents分析Worker...")

        # 创建Worker实例
        logger.info("📦 创建Worker实例...")
        worker = AnalysisWorker()

        # 启动Worker
        logger.info("▶️  启动Worker...")
        await worker.start()

        # 如果 start() 正常返回（没有异常），说明 Worker 已经停止
        logger.info("✅ Worker已安全退出")
        print("✅ Worker已安全退出")

    except KeyboardInterrupt:
        msg = "\n⏹️  收到中断信号，正在关闭Worker..."
        print(msg)
        if logger:
            logger.info(msg)
    except Exception as e:
        error_msg = f"❌ Worker启动失败: {e}"
        print(error_msg)
        if logger:
            logger.error(error_msg, exc_info=True)
        else:
            import traceback
            traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)
    finally:
        # 确保 Worker 正确清理资源
        if 'worker' in locals():
            try:
                await worker._cleanup()
                if logger:
                    logger.info("🧹 Worker资源清理完成")
            except Exception as cleanup_error:
                if logger:
                    logger.error(f"❌ Worker清理资源时出错: {cleanup_error}")
                else:
                    print(f"❌ Worker清理资源时出错: {cleanup_error}")

        # 强制刷新日志
        sys.stdout.flush()
        sys.stderr.flush()
        if logger:
            for handler in logger.handlers:
                handler.flush()


if __name__ == "__main__":
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    
    # 运行Worker
    asyncio.run(main())
