#!/usr/bin/env python3
"""
批量更新数据源引用
将所有"通达信"引用更新为"Tushare"或通用描述
"""

import os
import re
from pathlib import Path

def update_file_content(file_path: Path, replacements: list):
    """更新文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        for old_text, new_text in replacements:
            content = content.replace(old_text, new_text)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 更新: {file_path}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ 更新失败 {file_path}: {e}")
        return False

def main():
    """主函数"""
    print("🔧 批量更新数据源引用")
    print("=" * 50)
    
    # 项目根目录
    project_root = Path(__file__).parent.parent
    
    # 需要更新的文件模式
    file_patterns = [
        "**/*.py",
        "**/*.md",
        "**/*.txt"
    ]
    
    # 排除的目录
    exclude_dirs = {
        ".git", "__pycache__", "env", "venv", ".vscode", 
        "node_modules", ".pytest_cache", "dist", "build"
    }
    
    # 替换规则
    replacements = [
        # 数据来源标识
        ("数据来源: Tushare数据接口", "数据来源: Tushare数据接口"),
        ("数据来源: Tushare数据接口 (实时数据)", "数据来源: Tushare数据接口"),
        ("数据来源: Tushare数据接口\n", "数据来源: Tushare数据接口\n"),
        
        # 用户界面提示
        ("使用中国股票数据源进行基本面分析", "使用中国股票数据源进行基本面分析"),
        ("使用中国股票数据源", "使用中国股票数据源"),
        ("Tushare数据接口 + 基本面分析模型", "Tushare数据接口 + 基本面分析模型"),
        
        # 错误提示
        ("由于数据接口限制", "由于数据接口限制"),
        ("数据接口需要网络连接", "数据接口需要网络连接"),
        ("数据服务器", "数据服务器"),
        
        # 技术文档
        ("Tushare + FinnHub API", "Tushare + FinnHub API"),
        ("Tushare数据接口", "Tushare数据接口"),
        
        # CLI提示
        ("将使用中国股票数据源", "将使用中国股票数据源"),
        ("china_stock", "china_stock"),
        
        # 注释和说明
        ("# 中国股票数据", "# 中国股票数据"),
        ("数据源搜索功能", "数据源搜索功能"),
        
        # 变量名和标识符 (保持代码功能，只更新显示文本)
        ("'china_stock'", "'china_stock'"),
        ('"china_stock"', '"china_stock"'),
    ]
    
    # 收集所有需要更新的文件
    files_to_update = []
    
    for pattern in file_patterns:
        for file_path in project_root.glob(pattern):
            # 检查是否在排除目录中
            if any(exclude_dir in file_path.parts for exclude_dir in exclude_dirs):
                continue
            
            # 跳过二进制文件和特殊文件
            if file_path.suffix in {'.pyc', '.pyo', '.so', '.dll', '.exe'}:
                continue
                
            files_to_update.append(file_path)
    
    print(f"📁 找到 {len(files_to_update)} 个文件需要检查")
    
    # 更新文件
    updated_count = 0
    
    for file_path in files_to_update:
        if update_file_content(file_path, replacements):
            updated_count += 1
    
    print(f"\n📊 更新完成:")
    print(f"   检查文件: {len(files_to_update)}")
    print(f"   更新文件: {updated_count}")
    
    if updated_count > 0:
        print(f"\n🎉 成功更新 {updated_count} 个文件的数据源引用！")
        print("\n📋 主要更新内容:")
        print("   ✅ 'Tushare数据接口' → 'Tushare数据接口'")
        print("   ✅ '通达信数据源' → '中国股票数据源'")
        print("   ✅ 错误提示和用户界面文本")
        print("   ✅ 技术文档和注释")
    else:
        print("\n✅ 所有文件的数据源引用都是最新的")

if __name__ == "__main__":
    main()
