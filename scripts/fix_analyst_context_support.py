"""
批量修复所有 v2.0 分析师的 _build_system_prompt 方法，添加 context 参数支持

问题：
- 所有 v2.0 分析师的 _build_system_prompt 方法都没有 context 参数
- 导致调试模式下无法使用指定的模板ID

修复：
- 为所有 _build_system_prompt 方法添加 context=None 参数
- 在调用 get_agent_prompt 时传递 context

使用方法：
    python scripts/fix_analyst_context_support.py
"""

import os
import re
from pathlib import Path

# 需要修复的文件列表
FILES_TO_FIX = [
    "core/agents/adapters/fundamentals_analyst_v2.py",
    "core/agents/adapters/market_analyst_v2.py",
    "core/agents/adapters/news_analyst_v2.py",
    "core/agents/adapters/sector_analyst_v2.py",
    "core/agents/adapters/index_analyst_v2.py",
]

def fix_file(file_path: str):
    """修复单个文件"""
    print(f"\n{'='*80}")
    print(f"修复文件: {file_path}")
    print(f"{'='*80}")
    
    if not os.path.exists(file_path):
        print(f"   ⚠️  文件不存在: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 1. 修复方法签名：def _build_system_prompt(self, market_type: str) -> str:
    #    改为：def _build_system_prompt(self, market_type: str, context=None) -> str:
    pattern1 = r'def _build_system_prompt\(self, market_type: str\) -> str:'
    replacement1 = r'def _build_system_prompt(self, market_type: str, context=None) -> str:'
    
    if re.search(pattern1, content):
        content = re.sub(pattern1, replacement1, content)
        print(f"   ✅ 修复方法签名")
    else:
        print(f"   ℹ️  未找到需要修复的方法签名")
    
    # 2. 修复 get_agent_prompt 调用：添加 context=context 参数
    #    查找 get_agent_prompt(...) 调用，在最后一个参数后添加 context=context
    
    # 匹配模式：get_agent_prompt(..., fallback_prompt=None)
    # 替换为：get_agent_prompt(..., fallback_prompt=None, context=context)
    pattern2 = r'(get_agent_prompt\([^)]+fallback_prompt=None)\)'
    replacement2 = r'\1, context=context)'
    
    if re.search(pattern2, content):
        # 检查是否已经有 context 参数
        if 'context=context' not in content:
            content = re.sub(pattern2, replacement2, content)
            print(f"   ✅ 添加 context 参数到 get_agent_prompt 调用")
        else:
            print(f"   ℹ️  get_agent_prompt 已有 context 参数")
    else:
        print(f"   ℹ️  未找到 get_agent_prompt 调用")
    
    # 3. 更新文档字符串
    pattern3 = r'(def _build_system_prompt.*?\n.*?""".*?\n.*?Args:\n.*?market_type: 市场类型[^\n]*\n)(.*?Returns:)'
    replacement3 = r'\1            context: AgentContext 对象（用于调试模式）\n            \n        \2'
    
    if re.search(pattern3, content, re.DOTALL):
        if 'context: AgentContext' not in content:
            content = re.sub(pattern3, replacement3, content, flags=re.DOTALL)
            print(f"   ✅ 更新文档字符串")
        else:
            print(f"   ℹ️  文档字符串已包含 context 说明")
    
    # 检查是否有修改
    if content != original_content:
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✅ 文件已更新")
        return True
    else:
        print(f"   ℹ️  文件无需修改")
        return False


def main():
    print("=" * 80)
    print("批量修复 v2.0 分析师的 context 参数支持")
    print("=" * 80)
    
    fixed_count = 0
    skipped_count = 0
    
    for file_path in FILES_TO_FIX:
        if fix_file(file_path):
            fixed_count += 1
        else:
            skipped_count += 1
    
    print("\n" + "=" * 80)
    print("修复完成")
    print("=" * 80)
    print(f"   ✅ 已修复: {fixed_count} 个文件")
    print(f"   ℹ️  跳过: {skipped_count} 个文件")
    print("=" * 80)


if __name__ == "__main__":
    main()

