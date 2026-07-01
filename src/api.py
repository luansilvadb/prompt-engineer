import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.routers import jobs, frontend

app = FastAPI(title='Skill Optimizer API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    base_dir = Path(sys._MEIPASS)
else:
    base_dir = Path(__file__).parent.parent

frontend_dir = base_dir / 'frontend' / 'dist'

if (frontend_dir / 'assets').exists():
    app.mount('/assets', StaticFiles(directory=str(frontend_dir / 'assets')), name='assets')

app.include_router(jobs.router)
app.include_router(frontend.router)
