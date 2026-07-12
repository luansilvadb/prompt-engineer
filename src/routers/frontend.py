import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["Frontend"])

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    base_dir = Path(sys._MEIPASS)
else:
    base_dir = Path(__file__).parent.parent.parent

frontend_dir = base_dir / 'frontend'

@router.get('/{catchall:path}')
async def serve_spa(catchall: str):
    if catchall:
        file_path = frontend_dir / catchall
        if file_path.is_file():
            return FileResponse(file_path)

    index_file = frontend_dir / 'index.html'
    if index_file.is_file():
        return FileResponse(index_file)

    raise HTTPException(
        status_code=404,
        detail="Frontend build not found. Please run 'npm run build' in frontend directory."
    )
