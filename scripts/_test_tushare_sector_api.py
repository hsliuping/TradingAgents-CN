"""
测试 Tushare 同花顺板块三个接口是否可用
1. ths_index (板块列表)
2. ths_member (板块成分股 - 正向)
3. ths_member (个股所属板块 - 反向)
"""
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

import asyncio
from tradingagents.dataflows.providers.china.tushare import TushareProvider


async def main():
    provider = TushareProvider()
    await provider.connect()
    print(f"Tushare 连接状态: {'✅ 已连接' if provider.is_available() else '❌ 不可用'}")
    print()

    # ── 测试 1: 获取概念板块列表 (ths_index, type=S) ──
    print("=" * 60)
    print("测试 1: ths_index (概念板块列表, type=S)")
    print("=" * 60)
    try:
        df = await provider.get_ths_index_list(index_type="S")
        if df is not None and not df.empty:
            print(f"✅ 成功! 共 {len(df)} 个概念板块")
            # 搜索小米相关
            matched = df[df['name'].str.contains('小米', case=False, na=False)]
            if not matched.empty:
                print(f"  🔍 搜索'小米': 找到 {len(matched)} 个")
                for _, row in matched.iterrows():
                    print(f"     • {row['name']} ({row['ts_code']}) - 成分股 {row.get('count', 'N/A')} 只")
            else:
                print("  🔍 搜索'小米': 未找到匹配板块")
            # 显示前5个板块
            print(f"  前5个板块: {df['name'].head(5).tolist()}")
        else:
            print("❌ 返回空数据")
    except Exception as e:
        print(f"❌ 调用失败: {e}")

    print()

    # ── 测试 2: 获取板块成分股 (ths_member, 正向查询) ──
    print("=" * 60)
    print("测试 2: ths_member (板块成分股 - 正向查询)")
    print("=" * 60)
    # 先找一个概念板块的 ts_code
    test_ts_code = None
    try:
        df = await provider.get_ths_index_list(index_type="S")
        if df is not None and not df.empty:
            # 优先用小米相关板块，否则用第一个
            matched = df[df['name'].str.contains('小米', case=False, na=False)]
            if not matched.empty:
                test_ts_code = matched.iloc[0]['ts_code']
                test_name = matched.iloc[0]['name']
            else:
                test_ts_code = df.iloc[0]['ts_code']
                test_name = df.iloc[0]['name']
            print(f"  使用板块: {test_name} ({test_ts_code})")
    except Exception:
        pass

    if test_ts_code:
        try:
            members = await provider.get_ths_member(ts_code=test_ts_code)
            if members is not None and not members.empty:
                print(f"✅ 成功! 共 {len(members)} 只成分股")
                print(f"  字段: {list(members.columns)}")
                print(f"  前5只:")
                for _, row in members.head(5).iterrows():
                    code = row.get('code', row.get('con_code', 'N/A'))
                    name = row.get('name', row.get('con_name', 'N/A'))
                    print(f"     • {name} ({code})")
            else:
                print("❌ 返回空数据")
        except Exception as e:
            print(f"❌ 调用失败: {e}")
    else:
        print("⚠️ 跳过（无可用板块代码）")

    print()

    # ── 测试 3: 个股所属板块 (ths_member, 反向查询) ──
    print("=" * 60)
    print("测试 3: ths_member (个股所属板块 - 反向查询)")
    print("=" * 60)
    test_stock = "000001.SZ"  # 平安银行
    try:
        sectors = await provider.get_ths_member(con_code=test_stock)
        if sectors is not None and not sectors.empty:
            print(f"✅ 成功! {test_stock} 属于 {len(sectors)} 个板块")
            print(f"  字段: {list(sectors.columns)}")
            for _, row in sectors.head(10).iterrows():
                ts_code = row.get('ts_code', 'N/A')
                name = row.get('name', row.get('index_name', 'N/A'))
                print(f"     • {name} ({ts_code})")
        else:
            print("❌ 返回空数据")
    except Exception as e:
        print(f"❌ 调用失败: {e}")

    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

