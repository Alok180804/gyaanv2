from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Source:
    id: Optional[int]
    url: str
    drive_id: str
    drive_kind: str
    name: str
    active: bool = True
    status: str = 'pending'
    last_sync_at: Optional[str] = None
    error: Optional[str] = None


@dataclass
class LoadedDocument:
    source_id: int
    drive_file_id: str
    name: str
    mime_type: str
    file_type: str
    modified_time: Optional[str]
    content: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    slide_number: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    document_id: Optional[int]
    content: str
    metadata: dict[str, Any]


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'