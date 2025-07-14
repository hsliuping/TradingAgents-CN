#!/usr/bin/env python3
"""
构建包含PDF支持的Docker镜像
"""

import subprocess
import sys
import time
from pathlib import Path

def run_command(command, description, timeout=300):
    """运行命令并显示进度"""
    print(f"\n🔄 {description}...")
    print(f"命令: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            print(f"✅ {description}成功")
            if result.stdout.strip():
                print("输出:", result.stdout.strip()[-200:])  # 显示最后200字符
            return True
        else:
            print(f"❌ {description}失败")
            print("错误:", result.stderr.strip())
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ {description}超时")
        return False
    except Exception as e:
        print(f"❌ {description}异常: {e}")
        return False

def check_dockerfile():
    """检查Dockerfile是否包含PDF依赖"""
    print("🔍 检查Dockerfile配置...")
    
    dockerfile_path = Path("Dockerfile")
    if not dockerfile_path.exists():
        print("❌ Dockerfile不存在")
        return False
    
    content = dockerfile_path.read_text()
    
    required_packages = [
        'wkhtmltopdf',
        'xvfb',
        'fonts-wqy-zenhei',
        'pandoc'
    ]
    
    missing_packages = []
    for package in required_packages:
        if package not in content:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"⚠️ Dockerfile缺少PDF依赖: {', '.join(missing_packages)}")
        print("请确保Dockerfile包含以下包:")
        for package in required_packages:
            print(f"  - {package}")
        return False
    
    print("✅ Dockerfile包含所有PDF依赖")
    return True

def build_docker_image():
    """构建Docker镜像"""
    return run_command(
        "docker build -t tradingagents-cn:latest .",
        "构建Docker镜像",
        timeout=600  # 10分钟超时
    )

def test_docker_container():
    """测试Docker容器"""
    print("\n🧪 测试Docker容器...")
    
    # 启动容器进行测试
    start_cmd = """docker run -d --name tradingagents-test \
        -e DOCKER_CONTAINER=true \
        -e DISPLAY=:99 \
        tradingagents-cn:latest \
        python scripts/test_docker_pdf.py"""
    
    if not run_command(start_cmd, "启动测试容器", timeout=60):
        return False
    
    # 等待容器启动
    time.sleep(5)
    
    # 获取测试结果
    logs_cmd = "docker logs tradingagents-test"
    result = run_command(logs_cmd, "获取测试日志", timeout=30)
    
    # 清理测试容器
    cleanup_cmd = "docker rm -f tradingagents-test"
    run_command(cleanup_cmd, "清理测试容器", timeout=30)
    
    return result

def main():
    """主函数"""
    print("🐳 构建包含PDF支持的Docker镜像")
    print("=" * 50)
    
    # 检查当前目录
    if not Path("Dockerfile").exists():
        print("❌ 请在项目根目录运行此脚本")
        return False
    
    steps = [
        ("检查Dockerfile配置", check_dockerfile),
        ("构建Docker镜像", build_docker_image),
        ("测试Docker容器", test_docker_container),
    ]
    
    for step_name, step_func in steps:
        print(f"\n{'='*20} {step_name} {'='*20}")
        
        if not step_func():
            print(f"\n❌ {step_name}失败，构建中止")
            return False
    
    print("\n" + "="*50)
    print("🎉 Docker镜像构建完成！")
    print("=" * 50)
    
    print("\n📋 使用说明:")
    print("1. 启动完整服务:")
    print("   docker-compose up -d")
    print("\n2. 仅启动Web服务:")
    print("   docker run -p 8501:8501 tradingagents-cn:latest")
    print("\n3. 测试PDF功能:")
    print("   docker run tradingagents-cn:latest python scripts/test_docker_pdf.py")
    
    print("\n💡 提示:")
    print("- PDF导出功能已在Docker环境中优化")
    print("- 支持中文字体和虚拟显示器")
    print("- 如遇问题请查看容器日志")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
