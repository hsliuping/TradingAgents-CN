"""最小化托盘测试 - 用于排查 pystray 在 Windows 上不显示的问题"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 诊断：写入启动日志
log_file = project_root / "logs" / "tray_test.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
with open(log_file, "a", encoding="utf-8") as f:
    f.write(f"[{__import__('datetime').datetime.now()}] 启动 cwd={Path.cwd()} root={project_root}\n")

from PIL import Image, ImageDraw
import pystray

def create_icon():
    img = Image.new("RGB", (32, 32), (76, 175, 80))
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, 30, 30], fill=(76, 175, 80), outline=(255, 255, 255))
    return img

def on_quit(icon, _):
    icon.stop()

icon = pystray.Icon("test", icon=create_icon(), title="TradingAgents 测试",
    menu=pystray.Menu(pystray.MenuItem("退出", on_quit, default=True)))
icon.run()
