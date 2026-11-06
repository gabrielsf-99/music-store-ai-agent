from emporio.config import Settings


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://user:pass@host:5432/db"
    assert settings.openrouter_api_key.get_secret_value() == "secret-key"


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.db_schema == "emporio"
    assert settings.timezone == "America/Campo_Grande"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.openrouter_api_key is None


def test_api_key_is_not_exposed_in_repr(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")

    assert "secret-key" not in repr(Settings(_env_file=None))
