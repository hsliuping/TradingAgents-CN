"""检查 QMT 目录"""
import os
import sys

qmt_dir = r"D:\国金证券QMT交易端"

print(f"检查目录: {qmt_dir}")
print(f"目录存在: {os.path.exists(qmt_dir)}")

if os.path.exists(qmt_dir):
    print("\n目录内容：")
    try:
        items = os.listdir(qmt_dir)
        for item in items[:20]:  # 只显示前 20 个
            full_path = os.path.join(qmt_dir, item)
            item_type = "目录" if os.path.isdir(full_path) else "文件"
            print(f"  [{item_type}] {item}")
        
        if len(items) > 20:
            print(f"\n  ... 还有 {len(items) - 20} 个项目")
        
        # 查找关键文件
        print("\n查找关键文件：")
        key_files = ["XtMiniQmt.exe", "xtquant", "userdata_mini"]
        for key_file in key_files:
            found = False
            for root, dirs, files in os.walk(qmt_dir):
                if key_file in files or key_file in dirs:
                    rel_path = os.path.relpath(os.path.join(root, key_file), qmt_dir)
                    print(f"  ✅ 找到: {rel_path}")
                    found = True
                    break
            if not found:
                print(f"  ❌ 未找到: {key_file}")
                
    except Exception as e:
        print(f"错误: {e}")
else:
    print("❌ 目录不存在")

