#!/usr/bin/env python3
"""
开发环境启动脚本
同时启动后端和 Worker，方便调试
"""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# 确保在项目根目录
project_root = Path(__file__).parent.parent
os.chdir(project_root)

# 存储进程对象
processes = []


def signal_handler(sig, frame):
    """信号处理器，优雅关闭所有进程"""
    print("\n\n🛑 收到中断信号，正在关闭所有服务...")
    for proc in processes:
        try:
            proc.terminate()
        except:
            pass
    
    # 等待进程结束
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except:
            try:
                proc.kill()
            except:
                pass
    
    print("✅ 所有服务已关闭")
    sys.exit(0)


def main():
    """主函数"""
    print("🚀 TradingAgents-CN 开发环境启动器")
    print("=" * 60)
    print("将同时启动：")
    print("  1. FastAPI 后端服务")
    print("  2. Worker 队列消费者")
    print("=" * 60)
    print()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动后端服务
        print("📡 启动 FastAPI 后端服务...")
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "app"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=str(project_root)
        )
        processes.append(backend_proc)
        print(f"   ✅ 后端服务已启动 (PID: {backend_proc.pid})")
        
        # 等待后端启动
        print("   ⏳ 等待后端服务就绪...")
        time.sleep(3)
        
        # 启动 Worker
        print("\n🔧 启动 Worker 队列消费者...")
        worker_proc = subprocess.Popen(
            [sys.executable, "-m", "app.worker"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=str(project_root)
        )
        processes.append(worker_proc)
        print(f"   ✅ Worker 已启动 (PID: {worker_proc.pid})")
        
        print("\n" + "=" * 60)
        print("✅ 所有服务启动成功！")
        print("=" * 60)
        print("\n📍 服务地址：")
        print("  - API服务: http://127.0.0.1:8000")
        print("  - API文档: http://127.0.0.1:8000/docs")
        print("\n💡 提示：")
        print("  - 按 Ctrl+C 停止所有服务")
        print("  - 后端日志和 Worker 日志会同时输出到控制台")
        print("  - 详细日志请查看 logs/ 目录")
        print("\n" + "=" * 60)
        
        # 等待所有进程
        while True:
            # 检查进程是否还在运行
            for i, proc in enumerate(processes):
                if proc.poll() is not None:
                    # 进程已退出
                    service_name = "后端服务" if i == 0 else "Worker"
                    print(f"\n⚠️  {service_name} (PID: {proc.pid}) 已退出，退出码: {proc.returncode}")
                    # 退出所有进程
                    signal_handler(None, None)
                    return
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        signal_handler(None, None)
        sys.exit(1)


if __name__ == "__main__":
    main()
