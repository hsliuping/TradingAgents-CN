#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Windows 快捷方式（.lnk）的图标信息
"""

import sys
from pathlib import Path

try:
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False
    print("⚠️  win32com not available, using alternative method")

def check_shortcut_icon_win32com(lnk_path: str):
    """使用 win32com 检查快捷方式图标（最准确的方法）"""
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_path)
        
        print(f"📁 快捷方式路径: {lnk_path}")
        print(f"🎯 目标文件: {shortcut.TargetPath}")
        print(f"📝 参数: {shortcut.Arguments}")
        print(f"💼 工作目录: {shortcut.WorkingDirectory}")
        print(f"🖼️  图标路径: {shortcut.IconLocation}")
        print(f"📋 描述: {shortcut.Description}")
        print()
        
        # 解析图标路径
        icon_location = shortcut.IconLocation
        if icon_location:
            if ',' in icon_location:
                icon_path, icon_index = icon_location.rsplit(',', 1)
                icon_index = int(icon_index.strip())
            else:
                icon_path = icon_location
                icon_index = 0
            
            print(f"🔍 图标详细信息:")
            print(f"   图标文件: {icon_path}")
            print(f"   图标索引: {icon_index}")
            
            icon_file = Path(icon_path)
            if icon_file.exists():
                print(f"   ✅ 图标文件存在")
                print(f"   📦 文件大小: {icon_file.stat().st_size} 字节")
                
                # 如果是 .ico 文件，检查尺寸
                if icon_file.suffix.lower() == '.ico':
                    print(f"   📐 文件类型: ICO")
                    # 可以调用之前的检查脚本
                    try:
                        import subprocess
                        script_path = Path(__file__).parent / "check_icon_info.py"
                        if script_path.exists():
                            result = subprocess.run(
                                [sys.executable, str(script_path), str(icon_file)],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                print(f"   📊 图标尺寸信息:")
                                for line in result.stdout.split('\n'):
                                    if 'Icon size summary' in line or 'x' in line and 'icon' in line.lower():
                                        print(f"      {line.strip()}")
                    except Exception as e:
                        print(f"   ⚠️  无法检查图标尺寸: {e}")
            else:
                print(f"   ❌ 图标文件不存在！")
                print(f"   💡 这可能是图标显示为白色的原因")
        else:
            print(f"   ⚠️  未指定图标路径（使用默认图标）")
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()

def check_shortcut_icon_powershell(lnk_path: str):
    """使用 PowerShell 检查快捷方式图标（备用方法）"""
    import subprocess
    
    ps_script = f'''
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut("{lnk_path}")
Write-Host "Target: $($shortcut.TargetPath)"
Write-Host "Arguments: $($shortcut.Arguments)"
Write-Host "WorkingDirectory: $($shortcut.WorkingDirectory)"
Write-Host "IconLocation: $($shortcut.IconLocation)"
Write-Host "Description: $($shortcut.Description)"
'''
    
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(result.stdout)
        if result.stderr:
            print("错误:", result.stderr)
    except Exception as e:
        print(f"❌ PowerShell 检查失败: {e}")

def main():
    if len(sys.argv) > 1:
        lnk_path = sys.argv[1]
    else:
        # 默认检查开始菜单中的快捷方式
        start_menu_paths = [
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "TradingAgents-CN Pro",
            Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs/TradingAgents-CN Pro"),
        ]
        
        lnk_files = []
        for start_menu_path in start_menu_paths:
            if start_menu_path.exists():
                lnk_files.extend(list(start_menu_path.glob("*.lnk")))
        
        if not lnk_files:
            print("❌ 未找到快捷方式文件")
            print("💡 使用方法: python check_shortcut_icon.py <快捷方式路径>")
            print("   例如: python check_shortcut_icon.py \"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\TradingAgents-CN Pro\\Start TradingAgents-CN.lnk\"")
            return
        
        print(f"📋 找到 {len(lnk_files)} 个快捷方式:")
        for i, lnk_file in enumerate(lnk_files, 1):
            print(f"   {i}. {lnk_file.name}")
        print()
        
        # 检查第一个快捷方式
        lnk_path = str(lnk_files[0])
        print(f"🔍 检查: {lnk_files[0].name}")
        print()
    
    lnk_file = Path(lnk_path)
    if not lnk_file.exists():
        print(f"❌ 文件不存在: {lnk_path}")
        return
    
    if HAS_WIN32COM:
        check_shortcut_icon_win32com(lnk_path)
    else:
        print("⚠️  win32com 不可用，使用 PowerShell 方法")
        check_shortcut_icon_powershell(lnk_path)

if __name__ == "__main__":
    main()
