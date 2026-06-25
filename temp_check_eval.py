import asyncio
import json
from app.core.database import get_mongo_db

async def main():
    db = get_mongo_db()
    
    # 查找该版本的评估详情
    cursor = db.agent_evaluations.find({
        'version_id': 'spec_nanobot_financial_report_risk_tracker_v1_v2'
    }).sort('created_at', -1).limit(1)
    
    async for doc in cursor:
        print(f"Evaluation ID: {doc.get('_id')}")
        print(f"version_id: {doc.get('version_id')}")
        print(f"decision: {doc.get('decision')}")
        print(f"overall_score: {doc.get('overall_score')}")
        print(f"created_at: {doc.get('created_at')}")
        
        # 打印完整文档
        print("\nFull document:")
        print(json.dumps(doc, ensure_ascii=False, indent=2, default=str))

asyncio.run(main())