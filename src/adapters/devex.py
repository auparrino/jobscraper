import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


BASE = "https://www.devex.com"
# Devex paywalls full job details, but listing pages render enough to index.
# Filters: location=Argentina OR remote. Devex uses URL params.
PAGES = [
    f"{BASE}/jobs/search?filter%5Blocation%5D%5B%5D=Argentina",
    f"{BASE}/jobs/search?filter%5Bremote%5D=1",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en,es;q=0.8",
}


class DevexAdapter(Adapter):
    """Devex listing pages are public; job detail pages are partially paywalled.
    We index title + url + location from the list, user can click through.
    Selectors may drift — keep robust fallbacks."""
    name = "devex"

    def _parse(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        out: list[JobPosting] = []
        # Try structured cards first
        cards = soup.select("article, div.job-listing, li.job, div[data-job-id]")
        for c in cards:
            a = c.select_one("a[href*='/jobs/']")
            if not a:
                continue
            title = (a.get_text(strip=True) or "").strip()
            href = urljoin(BASE, a.get("href", ""))
            if not title or "/jobs/search" in href:
                continue
            loc_el = c.select_one(".location, [class*=location], [class*=Location]")
            org_el = c.select_one(".organization, .org, [class*=organization]")
            out.append(JobPosting(
                source=self.name,
                title=title,
                url=href,
                location=loc_el.get_text(" ", strip=True) if loc_el else None,
                organization=org_el.get_text(strip=True) if org_el else None,
            ))

        # Fallback: anchors to /jobs/<slug>
        if not out:
            seen = set()
            for a in soup.select("a[href*='/jobs/']"):
                href = urljoin(BASE, a.get("href", ""))
                if "/jobs/search" in href or href in seen:
                    continue
                title = (a.get_text(strip=True) or "").strip()
                if len(title) < 8:
                    continue
                seen.add(href)
                out.append(JobPosting(source=self.name, title=title, url=href))
        return out

    def fetch(self) -> list[JobPosting]:
        results: dict[str, JobPosting] = {}
        with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            for page in PAGES:
                try:
                    r = client.get(page)
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[devex] error fetching {page}: {e}")
                    continue
                for p in self._parse(r.text):
                    # Devex mixes worldwide jobs; keep only AR/remote signals
                    if relevant(p.location, p.title):
                        results.setdefault(p.fingerprint, p)
        return list(results.values())
