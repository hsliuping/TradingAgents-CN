import importlib
import warnings


def test_legacy_env_aliases_map_to_new(monkeypatch):
    # Ensure new keys are not set so aliasing triggers
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)

    # Set only legacy keys
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "8123")
    monkeypatch.setenv("API_DEBUG", "false")

    # Non-default secrets so Settings() (also run at module reload) passes the
    # production-mode secret check in app.core.config._check_secrets
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-abc123")
    monkeypatch.setenv("CSRF_SECRET", "test-csrf-secret-xyz789")

    # Reload module under warning capture to assert deprecation warnings
    import app.core.config as cfg
    # The import above (first one in a solo run) already executed the alias
    # mapping and wrote HOST/PORT/DEBUG into os.environ; clear them so the
    # reload re-triggers the mapping and its DeprecationWarning
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        importlib.reload(cfg)

    # At least one deprecation warning should be emitted
    assert any(isinstance(x.message, DeprecationWarning) for x in w), "No DeprecationWarning captured"

    # Verify values are mapped correctly
    s = cfg.Settings()
    assert s.HOST == "127.0.0.1"
    assert s.PORT == 8123
    assert s.DEBUG is False

