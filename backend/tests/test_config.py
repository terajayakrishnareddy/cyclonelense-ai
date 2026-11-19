import pytest
from pydantic import ValidationError

from app.config import Settings

GOOD = dict(environment="production", secret_key="Zx9" * 4 + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW", cors_origins="https://cyclones.example.org",
            database_url="postgresql+psycopg://cyclone:Rt7vK2mQ9xLw4Zp8@db:5432/cyclonelens")


def make(**over):
    return Settings(_env_file=None, **{**GOOD, **over})


def test_valid_production_config_accepted():
    s = make()
    assert s.is_production and not s.should_auto_migrate and s.cors_origin_list == ["https://cyclones.example.org"]


@pytest.mark.parametrize("over,needle", [
    ({"secret_key": ""}, "SECRET_KEY"),
    ({"secret_key": "short"}, "SECRET_KEY"),
    ({"secret_key": "CHANGE_THIS_IN_PRODUCTION_" + "a" * 20}, "SECRET_KEY"),
    ({"secret_key": "a" * 48}, "SECRET_KEY"),
    ({"cors_origins": ""}, "CORS_ORIGINS"),
    ({"cors_origins": "*"}, "wildcard"),
    ({"cors_origins": "https://*.example.org"}, "wildcard"),
    ({"cors_origins": "cyclones.example.org"}, "http"),
    ({"database_url": "sqlite:///./cyclonelens.db"}, "PostgreSQL"),
    ({"database_url": "postgresql+psycopg://cyclonelens:change_me_local_only@db/cyclonelens"}, "password"),
    ({"database_url": "postgresql+psycopg://cyclonelens:short@db/cyclonelens"}, "password"),
    ({"database_url": "postgresql+psycopg://cyclonelens@db/cyclonelens"}, "password"),
])
def test_unsafe_production_config_rejected(over, needle):
    with pytest.raises(ValidationError) as exc:
        make(**over)
    assert needle in str(exc.value)


def test_all_problems_reported_together():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, environment="production", secret_key="", cors_origins="*", database_url="sqlite:///x.db")
    msg = str(exc.value)
    assert "SECRET_KEY" in msg and "wildcard" in msg and "PostgreSQL" in msg


def test_development_gets_ephemeral_random_secret_not_a_static_default():
    a = Settings(_env_file=None, environment="development", secret_key="")
    b = Settings(_env_file=None, environment="development", secret_key="")
    assert a.secret_is_ephemeral and len(a.secret_key) >= 32 and a.secret_key != b.secret_key
    assert a.should_auto_migrate


def test_postgres_urls_normalised_to_psycopg3():
    assert Settings(_env_file=None, database_url="postgres://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(_env_file=None, database_url="postgresql://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"


def test_token_lifetime_bounds():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, access_token_minutes=0)
