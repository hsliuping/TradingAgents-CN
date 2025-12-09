#!/usr/bin/env python3
"""
用户注册和权限系统测试运行脚本
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_command(cmd, description=""):
    """运行命令并处理结果"""
    print(f"\n{'='*60}")
    if description:
        print(f"🧪 {description}")
    print(f"📝 执行命令: {' '.join(cmd)}")
    print('='*60)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

        if result.stdout:
            print("📤 输出:")
            print(result.stdout)

        if result.stderr:
            print("📤 错误:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"✅ {description} 执行成功")
            return True
        else:
            print(f"❌ {description} 执行失败，返回码: {result.returncode}")
            return False

    except Exception as e:
        print(f"❌ 执行 {description} 时发生异常: {e}")
        return False

def run_backend_tests(test_type="all"):
    """运行后端测试"""
    print("\n🚀 开始运行后端测试...")

    if test_type == "unit":
        # 运行单元测试
        cmd = ["python", "-m", "pytest", "tests/test_user_registration.py", "-v"]
        return run_command(cmd, "后端单元测试")

    elif test_type == "api":
        # 运行API测试
        cmd = ["python", "-m", "pytest", "tests/test_auth_api.py", "-v"]
        return run_command(cmd, "后端API测试")

    elif test_type == "integration":
        # 运行集成测试
        cmd = ["python", "-m", "pytest", "tests/test_integration.py", "-v"]
        return run_command(cmd, "后端集成测试")

    else:
        # 运行所有后端测试
        test_files = [
            "tests/test_user_registration.py",
            "tests/test_auth_api.py",
            "tests/test_integration.py"
        ]
        cmd = ["python", "-m", "pytest"] + test_files + ["-v", "--tb=short"]
        return run_command(cmd, "所有后端测试")

def run_frontend_tests(test_type="all"):
    """运行前端测试"""
    print("\n🚀 开始运行前端测试...")

    frontend_dir = PROJECT_ROOT / "frontend"

    if not frontend_dir.exists():
        print("❌ 前端目录不存在")
        return False

    # 检查是否安装了依赖
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("📦 安装前端依赖...")
        install_cmd = ["npm", "install"]
        if not run_command(install_cmd, "安装前端依赖", cwd=frontend_dir):
            return False

    if test_type == "unit":
        # 运行单元测试
        cmd = ["npm", "run", "test:unit"]
        return run_command(cmd, "前端单元测试", cwd=frontend_dir)

    elif test_type == "e2e":
        # 运行端到端测试
        cmd = ["npm", "run", "test:e2e"]
        return run_command(cmd, "前端端到端测试", cwd=frontend_dir)

    else:
        # 运行所有前端测试
        cmd = ["npm", "run", "test"]
        return run_command(cmd, "所有前端测试", cwd=frontend_dir)

def check_dependencies():
    """检查测试依赖"""
    print("\n🔍 检查测试依赖...")

    # 检查Python依赖
    try:
        import pytest
        import fastapi
        import pymongo
        print("✅ Python依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少Python依赖: {e}")
        print("💡 请运行: pip install pytest fastapi pymongo motor")
        return False

    # 检查数据库连接
    try:
        from app.core.config import settings
        from pymongo import MongoClient
        client = MongoClient(settings.MONGO_URI)
        client.server_info()
        print("✅ 数据库连接检查通过")
        client.close()
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("💡 请检查MongoDB是否运行以及配置是否正确")
        return False

    return True

def setup_test_environment():
    """设置测试环境"""
    print("\n⚙️ 设置测试环境...")

    # 设置环境变量
    os.environ["TESTING"] = "true"
    os.environ["MONGODB_DATABASE"] = "tradingagents_test"

    print("✅ 测试环境设置完成")
    return True

def cleanup_test_environment():
    """清理测试环境"""
    print("\n🧹 清理测试环境...")

    try:
        from app.services.user_service import user_service
        # 清理测试数据
        user_service.users_collection.delete_many({
            "username": {"$regex": "^test|^integration|^concurrent|^persistence"}
        })
        print("✅ 测试数据清理完成")
    except Exception as e:
        print(f"⚠️ 清理测试数据失败: {e}")

def generate_test_report():
    """生成测试报告"""
    print("\n📊 生成测试报告...")

    # 这里可以添加更详细的报告生成逻辑
    report = f"""
测试完成报告
================
测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
测试类型: 用户注册和权限系统
覆盖范围:
- 用户注册功能
- 用户登录功能
- 权限控制系统
- 数据验证
- 错误处理
- 集成测试

建议:
- 定期运行测试以确保功能正常
- 添加更多边界条件测试
- 监控性能测试结果
"""

    print(report)

    # 保存报告到文件
    with open(PROJECT_ROOT / "test_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    print("📝 测试报告已保存到 test_report.txt")

def main():
    parser = argparse.ArgumentParser(description="用户注册和权限系统测试运行器")
    parser.add_argument(
        "--backend",
        choices=["unit", "api", "integration", "all"],
        default="all",
        help="运行后端测试类型"
    )
    parser.add_argument(
        "--frontend",
        choices=["unit", "e2e", "all"],
        default="all",
        help="运行前端测试类型"
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="跳过依赖检查"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="跳过环境清理"
    )

    args = parser.parse_args()

    print("🎯 用户注册和权限系统测试套件")
    print("=" * 50)

    success = True

    # 检查依赖
    if not args.skip_deps:
        if not check_dependencies():
            print("❌ 依赖检查失败，退出测试")
            return False

    # 设置测试环境
    if not setup_test_environment():
        print("❌ 测试环境设置失败，退出测试")
        return False

    try:
        # 运行后端测试
        if args.backend:
            if not run_backend_tests(args.backend):
                success = False

        # 运行前端测试
        if args.frontend:
            if not run_frontend_tests(args.frontend):
                success = False

        # 生成测试报告
        generate_test_report()

        if success:
            print("\n🎉 所有测试执行完成！")
        else:
            print("\n❌ 部分测试失败，请检查上述输出")

        return success

    finally:
        # 清理测试环境
        if not args.no_cleanup:
            cleanup_test_environment()

if __name__ == "__main__":
    import time
    exit_code = 0 if main() else 1
    sys.exit(exit_code)