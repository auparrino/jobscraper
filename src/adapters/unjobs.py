import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import Adapter
from ..models import JobPosting


BASE = "https://unjobs.org"
# UNjobs uses "duty station" pages. Argentina + home-based.
PAGES = [
    f"{BASE}/duty_stations/argentina",
    f"{BASE}/duty_stations/home_based",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en,es;q=0.8",
}


class UNJobsAdapter(Adapter):
    name = "unjobs"

    def _parse(self, html: str) -> list[JobPosting]:
        soup = BeautifulSoup(html, "lxml")
        out: list[JobPosting] = []
        # UNjobs list items: <div class="job"> with <a class="jtitle"> inside
        for row in soup.select("div.job, li.job, article.job"):
            a = row.select_one("a.jtitle") or row.select_one("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = urljoin(BASE, a.get("href", ""))
            if not title or not href:
                continue
            # meta: organization + location typically in sibling spans
            org_el = row.select_one(".org, .source, .employer")
            loc_el = row.select_one(".duty, .duty_station, .location")
            date_el = row.select_one(".date, time")
            out.append(JobPosting(
                source=self.name,
                title=title,
                url=href,
                organization=org_el.get_text(strip=True) if org_el else None,
                location=loc_el.get_text(strip=True) if loc_el else None,
                posted_at=date_el.get("datetime") if date_el and date_el.has_attr("datetime")
                           else (date_el.get_text(strip=True) if date_el else None),
            ))

        # Fallback: UNjobs markup is inconsistent; scan anchors that look like job links
        if not out:
            for a in soup.select("a[href*='/vacancies/']"):
                title = a.get_text(strip=True)
                if len(title) < 8:
                    continue
                out.append(JobPosting(
                    source=self.name,
                    title=title,
                    url=urljoin(BASE, a.get("href", "")),
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
                    print(f"[unjobs] error fetching {page}: {e}")
                    continue
                for p in self._parse(r.text):
                    results.setdefault(p.fingerprint, p)
        return list(results.values())
