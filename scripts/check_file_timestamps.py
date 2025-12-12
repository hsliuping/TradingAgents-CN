"""
检查关键文件的修改时间
"""
import os
from pathlib import Path
from datetime import datetime

# 关键文件列表
key_files = [
    "tradingagents/dataflows/providers/china/tushare.py",
    "core/tools/sector_tools.py",
    "app/routers/templates_debug.py",
]

print("=" * 80)
print("📅 关键文件修改时间检查")
print("=" * 80)

for file_path in key_files:
    full_path = Path(file_path)
    if full_path.exists():
        mtime = os.path.getmtime(full_path)
        mtime_dt = datetime.fromtimestamp(mtime)
        print(f"\n📄 {file_path}")
        print(f"   修改时间: {mtime_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 检查是否有对应的 .pyc 文件
        pyc_path = Path(str(full_path).replace('.py', '.pyc'))
        if pyc_path.exists():
            pyc_mtime = os.path.getmtime(pyc_path)
            pyc_mtime_dt = datetime.fromtimestamp(pyc_mtime)
            print(f"   .pyc时间: {pyc_mtime_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if pyc_mtime > mtime:
                print(f"   ⚠️ .pyc 文件比源文件新！")
            elif pyc_mtime < mtime:
                print(f"   ✅ 源文件比 .pyc 新（正常）")
        else:
            print(f"   ✅ 无 .pyc 文件")
    else:
        print(f"\n❌ {file_path} - 文件不存在")

print("\n" + "=" * 80)

