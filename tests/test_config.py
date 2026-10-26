import psycopg
import pytest

from utils.config import encode_db_url_password

HOST = "aws-0-ap-northeast-1.pooler.supabase.com"


@pytest.mark.parametrize("password", ["Secret@12#abc", "p:a/s?s%w@rd", "plain123"])
def test_raw_special_characters_are_encoded(password):
    url = encode_db_url_password(f"postgresql://postgres.ref:{password}@{HOST}:5432/postgres?sslmode=require")
    params = psycopg.conninfo.conninfo_to_dict(url)
    assert params["host"] == HOST
    assert params["password"] == password
    assert params["user"] == "postgres.ref"
    assert params["sslmode"] == "require"


def test_already_encoded_password_is_not_double_encoded():
    url = f"postgresql://postgres.ref:Secret%4012%23abc@{HOST}:5432/postgres"
    assert psycopg.conninfo.conninfo_to_dict(encode_db_url_password(url))["password"] == "Secret@12#abc"


def test_urls_without_password_are_untouched():
    for url in ["postgresql://localhost/db", "postgresql://user@localhost/db", "host=localhost dbname=x"]:
        assert encode_db_url_password(url) == url
