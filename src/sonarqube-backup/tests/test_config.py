from src.config import Config


def test_defaults_from_empty_env():
    cfg = Config.from_env({})
    assert cfg.instance_name == "sonarqube"
    assert cfg.db_host == "db"
    assert cfg.db_port == 5432
    assert cfg.dump_format == "custom"
    assert cfg.retention_count == 14
    assert cfg.keep_local_archive is True
    assert cfg.schedule_mode == "cron"
    assert cfg.s3_enabled is False


def test_s3_enabled_requires_endpoint_and_bucket():
    assert Config.from_env({"S3_ENDPOINT": "https://s3"}).s3_enabled is False
    assert Config.from_env({"S3_BUCKET": "b"}).s3_enabled is False
    cfg = Config.from_env({"S3_ENDPOINT": "https://s3", "S3_BUCKET": "b"})
    assert cfg.s3_enabled is True


def test_bool_parsing():
    assert Config.from_env({"KEEP_LOCAL_ARCHIVE": "false"}).keep_local_archive is False
    assert Config.from_env({"KEEP_LOCAL_ARCHIVE": "0"}).keep_local_archive is False
    assert Config.from_env({"RUN_ON_STARTUP": "yes"}).run_on_startup is True
    assert Config.from_env({"RUN_ON_STARTUP": "  TRUE "}).run_on_startup is True


def test_int_parsing_falls_back_on_garbage():
    assert Config.from_env({"RETENTION_COUNT": "notanint"}).retention_count == 14
    assert Config.from_env({"RETENTION_COUNT": "7"}).retention_count == 7


def test_alert_channels_csv():
    cfg = Config.from_env({"ALERT_CHANNELS": "email, Teams ,webhook"})
    assert cfg.alert_channels == ("email", "teams", "webhook")
    assert Config.from_env({}).alert_channels == ()
