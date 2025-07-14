#!/usr/bin/env python3
"""
Docker环境快速配置脚本
帮助用户快速配置Docker部署环境
"""

import os
import shutil
from pathlib import Path

def setup_docker_env():
    """配置Docker环境"""
    project_root = Path(__file__).parent.parent
    env_example = project_root / ".env.example"
    env_file = project_root / ".env"
    
    print("🐳 TradingAgents-CN Docker环境配置向导")
    print("=" * 50)
    
    # 检查.env文件
    if env_file.exists():
        print("📁 发现现有的.env文件")
        choice = input("是否要备份现有配置并重新配置？(y/N): ").lower()
        if choice == 'y':
            backup_file = project_root / f".env.backup.{int(time.time())}"
            shutil.copy(env_file, backup_file)
            print(f"✅ 已备份到: {backup_file}")
        else:
            print("❌ 取消配置")
            return False
    
    # 复制模板文件
    if not env_example.exists():
        print("❌ 找不到.env.example文件")
        return False
    
    shutil.copy(env_example, env_file)
    print("✅ 已复制配置模板")
    
    # 读取配置文件
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Docker环境配置
    docker_configs = {
        'MONGODB_ENABLED': 'true',
        'REDIS_ENABLED': 'true',
        'MONGODB_HOST': 'mongodb',
        'REDIS_HOST': 'redis',
        'MONGODB_PORT': '27017',
        'REDIS_PORT': '6379'
    }
    
    print("\n🔧 配置Docker环境变量...")
    for key, value in docker_configs.items():
        # 替换配置值
        import re
        pattern = f'^{key}=.*$'
        replacement = f'{key}={value}'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # 写回文件
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Docker环境配置完成")
    
    # API密钥配置提醒
    print("\n🔑 API密钥配置")
    print("请编辑.env文件，配置以下API密钥（至少配置一个）：")
    print("- TRADINGAGENTS_DEEPSEEK_API_KEY")
    print("- TRADINGAGENTS_DASHSCOPE_API_KEY")
    print("- TRADINGAGENTS_TUSHARE_TOKEN")
    print("- TRADINGAGENTS_FINNHUB_API_KEY")
    
    # 显示下一步操作
    print("\n🚀 下一步操作：")
    print("1. 编辑.env文件，填入您的API密钥")
    print("2. 运行: docker-compose up -d")
    print("3. 访问: http://localhost:8501")
    
    return True

def check_docker():
    """检查Docker环境"""
    print("🔍 检查Docker环境...")
    
    # 检查Docker
    if shutil.which('docker') is None:
        print("❌ 未找到Docker，请先安装Docker Desktop")
        return False
    
    # 检查docker-compose
    if shutil.which('docker-compose') is None:
        print("❌ 未找到docker-compose，请确保Docker Desktop已正确安装")
        return False
    
    # 检查Docker是否运行
    try:
        import subprocess
        result = subprocess.run(['docker', 'info'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("❌ Docker未运行，请启动Docker Desktop")
            return False
    except Exception as e:
        print(f"❌ Docker检查失败: {e}")
        return False
    
    print("✅ Docker环境检查通过")
    return True

def main():
    """主函数"""
    import time
    
    if not check_docker():
        print("\n💡 请先安装并启动Docker Desktop:")
        print("- Windows/macOS: https://www.docker.com/products/docker-desktop")
        print("- Linux: https://docs.docker.com/engine/install/")
        return
    
    if setup_docker_env():
        print("\n🎉 Docker环境配置完成！")
        print("\n📚 更多信息请参考:")
        print("- Docker部署指南: docs/DOCKER_GUIDE.md")
        print("- 项目文档: README.md")
    else:
        print("\n❌ 配置失败")

if __name__ == "__main__":
    main()
