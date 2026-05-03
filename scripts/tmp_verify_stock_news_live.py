#!/usr/bin/env python

import json
import os
import sys
import traceback
from datetime import datetime


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def build_state() -> dict:
    ticker = os.environ.get("STOCK_NEWS_VERIFY_TICKER", "600519")
    analysis_date = os.environ.get("STOCK_NEWS_VERIFY_DATE", "2026-04-13")
    return {
        "ticker": ticker,
        "analysis_date": analysis_date,
    }


def ensure_output_dir() -> str:
    output_dir = os.path.join(ROOT, "logs", "tmp_live_checks")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)


def build_preview(news_list: list[dict], limit: int = 3) -> list[dict]:
    preview = []
    for item in news_list[:limit]:
        preview.append(
            {
                "title": str(item.get("title", "") or ""),
                "publish_time": str(item.get("publish_time", "") or ""),
                "source": str(item.get("source", "") or ""),
                "summary": str(item.get("summary", "") or "")[:200],
                "category": str(item.get("category", "") or ""),
                "sentiment": str(item.get("sentiment", "") or ""),
                "importance": str(item.get("importance", "") or ""),
            }
        )
    return preview


def check_tushare_access(start_date, end_date) -> dict:
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

    result = {
        "provider_available": False,
        "token_source": None,
        "permission_status": "unknown",
        "sample_rows": 0,
        "error": None,
    }

    try:
        provider = get_tushare_provider()
        result["provider_available"] = bool(provider and provider.is_available() and provider.api is not None)
        result["token_source"] = getattr(provider, "token_source", None)

        if not result["provider_available"]:
            result["permission_status"] = "provider_unavailable"
            return result

        try:
            sample_df = provider.api.news(
                src="sina",
                start_date=start_date.strftime("%Y-%m-%d %H:%M:%S"),
                end_date=end_date.strftime("%Y-%m-%d %H:%M:%S"),
            )
            if sample_df is None or sample_df.empty:
                result["permission_status"] = "accessible_but_no_rows"
                result["sample_rows"] = 0
            else:
                result["permission_status"] = "accessible"
                result["sample_rows"] = int(len(sample_df))
        except Exception as exc:
            error_text = str(exc)
            result["error"] = error_text
            lowered = error_text.lower()
            if any(keyword in lowered for keyword in ["permission", "unauthorized", "access denied", "point"]) or "权限" in error_text or "积分" in error_text:
                result["permission_status"] = "permission_denied"
            else:
                result["permission_status"] = "request_failed"

        return result
    except Exception as exc:
        result["permission_status"] = "provider_init_failed"
        result["error"] = str(exc)
        return result


def main() -> int:
    try:
        from core.tools.implementations.news import stock_news as module

        state = build_state()
        output_dir = ensure_output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = f"stock_news_live_{state['ticker']}_{state['analysis_date']}_{ts}"

        ticker = state["ticker"]
        analysis_date = state["analysis_date"]

        print("=" * 80)
        print("统一新闻工具 A 股 live 验证")
        print("=" * 80)
        print(f"ticker={ticker}")
        print(f"analysis_date={analysis_date}")

        start_date, end_date, start_date_str, end_date_str = module._build_a_share_news_window(analysis_date)
        clean_ticker = module._normalize_a_share_symbol(ticker)
        company_name = module._get_company_name(clean_ticker)
        enabled_sources = module._get_a_share_enabled_sources()

        db_result = module._query_news_from_database(
            symbol=clean_ticker,
            start_date=start_date,
            end_date=end_date,
            limit=20,
        )
        db_news = db_result.get("news") or []

        akshare_news = module._fetch_akshare_news_live(
            symbol=clean_ticker,
            start_date=start_date,
            end_date=end_date,
            limit=20,
        )

        unified_report = module.get_stock_news_unified.invoke({
            "ticker": ticker,
            "curr_date": analysis_date,
        })

        selected_path = "none"
        if "## 数据库缓存" in unified_report:
            selected_path = "database"
        elif "## AKShare东方财富新闻（实时）" in unified_report:
            selected_path = "akshare_live"

        summary = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "window": {
                "start": start_date_str,
                "end": end_date_str,
            },
            "company_name": company_name,
            "enabled_sources": enabled_sources,
            "database": {
                "count": len(db_news),
                "used_sources": db_result.get("used_sources") or [],
                "preview": build_preview(db_news),
            },
            "akshare_live": {
                "count": len(akshare_news),
                "preview": build_preview(akshare_news),
            },
            "selected_path": selected_path,
            "unified_report_length": len(unified_report),
        }

        summary_path = os.path.join(output_dir, f"{basename}_summary.json")
        report_path = os.path.join(output_dir, f"{basename}_report.txt")
        write_json(summary_path, summary)
        write_text(report_path, unified_report)

        print(f"company_name={company_name}")
        print(f"window={start_date_str} -> {end_date_str}")
        print(f"enabled_sources={enabled_sources}")
        print(f"db_count={len(db_news)} used_sources={db_result.get('used_sources') or []}")
        print(f"akshare_live_count={len(akshare_news)}")
        print(f"selected_path={selected_path}")
        print(f"summary_dump={summary_path}")
        print(f"report_dump={report_path}")
        print("report_preview_start")
        print(unified_report[:5000])
        print("report_preview_end")
        print("status=OK")
        return 0
    except Exception as exc:
        print(f"status=EXCEPTION: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())