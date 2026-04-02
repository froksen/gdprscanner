from dataclasses import dataclass, field
from typing import Literal, Optional


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
class ScanCompleteEvent:
    type: Literal["scan_complete"] = "scan_complete"
    files_scanned: int = 0
    findings_count: int = 0


@dataclass
class FindingEvent:
    type: Literal["finding"] = "finding"
    path: str = ""
    reason: str = ""
    snippet: Optional[str] = None
    age_days: Optional[int] = None
