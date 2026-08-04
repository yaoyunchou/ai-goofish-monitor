from src.infrastructure.config.runtime_status import build_runtime_config_summary


def test_runtime_summary_masks_database_url(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_DRIVER=postgres\n"
        "DATABASE_URL=postgresql://postgres:secret@db.example.com:5432/mydb\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.infrastructure.config.runtime_status.env_manager.env_file",
        env_file,
    )
    monkeypatch.chdir(tmp_path)

    summary = build_runtime_config_summary()
    assert summary["database_driver"] == "postgres"
    assert summary["database_url"]["host"] == "db.example.com"
    assert "secret" not in str(summary)
