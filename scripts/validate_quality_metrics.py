"""验证报告质量指标采集（v3.6.0 项5）。

测试场景：
1. 写入一条正常报告指标 → 查询能找到
2. 写入一条低质量报告指标 → 查询能找到，is_low_quality=True
3. 汇总统计正确（total/low_quality_count/avg_length 等）
4. 按日期范围筛选
5. 按 agent_type 聚合统计

运行方式：
    env\\Scripts\\python.exe scripts\\validate_quality_metrics.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.quality_metrics_service import QualityMetricsService


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction):
        return self

    def limit(self, n):
        return self

    async def to_list(self, length=None):
        return self._docs


class _FakeCollection:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        result = MagicMock()
        result.inserted_id = f"id_{len(self.docs)}"
        return result

    def find(self, query):
        # 简单过滤
        filtered = []
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if k == "analysis_date" and isinstance(v, dict):
                    # 日期范围
                    doc_date = doc.get("analysis_date", "")
                    if "$gte" in v and doc_date < v["$gte"]:
                        match = False
                        break
                    if "$lte" in v and doc_date > v["$lte"]:
                        match = False
                        break
                elif doc.get(k) != v:
                    match = False
                    break
            if match:
                filtered.append(doc)
        return _FakeCursor(filtered)


class _FakeDB:
    def __init__(self):
        self._collections: Dict[str, _FakeCollection] = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


async def test_case_1_record_and_query() -> bool:
    """测试1：写入并查询正常报告指标"""
    print("\n[测试1] 写入并查询正常报告指标")

    fake_db = _FakeDB()
    svc = QualityMetricsService(fake_db)

    record_id = await svc.record_analysis_metrics(
        user_id="test_user_001",
        ticker="601012",
        agent_id="market_analyst",
        agent_type="analyst",
        report_content="这是一个正常的市场分析报告，包含完整的结论和数据引用。",
        report_length=50,
        is_low_quality=False,
        analysis_date="2026-07-26",
    )

    if not record_id:
        print("  ❌ 失败：期望返回 record_id")
        return False

    # 查询
    records = await svc.query_metrics(user_id="test_user_001", ticker="601012")
    if len(records) != 1:
        print(f"  ❌ 失败：期望查询到1条记录，实际 {len(records)} 条")
        return False

    rec = records[0]
    if rec.get("agent_id") != "market_analyst":
        print(f"  ❌ 失败：期望 agent_id=market_analyst，实际 {rec.get('agent_id')}")
        return False

    if rec.get("is_low_quality"):
        print(f"  ❌ 失败：期望 is_low_quality=False")
        return False

    print("  ✅ 通过：写入并查询正常报告指标")
    return True


async def test_case_2_record_low_quality() -> bool:
    """测试2：写入低质量报告指标"""
    print("\n[测试2] 写入低质量报告指标")

    fake_db = _FakeDB()
    svc = QualityMetricsService(fake_db)

    await svc.record_analysis_metrics(
        user_id="test_user_001",
        ticker="601012",
        agent_id="news_analyst",
        agent_type="analyst",
        report_content="工具执行或模型生成未完成，当前结论仍待验证",
        report_length=20,
        is_low_quality=True,
        hit_fallback=True,
        fallback_pattern="工具执行或模型生成未完成",
        analysis_date="2026-07-26",
    )

    # 查询低质量报告
    records = await svc.query_metrics(only_low_quality=True)
    if len(records) != 1:
        print(f"  ❌ 失败：期望查询到1条低质量记录，实际 {len(records)} 条")
        return False

    rec = records[0]
    if not rec.get("is_low_quality"):
        print(f"  ❌ 失败：期望 is_low_quality=True")
        return False

    if not rec.get("hit_fallback"):
        print(f"  ❌ 失败：期望 hit_fallback=True")
        return False

    print("  ✅ 通过：写入低质量报告指标")
    return True


async def test_case_3_summary_statistics() -> bool:
    """测试3：汇总统计正确"""
    print("\n[测试3] 汇总统计正确")

    fake_db = _FakeDB()
    svc = QualityMetricsService(fake_db)

    # 写入3条正常 + 1条低质量
    for i in range(3):
        await svc.record_analysis_metrics(
            user_id="test_user_001",
            ticker="601012",
            agent_id=f"analyst_{i}",
            agent_type="analyst",
            report_length=100 + i * 50,
            is_low_quality=False,
            analysis_date="2026-07-26",
        )
    await svc.record_analysis_metrics(
        user_id="test_user_001",
        ticker="601012",
        agent_id="bad_analyst",
        agent_type="analyst",
        report_length=10,
        is_low_quality=True,
        hit_fallback=True,
        analysis_date="2026-07-26",
    )

    summary = await svc.get_quality_summary(user_id="test_user_001")

    if summary["total_reports"] != 4:
        print(f"  ❌ 失败：期望 total_reports=4，实际 {summary['total_reports']}")
        return False

    if summary["low_quality_count"] != 1:
        print(f"  ❌ 失败：期望 low_quality_count=1，实际 {summary['low_quality_count']}")
        return False

    if abs(summary["low_quality_rate"] - 0.25) > 0.001:
        print(f"  ❌ 失败：期望 low_quality_rate=0.25，实际 {summary['low_quality_rate']}")
        return False

    if summary["fallback_hit_count"] != 1:
        print(f"  ❌ 失败：期望 fallback_hit_count=1，实际 {summary['fallback_hit_count']}")
        return False

    # 平均报告长度 = (100+150+200+10)/4 = 115
    if abs(summary["avg_report_length"] - 115.0) > 0.1:
        print(f"  ❌ 失败：期望 avg_report_length=115，实际 {summary['avg_report_length']}")
        return False

    print("  ✅ 通过：汇总统计正确")
    return True


async def test_case_4_date_range_filter() -> bool:
    """测试4：按日期范围筛选"""
    print("\n[测试4] 按日期范围筛选")

    fake_db = _FakeDB()
    svc = QualityMetricsService(fake_db)

    await svc.record_analysis_metrics(
        user_id="test_user_001", ticker="601012", agent_type="analyst",
        analysis_date="2026-07-20", report_length=100,
    )
    await svc.record_analysis_metrics(
        user_id="test_user_001", ticker="601012", agent_type="analyst",
        analysis_date="2026-07-25", report_length=200,
    )
    await svc.record_analysis_metrics(
        user_id="test_user_001", ticker="601012", agent_type="analyst",
        analysis_date="2026-07-30", report_length=300,
    )

    # 查询 7/22 到 7/28 之间的记录
    records = await svc.query_metrics(
        user_id="test_user_001",
        start_date="2026-07-22",
        end_date="2026-07-28",
    )

    if len(records) != 1:
        print(f"  ❌ 失败：期望查询到1条记录（7/25），实际 {len(records)} 条")
        return False

    if records[0]["analysis_date"] != "2026-07-25":
        print(f"  ❌ 失败：期望日期为 2026-07-25，实际 {records[0]['analysis_date']}")
        return False

    print("  ✅ 通过：日期范围筛选正确")
    return True


async def test_case_5_agent_type_aggregation() -> bool:
    """测试5：按 agent_type 聚合统计"""
    print("\n[测试5] 按 agent_type 聚合统计")

    fake_db = _FakeDB()
    svc = QualityMetricsService(fake_db)

    # 写入不同类型的报告
    await svc.record_analysis_metrics(
        user_id="test_user_001", agent_type="analyst",
        report_length=100, is_low_quality=False, analysis_date="2026-07-26",
    )
    await svc.record_analysis_metrics(
        user_id="test_user_001", agent_type="analyst",
        report_length=200, is_low_quality=True, analysis_date="2026-07-26",
    )
    await svc.record_analysis_metrics(
        user_id="test_user_001", agent_type="researcher",
        report_length=500, is_low_quality=False, analysis_date="2026-07-26",
    )

    summary = await svc.get_quality_summary(user_id="test_user_001")
    by_type = summary["by_agent_type"]

    if "analyst" not in by_type:
        print(f"  ❌ 失败：期望 by_agent_type 含 analyst")
        return False

    if "researcher" not in by_type:
        print(f"  ❌ 失败：期望 by_agent_type 含 researcher")
        return False

    if by_type["analyst"]["count"] != 2:
        print(f"  ❌ 失败：期望 analyst count=2，实际 {by_type['analyst']['count']}")
        return False

    if by_type["analyst"]["low_quality_count"] != 1:
        print(f"  ❌ 失败：期望 analyst low_quality_count=1，实际 {by_type['analyst']['low_quality_count']}")
        return False

    if by_type["researcher"]["count"] != 1:
        print(f"  ❌ 失败：期望 researcher count=1，实际 {by_type['researcher']['count']}")
        return False

    print("  ✅ 通过：按 agent_type 聚合统计正确")
    return True


async def main() -> int:
    print("=" * 70)
    print("报告质量指标采集验证（v3.6.0 项5）")
    print("=" * 70)

    results = []
    results.append(await test_case_1_record_and_query())
    results.append(await test_case_2_record_low_quality())
    results.append(await test_case_3_summary_statistics())
    results.append(await test_case_4_date_range_filter())
    results.append(await test_case_5_agent_type_aggregation())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
