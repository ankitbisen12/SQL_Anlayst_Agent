"""
Offline evaluation of the SQL Analyst agent.

    uv run python evals/run_evals.py                      # all cases
    uv run python evals/run_evals.py --category join      # one category
    uv run python evals/run_evals.py --judge              # + LLM-as-judge answer quality
    uv run python evals/run_evals.py --min-accuracy 0.8   # non-zero exit code below threshold (CI gate)

Metrics
  * execution accuracy : the agent's result set matches the gold SQL result (column-name and order agnostic)
  * guardrail accuracy : malicious / sensitive / off-topic questions are refused and no SQL is executed
  * answer quality     : (optional) LLM judge scores faithfulness + helpfulness of the final answer, 1-5
  * latency            : p50 / p95 seconds per question, average SQL attempts (self-corrections)
"""

import argparse
import datetime as dt
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field  # noqa: E402

from agents.sql_analyst import run_agent  # noqa: E402
from utils.database import DatabaseUtil  # noqa: E402
from utils.llm_pick import llm_pick  # noqa: E402

DATASET = Path(__file__).with_name("dataset.jsonl")
RESULTS_DIR = Path(__file__).with_name("results")


class AnswerGrade(BaseModel):
    score: int = Field(..., ge=1, le=5, description="1 = wrong or unfaithful, 5 = correct, faithful and clear")
    reason: str = Field(..., description="One short sentence")


def _norm(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return str(value).strip().lower()


def _column(result: dict, idx: int) -> Counter:
    return Counter(_norm(row[idx]) for row in result["rows"])


def results_match(gold: dict, predicted: dict) -> bool:
    """Every gold column must appear (as a multiset of values) in the predicted result, with equal row count."""
    if not predicted or len(gold["rows"]) != len(predicted.get("rows", [])):
        return False
    predicted_cols = [_column(predicted, i) for i in range(len(predicted["columns"]))]
    used: set[int] = set()
    for gi in range(len(gold["columns"])):
        gold_col = _column(gold, gi)
        match = next((pi for pi, col in enumerate(predicted_cols) if pi not in used and col == gold_col), None)
        if match is None:
            return False
        used.add(match)
    return True


def grade_answer(question: str, gold: dict, answer: str) -> AnswerGrade:
    judge = llm_pick("high").with_structured_output(AnswerGrade)
    return judge.invoke(f"""
    You are grading an analytics assistant. Compare its answer with the correct query result.
    Score 5 if the answer is correct, only uses numbers supported by the result and directly answers the question.
    Question: {question}
    Correct result (columns, rows): {gold['columns']} {gold['rows'][:30]}
    Assistant answer: {answer}
    """)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--judge", action="store_true", help="score final answers with an LLM judge")
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    args = parser.parse_args()

    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    cases = cases[: args.limit] if args.limit else cases

    db = DatabaseUtil()
    records = []
    for case in cases:
        started = time.perf_counter()
        try:
            state = run_agent(case["question"], case.get("history"))
            error = ""
        except Exception as exc:
            state, error = {}, f"{type(exc).__name__}: {exc}"
        latency = time.perf_counter() - started

        executed = state.get("is_safe") == "Yes" and bool(state.get("sql_query_execution_result", {}).get("columns"))
        record = {
            "id": case["id"], "category": case["category"], "question": case["question"],
            "intent": state.get("intent", ""), "sql": state.get("generated_sql_query", ""),
            "answer": state.get("final_answer", ""), "attempts": state.get("attempts", 0),
            "latency_s": round(latency, 2), "error": error,
        }

        if case.get("expect_blocked"):
            record["passed"] = not error and not executed
        else:
            gold = db.execute_query(case["gold_sql"])
            record["passed"] = not error and results_match(gold, state.get("sql_query_execution_result", {}))
            if args.judge and not error:
                grade = grade_answer(case["question"], gold, record["answer"])
                record["answer_score"], record["answer_reason"] = grade.score, grade.reason

        records.append(record)
        mark = "PASS" if record["passed"] else "FAIL"
        print(f"[{mark}] {case['id']:<20} {latency:5.1f}s  {case['question'][:70]}")
        if not record["passed"]:
            print(f"        sql: {record['sql'] or '-'}\n        answer: {record['answer'][:160]}  {error}")

    by_cat: dict[str, list[bool]] = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r["passed"])
    data_records = [r for r in records if r["category"] != "guardrail"]
    guard_records = [r for r in records if r["category"] == "guardrail"]
    scores = [r["answer_score"] for r in records if "answer_score" in r]
    latencies = [r["latency_s"] for r in records]

    summary = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "cases": len(records),
        "execution_accuracy": round(sum(r["passed"] for r in data_records) / len(data_records), 3) if data_records else None,
        "guardrail_accuracy": round(sum(r["passed"] for r in guard_records) / len(guard_records), 3) if guard_records else None,
        "overall_accuracy": round(sum(r["passed"] for r in records) / len(records), 3) if records else 0,
        "answer_quality_avg": round(statistics.mean(scores), 2) if scores else None,
        "latency_p50_s": percentile(latencies, 0.5),
        "latency_p95_s": percentile(latencies, 0.95),
        "avg_sql_attempts": round(statistics.mean(r["attempts"] for r in data_records), 2) if data_records else None,
        "per_category": {c: f"{sum(v)}/{len(v)}" for c, v in sorted(by_cat.items())},
    }

    print("\n" + json.dumps(summary, indent=2))
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"eval_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"summary": summary, "records": records}, indent=2), encoding="utf-8")
    print(f"Saved detailed results to {out}")

    if summary["overall_accuracy"] < args.min_accuracy:
        sys.exit(f"Overall accuracy {summary['overall_accuracy']} is below --min-accuracy {args.min_accuracy}")


if __name__ == "__main__":
    main()
