import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.errors import register_error_handlers
from app.logging_config import request_context_middleware, setup_logging
from app.routers import auth, chat, conversations, doubts

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info("DoubtChat started (provider=%s)", settings.effective_provider)
    yield


app = FastAPI(title="DoubtChat", version="1.0.0", lifespan=lifespan)
app.middleware("http")(request_context_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)
register_error_handlers(app)

for r in (auth.router, conversations.router, chat.router, doubts.router):
    app.include_router(r)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
