from guardrails.pii import REDACTED, redact_result, redact_text


def test_email_and_phone_redacted():
    out = redact_text("Contact me at john.doe@example.com or +1 555-123-4567.")
    assert "john.doe@example.com" not in out and "555-123-4567" not in out
    assert out.count(REDACTED) == 2


def test_secrets_redacted():
    assert REDACTED in redact_text("key sk-proj-abcdefghijklmnopqrstuvwxyz123456")
    assert REDACTED in redact_text("password: hunter2")
    assert REDACTED in redact_text("AKIAABCDEFGHIJKLMNOP")


def test_credit_card_luhn():
    assert REDACTED in redact_text("card 4111 1111 1111 1111")
    assert redact_text("order 1234567890123") == "order 1234567890123"  # fails Luhn -> kept


def test_regular_values_untouched():
    for text in ["2024-05-01", "Average price is 152.35", "40.712800, -74.006000", "listing 12345"]:
        assert redact_text(text) == text


def test_sensitive_columns_masked():
    result = {"columns": ["host_name", "host_email"], "rows": [["Ann", "ann@x.com"]], "row_count": 1, "truncated": False}
    assert redact_result(result)["rows"] == [["Ann", REDACTED]]
