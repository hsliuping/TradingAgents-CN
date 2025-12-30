"""检查任务结果数据"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_mongo_db
from pprint import pprint

async def check_task_result(task_id: str):
    """检查任务结果数据"""
    # 使用项目的数据库连接
    db = get_mongo_db()
    
    print(f"\n🔍 检查任务: {task_id}\n")
    
    # 1. 检查 unified_analysis_tasks 集合
    print("=" * 80)
    print("1️⃣ 检查 unified_analysis_tasks 集合")
    print("=" * 80)
    unified_task = await db.unified_analysis_tasks.find_one({"task_id": task_id})
    if unified_task:
        print(f"✅ 找到任务")
        print(f"  状态: {unified_task.get('status')}")
        print(f"  进度: {unified_task.get('progress')}%")
        print(f"  当前步骤: {unified_task.get('current_step')}")
        
        result = unified_task.get("result")
        if result:
            print(f"\n📊 结果数据:")
            print(f"  结果类型: {type(result)}")
            print(f"  结果键: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            
            if isinstance(result, dict):
                print(f"\n  summary长度: {len(result.get('summary', ''))}")
                print(f"  recommendation长度: {len(result.get('recommendation', ''))}")
                print(f"  有decision字段: {bool(result.get('decision'))}")
                print(f"  有reports字段: {bool(result.get('reports'))}")
                print(f"  有state字段: {bool(result.get('state'))}")
                
                if result.get('decision'):
                    print(f"\n  📋 decision内容:")
                    pprint(result['decision'], indent=4)
                
                if result.get('reports'):
                    print(f"\n  📋 reports键: {list(result['reports'].keys())}")
                
                if result.get('summary'):
                    print(f"\n  📋 summary前200字符:")
                    print(f"  {result['summary'][:200]}...")
        else:
            print(f"❌ 没有result字段")
    else:
        print(f"❌ 未找到任务")
    
    # 2. 检查 analysis_reports 集合
    print("\n" + "=" * 80)
    print("2️⃣ 检查 analysis_reports 集合")
    print("=" * 80)
    report = await db.analysis_reports.find_one({"task_id": task_id})
    if report:
        print(f"✅ 找到报告")
        print(f"  analysis_id: {report.get('analysis_id')}")
        print(f"  stock_symbol: {report.get('stock_symbol')}")
        print(f"  summary长度: {len(report.get('summary', ''))}")
        print(f"  recommendation长度: {len(report.get('recommendation', ''))}")
    else:
        print(f"❌ 未找到报告")
    
    # 3. 检查 analysis_tasks 集合
    print("\n" + "=" * 80)
    print("3️⃣ 检查 analysis_tasks 集合")
    print("=" * 80)
    task = await db.analysis_tasks.find_one({"task_id": task_id})
    if task:
        print(f"✅ 找到任务")
        print(f"  状态: {task.get('status')}")
        result = task.get('result')
        if result:
            print(f"  result类型: {type(result)}")
            print(f"  result键: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        else:
            print(f"  ❌ 没有result字段")
    else:
        print(f"❌ 未找到任务")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_task_result.py <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    asyncio.run(check_task_result(task_id))

