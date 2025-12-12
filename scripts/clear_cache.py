"""
清理 Python 缓存文件
"""

import os
import shutil
from pathlib import Path

def clear_pycache(root_dir):
    """清理所有 __pycache__ 目录和 .pyc 文件"""
    count = 0
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 删除 __pycache__ 目录
        if '__pycache__' in dirnames:
            pycache_path = os.path.join(dirpath, '__pycache__')
            print(f"🗑️  删除: {pycache_path}")
            shutil.rmtree(pycache_path)
            count += 1
        
        # 删除 .pyc 文件
        for filename in filenames:
            if filename.endswith('.pyc'):
                pyc_path = os.path.join(dirpath, filename)
                print(f"🗑️  删除: {pyc_path}")
                os.remove(pyc_path)
                count += 1
    
    return count

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    
    print("=" * 80)
    print("🧹 清理 Python 缓存")
    print("=" * 80)
    
    count = clear_pycache(project_root)
    
    print("\n" + "=" * 80)
    print(f"✅ 清理完成！共删除 {count} 个缓存文件/目录")
    print("=" * 80)
    print("\n💡 提示：请重启 Web 服务器以加载最新代码")

