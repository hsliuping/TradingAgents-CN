"""
简单测试：使用代理访问 Yahoo Finance，获取港股新闻

运行示例：
  python scripts/test/yf_hk_news_test.py --symbol 0700 \
         --http-proxy http://127.0.0.1:10809 --https-proxy http://127.0.0.1:10809 \
         --days 2 --limit 20

也可通过环境变量：
  set HTTP_PROXY=http://127.0.0.1:10809
  set HTTPS_PROXY=http://127.0.0.1:10809
  python scripts/test/yf_hk_news_test.py --symbol 0700
"""

import argparse
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import yfinance as yf


def normalize_hk_symbol(code: str) -> str:
    """标准化港股代码为 Yahoo 期望格式：4位数字 + .HK"""
    if not code:
        return code
    s = str(code).strip().upper()
    if s.endswith('.HK'):
        s = s[:-3]
    if s.isdigit():
        s = s.lstrip('0') or '0'
        s = s.zfill(4)
        return f"{s}.HK"
    return s


def ensure_scheme(proxy: Optional[str]) -> Optional[str]:
    if not proxy:
        return None
    p = str(proxy).strip()
    if not p:
        return None
    if p.startswith(('http://', 'https://', 'socks5://', 'socks4://')):
        return p
    return f"http://{p}"


def build_session(http_proxy: Optional[str], https_proxy: Optional[str], ua: Optional[str]) -> requests.Session:
    session = requests.Session()
    proxies: Dict[str, str] = {}
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    if proxies:
        session.proxies.update(proxies)
    user_agent = (ua or os.environ.get('TA_HTTP_USER_AGENT', '').strip() or
                  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/121.0 Safari/537.36 TradingAgentsCN/1.0')
    session.headers.update({'User-Agent': user_agent})
    return session


def parse_article_datetime(article: Dict) -> Optional[datetime]:
    ts = article.get('providerPublishTime')
    if isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts)
        except Exception:
            pass
    for key in ('pubDate', 'published'):
        val = article.get(key)
        if isinstance(val, str) and val:
            for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S'):
                try:
                    return datetime.strptime(val, fmt)
                except Exception:
                    continue
    return None


def fetch_hk_news(symbol: str, days: int, limit: int, session: requests.Session) -> List[Dict]:
    yf_symbol = normalize_hk_symbol(symbol)
    ticker = yf.Ticker(yf_symbol, session=session)
    articles = getattr(ticker, 'news', [])
    if not articles:
        return []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    filtered: List[Dict] = []
    for a in articles:
        dt = parse_article_datetime(a)
        if dt and start_date <= dt <= end_date:
            filtered.append({
                'title': a.get('title', ''),
                'summary': a.get('summary', '') or a.get('content', ''),
                'url': a.get('link', ''),
                'source': a.get('publisher', ''),
                'publish_time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            })
    return filtered[:limit]


def main():
    parser = argparse.ArgumentParser(description='测试 Yahoo Finance 港股新闻（带代理）')
    parser.add_argument('--symbol', required=True, help='港股代码，如 0700 或 00700 或 0700.HK')
    parser.add_argument('--days', type=int, default=2, help='时间范围（天），默认 2')
    parser.add_argument('--limit', type=int, default=50, help='返回条数限制，默认 50')
    parser.add_argument('--http-proxy', type=str, default=None, help='HTTP 代理，如 http://127.0.0.1:10809')
    parser.add_argument('--https-proxy', type=str, default=None, help='HTTPS 代理，如 http://127.0.0.1:10809')
    parser.add_argument('--no-proxy', type=str, default=None, help='NO_PROXY 列表，逗号分隔')
    parser.add_argument('--ua', type=str, default=None, help='自定义 User-Agent')

    args = parser.parse_args()

    # 日志配置（尽量贴近项目风格）
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)-8s | %(message)s'
    )
    logger = logging.getLogger('agents')
    trace_id = str(uuid.uuid4())

    # 环境变量优先于命令行参数（保持与服务一致的优先级策略）
    env_http = os.environ.get('HTTP_PROXY')
    env_https = os.environ.get('HTTPS_PROXY')
    env_no = os.environ.get('NO_PROXY')

    http_proxy = ensure_scheme(env_http or args.http_proxy)
    https_proxy = ensure_scheme(env_https or args.https_proxy)
    no_proxy = (env_no or args.no_proxy or '').strip()

    if no_proxy:
        os.environ['NO_PROXY'] = no_proxy
        logger.info(f"🛑 NO_PROXY: {no_proxy} trace={trace_id}")

    session = build_session(http_proxy, https_proxy, args.ua)
    proxies_log = {k: v for k, v in (session.proxies or {}).items() if v}
    if proxies_log:
        logger.info(f"🌐 使用代理访问 Yahoo Finance: {proxies_log} trace={trace_id}")
    else:
        logger.info(f"🌐 未配置代理，直接访问 Yahoo Finance trace={trace_id}")

    # 获取新闻
    try:
        items = fetch_hk_news(args.symbol, args.days, args.limit, session)
        if not items:
            logger.warning(f"⚠️ 未获取到新闻数据（可能需要代理或被限频） trace={trace_id}")
        else:
            logger.info(f"✅ 成功获取到 {len(items)} 条新闻 trace={trace_id}")
            for i, it in enumerate(items, 1):
                print(f"[{i}] {it['publish_time']} | {it['source']} | {it['title']}")
                print(f"    {it['url']}")
    except Exception as e:
        logger.error(f"❌ 获取港股新闻失败: {e} trace={trace_id}")


if __name__ == '__main__':
    main()

