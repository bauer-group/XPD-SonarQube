from src.alerting import _should_send
from src.config import Config


def _cfg(**over):
    env = {"ALERT_ENABLED": "true", "ALERT_CHANNELS": "webhook"}
    env.update(over)
    return Config.from_env(env)


def test_disabled_never_sends():
    cfg = _cfg(ALERT_ENABLED="false")
    assert _should_send(cfg, "errors") is False


def test_no_channels_never_sends():
    cfg = _cfg(ALERT_CHANNELS="")
    assert _should_send(cfg, "errors") is False


def test_warnings_threshold_blocks_info_allows_warning_and_error():
    cfg = _cfg(ALERT_LEVEL="warnings")
    assert _should_send(cfg, "all") is False
    assert _should_send(cfg, "warnings") is True
    assert _should_send(cfg, "errors") is True


def test_errors_threshold_only_errors():
    cfg = _cfg(ALERT_LEVEL="errors")
    assert _should_send(cfg, "warnings") is False
    assert _should_send(cfg, "errors") is True


def test_all_threshold_sends_everything():
    cfg = _cfg(ALERT_LEVEL="all")
    assert _should_send(cfg, "all") is True
    assert _should_send(cfg, "warnings") is True
    assert _should_send(cfg, "errors") is True
