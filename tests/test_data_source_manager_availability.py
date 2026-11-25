from app.services.data_sources.manager import DataSourceManager


class _DummyAdapter:
    def __init__(self, name: str, available: bool):
        self._name = name
        self._available = available
        self._priority = 1
        self.probe_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    def is_available(self) -> bool:
        self.probe_count += 1
        return self._available


def test_disabled_data_source_is_skipped_before_probe() -> None:
    manager = DataSourceManager.__new__(DataSourceManager)
    qmt = _DummyAdapter("qmt", available=False)
    akshare = _DummyAdapter("akshare", available=True)

    manager.adapters = [qmt, akshare]
    manager._configured_enabled_map = {"qmt": False, "akshare": True}

    available = manager.get_available_adapters()

    assert qmt.probe_count == 0
    assert akshare.probe_count == 1
    assert available == [akshare]