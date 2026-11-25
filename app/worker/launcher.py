"""
Worker 启动器（主进程）
用于启动和监控 Worker 子进程，捕获子进程退出并记录日志

🔥 解决问题：当 Worker 被 taskkill /F 或任务管理器强制杀死时，
   Worker 内部的退出钩子无法执行，但主进程可以检测到子进程退出。
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def write_log(message: str, level: str = "INFO"):
    """写入日志"""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "worker.log"
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - LAUNCHER - {level} - {message}\n")
            f.flush()
        
        # 同时打印到控制台
        print(f"[{timestamp}] [{level}] {message}")
    except Exception as e:
        print(f"写入日志失败: {e}")


def write_exit_report(pid: int, returncode: int, runtime_seconds: float):
    """写入子进程退出报告"""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "worker.log"
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 解释退出码
        if returncode == 0:
            exit_reason = "正常退出"
        elif returncode < 0:
            # 负数表示被信号终止（Unix）
            exit_reason = f"被信号终止 (signal {-returncode})"
        elif returncode == 1:
            exit_reason = "一般错误"
        elif returncode == -1073741510:  # Windows: STATUS_CONTROL_C_EXIT
            exit_reason = "Ctrl+C 中断"
        elif returncode == -1073741819:  # Windows: STATUS_ACCESS_VIOLATION
            exit_reason = "访问违规（崩溃）"
        elif returncode == -1073740791:  # Windows: 被 taskkill 杀死
            exit_reason = "被强制终止 (taskkill /F 或任务管理器)"
        elif returncode == 1:
            exit_reason = "一般错误退出"
        else:
            exit_reason = f"未知退出码: {returncode}"
        
        # 格式化运行时间
        hours, remainder = divmod(int(runtime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"{timestamp} - LAUNCHER - Worker 子进程退出报告\n")
            f.write(f"{'='*60}\n")
            f.write(f"子进程 PID: {pid}\n")
            f.write(f"退出码: {returncode}\n")
            f.write(f"退出原因: {exit_reason}\n")
            f.write(f"运行时长: {runtime_str}\n")
            f.write(f"{'='*60}\n\n")
            f.flush()
        
        print(f"\n{'='*60}")
        print(f"Worker 子进程退出报告")
        print(f"{'='*60}")
        print(f"子进程 PID: {pid}")
        print(f"退出码: {returncode}")
        print(f"退出原因: {exit_reason}")
        print(f"运行时长: {runtime_str}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"写入退出报告失败: {e}")


def main():
    """主函数：启动并监控 Worker 子进程"""
    write_log("=" * 50)
    write_log("Worker 启动器开始运行")
    write_log(f"Python: {sys.executable}")
    write_log(f"工作目录: {os.getcwd()}")
    write_log(f"启动器 PID: {os.getpid()}")
    
    # 构建启动命令
    python_exe = sys.executable
    worker_module = "app.worker"
    
    write_log(f"启动 Worker 子进程: {python_exe} -m {worker_module}")
    
    start_time = time.time()
    
    # 启动子进程
    process = subprocess.Popen(
        [python_exe, "-m", worker_module],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # 行缓冲
        encoding='utf-8',
        errors='replace'
    )
    
    child_pid = process.pid
    write_log(f"Worker 子进程已启动, PID: {child_pid}")
    
    try:
        # 实时输出子进程的日志
        while True:
            line = process.stdout.readline()
            if line:
                print(line.rstrip())
            
            # 检查子进程是否退出
            returncode = process.poll()
            if returncode is not None:
                # 子进程已退出
                runtime = time.time() - start_time
                write_log(f"检测到 Worker 子进程退出, 退出码: {returncode}", "WARNING")
                write_exit_report(child_pid, returncode, runtime)
                break
            
            # 如果没有输出也没有退出，短暂等待
            if not line:
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        write_log("收到 Ctrl+C，正在终止 Worker 子进程...", "WARNING")
        process.terminate()
        process.wait(timeout=5)
        runtime = time.time() - start_time
        write_exit_report(child_pid, process.returncode or -1, runtime)
    
    write_log("Worker 启动器退出")


if __name__ == "__main__":
    main()

