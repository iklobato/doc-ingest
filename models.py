from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Client:
    name: str
    files: list[Path]


@dataclass
class Invoice:
    path: Path
    client_name: str


@dataclass
class UploadResult:
    status: str
    document: Optional[dict] = None
    message: Optional[str] = None
