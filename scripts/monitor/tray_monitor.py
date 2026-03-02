"""
Windows 系统托盘监控程序

监控 Redis、MongoDB、Nginx、Backend 服务状态，托盘图标显示健康度，
发生错误时弹出气泡通知。随 start_all.ps1 一起启动。
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path

# 项目根目录
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _log(msg: str, level: str = "INFO"):
    """写入日志到 logs/tray_monitor.log"""
    try:
        log_file = project_root / "logs" / "tray_monitor.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except Exception:
        pass


def _log_error(msg: str):
    _log(msg, "ERROR")


_log("tray_monitor 启动, cwd=%s, root=%s" % (Path.cwd(), project_root))

try:
    import psutil
    _log("psutil 已加载")
except ImportError:
    psutil = None
    _log("psutil 未安装", "WARN")

try:
    import pystray
    from PIL import Image, ImageDraw
    _log("pystray, PIL 已加载")
except ImportError as e:
    _log_error(f"缺少依赖: {e}\n请运行: pip install pystray Pillow")
    sys.exit(1)

# 监控的进程配置（与 process_monitor.py 一致）
PROCESS_CONFIGS = [
    {"name": "Nginx", "patterns": ["nginx.exe", "nginx"]},
    {"name": "Redis", "patterns": ["redis-server.exe", "redis-server"]},
    {"name": "MongoDB", "patterns": ["mongod.exe", "mongod"]},
    {"name": "Backend", "patterns": ["app\\__main__", "app/__main__", "app\\main", "app/main", "uvicorn"]},
]


def check_process(proc_config: dict) -> bool:
    """检查进程是否在运行"""
    if not psutil:
        return False
    patterns = proc_config["patterns"]
    proc_type = "python" if "app" in str(patterns) or "uvicorn" in str(patterns) else "exe"
    try:
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                info = proc.info
                proc_name = (info.get("name") or "").lower()
                cmdline = " ".join(info.get("cmdline") or []).lower()
                for p in patterns:
                    pl = p.lower()
                    if proc_type == "python":
                        if "python" in proc_name and pl in cmdline:
                            return True
                    else:
                        if pl.replace(".exe", "") in proc_name:
                            return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False


def get_status() -> dict[str, bool]:
    """获取各服务运行状态"""
    return {c["name"]: check_process(c) for c in PROCESS_CONFIGS}


def create_icon_image(color: str, size: int = 32) -> Image.Image:
    """创建托盘图标（32x32，Windows 推荐尺寸；使用 RGB 避免透明导致不显示）"""
    img = Image.new("RGB", (size, size), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    margin = 2
    box = [margin, margin, size - margin, size - margin]
    if color == "green":
        fill = (76, 175, 80)
    elif color == "yellow":
        fill = (255, 193, 7)
    else:
        fill = (244, 67, 54)
    draw.rounded_rectangle(box, radius=4, fill=fill, outline=(255, 255, 255), width=1)
    return img


def get_icon_color(status: dict[str, bool]) -> str:
    """根据状态返回图标颜色"""
    running = sum(1 for v in status.values() if v)
    total = len(status)
    if running == total:
        return "green"
    if running == 0:
        return "red"
    return "yellow"


def load_env(root: Path) -> dict:
    """从 .env 读取配置"""
    env_path = root / ".env"
    result = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            idx = line.find("=")
            if idx > 0:
                result[line[:idx].strip()] = line[idx + 1 :].strip()
    return result


def get_web_url(root: Path) -> str:
    """获取前端访问地址"""
    env = load_env(root)
    port = int(env.get("NGINX_PORT", "80"))
    return f"http://localhost:{port}" if port != 80 else "http://localhost"


def run_tray_monitor():
    """托盘监控主逻辑"""
    _log("run_tray_monitor 开始")
    root = project_root
    status_history: dict[str, bool] = {}
    _log("创建图标图像...")
    icon_images = {
        "green": create_icon_image("green"),
        "yellow": create_icon_image("yellow"),
        "red": create_icon_image("red"),
    }
    _log("图标图像已创建")

    def on_quit(icon: pystray.Icon):
        icon.stop()

    def show_status(icon: pystray.Icon, _):
        status = get_status()
        lines = [f"{name}: {'运行中' if ok else '已停止'}" for name, ok in status.items()]
        icon.notify("\n".join(lines), "TradingAgents-CN 服务状态")

    def open_logs(icon: pystray.Icon, _):
        logs_dir = root / "logs"
        logs_dir.mkdir(exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(logs_dir))

    def collect_diagnostics(icon: pystray.Icon, _):
        script = root / "scripts" / "installer" / "collect_service_logs.ps1"
        if script.exists():
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.Popen(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                    cwd=str(root),
                    creationflags=flags,
                )
                icon.notify("诊断包将保存到 logs/ 目录", "收集诊断信息")
            except Exception:
                icon.notify("执行失败", "收集诊断信息")

    def open_web(icon: pystray.Icon, _):
        url = get_web_url(root)
        if sys.platform == "win32":
            os.startfile(url)

    def stop_services(icon: pystray.Icon, _):
        """停止所有服务（含托盘自身）"""
        stop_script = root / "scripts" / "installer" / "stop_all.ps1"
        if not stop_script.exists():
            stop_script = root / "stop_all.ps1"
        if not stop_script.exists():
            icon.notify("未找到停止脚本", "停止失败")
            return
        try:
            icon.notify("正在停止所有服务…", "TradingAgents-CN")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(stop_script)],
                cwd=str(root),
                creationflags=flags,
            )
            time.sleep(1)
            icon.stop()
        except Exception as e:
            _log_error("停止服务异常: %s" % e)
            icon.notify("停止失败: %s" % str(e)[:50], "TradingAgents-CN")

    def restart_services(icon: pystray.Icon, _):
        """Restart: run restart_all.ps1 (stop_all -SkipTray keeps tray alive, restart_all kills it at end)"""
        restart_script = root / "scripts" / "installer" / "restart_all.ps1"
        if not restart_script.exists():
            restart_script = root / "restart_all.ps1"
        if not restart_script.exists():
            icon.notify("restart_all.ps1 not found", "Restart failed")
            return
        try:
            icon.notify("Restarting services...", "TradingAgents-CN")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(restart_script)],
                cwd=str(root),
                creationflags=flags,
            )
            # Do NOT icon.stop() - tray stays alive so restart_all (child) can finish
            # restart_all uses stop_all -SkipTray, then kills tray at end
        except Exception as e:
            _log_error("restart_services error: %s" % e)
            icon.notify("Restart failed: %s" % str(e)[:50], "TradingAgents-CN")

    def update_icon(icon: pystray.Icon):
        """定时更新图标和检测状态变化（延迟启动，确保托盘先显示）"""
        time.sleep(2)
        while getattr(icon, "visible", True):
            try:
                status = get_status()
                color = get_icon_color(status)
                icon.icon = icon_images[color]
                for name, running in status.items():
                    prev = status_history.get(name)
                    if prev is not None and prev != running:
                        if running:
                            icon.notify(f"{name} 已恢复运行", "服务状态")
                        else:
                            icon.notify(f"{name} 已停止", "服务异常")
                status_history.update(status)
            except Exception:
                pass
            for _ in range(30):
                if not getattr(icon, "visible", True):
                    break
                time.sleep(1)

    _log("创建菜单...")
    menu = pystray.Menu(
        pystray.MenuItem("查看状态", show_status, default=True),
        pystray.MenuItem("打开前端", open_web),
        pystray.MenuItem("重启服务", restart_services),
        pystray.MenuItem("停止服务", stop_services),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("打开日志目录", open_logs),
        pystray.MenuItem("收集诊断包", collect_diagnostics),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", on_quit),
    )

    initial_status = get_status()
    initial_color = get_icon_color(initial_status)
    status_history.update(initial_status)
    _log("初始状态: %s, 颜色: %s" % (initial_status, initial_color))

    _log("创建 Icon 对象...")
    icon = pystray.Icon(
        "TradingAgents-CN",
        icon=icon_images[initial_color],
        title="TradingAgents-CN 服务监控",
        menu=menu,
    )

    def setup_cb(icon_obj):
        icon_obj.visible = True  # 必须显式设置，否则自定义 setup 会覆盖默认显示逻辑
        _log("setup_cb 被调用，启动 update_icon 线程")
        t = threading.Thread(target=update_icon, args=(icon_obj,), daemon=True)
        t.start()

    _log("调用 icon.run()...")
    icon.run(setup=setup_cb)
    _log("icon.run() 已返回，程序退出")


if __name__ == "__main__":
    try:
        run_tray_monitor()
    except Exception as e:
        _log_error("run_tray_monitor 异常: %s" % e)
        import traceback
        _log_error(traceback.format_exc())
        raise
