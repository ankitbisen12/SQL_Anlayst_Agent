import pytest

from guardrails.sql_guard import validate_sql

SAFE = [
    "SELECT room_type, AVG(price) AS avg_price FROM listings GROUP BY room_type LIMIT 10",
    "WITH t AS (SELECT listing_id, price FROM listings) SELECT listing_id FROM t ORDER BY price DESC LIMIT 5",
    "```sql\nSELECT COUNT(*) FROM bookings;\n```",
    "SELECT city FROM neighbourhoods UNION SELECT country FROM guests",
    "SELECT n.city, COUNT(*) FROM listings l JOIN neighbourhoods n USING (neighbourhood_id) GROUP BY 1",
]

UNSAFE = [
    ("DELETE FROM listings", "Only SELECT"),
    ("DROP TABLE listings", "Only SELECT"),
    ("UPDATE listings SET price = 0", "Only SELECT"),
    ("INSERT INTO hosts (host_id) VALUES (1)", "Only SELECT"),
    ("TRUNCATE bookings", "Only SELECT"),
    ("SELECT 1; DROP TABLE listings", "single SQL statement"),
    ("WITH d AS (DELETE FROM listings RETURNING *) SELECT * FROM d", "forbidden operation"),
    ("SELECT * INTO backup FROM listings", "forbidden operation"),
    ("SELECT * FROM listings FOR UPDATE", "forbidden operation"),
    ("SELECT pg_sleep(30)", "pg_sleep"),
    ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
    ("SELECT query_to_xml('DELETE FROM listings', true, true, '')", "query_to_xml"),
    ("SELECT nextval('neighbourhoods_neighbourhood_id_seq')", "nextval"),
    ("SELECT usename, passwd FROM pg_shadow", "system catalogs"),
    ("SELECT table_name FROM information_schema.tables", "system catalogs"),
    ("SELECT host_email FROM hosts", "sensitive"),
    ("SELECT h.host_phone FROM hosts h", "sensitive"),
    ("SELECT email FROM guests WHERE guest_id = 1", "sensitive"),
    ("GRANT SELECT ON listings TO public", "Only SELECT"),
    ("VACUUM", "Only SELECT"),
    ("", "empty"),
]


@pytest.mark.parametrize("query", SAFE)
def test_safe_queries_pass(query):
    result = validate_sql(query)
    assert result.is_safe, result.reason


@pytest.mark.parametrize("query,reason", UNSAFE)
def test_unsafe_queries_blocked(query, reason):
    result = validate_sql(query)
    assert not result.is_safe
    assert reason.lower() in result.reason.lower()


def test_limit_added_when_missing():
    result = validate_sql("SELECT listing_id FROM listings")
    assert result.is_safe and "LIMIT 500" in result.sql


def test_excessive_limit_is_capped():
    result = validate_sql("SELECT listing_id FROM listings LIMIT 100000")
    assert result.is_safe and "LIMIT 500" in result.sql and "100000" not in result.sql


def test_reasonable_limit_kept_verbatim():
    query = "SELECT listing_id FROM listings LIMIT 10"
    assert validate_sql(query).sql == query
