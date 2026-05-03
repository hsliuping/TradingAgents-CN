#!/usr/bin/env python

import json
import os
import sys
import traceback
import unicodedata
from datetime import datetime
from typing import Any, Dict, List


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def build_state() -> dict:
    return {
        "ticker": os.environ.get("TUSHARE_NEWS_DEBUG_TICKER", "000002"),
        "analysis_date": os.environ.get("TUSHARE_NEWS_DEBUG_DATE", "2026-04-13"),
        "row_limit": int(os.environ.get("TUSHARE_NEWS_DEBUG_LIMIT", "8")),
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


def normalize_nfkc(value: Any) -> str:
    text = "" if value is None else str(value)
    return unicodedata.normalize("NFKC", " ".join(text.split()))


def build_extended_aliases(company_name: str, base_aliases: List[str]) -> List[str]:
    aliases = set(base_aliases)
    normalized_name = normalize_nfkc(company_name)
    if normalized_name:
        aliases.add(normalized_name)
        if len(normalized_name) >= 3 and normalized_name[-1].upper() in {"A", "B", "H"}:
            aliases.add(normalized_name[:-1])

    if company_name and len(company_name) >= 3 and company_name[-1] in {"Ａ", "Ｂ", "Ｈ"}:
        aliases.add(company_name[:-1])

    return [alias for alias in sorted(aliases, key=len, reverse=True) if len(alias) >= 2]


def build_text_blob(module, news_item: Dict[str, Any]) -> str:
    parts = [
        module._collapse_whitespace(news_item.get("title")),
        module._collapse_whitespace(news_item.get("content")),
        module._collapse_whitespace(news_item.get("summary")),
        " ".join(module._coerce_keywords(news_item.get("keywords"))),
    ]
    return " ".join(part for part in parts if part)


def analyze_processed_item(module, news_item: Dict[str, Any], symbol: str, company_name: str, aliases: List[str], extended_aliases: List[str]) -> Dict[str, Any]:
    text_blob = build_text_blob(module, news_item)
    nfkc_text_blob = normalize_nfkc(text_blob)
    symbol_clean = symbol.zfill(6)

    matched_aliases = [alias for alias in aliases if alias in text_blob]
    matched_extended_aliases = []
    for alias in extended_aliases:
        alias_nfkc = normalize_nfkc(alias)
        if alias in text_blob or (alias_nfkc and alias_nfkc in nfkc_text_blob):
            matched_extended_aliases.append(alias)

    current_relevant = module._is_relevant_a_share_news(news_item, symbol, company_name)
    current_score = module._calculate_a_share_news_relevance(news_item, symbol, company_name)

    return {
        "title": module._collapse_whitespace(news_item.get("title")),
        "publish_time": str(news_item.get("publish_time") or ""),
        "source": module._collapse_whitespace(news_item.get("source")),
        "category": module._collapse_whitespace(news_item.get("category")),
        "importance": module._collapse_whitespace(news_item.get("importance")),
        "current_relevant": current_relevant,
        "current_relevance_score": current_score,
        "symbol_hit": symbol_clean in text_blob or symbol in text_blob,
        "matched_aliases": matched_aliases,
        "matched_extended_aliases": matched_extended_aliases,
        "would_match_with_extended_aliases": bool(matched_extended_aliases),
        "title_nfkc": normalize_nfkc(news_item.get("title")),
        "summary_preview": module._collapse_whitespace(news_item.get("summary"))[:200],
        "content_preview": module._collapse_whitespace(news_item.get("content"))[:300],
    }


def build_raw_preview(news_df, row_limit: int) -> List[Dict[str, Any]]:
    preview = []
    if news_df is None or news_df.empty:
        return preview

    for _, row in news_df.head(row_limit).iterrows():
        preview.append(
            {
                "datetime": str(row.get("datetime", "") or ""),
                "title": str(row.get("title", "") or ""),
                "channels": str(row.get("channels", "") or ""),
                "content_preview": str(row.get("content", "") or "")[:300],
            }
        )
    return preview


def analyze_raw_matches(news_df, aliases: List[str], extended_aliases: List[str], symbol: str, row_limit: int) -> Dict[str, Any]:
    result = {
        "current_alias_match_count": 0,
        "extended_alias_match_count": 0,
        "symbol_match_count": 0,
        "current_alias_examples": [],
        "extended_alias_examples": [],
        "symbol_examples": [],
    }

    if news_df is None or news_df.empty:
        return result

    symbol_clean = symbol.zfill(6)

    for _, row in news_df.iterrows():
        title = str(row.get("title", "") or "")
        content = str(row.get("content", "") or "")
        combined = " ".join(part for part in [title, content] if part)
        combined_nfkc = normalize_nfkc(combined)

        current_alias_hits = [alias for alias in aliases if alias in combined]
        extended_alias_hits = []
        for alias in extended_aliases:
            alias_nfkc = normalize_nfkc(alias)
            if alias in combined or (alias_nfkc and alias_nfkc in combined_nfkc):
                extended_alias_hits.append(alias)

        symbol_hit = symbol_clean in combined or symbol in combined

        if current_alias_hits:
            result["current_alias_match_count"] += 1
            if len(result["current_alias_examples"]) < row_limit:
                result["current_alias_examples"].append(
                    {
                        "title": title,
                        "hits": current_alias_hits,
                        "content_preview": content[:300],
                    }
                )

        if extended_alias_hits:
            result["extended_alias_match_count"] += 1
            if len(result["extended_alias_examples"]) < row_limit:
                result["extended_alias_examples"].append(
                    {
                        "title": title,
                        "hits": extended_alias_hits,
                        "content_preview": content[:300],
                    }
                )

        if symbol_hit:
            result["symbol_match_count"] += 1
            if len(result["symbol_examples"]) < row_limit:
                result["symbol_examples"].append(
                    {
                        "title": title,
                        "content_preview": content[:300],
                    }
                )

    return result


def main() -> int:
    try:
        from core.tools.implementations.news import stock_news as module
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        state = build_state()
        output_dir = ensure_output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = f"tushare_news_debug_{state['ticker']}_{state['analysis_date']}_{ts}"

        start_date, end_date, start_date_str, end_date_str = module._build_a_share_news_window(state["analysis_date"])
        clean_ticker = module._normalize_a_share_symbol(state["ticker"])
        company_name = module._get_company_name(clean_ticker) or ""
        aliases = module._get_company_aliases(company_name)
        extended_aliases = build_extended_aliases(company_name, aliases)

        provider = get_tushare_provider()
        provider_available = bool(provider and provider.is_available() and provider.api is not None)

        summary: Dict[str, Any] = {
            "ticker": state["ticker"],
            "clean_ticker": clean_ticker,
            "analysis_date": state["analysis_date"],
            "window": {"start": start_date_str, "end": end_date_str},
            "provider_available": provider_available,
            "token_source": getattr(provider, "token_source", None),
            "company_name": company_name,
            "company_name_nfkc": normalize_nfkc(company_name),
            "aliases": aliases,
            "extended_aliases": extended_aliases,
            "sources": {},
        }

        if not provider_available:
            summary["error"] = "provider_unavailable"
            output_json = os.path.join(output_dir, f"{basename}_summary.json")
            output_txt = os.path.join(output_dir, f"{basename}_report.txt")
            write_json(output_json, summary)
            write_text(output_txt, json.dumps(summary, ensure_ascii=False, indent=2))
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 1

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("Tushare news relevance debug")
        report_lines.append("=" * 80)
        report_lines.append(f"ticker={state['ticker']}")
        report_lines.append(f"clean_ticker={clean_ticker}")
        report_lines.append(f"analysis_date={state['analysis_date']}")
        report_lines.append(f"window={start_date_str} -> {end_date_str}")
        report_lines.append(f"company_name={company_name}")
        report_lines.append(f"company_name_nfkc={normalize_nfkc(company_name)}")
        report_lines.append(f"aliases={aliases}")
        report_lines.append(f"extended_aliases={extended_aliases}")
        report_lines.append(f"token_source={getattr(provider, 'token_source', None)}")

        for source_code in module.TUSHARE_LIVE_SOURCES:
            report_lines.append("")
            report_lines.append(f"## source={source_code}")
            source_info: Dict[str, Any] = {
                "raw_rows": 0,
                "raw_match_stats": {},
                "processed_rows": 0,
                "current_relevant_count": 0,
                "extended_alias_match_count": 0,
                "raw_preview": [],
                "processed_preview": [],
                "error": None,
            }
            try:
                news_df = provider.api.news(
                    src=source_code,
                    start_date=start_date.strftime("%Y-%m-%d %H:%M:%S"),
                    end_date=end_date.strftime("%Y-%m-%d %H:%M:%S"),
                )
                source_info["raw_rows"] = 0 if news_df is None else int(len(news_df))
                source_info["raw_preview"] = build_raw_preview(news_df, state["row_limit"])
                source_info["raw_match_stats"] = analyze_raw_matches(
                    news_df,
                    aliases,
                    extended_aliases,
                    clean_ticker,
                    state["row_limit"],
                )

                if news_df is None or news_df.empty:
                    report_lines.append("raw_rows=0")
                    summary["sources"][source_code] = source_info
                    continue

                report_lines.append(
                    "raw_match_stats="
                    + json.dumps(source_info["raw_match_stats"], ensure_ascii=False)
                )

                processed_news = provider._process_tushare_news(news_df, source_code, symbol=None, limit=state["row_limit"])
                source_info["processed_rows"] = len(processed_news)

                analyzed_items = []
                for item in processed_news[: state["row_limit"]]:
                    analyzed = analyze_processed_item(
                        module,
                        item,
                        clean_ticker,
                        company_name,
                        aliases,
                        extended_aliases,
                    )
                    analyzed_items.append(analyzed)

                source_info["processed_preview"] = analyzed_items
                source_info["current_relevant_count"] = sum(1 for item in analyzed_items if item["current_relevant"])
                source_info["extended_alias_match_count"] = sum(
                    1 for item in analyzed_items if item["would_match_with_extended_aliases"]
                )

                report_lines.append(f"raw_rows={source_info['raw_rows']}")
                report_lines.append(f"processed_rows={source_info['processed_rows']}")
                report_lines.append(f"current_relevant_count={source_info['current_relevant_count']}")
                report_lines.append(f"extended_alias_match_count={source_info['extended_alias_match_count']}")

                for idx, item in enumerate(analyzed_items, start=1):
                    report_lines.append(f"[{idx}] title={item['title']}")
                    report_lines.append(
                        "    current_relevant="
                        f"{item['current_relevant']} score={item['current_relevance_score']} symbol_hit={item['symbol_hit']}"
                    )
                    report_lines.append(f"    matched_aliases={item['matched_aliases']}")
                    report_lines.append(f"    matched_extended_aliases={item['matched_extended_aliases']}")
                    report_lines.append(f"    summary_preview={item['summary_preview']}")

            except Exception as exc:
                source_info["error"] = str(exc)
                report_lines.append(f"error={exc}")

            summary["sources"][source_code] = source_info

        output_json = os.path.join(output_dir, f"{basename}_summary.json")
        output_txt = os.path.join(output_dir, f"{basename}_report.txt")
        write_json(output_json, summary)
        write_text(output_txt, "\n".join(report_lines))

        print("\n".join(report_lines))
        print(f"summary_dump={output_json}")
        print(f"report_dump={output_txt}")
        print("status=OK")
        return 0
    except Exception as exc:
        print(f"status=EXCEPTION: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())