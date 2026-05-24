from datetime import datetime, timedelta

from tradingagents.tools.analysis import peer_history


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def limit(self, _limit):
        self.docs = self.docs[:_limit]
        return self

    def sort(self, key, direction):
        reverse = direction < 0
        self.docs.sort(key=lambda doc: doc.get(key, ""), reverse=reverse)
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query, projection=None, sort=None):
        for doc in self.docs:
            code = doc.get("code") or doc.get("symbol")
            if "$or" in query and any(part.get("code") == code or part.get("symbol") == code for part in query["$or"]):
                return dict(doc)
        return None

    def find(self, query, projection=None):
        docs = self.docs
        if query.get("industry"):
            docs = [doc for doc in docs if doc.get("industry") == query["industry"]]
        if query.get("period"):
            docs = [doc for doc in docs if doc.get("period") == query["period"]]
        if "$or" in query:
            codes = set()
            for part in query["$or"]:
                if "code" in part:
                    codes.add(part["code"])
                if "symbol" in part:
                    codes.add(part["symbol"])
            if codes:
                docs = [doc for doc in docs if (doc.get("code") in codes or doc.get("symbol") in codes)]
        return FakeCursor([dict(doc) for doc in docs])


class FakeDb:
    def __init__(self, basics, daily):
        self.collections = {
            "stock_basic_info": FakeCollection(basics),
            "stock_daily_quotes": FakeCollection(daily),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_peer_comparison_report(monkeypatch):
    basics = [
        {"code": "000001", "name": "平安银行", "industry": "银行", "total_mv": 1000, "pe_ttm": 6, "pb_mrq": 0.7, "ps": 2, "roe": 11},
        {"code": "600036", "name": "招商银行", "industry": "银行", "total_mv": 1200, "pe_ttm": 7, "pb_mrq": 0.9, "ps": 2.2, "roe": 14},
        {"code": "601398", "name": "工商银行", "industry": "银行", "total_mv": 1500, "pe_ttm": 5, "pb_mrq": 0.6, "ps": 1.8, "roe": 12},
        {"code": "601939", "name": "建设银行", "industry": "银行", "total_mv": 1300, "pe_ttm": 5.5, "pb_mrq": 0.65, "ps": 1.9, "roe": 13},
    ]
    monkeypatch.setattr(peer_history, "_get_db", lambda: FakeDb(basics, []))

    report = peer_history.build_peer_comparison_report("000001", peer_limit=3)

    assert "## 同业对比" in report
    assert "行业估值统计" in report
    assert "平安银行" in report
    assert "招商银行" in report
    assert "PE/PE_TTM" in report


def test_historical_percentile_report(monkeypatch):
    start = datetime.now() - timedelta(days=20)
    daily = []
    for idx in range(10):
        day = start + timedelta(days=idx)
        daily.append(
            {
                "symbol": "000001",
                "period": "daily",
                "trade_date": day.strftime("%Y-%m-%d"),
                "close": 10 + idx,
                "pe_ttm": 5 + idx,
                "pb_mrq": 0.5 + idx * 0.1,
            }
        )
    monkeypatch.setattr(peer_history, "_get_db", lambda: FakeDb([], daily))

    report = peer_history.build_historical_percentile_report("000001", years=3)

    assert "## 历史分位" in report
    assert "收盘价" in report
    assert "PE/PE_TTM" in report
    assert "PB/PB_MRQ" in report
    assert "100.0%" in report


def test_historical_percentile_report_without_pe_pb_series(monkeypatch):
    start = datetime.now() - timedelta(days=20)
    daily = []
    for idx in range(10):
        day = start + timedelta(days=idx)
        daily.append(
            {
                "symbol": "000001",
                "period": "daily",
                "trade_date": day.strftime("%Y-%m-%d"),
                "close": 10 + idx,
            }
        )
    monkeypatch.setattr(peer_history, "_get_db", lambda: FakeDb([], daily))

    report = peer_history.build_historical_percentile_report("000001", years=3)

    assert "收盘价" in report
    assert "100.0%" in report
    assert "PE/PE_TTM：缺少可用历史序列" in report
    assert "PB/PB_MRQ：缺少可用历史序列" in report
