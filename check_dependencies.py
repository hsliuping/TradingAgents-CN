#!/usr/bin/env python3
"""
环境依赖检查脚本
检查并确保所有必要的依赖包已正确安装
"""

import os
import sys
import importlib
import subprocess
from pathlib import Path

# 添加项目根目录到系统路径
sys.path.append('.')

# 设置环境变量
os.environ['PYTHONPATH'] = '.'

# 关键依赖列表
REQUIRED_PACKAGES = [
    # LangChain相关
    'langchain_openai',
    'langchain_anthropic',
    'langchain_google_genai',
    # 项目内部模块
    'tradingagents',
    'tradingagents.utils.logging_init',
    'tradingagents.dataflows.data_source_manager',
    'tradingagents.graph.trading_graph',
]

# 可选依赖列表
OPTIONAL_PACKAGES = [
    'streamlit',
    'pandas',
    'numpy',
    'matplotlib',
    'tensorflow',
    'torch',
    'akshare',
    'baostock',
    'tushare',
]

print("=== TradingAgents-CN 环境依赖检查 ===")

# 检查关键依赖
print("\n--- 检查关键依赖 ---")
missing_packages = []

for package in REQUIRED_PACKAGES:
    try:
        # 尝试导入模块
        module = importlib.import_module(package)
        print(f"✅ {package} 已安装")
    except ImportError as e:
        print(f"❌ {package} 导入失败: {e}")
        # 提取基础包名（去除子模块路径）
        base_package = package.split('.')[0]
        if base_package not in missing_packages and base_package not in ['tradingagents']:
            missing_packages.append(base_package)

# 检查可选依赖
print("\n--- 检查可选依赖 ---")
for package in OPTIONAL_PACKAGES:
    try:
        # 尝试导入模块
        module = importlib.import_module(package)
        print(f"✅ {package} 已安装")
    except ImportError as e:
        print(f"⚠️ {package} 未安装: {e}")

# 检查环境变量和配置文件
print("\n--- 检查环境变量和配置 ---")

# 检查.env文件
env_file = Path('.env')
if env_file.exists():
    print(f"✅ .env 文件存在")
    
    # 读取.env文件并检查关键配置
    with open(env_file, 'r', encoding='utf-8') as f:
        env_content = f.read()
        
    # 检查关键API密钥
    api_keys = [
        'OPENAI_API_KEY',
        'GOOGLE_API_KEY',
        'ANTHROPIC_API_KEY',
        'DASHSCOPE_API_KEY',
        'TUSHARE_TOKEN',
        'DEEPSEEK_API_KEY'
    ]
    
    for key in api_keys:
        if key in env_content:
            print(f"✅ {key} 已配置")
        else:
            print(f"⚠️ {key} 未配置")
else:
    print(f"❌ .env 文件不存在")
    # 尝试从示例文件创建
    env_example = Path('.env.example')
    if env_example.exists():
        print(f"ℹ️ 发现 .env.example 文件，可以用它创建 .env 文件")

# 检查日志目录
log_dir = Path('./logs')
if not log_dir.exists():
    print(f"⚠️ 日志目录不存在，将创建: {log_dir}")
    log_dir.mkdir(exist_ok=True)
    print(f"✅ 已创建日志目录: {log_dir}")
else:
    print(f"✅ 日志目录已存在: {log_dir}")

# 如果有缺失的包，尝试安装
if missing_packages:
    print("\n--- 尝试安装缺失的包 ---")
    for package in missing_packages:
        print(f"📦 安装 {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} 安装成功")
        except Exception as e:
            print(f"❌ {package} 安装失败: {e}")

# 检查web目录结构
print("\n--- 检查Web应用结构 ---")
web_dir = Path('./web')
if web_dir.exists():
    print(f"✅ Web目录存在")
    
    # 检查关键文件
    key_files = [
        'app.py',
        'utils/analysis_runner.py',
        'utils/api_checker.py',
    ]
    
    for file in key_files:
        file_path = web_dir / file
        if file_path.exists():
            print(f"✅ {file} 文件存在")
        else:
            print(f"❌ {file} 文件不存在")
else:
    print(f"❌ Web目录不存在")

# 打印总结
print("\n=== 检查完成 ===")
if missing_packages:
    print(f"⚠️ 有 {len(missing_packages)} 个关键依赖缺失，请手动安装或检查问题")
else:
    print("✅ 所有关键依赖已安装")
print("建议使用修复版启动脚本运行应用：")
print("  python start_web_fixed.py")
