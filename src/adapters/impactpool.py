import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


BASE = "https://www.impactpool.org"
# Impactpool's query params (?countries=, ?remote=) don't appear to filter
# server-side — the page returns a generic listing regardless. So we fetch
# the generic listings and post-filter locally for AR / remote signals.
PAGES = [
    f"{BASE}/jobs?countries=Argentina",
    f"{BASE}/jobs?remote=true",
    f"{BASE}/jobs",  # general feed, post-filtered
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en;q=0.9,es;q=0.8",
}


class ImpactpoolAdapter(Adapter):
    name = "impactpool"

    def _parse(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        out: list[JobPosting] = []
        for a in soup.select('a[href^="/jobs/"]'):
            href = a.get("href", "")
            # job detail URLs look like /jobs/<numeric-id>
            tail = href[len("/jobs/"):]
            if not tail or not tail.split("?")[0].isdigit():
                continue
            text = a.get_text("\n", strip=True)
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            if not lines:
                continue
            title = lines[0]
            organization = lines[1] if len(lines) > 1 else None
            # Remaining lines are typically location bits + seniority
            location = " | ".join(lines[2:-1]) if len(lines) > 3 else (lines[2] if len(lines) > 2 else None)
            out.append(JobPosting(
                source=self.name,
                title=title,
                url=urljoin(BASE, href),
                organization=organization,
                location=location,
            ))
        return out

    def fetch(self) -> list[JobPosting]:
        results: dict[str, JobPosting] = {}
        with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            for page in PAGES:
                try:
                    r = client.get(page)
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[impactpool] error fetching {page}: {e}")
                    continue
                for p in self._parse(r.text):
                    if relevant(p.location, p.title):
                        results.setdefault(p.fingerprint, p)
        return list(results.values())
