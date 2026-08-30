from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings


class StimulusCatalogService:
    """Consulta metadatos de estímulos sin exponer la carpeta de videos."""

    def __init__(self) -> None:
        self.metadata_file = Path(settings.stimulus_metadata_file)

    def lookup(self, filename: str) -> dict[str, object] | None:
        requested = Path(filename).stem.casefold()
        return next((value for key, value in self._rows().items() if Path(key).stem.casefold() == requested), None)

    def catalog(self) -> list[dict[str, object]]:
        return list(self._rows().values())

    def _rows(self) -> dict[str, dict[str, object]]:
        if not self.metadata_file.exists():
            return {}
        return json.loads(self.metadata_file.read_text(encoding="utf-8"))
