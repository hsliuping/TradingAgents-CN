#!/usr/bin/env python3
"""
回测功能验证脚本
检查：回测服务健康、主平台 API、端到端执行
"""
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BACKTEST_SAMPLE_DSL = {
    "name": "验证用策略",
    "description": "测试回测服务连通性",
    "universe": {"type": "static", "symbols": ["600519", "000858"]},
    "entry_rules": [{"type": "calendar_month", "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}],
    "exit_rules": [{"type": "holding_days", "days": 90}],
    "config": {
        "start_year": 2022,
        "end_year": 2023,
        "initial_capital": 1000000,
        "max_positions": 5,
        "market": "CN",
        "data_source": "tushare",
    },
}


async def check_backtest_service():
    """1. 检查回测服务 /health"""
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:8900/health", timeout=5) as r:
            data = json.loads(r.read().decode())
        print("✅ 回测服务: 正常", data)
        return True
    except Exception as e:
        print("❌ 回测服务: 未启动或无法连接", e)
        print("   请先运行: cd backtest-service && pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8900")
        return False


async def check_backtest_run_direct():
    """2. 直接调用回测服务 /run"""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:8900/run",
            data=json.dumps({"strategy": BACKTEST_SAMPLE_DSL}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
        if data.get("success"):
            print("✅ 回测执行: 成功", json.dumps(data.get("summary", {}), indent=2, ensure_ascii=False))
            return True
        else:
            print("⚠️ 回测执行: 失败", data.get("error", data))
            return False
    except Exception as e:
        print("❌ 回测执行: 异常", e)
        return False


async def check_main_api():
    """3. 检查主平台回测 API 是否注册"""
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=5) as r:
            openapi = json.loads(r.read().decode())
        paths = openapi.get("paths", {})
        has_backtest = any("/backtest" in p for p in paths)
        if has_backtest:
            print("✅ 主平台 API: 回测路由已注册")
            for p in sorted(paths):
                if "/backtest" in p:
                    print("  -", p)
            return True
        else:
            print("❌ 主平台 API: 未找到 /api/backtest 路由")
            return False
    except Exception as e:
        print("❌ 主平台 API: 无法连接 (主服务可能未启动)", e)
        return False


async def main():
    print("=" * 50)
    print("回测功能验证")
    print("=" * 50)
    results = []

    print("\n[1] 回测服务 (http://localhost:8900)")
    r1 = await check_backtest_service()
    results.append(("回测服务", r1))

    if r1:
        print("\n[2] 回测执行 (POST /run)")
        r2 = await check_backtest_run_direct()
        results.append(("回测执行", r2))

    print("\n[3] 主平台回测 API (http://localhost:8000)")
    r3 = await check_main_api()
    results.append(("主平台API", r3))

    print("\n" + "=" * 50)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"结果: {passed}/{total} 通过")
    if passed == total:
        print("✅ 回测功能验证通过")
    else:
        print("⚠️ 请根据上述提示修复后重试")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
