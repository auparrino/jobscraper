import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


BASE = "https://jobs.unicef.org"
# Search pages render listings server-side in the initial HTML. The
# ?location= filter is approximate — UNICEF's index matches tokens broadly,
# so we always post-filter with relevant().
PAGES = [
    f"{BASE}/en-us/search/?location=Argentina",
    f"{BASE}/en-us/search/?keywords=remote",
    f"{BASE}/en-us/search/?keywords=home-based",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en;q=0.9,es;q=0.8",
}


class UnicefAdapter(Adapter):
    name = "unicef"

    def _parse(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        out: list[JobPosting] = []
        seen = set()
        for a in soup.select('a[href*="/en-us/job/"]'):
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 6:
                continue
            # Location is often in a sibling span or in the URL slug tail.
            # UNICEF slugs frequently embed duty-station + country.
            slug = href.rsplit("/", 1)[-1]
            out.append(JobPosting(
                source=self.name,
                title=title,
                url=urljoin(BASE, href),
                location=slug.replace("-", " "),  # best-effort, used for filtering
                organization="UNICEF",
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
                    print(f"[unicef] error fetching {page}: {e}")
                    continue
                for p in self._parse(r.text):
                    if relevant(p.location, p.title):
                        # Clean the slug-location to something nicer once filter passes
                        p.location = None if "remote" in (p.location or "") else p.location
                        results.setdefault(p.fingerprint, p)
        return list(results.values())
