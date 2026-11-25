"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# Structured JSON Logging
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "lvl": record.levelname,
            "logger": record.name,
        }
        try:
            parsed = json.loads(msg)
            if isinstance(parsed, dict):
                data.update(parsed)
            else:
                data["msg"] = parsed
        except Exception:
            data["msg"] = msg
        return json.dumps(data)


log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(JsonFormatter())

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: xử lý SIGTERM và shutdown an toàn."""
    logger.info(json.dumps({"event": "startup", "app": "production-agent", "port": settings.port}))
    yield
    logger.info(json.dumps({"event": "shutdown", "action": "graceful_exit", "status": "completed"}))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def json_logging_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(json.dumps({
        "event": "request",
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": duration_ms,
    }))
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None

    class Config:
        extra = "ignore"


@app.get("/health")
def health():
    """GET /health — liveness probe: luôn trả 200 khi container/process còn chạy."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """GET /ready — readiness probe: 200 khi Redis kết nối được, 503 khi mất kết nối."""
    if redis_healthy():
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "not ready", "error": "Redis unavailable"})


@app.post("/ask")
def ask(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):
    """POST /ask — xử lý câu hỏi với đầy đủ Auth, Rate Limiter và Cost Guard."""
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    in_tokens = max(10, len(body.question.split()) * 2)
    out_tokens = max(20, len(answer.split()) * 2)
    record_cost(in_tokens, out_tokens)

    return {"question": body.question, "answer": answer}
