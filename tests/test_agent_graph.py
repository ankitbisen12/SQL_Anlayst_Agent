"""
Graph-level tests with a fake LLM and a fake database: every routing path of the agent is exercised
without network access or API cost.
"""

from types import SimpleNamespace

import pytest

import agents.sql_analyst as agent
from Models.schema import curationSchema, judgeSchema, sqlGenerationSchema


class FakeLLM:
    def __init__(self, script: dict):
        self.script = script  # schema class / "text" -> list of responses (popped in order)
        self.schema = None

    def with_structured_output(self, schema):
        clone = FakeLLM(self.script)
        clone.schema = schema
        return clone

    def invoke(self, prompt):
        return self.script[self.schema].pop(0)

    def stream(self, prompt):
        for word in self.script["text"]:
            yield SimpleNamespace(text=word, content=word)


class FakeDB:
    def __init__(self, results):
        self.results = list(results)
        self.executed = []

    def __call__(self):
        return self

    def schema_details(self, schema):
        return "Table: bookings\n  Columns:\n    - payment_method (text)"

    def execute_query(self, query):
        self.executed.append(query)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


RESULT = {"columns": ["payment_method", "n"], "rows": [["Credit Card", 10], ["PayPal", 4]], "row_count": 2, "truncated": False}


def install(monkeypatch, script, db_results=(RESULT,)):
    db = FakeDB(db_results)
    monkeypatch.setattr(agent, "llm_pick", lambda level: FakeLLM(script))
    monkeypatch.setattr(agent, "DatabaseUtil", db)
    return db


def curated(intent="data_question", q="Payment methods and their usage"):
    return curationSchema(intent=intent, curated_question=q)


def sql(query, answerable=True):
    return sqlGenerationSchema(answerable=answerable, sql=query, reason="counts bookings per payment method")


def collect(question):
    return list(agent.stream_agent(question))


def test_happy_path_streams_everything(monkeypatch):
    install(monkeypatch, {
        curationSchema: [curated()],
        sqlGenerationSchema: [sql("SELECT payment_method, COUNT(*) AS n FROM bookings GROUP BY 1 LIMIT 10")],
        judgeSchema: [judgeSchema(answer="Yes", comments="read only")],
        "text": ["Credit Card ", "is most used."],
    })
    events = collect("What payment methods exist?")
    types = [e["type"] for e in events]
    assert {"sql", "result", "chart"} <= set(types)
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Credit Card is most used."
    assert events[-1]["type"] == "done" and events[-1]["answer"] == "Credit Card is most used."
    assert next(e for e in events if e["type"] == "chart")["chart"]["type"] == "bar"


def test_input_guardrail_blocks_without_llm(monkeypatch):
    install(monkeypatch, {})  # any LLM call would fail: script is empty
    events = collect("DROP TABLE listings")
    assert events[-1]["intent"] == "modify_request"
    assert "only read" in events[-1]["answer"]


def test_classifier_refuses_off_topic(monkeypatch):
    install(monkeypatch, {curationSchema: [curated(intent="off_topic")]})
    assert collect("Write me a poem about the sea")[-1]["intent"] == "off_topic"


def test_unsafe_generated_sql_is_cancelled(monkeypatch):
    db = install(monkeypatch, {curationSchema: [curated()], sqlGenerationSchema: [sql("DELETE FROM bookings")]})
    final = collect("How many bookings?")[-1]
    assert "not a safe" in final["answer"] and final["sql"] == ""
    assert db.executed == []


def test_llm_judge_can_veto(monkeypatch):
    db = install(monkeypatch, {
        curationSchema: [curated()],
        sqlGenerationSchema: [sql("SELECT payment_method FROM bookings LIMIT 10")],
        judgeSchema: [judgeSchema(answer="No", comments="suspicious")],
    })
    assert "suspicious" in collect("payment methods")[-1]["answer"]
    assert db.executed == []


def test_self_correction_after_db_error(monkeypatch):
    db = install(
        monkeypatch,
        {
            curationSchema: [curated()],
            sqlGenerationSchema: [sql("SELECT pay FROM bookings LIMIT 10"), sql("SELECT payment_method, COUNT(*) AS n FROM bookings GROUP BY 1 LIMIT 10")],
            judgeSchema: [judgeSchema(answer="Yes", comments="ok"), judgeSchema(answer="Yes", comments="ok")],
            "text": ["Done."],
        },
        db_results=[RuntimeError('column "pay" does not exist'), RESULT],
    )
    final = collect("payment methods")[-1]
    assert final["attempts"] == 2 and final["answer"] == "Done."
    assert len(db.executed) == 2


def test_gives_up_after_max_retries(monkeypatch):
    errors = [RuntimeError("boom")] * 3
    install(
        monkeypatch,
        {
            curationSchema: [curated()],
            sqlGenerationSchema: [sql("SELECT x FROM bookings LIMIT 1")] * 3,
            judgeSchema: [judgeSchema(answer="Yes", comments="ok")] * 3,
        },
        db_results=errors,
    )
    final = collect("payment methods")[-1]
    assert final["attempts"] == 3 and "couldn't" in final["answer"]


def test_unanswerable_question(monkeypatch):
    install(monkeypatch, {curationSchema: [curated()], sqlGenerationSchema: [sql("", answerable=False)]})
    assert "couldn't answer" in collect("What is the weather in Austin?")[-1]["answer"]


@pytest.fixture(autouse=True)
def judge_enabled(monkeypatch):
    monkeypatch.setattr(agent.get_settings(), "enable_llm_judge", True)
