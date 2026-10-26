from utils.visualization import suggest_chart


def test_metric():
    assert suggest_chart("how many listings", {"columns": ["count"], "rows": [[2000]]})["type"] == "metric"


def test_bar_for_categories():
    r = {"columns": ["room_type", "avg_price"], "rows": [["Entire home/apt", 210.5], ["Private room", 95.0]]}
    assert suggest_chart("average price by room type", r) == {"type": "bar", "x": "room_type", "y": ["avg_price"]}


def test_pie_for_share_questions():
    r = {"columns": ["payment_method", "n"], "rows": [["Card", 10], ["PayPal", 4], ["Apple Pay", 2]]}
    assert suggest_chart("share of payment methods", r)["type"] == "pie"


def test_line_for_time_series():
    r = {"columns": ["month", "bookings"], "rows": [["2024-01-01", 300], ["2024-02-01", 320], ["2024-03-01", 410]]}
    assert suggest_chart("monthly bookings", r) == {"type": "line", "x": "month", "y": ["bookings"]}


def test_id_columns_are_not_measures():
    r = {"columns": ["listing_id", "name"], "rows": [[1, "a"], [2, "b"]]}
    assert suggest_chart("list listings", r)["type"] == "table"


def test_empty():
    assert suggest_chart("x", {"columns": ["a"], "rows": []})["type"] == "none"
