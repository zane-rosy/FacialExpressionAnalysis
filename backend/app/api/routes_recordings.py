import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.analysis import RecordingSavedResponse

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.post(
    "/save",
    response_model=RecordingSavedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_recording(
    file: UploadFile = File(...),
    label: str = Form(""),
) -> RecordingSavedResponse:
    """Guarda una grabación de webcam en disco de forma permanente."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falta el nombre del archivo.")

    now = datetime.now(timezone.utc)
    date_folder = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    safe_label = "".join(c for c in label if c.isalnum() or c in " _-").strip()
    label_part = f"_{safe_label}" if safe_label else ""

    filename = f"grabacion_{timestamp}{label_part}.mp4"
    output_dir = Path(settings.recording_output_path) / date_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename

    content = await file.read()
    with open(output_path, "wb") as f:
        f.write(content)

    return RecordingSavedResponse(
        filename=filename,
        path=str(output_path),
        label=label,
        recorded_at=now.isoformat(),
    )
