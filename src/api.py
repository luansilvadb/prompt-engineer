import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.infrastructure.logging_config import setup_logging
from src.infrastructure.exception_handlers import register_exception_handlers
from src.routers import jobs, frontend

# ── Logging estruturado ──────────────────────────────────────────────────────
setup_logging()

# ── Rate Limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title="Skill Optimizer API", version="0.4.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ────────────────────────────────────────────────────────
register_exception_handlers(app)

# ── Static Files (frontend SPA) ───────────────────────────────────────────────
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    base_dir = Path(sys._MEIPASS)
else:
    base_dir = Path(__file__).parent.parent

frontend_dir = base_dir / "frontend"

if (frontend_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")

if (frontend_dir / "src").exists():
    app.mount("/src", StaticFiles(directory=str(frontend_dir / "src")), name="src")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(jobs.router)
app.include_router(frontend.router)