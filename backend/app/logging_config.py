import contextvars
import json
import logging
import time
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").disabled = True  # we log requests ourselves


def log(logger: logging.Logger, msg: str, **fields) -> None:
    logger.info(msg, extra={"extra_fields": fields})


async def request_context_middleware(request, call_next):
    """Assign a request id, log method/path/status/duration. Never logs bodies."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    start = time.perf_counter()
    logger = logging.getLogger("http")
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error", extra={"extra_fields": {"path": request.url.path}})
        raise
    finally:
        pass
    duration = round((time.perf_counter() - start) * 1000, 1)
    log(
        logger,
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration,
    )
    response.headers["X-Request-ID"] = rid
    request_id_var.reset(token)
    return response
