#!/usr/bin/env python3
"""
TradingAgents-CN Pro - 统一启动脚本（Python版本）

功能：
1. 启动所有服务（MongoDB, Redis, Backend, Worker, Nginx）
2. 监控进程状态并自动重启崩溃的进程
3. 保存 PID 到 runtime/pids.json
4. 正确处理日志输出
5. 优雅关闭所有进程

使用方法：
    python scripts/installer/start_all.py
    python scripts/installer/start_all.py --no-restart  # 禁用自动重启
"""

import os
import sys
import json
import time
import signal
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class ProcessManager:
    """进程管理器"""
    
    def __init__(self, auto_restart: bool = True):
        """
        初始化进程管理器
        
        Args:
            auto_restart: 是否自动重启崩溃的进程
        """
        self.auto_restart = auto_restart
        self.processes: Dict[str, subprocess.Popen] = {}
        self.process_configs: Dict[str, dict] = {}
        self.running = False
        self.restart_counts: Dict[str, int] = {}
        self.max_restarts = 5  # 最大重启次数
        
        # 设置日志
        self._setup_logging()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self):
        """设置日志"""
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / "start_all.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"\n🛑 收到信号 {signum}，正在关闭所有服务...")
        self.running = False
        self.stop_all()
        sys.exit(0)
    
    def _get_python_exe(self) -> str:
        """获取 Python 可执行文件路径"""
        # 优先使用嵌入式 Python（便携版/安装版）
        embedded_python = project_root / "vendors" / "python" / "python.exe"
        if embedded_python.exists():
            return str(embedded_python)
        
        # 使用虚拟环境 Python（开发版）
        venv_python = project_root / "venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return str(venv_python)
        
        # 使用系统 Python
        return sys.executable
    
    def _get_process_configs(self) -> Dict[str, dict]:
        """获取进程配置"""
        python_exe = self._get_python_exe()
        
        # 读取端口配置
        env_file = project_root / ".env"
        backend_port = "8000"
        mongo_port = "27017"
        redis_port = "6379"
        nginx_port = "80"
        
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('PORT='):
                        backend_port = line.split('=')[1].strip()
                    elif line.startswith('MONGODB_PORT='):
                        mongo_port = line.split('=')[1].strip()
                    elif line.startswith('REDIS_PORT='):
                        redis_port = line.split('=')[1].strip()
                    elif line.startswith('NGINX_PORT='):
                        nginx_port = line.split('=')[1].strip()
        
        configs = {}
        
        # MongoDB
        mongod_exe = project_root / "vendors" / "mongodb" / "bin" / "mongod.exe"
        if mongod_exe.exists():
            mongo_data_dir = project_root / "data" / "mongodb"
            mongo_data_dir.mkdir(parents=True, exist_ok=True)
            mongo_log_file = project_root / "logs" / "mongodb.log"
            
            configs["mongodb"] = {
                "name": "MongoDB",
                "command": [
                    str(mongod_exe),
                    "--dbpath", str(mongo_data_dir),
                    "--port", mongo_port,
                    "--logpath", str(mongo_log_file),
                    "--logappend"
                ],
                "cwd": str(project_root),
                "auto_restart": True,
                "critical": True
            }

        # Redis
        redis_exe = project_root / "vendors" / "redis" / "redis-server.exe"
        if redis_exe.exists():
            redis_conf = project_root / "runtime" / "redis.conf"
            redis_log_file = project_root / "logs" / "redis.log"

            configs["redis"] = {
                "name": "Redis",
                "command": [str(redis_exe), str(redis_conf)],
                "cwd": str(project_root),
                "auto_restart": True,
                "critical": True
            }

        # Backend API
        app_main = project_root / "app" / "__main__.py"
        if app_main.exists():
            backend_log_file = project_root / "logs" / "backend.log"

            configs["backend"] = {
                "name": "Backend API",
                "command": [python_exe, str(app_main)],
                "cwd": str(project_root),
                "auto_restart": True,
                "critical": True,
                "log_file": str(backend_log_file)
            }

        # Worker
        worker_main = project_root / "app" / "worker" / "__main__.py"
        if worker_main.exists():
            worker_log_file = project_root / "logs" / "worker.log"

            configs["worker"] = {
                "name": "Worker",
                "command": [python_exe, str(worker_main)],
                "cwd": str(project_root),
                "auto_restart": True,
                "critical": False,  # Worker 不是关键进程
                "log_file": str(worker_log_file)
            }

        # Nginx
        nginx_exe = project_root / "vendors" / "nginx" / "nginx-1.29.3" / "nginx.exe"
        if nginx_exe.exists():
            nginx_conf = project_root / "runtime" / "nginx.conf"
            nginx_work_dir = project_root / "vendors" / "nginx" / "nginx-1.29.3"

            configs["nginx"] = {
                "name": "Nginx",
                "command": [str(nginx_exe), "-c", str(nginx_conf)],
                "cwd": str(nginx_work_dir),
                "auto_restart": True,
                "critical": False
            }

        return configs

    def start_process(self, name: str, config: dict) -> bool:
        """
        启动单个进程

        Args:
            name: 进程名称
            config: 进程配置

        Returns:
            是否启动成功
        """
        try:
            self.logger.info(f"🚀 启动 {config['name']}...")

            # 设置环境变量
            env = os.environ.copy()
            env['PYTHONPATH'] = str(project_root)
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'

            # 打开日志文件（如果配置了）
            log_file = config.get('log_file')
            if log_file:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                stdout = open(log_file, 'a', encoding='utf-8')
                stderr = subprocess.STDOUT
            else:
                stdout = subprocess.DEVNULL
                stderr = subprocess.DEVNULL

            # 启动进程
            process = subprocess.Popen(
                config['command'],
                cwd=config['cwd'],
                env=env,
                stdout=stdout,
                stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            self.processes[name] = process
            self.process_configs[name] = config
            self.restart_counts[name] = 0

            self.logger.info(f"✅ {config['name']} 已启动 (PID: {process.pid})")

            # 等待一下，检查是否立即崩溃
            time.sleep(1)
            if process.poll() is not None:
                self.logger.error(f"❌ {config['name']} 启动后立即退出 (返回码: {process.returncode})")
                return False

            return True

        except Exception as e:
            self.logger.error(f"❌ 启动 {config['name']} 失败: {e}")
            return False

    def stop_process(self, name: str, timeout: int = 5):
        """
        停止单个进程

        Args:
            name: 进程名称
            timeout: 超时时间（秒）
        """
        if name not in self.processes:
            return

        process = self.processes[name]
        config = self.process_configs[name]

        try:
            if process.poll() is None:  # 进程仍在运行
                self.logger.info(f"🛑 停止 {config['name']} (PID: {process.pid})...")
                process.terminate()

                # 等待进程优雅退出
                try:
                    process.wait(timeout=timeout)
                    self.logger.info(f"✅ {config['name']} 已停止")
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"⚡ 强制杀死 {config['name']}...")
                    process.kill()
                    process.wait()
                    self.logger.info(f"✅ {config['name']} 已强制停止")
        except Exception as e:
            self.logger.error(f"❌ 停止 {config['name']} 失败: {e}")
        finally:
            del self.processes[name]
            del self.process_configs[name]

    def stop_all(self):
        """停止所有进程"""
        self.logger.info("🔄 正在停止所有服务...")

        # 按相反顺序停止（先停止 Nginx, Worker, Backend, 最后停止 Redis, MongoDB）
        stop_order = ["nginx", "worker", "backend", "redis", "mongodb"]

        for name in stop_order:
            if name in self.processes:
                self.stop_process(name)

        # 停止剩余的进程
        for name in list(self.processes.keys()):
            self.stop_process(name)

        self.logger.info("✅ 所有服务已停止")

    def save_pids(self):
        """保存 PID 到 runtime/pids.json"""
        try:
            runtime_dir = project_root / "runtime"
            runtime_dir.mkdir(exist_ok=True)

            pids = {}
            for name, process in self.processes.items():
                if process.poll() is None:  # 进程仍在运行
                    pids[name] = process.pid

            pids_file = runtime_dir / "pids.json"
            with open(pids_file, 'w', encoding='utf-8') as f:
                json.dump(pids, f, indent=4)

            self.logger.debug(f"💾 已保存 PID 到 {pids_file}")

        except Exception as e:
            self.logger.error(f"❌ 保存 PID 失败: {e}")

    def check_and_restart(self):
        """检查进程状态并重启崩溃的进程"""
        for name in list(self.processes.keys()):
            process = self.processes[name]
            config = self.process_configs[name]

            # 检查进程是否退出
            if process.poll() is not None:
                exit_code = process.returncode
                self.logger.warning(f"⚠️  {config['name']} 已退出 (返回码: {exit_code})")

                # 从进程列表中移除
                del self.processes[name]

                # 检查是否需要重启
                if self.auto_restart and config.get('auto_restart', False):
                    restart_count = self.restart_counts.get(name, 0)

                    if restart_count < self.max_restarts:
                        self.logger.info(f"🔄 尝试重启 {config['name']} (第 {restart_count + 1}/{self.max_restarts} 次)...")

                        # 等待一下再重启
                        time.sleep(2)

                        if self.start_process(name, config):
                            self.restart_counts[name] = restart_count + 1
                            self.logger.info(f"✅ {config['name']} 重启成功")
                        else:
                            self.logger.error(f"❌ {config['name']} 重启失败")

                            # 如果是关键进程，停止所有服务
                            if config.get('critical', False):
                                self.logger.error(f"💥 关键进程 {config['name']} 重启失败，停止所有服务")
                                self.running = False
                    else:
                        self.logger.error(f"❌ {config['name']} 已达到最大重启次数 ({self.max_restarts})，放弃重启")

                        # 如果是关键进程，停止所有服务
                        if config.get('critical', False):
                            self.logger.error(f"💥 关键进程 {config['name']} 无法恢复，停止所有服务")
                            self.running = False

    def monitor(self):
        """监控所有进程"""
        self.logger.info("👀 开始监控服务状态...")
        self.running = True

        check_count = 0

        try:
            while self.running:
                # 检查并重启崩溃的进程
                self.check_and_restart()

                # 保存 PID
                self.save_pids()

                # 每 30 秒输出一次状态摘要
                check_count += 1
                if check_count % 6 == 0:  # 5秒检查一次，6次 = 30秒
                    self.logger.info("📊 进程状态摘要:")
                    for name, process in self.processes.items():
                        config = self.process_configs[name]
                        if process.poll() is None:
                            self.logger.info(f"   ✅ {config['name']} (PID: {process.pid})")
                        else:
                            self.logger.info(f"   ❌ {config['name']} (已退出)")

                # 检查是否所有进程都已退出
                if len(self.processes) == 0:
                    self.logger.error("❌ 所有进程都已退出")
                    break

                time.sleep(5)  # 每 5 秒检查一次

        except KeyboardInterrupt:
            self.logger.info("\n🛑 收到中断信号...")
        finally:
            self.stop_all()

    def start_all(self):
        """启动所有进程"""
        self.logger.info("🚀 TradingAgents-CN Pro - 启动所有服务")
        self.logger.info("=" * 60)

        # 获取进程配置
        self.process_configs = self._get_process_configs()

        if not self.process_configs:
            self.logger.error("❌ 没有找到任何可启动的服务")
            return False

        # 按顺序启动进程
        start_order = ["mongodb", "redis", "backend", "worker", "nginx"]

        for name in start_order:
            if name in self.process_configs:
                config = self.process_configs[name]

                if not self.start_process(name, config):
                    if config.get('critical', False):
                        self.logger.error(f"❌ 关键服务 {config['name']} 启动失败，停止所有服务")
                        self.stop_all()
                        return False
                    else:
                        self.logger.warning(f"⚠️  非关键服务 {config['name']} 启动失败，继续启动其他服务")

                # 等待一下再启动下一个服务
                time.sleep(1)

        # 保存 PID
        self.save_pids()

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("🎉 所有服务启动成功!")
        self.logger.info("=" * 60)
        self.logger.info("")
        self.logger.info("📍 服务地址:")
        for name, process in self.processes.items():
            config = self.process_configs[name]
            self.logger.info(f"   {config['name']}: PID {process.pid}")
        self.logger.info("")
        self.logger.info("💡 提示:")
        self.logger.info("   - 按 Ctrl+C 停止所有服务")
        self.logger.info("   - 查看日志: logs/ 目录")
        self.logger.info("   - 监控状态: python scripts/monitor/monitor_status.ps1")
        self.logger.info("")

        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='TradingAgents-CN Pro 启动脚本')
    parser.add_argument('--no-restart', action='store_true', help='禁用自动重启')
    args = parser.parse_args()

    manager = ProcessManager(auto_restart=not args.no_restart)

    if manager.start_all():
        manager.monitor()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()


