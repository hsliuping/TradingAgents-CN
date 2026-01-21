"""
Worker 模块启动入口
支持使用 python -m app.worker 启动 Worker

🔥 增强版：添加全局错误捕获和退出日志机制
- atexit 钩子：进程正常退出时记录
- 信号处理：捕获 SIGTERM, SIGINT 等信号
- 全局异常钩子：捕获未处理的异常
- 资源监控：记录内存使用等信息
"""

import asyncio
import sys
import os
import logging
import traceback
import atexit
import signal
import threading
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ==================== 全局状态 ====================
_worker_state = {
    "pid": os.getpid(),
    "start_time": datetime.now(),
    "last_task_id": None,
    "last_task_time": None,
    "task_count": 0,
    "error_count": 0,
    "last_error": None,
    "status": "starting",
}


def get_worker_state() -> dict:
    """获取 Worker 当前状态（供外部更新）"""
    return _worker_state


def update_worker_state(**kwargs):
    """更新 Worker 状态"""
    _worker_state.update(kwargs)
    _worker_state["last_update"] = datetime.now().isoformat()


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


def write_exit_log(reason: str, details: str = ""):
    """写入退出日志（确保在任何情况下都能记录）"""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "worker.log"

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 计算运行时长
        runtime = datetime.now() - _worker_state.get("start_time", datetime.now())
        runtime_str = str(runtime).split('.')[0]  # 移除微秒

        # 获取内存使用情况
        memory_info = "未知"
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_info = f"{memory_mb:.2f} MB"
        except Exception:
            pass

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"{timestamp} - EXIT - Worker 进程退出\n")
            f.write(f"{'='*60}\n")
            f.write(f"退出原因: {reason}\n")
            f.write(f"PID: {_worker_state.get('pid', '未知')}\n")
            f.write(f"运行时长: {runtime_str}\n")
            f.write(f"内存使用: {memory_info}\n")
            f.write(f"处理任务数: {_worker_state.get('task_count', 0)}\n")
            f.write(f"错误次数: {_worker_state.get('error_count', 0)}\n")
            f.write(f"最后状态: {_worker_state.get('status', '未知')}\n")
            f.write(f"最后任务: {_worker_state.get('last_task_id', '无')}\n")
            f.write(f"最后错误: {_worker_state.get('last_error', '无')}\n")
            if details:
                f.write(f"详细信息:\n{details}\n")
            f.write(f"{'='*60}\n\n")
            f.flush()
    except Exception as e:
        # 最后的备用方案：写入标准错误
        try:
            sys.stderr.write(f"EXIT LOG FAILED: {e}\n")
            sys.stderr.write(f"Reason: {reason}\n")
            sys.stderr.flush()
        except Exception:
            pass


def _atexit_handler():
    """atexit 钩子 - 进程正常退出时调用"""
    write_exit_log("正常退出 (atexit)", f"状态: {_worker_state}")


def _signal_handler(signum, frame):
    """信号处理器 - 捕获 SIGTERM, SIGINT 等信号"""
    signal_names = {
        signal.SIGINT: "SIGINT (Ctrl+C)",
        signal.SIGTERM: "SIGTERM (终止信号)",
    }
    # Windows 特有信号
    if hasattr(signal, 'SIGBREAK'):
        signal_names[signal.SIGBREAK] = "SIGBREAK (Ctrl+Break)"

    signal_name = signal_names.get(signum, f"信号 {signum}")
    write_exit_log(f"收到信号: {signal_name}", f"状态: {_worker_state}")

    # 更新状态
    update_worker_state(status="shutting_down")

    # 退出进程
    sys.exit(0)


def _exception_hook(exc_type, exc_value, exc_tb):
    """全局异常钩子 - 捕获未处理的异常"""
    # 格式化异常信息
    tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))

    # 更新状态
    update_worker_state(
        status="crashed",
        last_error=str(exc_value),
        error_count=_worker_state.get("error_count", 0) + 1
    )

    write_exit_log(
        f"未捕获的异常: {exc_type.__name__}: {exc_value}",
        f"堆栈跟踪:\n{tb_str}\n\n状态: {_worker_state}"
    )

    # 调用原始的异常钩子
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _threading_exception_hook(args):
    """线程异常钩子 - 捕获线程中未处理的异常（Python 3.8+）"""
    tb_str = ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))

    update_worker_state(
        last_error=f"线程异常: {args.exc_value}",
        error_count=_worker_state.get("error_count", 0) + 1
    )

    write_exit_log(
        f"线程异常: {args.exc_type.__name__}: {args.exc_value}",
        f"线程: {args.thread.name if args.thread else '未知'}\n堆栈跟踪:\n{tb_str}"
    )


def setup_exit_handlers():
    """设置所有退出处理器"""
    # 1. atexit 钩子
    atexit.register(_atexit_handler)

    # 2. 信号处理器
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    if hasattr(signal, 'SIGBREAK'):  # Windows
        signal.signal(signal.SIGBREAK, _signal_handler)

    # 3. 全局异常钩子
    sys.excepthook = _exception_hook

    # 4. 线程异常钩子 (Python 3.8+)
    if hasattr(threading, 'excepthook'):
        threading.excepthook = _threading_exception_hook

    write_startup_log("退出处理器已设置 (atexit, signal, excepthook)")


async def main():
    """主函数"""
    logger = None
    worker = None

    # 首先写入启动日志（确保即使 logging 系统有问题也能记录）
    write_startup_log("Worker process starting...")
    write_startup_log(f"Python: {sys.executable}")
    write_startup_log(f"Working directory: {os.getcwd()}")
    write_startup_log(f"PID: {os.getpid()}")

    # 更新状态
    update_worker_state(status="initializing")

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
        update_worker_state(status="importing")
        try:
            from app.worker.analysis_worker import AnalysisWorker
            logger.info("AnalysisWorker module imported successfully")
        except Exception as import_error:
            update_worker_state(status="import_failed", last_error=str(import_error))
            logger.error(f"Failed to import AnalysisWorker: {import_error}")
            logger.error(traceback.format_exc())
            write_exit_log(f"导入失败: {import_error}", traceback.format_exc())
            sys.exit(1)

        # 创建Worker实例
        update_worker_state(status="creating_instance")
        logger.info("Creating Worker instance...")
        worker = AnalysisWorker()
        logger.info(f"Worker instance created: {worker.worker_id}")

        # 启动Worker（这个函数会一直运行直到被停止）
        update_worker_state(status="running")
        logger.info("Starting Worker main loop...")
        await worker.start()

        # 如果 start() 正常返回，说明 Worker 被优雅停止
        update_worker_state(status="stopped_normally")
        logger.info("Worker main loop ended normally")
        write_exit_log("主循环正常结束")

    except KeyboardInterrupt:
        update_worker_state(status="interrupted")
        msg = "Received interrupt signal (Ctrl+C), shutting down..."
        if logger:
            logger.info(msg)
        write_exit_log("用户中断 (Ctrl+C)")

    except asyncio.CancelledError:
        update_worker_state(status="cancelled")
        msg = "Async task cancelled"
        if logger:
            logger.info(msg)
        write_exit_log("异步任务被取消")

    except Exception as e:
        update_worker_state(
            status="crashed",
            last_error=str(e),
            error_count=_worker_state.get("error_count", 0) + 1
        )
        error_msg = f"Worker crashed with error: {e}"
        tb_str = traceback.format_exc()
        if logger:
            logger.error(error_msg)
            logger.error(tb_str)
        write_exit_log(f"崩溃: {e}", tb_str)
        sys.exit(1)

    finally:
        # 确保 Worker 正确清理资源
        if worker is not None:
            try:
                update_worker_state(status="cleaning_up")
                if logger:
                    logger.info("Cleaning up Worker resources...")
                await worker._cleanup()
                if logger:
                    logger.info("Worker resources cleaned up successfully")
            except Exception as cleanup_error:
                if logger:
                    logger.error(f"Error during cleanup: {cleanup_error}")
                update_worker_state(last_error=f"清理失败: {cleanup_error}")

        # 强制刷新所有日志处理器
        if logger:
            for handler in logging.getLogger().handlers:
                try:
                    handler.flush()
                except Exception:
                    pass


if __name__ == "__main__":
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)

    # 写入进程启动标记
    write_startup_log("=" * 60)
    write_startup_log("Worker __main__ starting")

    # 🔥 设置退出处理器（在最早的时机设置）
    setup_exit_handlers()

    try:
        # 运行Worker
        asyncio.run(main())
    except SystemExit as e:
        # 正常退出
        write_exit_log(f"系统退出 (exit code: {e.code})")
        raise
    except Exception as e:
        # 最后的异常捕获
        update_worker_state(
            status="fatal_error",
            last_error=str(e),
            error_count=_worker_state.get("error_count", 0) + 1
        )
        write_exit_log(f"致命错误: {e}", traceback.format_exc())
        sys.exit(1)
