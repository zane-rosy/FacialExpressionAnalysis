import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile


@dataclass
class TemporaryUpload:
    path: Path


class TemporaryFileService:
    async def create_upload_copy(self, file: UploadFile) -> TemporaryUpload:
        suffix = Path(file.filename or "upload.bin").suffix or ".bin"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temporary_path = Path(temp_file.name)

        return TemporaryUpload(path=temporary_path)

    def cleanup(self, path: Path) -> None:
        if path.exists():
            path.unlink()
