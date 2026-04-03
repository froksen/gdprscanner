from dataclasses import dataclass, field
from typing import Literal, Optional, List


@dataclass
class OpenConfigEvent:
    type: Literal["open_config"] = "open_config"


@dataclass
class ScanNowEvent:
    type: Literal["scan_now"] = "scan_now"


@dataclass
class ShutdownEvent:
    type: Literal["shutdown"] = "shutdown"


@dataclass
class ScanProgressEvent:
    type: Literal["scan_progress"] = "scan_progress"
    current: int = 0
    total: int = 0
    current_file: str = ""


@dataclass
class ScanCompleteEvent:
    type: Literal["scan_complete"] = "scan_complete"
    files_scanned: int = 0
    findings_count: int = 0


@dataclass
class FileFinding:
    """One GDPR hit within a file."""
    reason: str
    snippet: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class FindingEvent:
    """All GDPR hits for a single file — one event per file."""
    type: Literal["finding"] = "finding"
    path: str = ""
    age_days: Optional[int] = None
    findings: List[FileFinding] = field(default_factory=list)
