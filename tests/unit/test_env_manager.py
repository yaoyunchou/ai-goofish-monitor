from src.infrastructure.config.env_manager import EnvManager


def test_get_value_prefers_env_file_when_key_present(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("WEBHOOK_URL=https://hooks.example.com/new\n", encoding="utf-8")
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/old")

    manager = EnvManager(str(env_file))

    assert manager.get_value("WEBHOOK_URL") == "https://hooks.example.com/new"


def test_get_value_falls_back_to_runtime_when_key_missing_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/runtime")

    manager = EnvManager(str(env_file))

    assert manager.get_value("WEBHOOK_URL") == "https://hooks.example.com/runtime"


def test_config_source_env_file_vs_process(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://from-file\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql://from-process")

    manager = EnvManager(str(env_file))

    assert manager.config_source("DATABASE_URL") == "env_file"
    assert manager.get_value("DATABASE_URL") == "postgresql://from-file"

    env_file.write_text("", encoding="utf-8")
    assert manager.config_source("DATABASE_URL") == "process_env"
