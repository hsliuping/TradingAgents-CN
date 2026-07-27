from datetime import date, datetime

import pytest

from app.services.alphaguard.real_data_candidate_service import (
    CandidateDataFetchResult,
    CandidateRealDataService,
)
from tests.unit.alphaguard._fakes import FakeDB


class FixedCandidateProvider:
    name = "fixed-real-provider"

    @staticmethod
    def capability_check():
        return {"available": True}

    @staticmethod
    def fetch(symbol, start, end):
        raw = {
            "date": "2026-07-24",
            "code": "sh.600519",
            "open": "1400",
            "high": "1420",
            "low": "1390",
            "close": "1410",
            "preclose": "1401",
            "volume": "123400",
            "amount": "173994000",
            "adjustflag": "3",
            "turn": "0.10",
            "tradestatus": "1",
            "pctChg": "0.64",
            "isST": "0",
            "peTTM": "22",
            "pbMRQ": "8",
        }
        qfq = {
            **raw,
            "adjustflag": "2",
            "open": "1395",
            "high": "1415",
            "low": "1385",
            "close": "1405",
        }
        benchmark = {
            **raw,
            "code": "sh.000300",
            "open": "4000",
            "high": "4020",
            "low": "3990",
            "close": "4010",
        }
        financial = {
            "code": "sh.600519",
            "pubDate": "2026-04-30",
            "statDate": "2026-03-31",
            "roeAvg": "8.2",
            "npMargin": "51.2",
            "gpMargin": "92.1",
            "netProfit": "25000000000",
            "epsTTM": "62.1",
            "MBRevenue": "52000000000",
            "totalShare": "125619.78",
            "liqaShare": "125619.78",
        }
        news = {
            "新闻标题": "公司经营情况更新",
            "文章来源": "测试公共源",
            "发布时间": "2026-07-24 10:30:00",
            "新闻链接": "https://example.invalid/news/1",
            "新闻内容": "公开资料摘要",
        }
        announcement = {
            "公告标题": "2026年半年度报告",
            "公告时间": "2026-07-24",
            "公告链接": (
                "https://example.invalid/announcement?"
                "announcementId=real-announcement-1"
            ),
        }
        industry = {
            "code": "sh.600519",
            "industry": "C15酒、饮料和精制茶制造业",
            "industryClassification": "证监会行业分类",
            "updateDate": "2026-07-27",
        }
        return CandidateDataFetchResult(
            provider_versions={"baostock": "00.9.30", "akshare": "1.18.78"},
            raw_prices=(raw,),
            qfq_prices=(qfq,),
            benchmark_prices=(benchmark,),
            financials=(financial,),
            news=(news,),
            announcements=(announcement,),
            industry=(industry,),
            response_hashes={
                "raw_prices": "a",
                "qfq_prices": "b",
                "benchmark_prices": "c",
                "financials": "d",
                "news": "e",
                "announcements": "f",
                "industry": "g",
            },
        )


@pytest.mark.asyncio
async def test_candidate_real_data_dry_run_is_read_only_and_reports_versions():
    db = FakeDB()
    await db["stock_basic_info"].insert_one(
        {"symbol": "600519", "code": "600519", "name": "贵州茅台"}
    )
    result = await CandidateRealDataService(db).sync_candidate(
        symbol="600519",
        start=date(2026, 7, 24),
        end=date(2026, 7, 24),
        execute=False,
        provider=FixedCandidateProvider(),
        collected_at=datetime(2026, 7, 27, 13),
    )
    assert result["write"] is False
    assert result["categories"]["RAW_QFQ_DAILY_PRICE"]["record_count"] == 1
    assert result["data_versions"]["price"].endswith(
        "alphaguard-candidate-real-data-v1"
    )
    assert db["stock_daily_quotes"].count() == 0
    assert db["sync_status"].count() == 0


@pytest.mark.asyncio
async def test_candidate_real_data_execute_is_idempotent_and_traceable():
    db = FakeDB()
    await db["stock_basic_info"].insert_one(
        {"symbol": "600519", "code": "600519", "name": "贵州茅台"}
    )
    service = CandidateRealDataService(db)
    kwargs = {
        "symbol": "600519",
        "start": date(2026, 7, 24),
        "end": date(2026, 7, 24),
        "execute": True,
        "provider": FixedCandidateProvider(),
        "collected_at": datetime(2026, 7, 27, 13),
    }
    first = await service.sync_candidate(**kwargs)
    second = await service.sync_candidate(**kwargs)

    assert first["categories"]["RAW_QFQ_DAILY_PRICE"]["created"] == 1
    assert second["categories"]["RAW_QFQ_DAILY_PRICE"]["created"] == 0
    assert second["categories"]["RAW_QFQ_DAILY_PRICE"]["reused"] == 1
    price = await db["stock_daily_quotes"].find_one(
        {"ref_id": "price-600519-2026-07-24"}
    )
    assert price["price_adjustment_mode"] == "QFQ"
    assert price["raw_data_version"]
    assert price["content_hash"]
    financial = await db["stock_financial_data"].find_one({})
    assert financial["published_at"] == datetime(2026, 4, 30)
    industry = await db["stock_industry_history"].find_one({})
    assert industry["industry_code"] == "C15"
    assert industry["history_coverage_status"] == "CURRENT_ONLY"
    assert db["sync_status"].count() == 1

    precheck = await service.precheck_candidate(
        symbol="600519",
        trade_date=date(2026, 7, 24),
        cutoff_at=datetime(2026, 7, 27, 13),
    )
    assert precheck["data_quality"]["status"] == "PASS"
    assert precheck["reference_counts"] == {
        "prices": 1,
        "benchmark_prices": 1,
        "financials": 1,
        "news": 1,
        "announcements": 1,
        "market_context": 0,
        "trading_calendar": 0,
    }
    assert precheck["snapshot_preconditions"] == {
        "price_target_exists": True,
        "benchmark_target_exists": True,
        "market_context_exists": False,
        "calendar_visible_at_cutoff": False,
    }
