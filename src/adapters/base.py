from abc import ABC, abstractmethod
from ..models import JobPosting


REMOTE_KEYWORDS = (
    "remote", "remoto", "home-based", "home based", "homebased",
    "teletrabajo", "telework", "virtual", "anywhere",
)

AR_KEYWORDS = (
    # Unambiguous substrings only. "ar " / "ar," / "ar)" were removed because
    # they match "madagascar", "qatar", etc. Cordoba/Rosario/Mendoza are also
    # too ambiguous (other countries have same-named cities).
    "argentina",
    "buenos aires",
    "baires",
)


def looks_argentina(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in AR_KEYWORDS)


def looks_remote(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in REMOTE_KEYWORDS)


def relevant(location: str | None, title: str | None = None, desc: str | None = None) -> bool:
    blob = " ".join(filter(None, [location, title, desc]))
    return looks_argentina(blob) or looks_remote(blob)


class Adapter(ABC):
    name: str = ""

    @abstractmethod
    def fetch(self) -> list[JobPosting]:
        ...
