from dataclasses import dataclass
from typing import Any, Dict

@dataclass(frozen=True)
class Event:
    type: str
    job_id: str
    data: Dict[str, Any]
