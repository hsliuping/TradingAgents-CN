from app.services.data_sources.qmt_adapter import QMTAdapter


class _DummyXt:
    def __init__(self, connected: bool = False):
        self.connected = connected
        self.connect_calls = []

    def get_full_tick(self, _symbols):
        if not self.connected:
            raise RuntimeError("not connected")
        return {}

    def connect(self, port):
        self.connect_calls.append(port)


class _DummyXtDataCenter:
    def __init__(self):
        self.init_calls = []
        self.listen_calls = []
        self.data_dirs = []

    def set_data_home_dir(self, value):
        self.data_dirs.append(value)

    def set_token(self, _value):
        raise AssertionError("set_token should not be called in these tests")

    def set_allow_optmize_address(self, _value):
        raise AssertionError("set_allow_optmize_address should not be called in these tests")

    def set_kline_mirror_markets(self, _value):
        raise AssertionError("set_kline_mirror_markets should not be called in these tests")

    def set_kline_mirror_enabled(self, _value):
        raise AssertionError("set_kline_mirror_enabled should not be called in these tests")

    def set_init_markets(self, _value):
        pass

    def init(self, start_local_service=False):
        self.init_calls.append(start_local_service)

    def listen(self, port):
        self.listen_calls.append(port)
        return 58620


def _set_default_qmt_env(monkeypatch) -> None:
    monkeypatch.setenv("QMT_DATA_DIR", r"D:\gjzq\bin.x64")
    monkeypatch.setenv("QMT_LISTEN_PORT", "0")
    monkeypatch.setenv("QMT_LISTEN_PORT_RANGE", "58620-58650")
    monkeypatch.setenv("QMT_INIT_MARKETS", "SH,SZ")
    monkeypatch.setenv("QMT_TOKEN", "")
    monkeypatch.setenv("QMT_ALLOW_OPTIMIZE_ADDRESSES", "")
    monkeypatch.setenv("QMT_KLINE_MIRROR_MARKETS", "")
    monkeypatch.setenv("QMT_KLINE_MIRROR_ENABLED", "false")
    monkeypatch.setenv("QMT_START_LOCAL_SERVICE", "false")


def test_bootstrap_skips_active_init_for_default_miniqmt_mode(monkeypatch):
    _set_default_qmt_env(monkeypatch)

    dummy_xt = _DummyXt(connected=False)
    dummy_xtdc = _DummyXtDataCenter()

    monkeypatch.setattr("app.services.data_sources.qmt_adapter._get_xtdata", lambda: dummy_xt)
    monkeypatch.setattr("app.services.data_sources.qmt_adapter._get_xtdatacenter", lambda: dummy_xtdc)

    adapter = QMTAdapter()
    adapter._bootstrap_connection()

    assert dummy_xtdc.init_calls == []
    assert dummy_xtdc.listen_calls == []
    assert dummy_xt.connect_calls == []


def test_bootstrap_initializes_when_local_service_is_explicitly_enabled(monkeypatch):
    _set_default_qmt_env(monkeypatch)
    monkeypatch.setenv("QMT_START_LOCAL_SERVICE", "true")

    dummy_xt = _DummyXt(connected=False)
    dummy_xtdc = _DummyXtDataCenter()

    monkeypatch.setattr("app.services.data_sources.qmt_adapter._get_xtdata", lambda: dummy_xt)
    monkeypatch.setattr("app.services.data_sources.qmt_adapter._get_xtdatacenter", lambda: dummy_xtdc)

    adapter = QMTAdapter()
    adapter._bootstrap_connection()

    assert dummy_xtdc.data_dirs == [r"D:\gjzq\bin.x64"]
    assert dummy_xtdc.init_calls == [True]
    assert dummy_xtdc.listen_calls == [(58620, 58650)]
    assert dummy_xt.connect_calls == [58620]
