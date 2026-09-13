import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.analysis import RecordingAnalysisMetadata, RecordingSavedResponse

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.post(
    "/save",
    response_model=RecordingSavedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_recording(
    file: UploadFile = File(...),
    label: str = Form(""),
    participant_id: str = Form(""),
    stimulus_clip_id: str = Form(""),
    stimulus_source_title: str = Form(""),
    stimulus_description: str = Form(""),
) -> RecordingSavedResponse:
    """Guarda una grabación de webcam en disco de forma permanente."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falta el nombre del archivo.")

    now = datetime.now(timezone.utc)
    date_folder = now.strftime("%Y-%m-%d")
    requested_name = Path(file.filename).name
    filename = "".join(c for c in requested_name if c.isalnum() or c in "._-").strip(".")
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de archivo inválido.")
    if Path(filename).suffix.casefold() != ".mp4":
        filename = f"{Path(filename).stem}.mp4"
    output_dir = Path(settings.recording_output_path) / date_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename

    content = await file.read()
    with open(output_path, "wb") as f:
        f.write(content)

    metadata = {
        "reactionFile": filename,
        "participantId": participant_id,
        "label": label,
        "stimulusClipId": stimulus_clip_id or None,
        "stimulusSourceTitle": stimulus_source_title or None,
        "stimulusDescription": stimulus_description or None,
        "recordedAt": now.isoformat(),
        "analysis": None,
    }
    output_path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return RecordingSavedResponse(
        filename=filename,
        path=str(output_path),
        label=label,
        recorded_at=now.isoformat(),
    )


@router.patch("/{filename}/metadata", status_code=status.HTTP_204_NO_CONTENT)
async def update_recording_metadata(filename: str, analysis: RecordingAnalysisMetadata) -> None:
    safe_name = Path(filename).name
    metadata_path = Path(settings.recording_output_path) / datetime.now(timezone.utc).strftime("%Y-%m-%d") / Path(safe_name).with_suffix(".json")
    if not metadata_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontró el archivo de metadatos.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["analysis"] = analysis.model_dump(by_alias=True)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
