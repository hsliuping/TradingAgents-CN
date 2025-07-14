#!/usr/bin/env python3
"""
Git分支管理工具
帮助管理TradingAgents-CN项目的分支
"""

import subprocess
import sys
from typing import List, Dict
import argparse

class BranchManager:
    def __init__(self):
        self.current_branch = self.get_current_branch()
        
    def run_git_command(self, command: List[str]) -> tuple:
        """运行Git命令"""
        try:
            result = subprocess.run(
                ['git'] + command, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return True, result.stdout.strip(), result.stderr.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stdout, e.stderr
    
    def get_current_branch(self) -> str:
        """获取当前分支"""
        success, stdout, _ = self.run_git_command(['branch', '--show-current'])
        return stdout if success else "unknown"
    
    def get_all_branches(self) -> Dict[str, List[str]]:
        """获取所有分支"""
        branches = {'local': [], 'remote': []}
        
        # 本地分支
        success, stdout, _ = self.run_git_command(['branch'])
        if success:
            for line in stdout.split('\n'):
                branch = line.strip().replace('* ', '')
                if branch:
                    branches['local'].append(branch)
        
        # 远程分支
        success, stdout, _ = self.run_git_command(['branch', '-r'])
        if success:
            for line in stdout.split('\n'):
                branch = line.strip()
                if branch and not branch.startswith('origin/HEAD'):
                    branches['remote'].append(branch)
        
        return branches
    
    def get_merged_branches(self, target_branch: str = 'main') -> List[str]:
        """获取已合并到目标分支的分支"""
        success, stdout, _ = self.run_git_command(['branch', '--merged', target_branch])
        if not success:
            return []
        
        merged = []
        for line in stdout.split('\n'):
            branch = line.strip().replace('* ', '')
            if branch and branch != target_branch:
                merged.append(branch)
        
        return merged
    
    def get_unmerged_branches(self, target_branch: str = 'main') -> List[str]:
        """获取未合并到目标分支的分支"""
        success, stdout, _ = self.run_git_command(['branch', '--no-merged', target_branch])
        if not success:
            return []
        
        unmerged = []
        for line in stdout.split('\n'):
            branch = line.strip().replace('* ', '')
            if branch and branch != target_branch:
                unmerged.append(branch)
        
        return unmerged
    
    def check_status(self):
        """检查Git状态"""
        print("🔍 Git分支状态检查")
        print("=" * 50)
        
        # 当前分支
        print(f"📍 当前分支: {self.current_branch}")
        
        # 未提交的更改
        success, stdout, _ = self.run_git_command(['status', '--porcelain'])
        if success:
            if stdout:
                print(f"⚠️ 未提交的更改: {len(stdout.split())} 个文件")
                for line in stdout.split('\n')[:5]:  # 只显示前5个
                    if line:
                        print(f"   {line}")
                if len(stdout.split('\n')) > 5:
                    print(f"   ... 还有 {len(stdout.split('\n')) - 5} 个文件")
            else:
                print("✅ 工作目录干净")
        
        # 分支信息
        branches = self.get_all_branches()
        print(f"\n📋 本地分支 ({len(branches['local'])}个):")
        for branch in branches['local']:
            marker = "👉 " if branch == self.current_branch else "   "
            print(f"{marker}{branch}")
        
        print(f"\n🌐 远程分支 ({len(branches['remote'])}个):")
        for branch in branches['remote'][:10]:  # 只显示前10个
            print(f"   {branch}")
        if len(branches['remote']) > 10:
            print(f"   ... 还有 {len(branches['remote']) - 10} 个远程分支")
        
        # 合并状态
        merged = self.get_merged_branches()
        unmerged = self.get_unmerged_branches()
        
        print(f"\n✅ 已合并到main ({len(merged)}个):")
        for branch in merged:
            print(f"   {branch}")
        
        print(f"\n⚠️ 未合并到main ({len(unmerged)}个):")
        for branch in unmerged:
            print(f"   {branch}")
    
    def release_version(self, version: str):
        """发布版本"""
        print(f"🚀 发布版本 {version}")
        print("=" * 50)
        
        # 检查当前状态
        success, stdout, _ = self.run_git_command(['status', '--porcelain'])
        if success and stdout:
            print("❌ 工作目录不干净，请先提交所有更改")
            return False
        
        # 切换到main分支
        print("📍 切换到main分支...")
        success, _, stderr = self.run_git_command(['checkout', 'main'])
        if not success:
            print(f"❌ 切换到main分支失败: {stderr}")
            return False
        
        # 拉取最新代码
        print("📥 拉取最新代码...")
        success, _, stderr = self.run_git_command(['pull', 'origin', 'main'])
        if not success:
            print(f"❌ 拉取代码失败: {stderr}")
            return False
        
        # 合并当前功能分支（如果不是main）
        if self.current_branch != 'main':
            print(f"🔀 合并分支 {self.current_branch}...")
            success, _, stderr = self.run_git_command(['merge', self.current_branch])
            if not success:
                print(f"❌ 合并失败: {stderr}")
                return False
        
        # 创建标签
        print(f"🏷️ 创建版本标签 {version}...")
        success, _, stderr = self.run_git_command(['tag', '-a', version, '-m', f'Release {version}'])
        if not success:
            print(f"❌ 创建标签失败: {stderr}")
            return False
        
        # 推送到远程
        print("📤 推送到远程...")
        success, _, stderr = self.run_git_command(['push', 'origin', 'main', '--tags'])
        if not success:
            print(f"❌ 推送失败: {stderr}")
            return False
        
        print(f"✅ 版本 {version} 发布成功！")
        return True
    
    def cleanup_branches(self, dry_run: bool = True):
        """清理已合并的分支"""
        print("🧹 清理已合并的分支")
        print("=" * 50)
        
        merged = self.get_merged_branches()
        feature_branches = [b for b in merged if b.startswith(('feature/', 'hotfix/'))]
        
        if not feature_branches:
            print("✅ 没有需要清理的功能分支")
            return
        
        print(f"📋 发现 {len(feature_branches)} 个已合并的功能分支:")
        for branch in feature_branches:
            print(f"   {branch}")
        
        if dry_run:
            print("\n💡 这是预览模式，使用 --no-dry-run 执行实际删除")
            return
        
        # 确认删除
        confirm = input(f"\n❓ 确认删除这 {len(feature_branches)} 个分支? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ 取消删除操作")
            return
        
        # 删除分支
        deleted_count = 0
        for branch in feature_branches:
            print(f"🗑️ 删除分支: {branch}")
            success, _, stderr = self.run_git_command(['branch', '-d', branch])
            if success:
                deleted_count += 1
                # 尝试删除远程分支
                self.run_git_command(['push', 'origin', '--delete', branch])
            else:
                print(f"   ❌ 删除失败: {stderr}")
        
        print(f"✅ 成功删除 {deleted_count} 个分支")
    
    def create_feature_branch(self, branch_name: str, base_branch: str = 'main'):
        """创建功能分支"""
        print(f"🌱 创建功能分支: {branch_name}")
        print("=" * 50)
        
        # 切换到基础分支
        print(f"📍 切换到基础分支: {base_branch}")
        success, _, stderr = self.run_git_command(['checkout', base_branch])
        if not success:
            print(f"❌ 切换失败: {stderr}")
            return False
        
        # 拉取最新代码
        print("📥 拉取最新代码...")
        success, _, stderr = self.run_git_command(['pull', 'origin', base_branch])
        if not success:
            print(f"❌ 拉取失败: {stderr}")
            return False
        
        # 创建新分支
        print(f"🌱 创建新分支: {branch_name}")
        success, _, stderr = self.run_git_command(['checkout', '-b', branch_name])
        if not success:
            print(f"❌ 创建分支失败: {stderr}")
            return False
        
        print(f"✅ 功能分支 {branch_name} 创建成功！")
        return True

def main():
    parser = argparse.ArgumentParser(description='Git分支管理工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 状态检查
    subparsers.add_parser('status', help='检查分支状态')
    
    # 版本发布
    release_parser = subparsers.add_parser('release', help='发布版本')
    release_parser.add_argument('version', help='版本号 (如: v0.1.6)')
    
    # 分支清理
    cleanup_parser = subparsers.add_parser('cleanup', help='清理已合并的分支')
    cleanup_parser.add_argument('--no-dry-run', action='store_true', help='执行实际删除')
    
    # 创建功能分支
    create_parser = subparsers.add_parser('create', help='创建功能分支')
    create_parser.add_argument('name', help='分支名称')
    create_parser.add_argument('--base', default='main', help='基础分支 (默认: main)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = BranchManager()
    
    if args.command == 'status':
        manager.check_status()
    elif args.command == 'release':
        manager.release_version(args.version)
    elif args.command == 'cleanup':
        manager.cleanup_branches(dry_run=not args.no_dry_run)
    elif args.command == 'create':
        manager.create_feature_branch(args.name, args.base)

if __name__ == '__main__':
    main()
