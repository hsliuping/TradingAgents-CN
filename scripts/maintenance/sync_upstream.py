#!/usr/bin/env python3
"""
上游同步脚本 - 自动同步原项目的更新
"""

import subprocess
import sys
import json
import requests
from datetime import datetime
from pathlib import Path

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('scripts')

class UpstreamSyncer:
    """上游同步器"""
    
    def __init__(self):
        self.upstream_repo = "TauricResearch/TradingAgents"
        self.origin_repo = "hsliuping/TradingAgents-CN"
        self.upstream_url = f"https://github.com/{self.upstream_repo}.git"
        self.github_api_base = "https://api.github.com"
        
    def check_git_status(self):
        """检查Git状态"""
        try:
            # 检查是否有未提交的更改
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True, check=True)
            if result.stdout.strip():
                logger.error(f"❌ 检测到未提交的更改，请先提交或暂存：")
                print(result.stdout)
                return False
            
            logger.info(f"✅ Git状态检查通过")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Git状态检查失败: {e}")
            return False
    
    def fetch_upstream(self):
        """获取上游更新"""
        try:
            logger.info(f"🔄 获取上游仓库更新...")
            subprocess.run(['git', 'fetch', 'upstream'], check=True)
            logger.info(f"✅ 上游更新获取成功")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 获取上游更新失败: {e}")
            return False
    
    def get_upstream_commits(self):
        """获取上游新提交"""
        try:
            # 获取上游main分支的最新提交
            result = subprocess.run([
                'git', 'log', '--oneline', '--no-merges',
                'HEAD..upstream/main'
            ], capture_output=True, text=True, check=True)
            
            commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
            return [commit for commit in commits if commit]
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 获取上游提交失败: {e}")
            return []
    
    def analyze_changes(self):
        """分析上游变更"""
        commits = self.get_upstream_commits()
        
        if not commits:
            logger.info(f"✅ 没有新的上游更新")
            return None
        
        logger.info(f"📊 发现 {len(commits)} 个新提交:")
        for i, commit in enumerate(commits[:10], 1):  # 只显示前10个
            logger.info(f"  {i}. {commit}")
        
        if len(commits) > 10:
            logger.info(f"  ... 还有 {len(commits) - 10} 个提交")
        
        # 分析变更类型
        change_analysis = self._analyze_commit_types(commits)
        return {
            "commits": commits,
            "analysis": change_analysis,
            "total_count": len(commits)
        }
    
    def _analyze_commit_types(self, commits):
        """分析提交类型"""
        analysis = {
            "features": [],
            "fixes": [],
            "docs": [],
            "others": []
        }
        
        for commit in commits:
            commit_lower = commit.lower()
            if any(keyword in commit_lower for keyword in ['feat', 'feature', 'add']):
                analysis["features"].append(commit)
            elif any(keyword in commit_lower for keyword in ['fix', 'bug', 'patch']):
                analysis["fixes"].append(commit)
            elif any(keyword in commit_lower for keyword in ['doc', 'readme', 'comment']):
                analysis["docs"].append(commit)
            else:
                analysis["others"].append(commit)
        
        return analysis
    
    def create_sync_branch(self):
        """创建同步分支"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"sync_upstream_{timestamp}"
        
        try:
            logger.info(f"🌿 创建同步分支: {branch_name}")
            subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
            logger.info(f"✅ 同步分支 {branch_name} 创建成功")
            return branch_name
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 创建同步分支失败: {e}")
            return None
    
    def merge_upstream(self, strategy="merge"):
        """合并上游更新"""
        try:
            if strategy == "merge":
                logger.info(f"🔀 合并上游更新...")
                subprocess.run(['git', 'merge', 'upstream/main'], check=True)
            elif strategy == "rebase":
                logger.info(f"🔀 变基上游更新...")
                subprocess.run(['git', 'rebase', 'upstream/main'], check=True)
            
            logger.info(f"✅ 上游更新合并成功")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 合并上游更新失败: {e}")
            logger.info(f"💡 可能存在冲突，需要手动解决")
            return False
    
    def check_conflicts(self):
        """检查合并冲突"""
        try:
            result = subprocess.run(['git', 'diff', '--name-only', '--diff-filter=U'], 
                                  capture_output=True, text=True, check=True)
            conflicts = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            if conflicts:
                logger.warning(f"⚠️  检测到合并冲突:")
                for conflict in conflicts:
                    logger.info(f"  - {conflict}")
                return conflicts
            else:
                logger.info(f"✅ 没有合并冲突")
                return []
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 检查冲突失败: {e}")
            return []
    
    def generate_sync_report(self, changes, conflicts=None):
        """生成同步报告"""
        report = {
            "sync_time": datetime.now().isoformat(),
            "upstream_repo": self.upstream_repo,
            "changes": changes,
            "conflicts": conflicts or [],
            "status": "success" if not conflicts else "conflicts"
        }
        
        # 保存报告
        report_file = Path("sync_reports") / f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 同步报告已保存: {report_file}")
        return report
    
    def run_sync(self, strategy="merge", auto_merge=False):
        """执行完整同步流程"""
        logger.info(f"🚀 开始上游同步流程...")
        
        # 1. 检查Git状态
        if not self.check_git_status():
            return False
        
        # 2. 获取上游更新
        if not self.fetch_upstream():
            return False
        
        # 3. 分析变更
        changes = self.analyze_changes()
        if not changes:
            return True
        
        # 4. 询问用户是否继续
        if not auto_merge:
            response = input(f"\n发现 {changes['total_count']} 个新提交，是否继续同步？(y/N): ")
            if response.lower() != 'y':
                logger.error(f"❌ 用户取消同步")
                return False
        
        # 5. 创建同步分支
        sync_branch = self.create_sync_branch()
        if not sync_branch:
            return False
        
        # 6. 合并上游更新
        if not self.merge_upstream(strategy):
            # 检查冲突
            conflicts = self.check_conflicts()
            if conflicts:
                logger.info(f"\n📋 冲突解决指南:")
                logger.info(f"1. 手动解决冲突文件")
                logger.info(f"2. 运行: git add <解决的文件>")
                logger.info(f"3. 运行: git commit")
                logger.info(f"4. 运行: git checkout main")
                logger.info(f"5. 运行: git merge ")
                
                # 生成冲突报告
                self.generate_sync_report(changes, conflicts)
                return False
        
        # 7. 生成同步报告
        self.generate_sync_report(changes)
        
        # 8. 切换回主分支并合并
        try:
            subprocess.run(['git', 'checkout', 'main'], check=True)
            subprocess.run(['git', 'merge', sync_branch], check=True)
            logger.info(f"✅ 同步完成，已合并到主分支")
            
            # 询问是否删除同步分支
            if not auto_merge:
                response = input(f"是否删除同步分支 {sync_branch}？(Y/n): ")
                if response.lower() != 'n':
                    subprocess.run(['git', 'branch', '-d', sync_branch], check=True)
                    logger.info(f"🗑️  已删除同步分支 {sync_branch}")
            
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 合并到主分支失败: {e}")
            return False

def main():
    """主函数"""
    import argparse

    
    parser = argparse.ArgumentParser(description="同步上游仓库更新")
    parser.add_argument("--strategy", choices=["merge", "rebase"], 
                       default="merge", help="合并策略")
    parser.add_argument("--auto", action="store_true", 
                       help="自动模式，不询问用户确认")
    
    args = parser.parse_args()
    
    syncer = UpstreamSyncer()
    success = syncer.run_sync(strategy=args.strategy, auto_merge=args.auto)
    
    if success:
        logger.info(f"\n🎉 同步完成！")
        logger.info(f"💡 建议接下来:")
        logger.info(f"1. 检查同步的更改是否与您的修改兼容")
        logger.info(f"2. 运行测试确保功能正常")
        logger.info(f"3. 更新文档以反映新变化")
        logger.info(f"4. 推送到您的远程仓库")
    else:
        logger.error(f"\n❌ 同步失败，请检查错误信息")
        sys.exit(1)

if __name__ == "__main__":
    main()
