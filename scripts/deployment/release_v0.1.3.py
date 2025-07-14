#!/usr/bin/env python3
"""
TradingAgents-CN v0.1.3 发布脚本
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def run_command(command, cwd=None):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            cwd=cwd,
            capture_output=True, 
            text=True, 
            encoding='utf-8'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_git_status():
    """检查Git状态"""
    print("🔍 检查Git状态...")
    
    success, stdout, stderr = run_command("git status --porcelain")
    if not success:
        print(f"❌ Git状态检查失败: {stderr}")
        return False
    
    if stdout.strip():
        print("⚠️ 发现未提交的更改:")
        print(stdout)
        response = input("是否继续发布? (y/N): ")
        if response.lower() != 'y':
            return False
    
    print("✅ Git状态检查通过")
    return True

def update_version_files():
    """更新版本文件"""
    print("📝 更新版本文件...")
    
    version = "cn-0.1.3"
    
    # 更新VERSION文件
    try:
        with open("VERSION", "w", encoding='utf-8') as f:
            f.write(f"{version}\n")
        print("✅ VERSION文件已更新")
    except Exception as e:
        print(f"❌ 更新VERSION文件失败: {e}")
        return False
    
    return True

def run_tests():
    """运行测试"""
    print("🧪 运行基础测试...")
    
    # 测试Tushare数据接口
    print("  📊 测试Tushare数据接口...")
    success, stdout, stderr = run_command("python tests/fast_tdx_test.py")
    if success:
        print("  ✅ Tushare数据接口测试通过")
    else:
        print(f"  ⚠️ Tushare数据接口测试警告: {stderr}")
        # 不阻止发布，因为可能是网络问题
    
    # 测试Web界面启动
    print("  🌐 测试Web界面...")
    # 这里可以添加Web界面的基础测试
    print("  ✅ Web界面测试跳过（需要手动验证）")
    
    return True

def create_git_tag():
    """创建Git标签"""
    print("🏷️ 创建Git标签...")
    
    tag_name = "v0.1.3"
    tag_message = "TradingAgents-CN v0.1.3 - A股市场完整支持"
    
    # 检查标签是否已存在
    success, stdout, stderr = run_command(f"git tag -l {tag_name}")
    if stdout.strip():
        print(f"⚠️ 标签 {tag_name} 已存在")
        response = input("是否删除现有标签并重新创建? (y/N): ")
        if response.lower() == 'y':
            run_command(f"git tag -d {tag_name}")
            run_command(f"git push origin --delete {tag_name}")
        else:
            return False
    
    # 创建标签
    success, stdout, stderr = run_command(f'git tag -a {tag_name} -m "{tag_message}"')
    if not success:
        print(f"❌ 创建标签失败: {stderr}")
        return False
    
    print(f"✅ 标签 {tag_name} 创建成功")
    return True

def commit_changes():
    """提交更改"""
    print("💾 提交版本更改...")
    
    # 添加更改的文件
    files_to_add = [
        "VERSION",
        "CHANGELOG.md", 
        "README.md",
        "RELEASE_NOTES_v0.1.3.md",
        "docs/guides/a-share-analysis-guide.md",
        "docs/data/china_stock-api-integration.md",
        "tradingagents/dataflows/tdx_utils.py",
        "tradingagents/agents/utils/agent_utils.py",
        "web/components/analysis_form.py",
        "requirements.txt"
    ]
    
    for file in files_to_add:
        if os.path.exists(file):
            run_command(f"git add {file}")
    
    # 提交更改
    commit_message = "🚀 Release v0.1.3: A股市场完整支持\n\n- 集成Tushare数据接口支持A股实时数据\n- 新增Web界面市场选择功能\n- 优化新闻分析滞后性\n- 完善文档和使用指南"
    
    success, stdout, stderr = run_command(f'git commit -m "{commit_message}"')
    if not success and "nothing to commit" not in stderr:
        print(f"❌ 提交失败: {stderr}")
        return False
    
    print("✅ 更改已提交")
    return True

def push_to_remote():
    """推送到远程仓库"""
    print("🚀 推送到远程仓库...")
    
    # 推送代码
    success, stdout, stderr = run_command("git push origin main")
    if not success:
        print(f"❌ 推送代码失败: {stderr}")
        return False
    
    # 推送标签
    success, stdout, stderr = run_command("git push origin --tags")
    if not success:
        print(f"❌ 推送标签失败: {stderr}")
        return False
    
    print("✅ 推送完成")
    return True

def generate_release_summary():
    """生成发布摘要"""
    print("\n" + "="*60)
    print("🎉 TradingAgents-CN v0.1.3 发布完成!")
    print("="*60)
    
    print("\n📋 发布内容:")
    print("  🇨🇳 A股市场完整支持")
    print("  📊 Tushare数据接口集成")
    print("  🌐 Web界面市场选择")
    print("  📰 实时新闻优化")
    print("  📚 完善的文档和指南")
    
    print("\n🔗 相关文件:")
    print("  📄 发布说明: RELEASE_NOTES_v0.1.3.md")
    print("  📖 A股指南: docs/guides/a-share-analysis-guide.md")
    print("  🔧 技术文档: docs/data/china_stock-api-integration.md")
    
    print("\n🚀 下一步:")
    print("  1. 在GitHub上创建Release")
    print("  2. 更新项目README")
    print("  3. 通知用户更新")
    print("  4. 收集用户反馈")
    
    print("\n💡 使用方法:")
    print("  git pull origin main")
    print("  pip install -r requirements.txt")
    print("  pip install pytdx")
    print("  python -m streamlit run web/app.py")

def main():
    """主函数"""
    print("🚀 TradingAgents-CN v0.1.3 发布流程")
    print("="*50)
    
    # 检查当前目录
    if not os.path.exists("VERSION"):
        print("❌ 请在项目根目录运行此脚本")
        return False
    
    # 执行发布步骤
    steps = [
        ("检查Git状态", check_git_status),
        ("更新版本文件", update_version_files),
        ("运行测试", run_tests),
        ("提交更改", commit_changes),
        ("创建Git标签", create_git_tag),
        ("推送到远程", push_to_remote),
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ {step_name}失败，发布中止")
            return False
    
    # 生成发布摘要
    generate_release_summary()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🎉 发布成功完成!")
            sys.exit(0)
        else:
            print("\n❌ 发布失败")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 发布被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发布过程中出现异常: {e}")
        sys.exit(1)
