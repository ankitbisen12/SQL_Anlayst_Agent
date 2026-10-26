import json
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.sql_analyst import run_agent, stream_agent
from utils.config import get_settings
from utils.database import DatabaseUtil, close_pool

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("api")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(title="Airbnb SQL Analyst API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# ---------------- request models ----------------
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=settings.max_question_chars)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


# ---------------- security dependencies ----------------
class RateLimiter:
    """
    Sliding-window limiter per client IP. In-memory, so it is per instance:
    put a shared store (e.g. Redis) or the platform's rate limiting in front when running multiple replicas.
    """

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit, self.window = limit, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = Lock()

    def __call__(self, request: Request) -> None:
        if self.limit <= 0:
            return
        forwarded = request.headers.get("x-forwarded-for", "")
        key = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
            q.append(now)


rate_limit = RateLimiter(settings.rate_limit_per_minute)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.app_api_key and x_api_key != settings.app_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ---------------- middleware ----------------
@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%d",
        request_id, request.method, request.url.path, response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


# ---------------- routes ----------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/health/ready")
def ready():
    try:
        DatabaseUtil().ping()
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database is not reachable.") from exc
    return {"status": "ready"}


def _sse(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"


@app.post("/api/chat/stream", dependencies=[Depends(require_api_key), Depends(rate_limit)])
def chat_stream(body: ChatRequest):
    history = [t.model_dump() for t in body.history]

    def event_source():
        try:
            for event in stream_agent(body.question, history):
                yield _sse(event)
        except Exception:
            logger.exception("Agent failed")
            yield _sse({"type": "error", "message": "Something went wrong while answering. Please try again."})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/chat", dependencies=[Depends(require_api_key), Depends(rate_limit)])
def chat(body: ChatRequest):
    """Non-streaming variant for scripts and integrations."""
    state = run_agent(body.question, [t.model_dump() for t in body.history])
    return {
        "answer": state.get("final_answer", ""),
        "intent": state.get("intent", ""),
        "sql": state.get("generated_sql_query", "") if state.get("is_safe") == "Yes" else "",
        "result": state.get("sql_query_execution_result", {}),
        "chart": state.get("chart", {}),
    }


# Serve the built React app from the same origin when it exists (single-container deployment).
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        file = (FRONTEND_DIST / full_path).resolve()
        if full_path and file.is_file() and FRONTEND_DIST in file.parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
