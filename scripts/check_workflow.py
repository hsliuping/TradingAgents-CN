import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
load_dotenv()

async def main():
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL', 'mongodb://localhost:27017'))
    db = client['tradingagents']

    # 列出所有工作流
    print("=== 所有工作流 ===")
    async for wf in db.workflows.find():
        print(f"ID: {wf.get('id')}")
        print(f"  name: {wf.get('name')}")
        print()

    # 查找特定工作流
    workflow = await db.workflows.find_one({'id': '85caaed6-6ac8-4b56-b530-03ea4d0630ef'})
    if not workflow:
        # 尝试按 _id 查找
        from bson import ObjectId
        try:
            workflow = await db.workflows.find_one({'_id': ObjectId('85caaed6-6ac8-4b56-b530-03ea4d0630ef')})
        except:
            pass

    print("=== 工作流节点 ===")
    if workflow:
        for node in workflow.get('nodes', []):
            print(f"ID: {node.get('id')}")
            print(f"  type: {node.get('type')}")
            print(f"  label: {node.get('label')}")
            print(f"  agent_id: {node.get('agent_id')}")
            print()
    else:
        print('Workflow not found')

asyncio.run(main())

