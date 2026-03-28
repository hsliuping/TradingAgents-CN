#!/usr/bin/env python3
"""
TradingAgents-CN v1.0.0-preview 前端启动脚本
"""

import subprocess
import sys
import time
import shutil
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def check_node_version():
    """检查Node.js版本"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Node.js版本: {version}")
            
            # 检查版本是否满足要求 (>=18.0.0)
            version_num = version.replace('v', '').split('.')[0]
            if int(version_num) >= 18:
                return True
            else:
                print(f"❌ Node.js版本过低，需要 >= 18.0.0，当前版本: {version}")
                return False
        else:
            print("❌ Node.js未安装")
            return False
    except FileNotFoundError:
        print("❌ Node.js未安装")
        return False

def check_npm():
    """检查npm"""
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ npm版本: {version}")
            return True
        else:
            print("❌ npm未安装")
            return False
    except FileNotFoundError:
        print("❌ npm未安装")
        return False

def detect_frontend_runner():
    """优先使用 pnpm，没有再退回 corepack+yarn。"""
    if shutil.which('pnpm'):
        return ['pnpm']
    if shutil.which('corepack'):
        return ['corepack', 'yarn']
    return None

def install_dependencies():
    """安装依赖"""
    print("📦 安装前端依赖...")
    
    frontend_dir = get_project_root() / "frontend"
    
    try:
        # 检查package.json是否存在
        if not (frontend_dir / "package.json").exists():
            print("❌ package.json不存在")
            return False
        
        runner = detect_frontend_runner()
        if not runner:
            print("❌ 未找到 pnpm 或 corepack，无法安装前端依赖")
            return False

        # 安装依赖
        result = subprocess.run(
            runner + ['install', '--frozen-lockfile'],
            cwd=frontend_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ 依赖安装成功")
            return True
        else:
            print(f"❌ 依赖安装失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 安装依赖时出错: {e}")
        return False

def start_dev_server():
    """启动开发服务器"""
    print("🚀 启动前端开发服务器...")
    
    frontend_dir = get_project_root() / "frontend"
    
    try:
        runner = detect_frontend_runner()
        if not runner:
            print("❌ 未找到 pnpm 或 corepack，无法启动前端开发服务器")
            return False

        # 启动开发服务器
        process = subprocess.Popen(
            runner + ['dev', '--host', '0.0.0.0', '--port', '3000'],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        print("✅ 开发服务器已启动")
        print("📍 前端地址: http://localhost:3000")
        print("💡 提示: 按 Ctrl+C 停止服务器")
        print("-" * 50)
        
        # 实时输出日志
        try:
            for line in process.stdout:
                print(line.rstrip())
        except KeyboardInterrupt:
            print("\n🛑 收到中断信号，正在停止服务器...")
            process.terminate()
            process.wait()
            print("✅ 前端服务器已停止")
            
    except Exception as e:
        print(f"❌ 启动开发服务器失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 TradingAgents-CN v1.0.0-preview 前端启动器")
    print("=" * 60)
    
    # 检查Node.js
    if not check_node_version():
        print("\n💡 请安装Node.js 18或更高版本:")
        print("   https://nodejs.org/")
        sys.exit(1)
    
    # 检查npm
    if not check_npm():
        print("\n💡 请安装npm:")
        print("   npm通常随Node.js一起安装")
        sys.exit(1)
    
    # 检查前端目录
    frontend_dir = get_project_root() / "frontend"
    if not frontend_dir.exists():
        print("❌ frontend目录不存在")
        sys.exit(1)
    
    # 检查是否需要安装依赖
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("📦 检测到首次运行，需要安装依赖...")
        if not install_dependencies():
            sys.exit(1)
    else:
        print("✅ 依赖已安装")
    
    print("\n🎯 准备启动前端服务...")
    time.sleep(1)
    
    # 启动开发服务器
    start_dev_server()

if __name__ == "__main__":
    main()
