"""Native HTTP entry point for the central engine's isolated releases."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .architect_planner import ClientIntent
from .central_engine import PREFIX, find_file, generate_central

ROOT = Path(__file__).resolve().parents[2] / "outputs" / "central"
router = APIRouter(prefix="/api/central/v1", tags=["central-engine"])


@router.post("/design")
def design(intent: ClientIntent):
    try:
        return generate_central(intent, ROOT)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get(PREFIX.removeprefix("/api/central/v1") + "/{run_id}/files/{filename}")
def file(run_id: str, filename: str):
    path = find_file(ROOT, run_id, filename)
    if path is None:
        raise HTTPException(status_code=404)
    return FileResponse(path, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
