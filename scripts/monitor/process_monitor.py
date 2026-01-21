"""
进程监控守护进程

监控关键进程的状态，包括：
- Worker 进程
- Nginx
- Redis
- MongoDB

功能：
1. 定时扫描进程状态
2. 检测进程退出
3. 记录退出代码和原因
4. 输出告警信息
"""

import os
import sys
import time
import logging
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 尝试导入 psutil（如果可用）
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class ProcessStatus(Enum):
    """进程状态"""
    RUNNING = "running"
    STOPPED = "stopped"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class ProcessInfo:
    """进程信息"""
    name: str
    pid: Optional[int] = None
    status: ProcessStatus = ProcessStatus.NOT_FOUND
    exit_code: Optional[int] = None
    exit_time: Optional[str] = None
    error_message: Optional[str] = None
    command_line: Optional[str] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    start_time: Optional[str] = None


class ProcessMonitor:
    """进程监控器 - 支持自动重启"""

    def __init__(
        self,
        check_interval: int = 30,
        log_file: str = "logs/process_monitor.log",
        pid_file: str = "logs/process_monitor.pid",
        history_file: str = "logs/process_monitor_history.json",
        auto_restart: bool = False,
        restart_delay: int = 5,
        max_restarts: int = 3,
        restart_window: int = 300
    ):
        """
        初始化进程监控器

        Args:
            check_interval: 检查间隔（秒）
            log_file: 日志文件路径
            pid_file: PID 文件路径
            history_file: 历史记录文件路径
            auto_restart: 是否自动重启已退出的进程
            restart_delay: 重启延迟（秒）
            max_restarts: 在 restart_window 时间内最大重启次数
            restart_window: 重启计数窗口（秒）
        """
        self.check_interval = check_interval
        self.log_file = log_file
        self.pid_file = pid_file
        self.history_file = history_file
        self.running = False

        # 自动重启配置
        self.auto_restart = auto_restart
        self.restart_delay = restart_delay
        self.max_restarts = max_restarts
        self.restart_window = restart_window

        # 重启计数器 {进程名: [(时间戳, 成功/失败), ...]}
        self.restart_history: Dict[str, List[Tuple[float, bool]]] = {}

        # 设置日志
        self._setup_logging()
        self.logger = logging.getLogger(__name__)

        # 进程历史记录（用于检测状态变化）
        self.process_history: Dict[str, ProcessInfo] = {}

        # 加载历史记录
        self._load_history()

        # 定义要监控的进程
        self.monitored_processes = self._get_monitored_processes()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 确保日志目录存在
        log_dir = Path(self.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置日志格式
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # 创建格式化器
        formatter = logging.Formatter(log_format, date_format)
        
        # 文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        # 控制台处理器（确保输出到控制台）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()  # 清除现有处理器
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # 确保输出立即刷新（sys 已在文件开头导入，不需要重复导入）
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    def _get_monitored_processes(self) -> List[Dict[str, any]]:
        """
        获取要监控的进程列表

        Returns:
            进程配置列表
        """
        # 获取项目根目录
        root = Path(__file__).parent.parent.parent

        # 检测 Python 路径和项目根目录
        python_exe = self._detect_python_exe()
        project_root = str(root)

        return [
            {
                "name": "Worker",
                "type": "python",
                "patterns": [
                    "worker",
                    "app\\worker\\__main__",
                    "app/worker/__main__"
                ],
                "description": "分析任务 Worker 进程",
                "restart_enabled": True,  # 允许自动重启
                "restart_command": self._get_worker_restart_cmd(python_exe, project_root)
            },
            {
                "name": "Nginx",
                "type": "executable",
                "patterns": ["nginx.exe", "nginx"],
                "description": "Nginx Web 服务器",
                "restart_enabled": False  # 不自动重启
            },
            {
                "name": "Redis",
                "type": "executable",
                "patterns": ["redis-server.exe", "redis-server"],
                "description": "Redis 缓存服务器",
                "restart_enabled": False
            },
            {
                "name": "MongoDB",
                "type": "executable",
                "patterns": ["mongod.exe", "mongod"],
                "description": "MongoDB 数据库服务器",
                "restart_enabled": False
            },
            {
                "name": "Backend API",
                "type": "python",
                "patterns": [
                    "app\\__main__",
                    "app/__main__",
                    "app\\main",
                    "app/main",
                    "uvicorn"
                ],
                "description": "FastAPI 后端服务",
                "restart_enabled": True,  # 允许自动重启
                "restart_command": self._get_backend_restart_cmd(python_exe, project_root)
            }
        ]

    def _detect_python_exe(self) -> str:
        """检测 Python 可执行文件路径"""
        root = Path(__file__).parent.parent.parent

        # 尝试便携版 Python
        portable_python = root / "vendors" / "python" / "python.exe"
        if portable_python.exists():
            return str(portable_python)

        # 尝试虚拟环境 Python
        venv_python = root / "venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return str(venv_python)

        env_python = root / "env" / "Scripts" / "python.exe"
        if env_python.exists():
            return str(env_python)

        # 使用系统 Python
        return sys.executable

    def _get_worker_restart_cmd(self, python_exe: str, project_root: str) -> List[str]:
        """获取 Worker 重启命令"""
        worker_main = Path(project_root) / "app" / "worker" / "__main__.py"
        return [python_exe, str(worker_main)]

    def _get_backend_restart_cmd(self, python_exe: str, project_root: str) -> List[str]:
        """获取 Backend 重启命令"""
        app_main = Path(project_root) / "app" / "main.py"
        return [python_exe, str(app_main)]

    def _can_restart(self, process_name: str) -> bool:
        """
        检查是否可以重启进程（防止无限重启）

        Args:
            process_name: 进程名称

        Returns:
            是否可以重启
        """
        now = time.time()

        # 获取该进程的重启历史
        history = self.restart_history.get(process_name, [])

        # 清理过期的重启记录（超过窗口期）
        history = [(t, s) for t, s in history if now - t < self.restart_window]
        self.restart_history[process_name] = history

        # 检查重启次数是否超过限制
        if len(history) >= self.max_restarts:
            self.logger.warning(
                f"[{process_name}] 在 {self.restart_window} 秒内已重启 {len(history)} 次，"
                f"超过最大限制 {self.max_restarts}，暂停自动重启"
            )
            return False

        return True

    def _record_restart(self, process_name: str, success: bool):
        """记录重启尝试"""
        if process_name not in self.restart_history:
            self.restart_history[process_name] = []
        self.restart_history[process_name].append((time.time(), success))

    def restart_process(self, process_config: Dict) -> bool:
        """
        重启进程

        Args:
            process_config: 进程配置

        Returns:
            是否成功启动
        """
        name = process_config['name']

        # 检查是否允许重启
        if not process_config.get('restart_enabled', False):
            self.logger.info(f"[{name}] 未启用自动重启")
            return False

        # 检查重启命令
        restart_cmd = process_config.get('restart_command')
        if not restart_cmd:
            self.logger.warning(f"[{name}] 没有配置重启命令")
            return False

        # 检查重启频率限制
        if not self._can_restart(name):
            return False

        try:
            self.logger.info(f"[{name}] 尝试重启进程...")
            self.logger.info(f"   命令: {' '.join(restart_cmd)}")

            # 等待一段时间再重启
            if self.restart_delay > 0:
                self.logger.info(f"   等待 {self.restart_delay} 秒后重启...")
                time.sleep(self.restart_delay)

            # 获取项目根目录
            root = Path(__file__).parent.parent.parent

            # 设置环境变量
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'

            # 启动进程
            if sys.platform == 'win32':
                # Windows: 使用 CREATE_NEW_PROCESS_GROUP 创建独立进程
                process = subprocess.Popen(
                    restart_cmd,
                    cwd=str(root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )
            else:
                # Linux/Mac
                process = subprocess.Popen(
                    restart_cmd,
                    cwd=str(root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )

            self.logger.info(f"[{name}] 进程已启动，新 PID: {process.pid}")
            self._record_restart(name, True)
            return True

        except Exception as e:
            self.logger.error(f"[{name}] 重启失败: {e}")
            self._record_restart(name, False)
            return False
    
    def _load_history(self):
        """加载历史记录"""
        try:
            if Path(self.history_file).exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, info in data.items():
                        self.process_history[name] = ProcessInfo(
                            name=info['name'],
                            pid=info.get('pid'),
                            status=ProcessStatus(info.get('status', 'not_found')),
                            exit_code=info.get('exit_code'),
                            exit_time=info.get('exit_time'),
                            error_message=info.get('error_message'),
                            command_line=info.get('command_line'),
                            memory_mb=info.get('memory_mb'),
                            cpu_percent=info.get('cpu_percent'),
                            start_time=info.get('start_time')
                        )
        except Exception as e:
            self.logger.warning(f"加载历史记录失败: {e}")
    
    def _save_history(self):
        """保存历史记录"""
        try:
            history_dir = Path(self.history_file).parent
            history_dir.mkdir(parents=True, exist_ok=True)
            
            data = {}
            for name, info in self.process_history.items():
                data[name] = {
                    'name': info.name,
                    'pid': info.pid,
                    'status': info.status.value,
                    'exit_code': info.exit_code,
                    'exit_time': info.exit_time,
                    'error_message': info.error_message,
                    'command_line': info.command_line,
                    'memory_mb': info.memory_mb,
                    'cpu_percent': info.cpu_percent,
                    'start_time': info.start_time
                }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"保存历史记录失败: {e}")
    
    def _check_process_psutil(self, process_config: Dict) -> Optional[ProcessInfo]:
        """
        使用 psutil 检查进程（推荐方法）
        
        Args:
            process_config: 进程配置
            
        Returns:
            进程信息，如果未找到返回 None
        """
        if not PSUTIL_AVAILABLE:
            return None
        
        try:
            name = process_config['name']
            patterns = process_config['patterns']
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'memory_info', 'cpu_percent', 'create_time']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info.get('name', '').lower()
                    cmdline = ' '.join(proc_info.get('cmdline', [])).lower() if proc_info.get('cmdline') else ''
                    
                    # 检查是否匹配模式
                    matched = False
                    for pattern in patterns:
                        pattern_lower = pattern.lower()
                        if pattern_lower in proc_name or pattern_lower in cmdline:
                            # 进一步验证（避免误匹配）
                            if process_config['type'] == 'python':
                                if 'python' in proc_name and any(p in cmdline for p in patterns):
                                    matched = True
                                    break
                            else:
                                if pattern_lower.replace('.exe', '') in proc_name:
                                    matched = True
                                    break
                    
                    if matched:
                        # 计算内存使用（MB）
                        memory_mb = None
                        if proc_info.get('memory_info'):
                            memory_mb = proc_info['memory_info'].rss / 1024 / 1024
                        
                        # 获取 CPU 使用率
                        cpu_percent = proc_info.get('cpu_percent')
                        if cpu_percent is None:
                            try:
                                cpu_percent = proc.cpu_percent(interval=0.1)
                            except:
                                cpu_percent = None
                        
                        # 获取启动时间
                        start_time = None
                        if proc_info.get('create_time'):
                            start_time = datetime.fromtimestamp(proc_info['create_time']).isoformat()
                        
                        # 获取命令行
                        command_line = ' '.join(proc_info.get('cmdline', [])) if proc_info.get('cmdline') else None
                        
                        return ProcessInfo(
                            name=name,
                            pid=proc_info['pid'],
                            status=ProcessStatus.RUNNING,
                            command_line=command_line,
                            memory_mb=memory_mb,
                            cpu_percent=cpu_percent,
                            start_time=start_time
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    self.logger.debug(f"检查进程时出错: {e}")
                    continue
            
            return None
        except Exception as e:
            self.logger.error(f"使用 psutil 检查进程失败: {e}")
            return None
    
    def _check_process_powershell(self, process_config: Dict) -> Optional[ProcessInfo]:
        """
        使用 PowerShell 检查进程（Windows 备用方法）
        
        Args:
            process_config: 进程配置
            
        Returns:
            进程信息，如果未找到返回 None
        """
        try:
            name = process_config['name']
            patterns = process_config['patterns']
            
            # 构建 PowerShell 命令
            # 获取所有进程，包括命令行参数
            ps_cmd = """
            Get-Process | Where-Object {
                $proc = $_
                $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
                $matched = $false
                $patterns = @('""" + "', '".join(patterns) + """')
                foreach ($pattern in $patterns) {
                    if ($proc.ProcessName -like "*$pattern*" -or $cmdline -like "*$pattern*") {
                        $matched = $true
                        break
                    }
                }
                $matched
            } | Select-Object Id, ProcessName, @{Name='CommandLine';Expression={(Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine}}, @{Name='WorkingSet';Expression={$_.WorkingSet}}, @{Name='CPU';Expression={$_.CPU}}, @{Name='StartTime';Expression={$_.StartTime}} | ConvertTo-Json
            """
            
            result = subprocess.run(
                ['powershell', '-Command', ps_cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    processes = json.loads(result.stdout)
                    if not isinstance(processes, list):
                        processes = [processes]
                    
                    for proc in processes:
                        # 验证是否真的匹配
                        proc_name = proc.get('ProcessName', '').lower()
                        cmdline = (proc.get('CommandLine') or '').lower()
                        
                        matched = False
                        for pattern in patterns:
                            pattern_lower = pattern.lower()
                            if pattern_lower in proc_name or pattern_lower in cmdline:
                                matched = True
                                break
                        
                        if matched:
                            # 计算内存使用（MB）
                            memory_mb = None
                            if proc.get('WorkingSet'):
                                memory_mb = proc['WorkingSet'] / 1024 / 1024
                            
                            # CPU 使用率（PowerShell 返回的是累计 CPU 时间，不是百分比）
                            cpu_percent = None
                            
                            # 启动时间
                            start_time = None
                            if proc.get('StartTime'):
                                try:
                                    start_time = datetime.fromisoformat(proc['StartTime'].replace('/', '-')).isoformat()
                                except:
                                    pass
                            
                            return ProcessInfo(
                                name=name,
                                pid=proc.get('Id'),
                                status=ProcessStatus.RUNNING,
                                command_line=proc.get('CommandLine'),
                                memory_mb=memory_mb,
                                cpu_percent=cpu_percent,
                                start_time=start_time
                            )
                except json.JSONDecodeError:
                    pass
            
            return None
        except Exception as e:
            self.logger.debug(f"使用 PowerShell 检查进程失败: {e}")
            return None
    
    def check_process(self, process_config: Dict) -> ProcessInfo:
        """
        检查进程状态
        
        Args:
            process_config: 进程配置
            
        Returns:
            进程信息
        """
        name = process_config['name']
        
        # 优先使用 psutil
        if PSUTIL_AVAILABLE:
            proc_info = self._check_process_psutil(process_config)
        else:
            proc_info = None
        
        # 如果 psutil 不可用或未找到，尝试 PowerShell
        if proc_info is None:
            if sys.platform == 'win32':
                proc_info = self._check_process_powershell(process_config)
        
        # 如果仍未找到
        if proc_info is None:
            proc_info = ProcessInfo(
                name=name,
                status=ProcessStatus.NOT_FOUND
            )
        
        return proc_info
    
    def check_all_processes(self) -> Dict[str, ProcessInfo]:
        """
        检查所有监控的进程
        
        Returns:
            进程信息字典
        """
        results = {}
        
        for process_config in self.monitored_processes:
            try:
                proc_info = self.check_process(process_config)
                results[process_config['name']] = proc_info
            except Exception as e:
                self.logger.error(f"检查进程 {process_config['name']} 失败: {e}")
                results[process_config['name']] = ProcessInfo(
                    name=process_config['name'],
                    status=ProcessStatus.ERROR,
                    error_message=str(e)
                )
        
        return results
    
    def detect_changes(self, current_status: Dict[str, ProcessInfo]) -> List[Tuple[str, ProcessInfo, Optional[ProcessInfo]]]:
        """
        检测进程状态变化
        
        Args:
            current_status: 当前进程状态
            
        Returns:
            变化列表：(进程名, 当前状态, 之前状态)
        """
        changes = []
        
        for name, current_info in current_status.items():
            previous_info = self.process_history.get(name)
            
            # 检测状态变化
            if previous_info is None:
                # 新发现的进程
                if current_info.status == ProcessStatus.RUNNING:
                    changes.append((name, current_info, None))
            elif previous_info.status != current_info.status:
                # 状态发生变化
                changes.append((name, current_info, previous_info))
            elif current_info.status == ProcessStatus.RUNNING and previous_info.pid != current_info.pid:
                # 进程重启（PID 变化）
                changes.append((name, current_info, previous_info))
        
        return changes
    
    def report_changes(self, changes: List[Tuple[str, ProcessInfo, Optional[ProcessInfo]]]):
        """
        报告进程状态变化
        
        Args:
            changes: 变化列表
        """
        for name, current_info, previous_info in changes:
            if previous_info is None:
                # 新进程启动
                self.logger.info(
                    f"✅ [{name}] 进程已启动\n"
                    f"   PID: {current_info.pid}\n"
                    f"   命令行: {current_info.command_line}\n"
                    f"   内存: {current_info.memory_mb:.2f} MB" if current_info.memory_mb else ""
                )
            elif current_info.status == ProcessStatus.RUNNING and previous_info.status != ProcessStatus.RUNNING:
                # 进程恢复运行
                self.logger.info(
                    f"✅ [{name}] 进程已恢复运行\n"
                    f"   新 PID: {current_info.pid}\n"
                    f"   之前状态: {previous_info.status.value}\n"
                    f"   退出代码: {previous_info.exit_code}" if previous_info.exit_code else ""
                )
            elif current_info.status != ProcessStatus.RUNNING and previous_info.status == ProcessStatus.RUNNING:
                # 进程退出
                exit_code_str = f"退出代码: {current_info.exit_code}" if current_info.exit_code is not None else "退出代码: 未知"
                exit_time_str = f"退出时间: {current_info.exit_time}" if current_info.exit_time else ""
                error_str = f"错误信息: {current_info.error_message}" if current_info.error_message else ""
                
                self.logger.error(
                    f"❌ [{name}] 进程已退出！\n"
                    f"   之前 PID: {previous_info.pid}\n"
                    f"   当前状态: {current_info.status.value}\n"
                    f"   {exit_code_str}\n"
                    f"   {exit_time_str}\n"
                    f"   {error_str}\n"
                    f"   命令行: {previous_info.command_line}\n"
                    f"   💡 建议: 检查日志文件或系统事件查看器获取详细错误信息"
                )
            elif current_info.pid != previous_info.pid and current_info.status == ProcessStatus.RUNNING:
                # 进程重启（PID 变化）
                self.logger.warning(
                    f"⚠️ [{name}] 进程已重启\n"
                    f"   旧 PID: {previous_info.pid}\n"
                    f"   新 PID: {current_info.pid}\n"
                    f"   退出代码: {previous_info.exit_code}" if previous_info.exit_code else ""
                )
    
    def save_pid(self):
        """保存守护进程 PID"""
        try:
            pid_dir = Path(self.pid_file).parent
            pid_dir.mkdir(parents=True, exist_ok=True)
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            self.logger.warning(f"保存 PID 文件失败: {e}")
    
    def remove_pid(self):
        """删除 PID 文件"""
        try:
            if Path(self.pid_file).exists():
                Path(self.pid_file).unlink()
        except Exception as e:
            self.logger.warning(f"删除 PID 文件失败: {e}")
    
    def run(self):
        """运行监控循环"""
        self.logger.info("=" * 70)
        self.logger.info("Process Monitor Daemon Started")
        self.logger.info(f"Check interval: {self.check_interval} seconds")
        self.logger.info(f"Log file: {self.log_file}")
        self.logger.info(f"Monitored processes: {len(self.monitored_processes)}")
        self.logger.info(f"Auto restart: {'ENABLED' if self.auto_restart else 'DISABLED'}")
        if self.auto_restart:
            self.logger.info(f"  - Max restarts: {self.max_restarts} in {self.restart_window}s")
            self.logger.info(f"  - Restart delay: {self.restart_delay}s")
        self.logger.info("=" * 70)

        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil not installed, using PowerShell method (slower)")
            self.logger.warning("Recommend: pip install psutil")

        # 保存 PID
        self.save_pid()

        self.running = True

        try:
            while self.running:
                # 检查所有进程
                current_status = self.check_all_processes()

                # 检测变化
                changes = self.detect_changes(current_status)

                # 报告变化
                if changes:
                    self.report_changes(changes)

                    # 如果启用了自动重启，尝试重启已退出的进程
                    if self.auto_restart:
                        self._try_restart_stopped_processes(changes, current_status)

                # 更新历史记录
                self.process_history.update(current_status)
                self._save_history()

                # 输出当前状态摘要（每 10 次检查输出一次）
                if not hasattr(self, '_check_count'):
                    self._check_count = 0
                self._check_count += 1

                if self._check_count % 10 == 0:
                    self.logger.info("Process status summary:")
                    for name, info in current_status.items():
                        status_icon = "[OK]" if info.status == ProcessStatus.RUNNING else "[STOPPED]"
                        pid_str = f"PID: {info.pid}" if info.pid else "Not running"
                        memory_str = f", Memory: {info.memory_mb:.2f} MB" if info.memory_mb else ""
                        self.logger.info(f"   {status_icon} [{name}] {pid_str}{memory_str}")

                # 等待下次检查
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            self.logger.info("\nReceived interrupt signal, shutting down...")
        except Exception as e:
            self.logger.error(f"Monitor loop error: {e}", exc_info=True)
        finally:
            self.running = False
            self.remove_pid()
            self.logger.info("Process Monitor Daemon stopped")

    def _try_restart_stopped_processes(
        self,
        changes: List[Tuple[str, ProcessInfo, Optional[ProcessInfo]]],
        current_status: Dict[str, ProcessInfo]
    ):
        """
        尝试重启已停止的进程

        Args:
            changes: 进程状态变化列表
            current_status: 当前进程状态
        """
        for name, current_info, previous_info in changes:
            # 只处理从运行变为停止的情况
            if previous_info and previous_info.status == ProcessStatus.RUNNING and current_info.status != ProcessStatus.RUNNING:
                # 查找进程配置
                process_config = None
                for config in self.monitored_processes:
                    if config['name'] == name:
                        process_config = config
                        break

                if process_config:
                    self.logger.info(f"[{name}] Attempting auto restart...")
                    success = self.restart_process(process_config)
                    if success:
                        self.logger.info(f"[{name}] Auto restart initiated")
                    else:
                        self.logger.warning(f"[{name}] Auto restart failed or disabled")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Process Monitor Daemon - Monitor and optionally auto-restart processes'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Check interval in seconds (default: 30)'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='logs/process_monitor.log',
        help='Log file path (default: logs/process_monitor.log)'
    )
    parser.add_argument(
        '--pid-file',
        type=str,
        default='logs/process_monitor.pid',
        help='PID file path (default: logs/process_monitor.pid)'
    )
    parser.add_argument(
        '--history-file',
        type=str,
        default='logs/process_monitor_history.json',
        help='History file path (default: logs/process_monitor_history.json)'
    )
    parser.add_argument(
        '--auto-restart',
        action='store_true',
        default=False,
        help='Enable auto restart for stopped processes (default: disabled)'
    )
    parser.add_argument(
        '--restart-delay',
        type=int,
        default=5,
        help='Delay before restart in seconds (default: 5)'
    )
    parser.add_argument(
        '--max-restarts',
        type=int,
        default=3,
        help='Max restarts within restart window (default: 3)'
    )
    parser.add_argument(
        '--restart-window',
        type=int,
        default=300,
        help='Restart count window in seconds (default: 300)'
    )

    args = parser.parse_args()

    # 创建监控器
    monitor = ProcessMonitor(
        check_interval=args.interval,
        log_file=args.log_file,
        pid_file=args.pid_file,
        history_file=args.history_file,
        auto_restart=args.auto_restart,
        restart_delay=args.restart_delay,
        max_restarts=args.max_restarts,
        restart_window=args.restart_window
    )

    # 运行监控
    monitor.run()


if __name__ == "__main__":
    main()
