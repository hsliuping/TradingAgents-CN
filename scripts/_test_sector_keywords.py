"""搜索行业板块(N)中的热门概念关键词"""
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

import asyncio
from tradingagents.dataflows.providers.china.tushare import TushareProvider


async def main():
    p = TushareProvider()
    await p.connect()

    for idx_type, label in [("N", "行业板块"), ("S", "概念板块"), ("R", "地域板块")]:
        df = await p.get_ths_index_list(index_type=idx_type)
        count = len(df) if df is not None else 0
        print(f"\n{'='*60}")
        print(f"{label}({idx_type}): 共 {count} 个")
        print(f"{'='*60}")

        if df is None or df.empty:
            continue

        keywords = [
            "小米", "华为", "特斯拉", "光伏", "人工智能", "AI",
            "机器人", "芯片", "半导体", "新能源汽车", "白酒",
            "ChatGPT", "汽车", "苹果", "比亚迪", "锂电",
        ]
        for kw in keywords:
            matched = df[df['name'].str.contains(kw, case=False, na=False)]
            if not matched.empty:
                names = [f"{r['name']}({r['ts_code']})" for _, r in matched.iterrows()]
                print(f"  '{kw}': {names}")


asyncio.run(main())

