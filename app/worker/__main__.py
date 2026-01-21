"""
Worker 模块启动入口
支持使用 python -m app.worker 启动 Worker
"""

import asyncio
import sys
import os
import logging
import traceback
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def setup_logging():
    """设置日志配置 - 确保日志在任何情况下都能写入文件"""
    # 确保日志目录存在
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "worker.log"

    # 创建文件处理器，使用追加模式
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8', mode='a')
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    # 创建控制台处理器（可能因编码问题失败，但不影响文件日志）
    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    except Exception:
        console_handler = None

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    if console_handler:
        root_logger.addHandler(console_handler)

    # 强制刷新输出（忽略编码错误）
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(line_buffering=True, errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(line_buffering=True, errors='replace')
    except Exception:
        pass

    return logging.getLogger(__name__)


def write_startup_log(message: str):
    """直接写入启动日志（绕过 logging 模块，确保记录）"""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "worker.log"

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - STARTUP - {message}\n")
            f.flush()
    except Exception:
        pass


async def main():
    """主函数"""
    logger = None
    worker = None

    # 首先写入启动日志（确保即使 logging 系统有问题也能记录）
    write_startup_log("Worker process starting...")
    write_startup_log(f"Python: {sys.executable}")
    write_startup_log(f"Working directory: {os.getcwd()}")
    write_startup_log(f"PID: {os.getpid()}")

    try:
        # 设置日志系统
        logger = setup_logging()
        logger.info("=" * 60)
        logger.info("Worker process starting...")
        logger.info(f"Python: {sys.executable}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"PID: {os.getpid()}")
        logger.info("=" * 60)

        # 导入 Worker（延迟导入，避免导入错误导致无日志）
        try:
            from app.worker.analysis_worker import AnalysisWorker
            logger.info("AnalysisWorker module imported successfully")
        except Exception as import_error:
            logger.error(f"Failed to import AnalysisWorker: {import_error}")
            logger.error(traceback.format_exc())
            write_startup_log(f"IMPORT ERROR: {import_error}")
            sys.exit(1)

        # 创建Worker实例
        logger.info("Creating Worker instance...")
        worker = AnalysisWorker()
        logger.info(f"Worker instance created: {worker.worker_id}")

        # 启动Worker（这个函数会一直运行直到被停止）
        logger.info("Starting Worker main loop...")
        await worker.start()

        # 如果 start() 正常返回，说明 Worker 被优雅停止
        logger.info("Worker main loop ended normally")
        write_startup_log("Worker stopped normally")

    except KeyboardInterrupt:
        msg = "Received interrupt signal (Ctrl+C), shutting down..."
        if logger:
            logger.info(msg)
        write_startup_log(msg)

    except Exception as e:
        error_msg = f"Worker crashed with error: {e}"
        if logger:
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        write_startup_log(f"CRASH: {error_msg}")
        write_startup_log(traceback.format_exc())
        sys.exit(1)

    finally:
        # 确保 Worker 正确清理资源
        if worker is not None:
            try:
                if logger:
                    logger.info("Cleaning up Worker resources...")
                await worker._cleanup()
                if logger:
                    logger.info("Worker resources cleaned up successfully")
            except Exception as cleanup_error:
                if logger:
                    logger.error(f"Error during cleanup: {cleanup_error}")
                write_startup_log(f"CLEANUP ERROR: {cleanup_error}")

        # 强制刷新所有日志处理器
        if logger:
            for handler in logging.getLogger().handlers:
                try:
                    handler.flush()
                except Exception:
                    pass

        write_startup_log("Worker process exiting")


if __name__ == "__main__":
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)

    # 写入进程启动标记
    write_startup_log("=" * 60)
    write_startup_log("Worker __main__ starting")

    try:
        # 运行Worker
        asyncio.run(main())
    except Exception as e:
        # 最后的异常捕获
        write_startup_log(f"FATAL: {e}")
        write_startup_log(traceback.format_exc())
        sys.exit(1)
