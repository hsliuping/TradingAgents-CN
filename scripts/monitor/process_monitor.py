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
    """进程监控器"""
    
    def __init__(
        self,
        check_interval: int = 30,
        log_file: str = "logs/process_monitor.log",
        pid_file: str = "logs/process_monitor.pid",
        history_file: str = "logs/process_monitor_history.json"
    ):
        """
        初始化进程监控器
        
        Args:
            check_interval: 检查间隔（秒）
            log_file: 日志文件路径
            pid_file: PID 文件路径
            history_file: 历史记录文件路径
        """
        self.check_interval = check_interval
        self.log_file = log_file
        self.pid_file = pid_file
        self.history_file = history_file
        self.running = False
        
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
        
        # 确保输出立即刷新
        import sys
        sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None
    
    def _get_monitored_processes(self) -> List[Dict[str, any]]:
        """
        获取要监控的进程列表
        
        Returns:
            进程配置列表
        """
        # 获取项目根目录
        root = Path(__file__).parent.parent.parent
        
        return [
            {
                "name": "Worker",
                "type": "python",
                "patterns": [
                    "python.*worker.*__main__",
                    "python.*app\\\\worker\\\\__main__",
                    "python.*app/worker/__main__"
                ],
                "description": "分析任务 Worker 进程"
            },
            {
                "name": "Nginx",
                "type": "executable",
                "patterns": ["nginx.exe", "nginx"],
                "description": "Nginx Web 服务器"
            },
            {
                "name": "Redis",
                "type": "executable",
                "patterns": ["redis-server.exe", "redis-server"],
                "description": "Redis 缓存服务器"
            },
            {
                "name": "MongoDB",
                "type": "executable",
                "patterns": ["mongod.exe", "mongod"],
                "description": "MongoDB 数据库服务器"
            },
            {
                "name": "Backend API",
                "type": "python",
                "patterns": [
                    "python.*uvicorn.*app.main",
                    "python.*app\\\\main",
                    "python.*app/main"
                ],
                "description": "FastAPI 后端服务"
            }
        ]
    
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
        self.logger.info("🚀 进程监控守护进程启动")
        self.logger.info(f"📊 监控间隔: {self.check_interval} 秒")
        self.logger.info(f"📝 日志文件: {self.log_file}")
        self.logger.info(f"📋 监控进程数: {len(self.monitored_processes)}")
        self.logger.info("=" * 70)
        
        if not PSUTIL_AVAILABLE:
            self.logger.warning("⚠️ psutil 未安装，将使用 PowerShell 方法（可能较慢）")
            self.logger.warning("💡 建议安装: pip install psutil")
        
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
                
                # 更新历史记录
                self.process_history.update(current_status)
                self._save_history()
                
                # 输出当前状态摘要（每 10 次检查输出一次）
                if not hasattr(self, '_check_count'):
                    self._check_count = 0
                self._check_count += 1
                
                if self._check_count % 10 == 0:
                    self.logger.info("📊 进程状态摘要:")
                    for name, info in current_status.items():
                        status_icon = "✅" if info.status == ProcessStatus.RUNNING else "❌"
                        pid_str = f"PID: {info.pid}" if info.pid else "未运行"
                        memory_str = f", 内存: {info.memory_mb:.2f} MB" if info.memory_mb else ""
                        self.logger.info(f"   {status_icon} [{name}] {pid_str}{memory_str}")
                
                # 等待下次检查
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("\n⏹️  收到中断信号，正在关闭监控守护进程...")
        except Exception as e:
            self.logger.error(f"❌ 监控循环异常: {e}", exc_info=True)
        finally:
            self.running = False
            self.remove_pid()
            self.logger.info("✅ 进程监控守护进程已退出")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='进程监控守护进程')
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='检查间隔（秒），默认 30 秒'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='logs/process_monitor.log',
        help='日志文件路径，默认 logs/process_monitor.log'
    )
    parser.add_argument(
        '--pid-file',
        type=str,
        default='logs/process_monitor.pid',
        help='PID 文件路径，默认 logs/process_monitor.pid'
    )
    parser.add_argument(
        '--history-file',
        type=str,
        default='logs/process_monitor_history.json',
        help='历史记录文件路径，默认 logs/process_monitor_history.json'
    )
    
    args = parser.parse_args()
    
    # 创建监控器
    monitor = ProcessMonitor(
        check_interval=args.interval,
        log_file=args.log_file,
        pid_file=args.pid_file,
        history_file=args.history_file
    )
    
    # 运行监控
    monitor.run()


if __name__ == "__main__":
    main()
