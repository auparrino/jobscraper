from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional


@dataclass
class JobPosting:
    source: str
    title: str
    url: str
    location: Optional[str] = None
    posted_at: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = None
    raw: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        basis = f"{self.source}|{self.url}|{self.title}".lower().strip()
        return sha256(basis.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint
        d["seen_at"] = datetime.now(timezone.utc).isoformat()
        return d
