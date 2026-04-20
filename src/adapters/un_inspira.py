import httpx
from bs4 import BeautifulSoup

from .base import Adapter, relevant
from ..models import JobPosting


# UN Careers (fka Inspira) exposes a public RSS feed at /jobfeed with the
# full global UN openings — hundreds of items. We post-filter for AR / remote.
FEED_URL = "https://careers.un.org/jobfeed"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}


class UNInspiraAdapter(Adapter):
    name = "un-inspira"

    def _parse(self, xml: str) -> list[JobPosting]:
        soup = BeautifulSoup(xml, "xml")
        out: list[JobPosting] = []
        for item in soup.find_all("item"):
            title = (item.title.text if item.title else "").strip()
            url = (item.link.text if item.link else "").strip()
            pub = (item.pubDate.text if item.pubDate else None)
            desc_html = (item.description.text if item.description else "")
            # Description body has embedded meta like "Duty Station : Buenos Aires"
            meta_soup = BeautifulSoup(desc_html, "lxml")
            text = meta_soup.get_text("\n", strip=True)
            location = None
            organization = None
            for line in text.split("\n"):
                low = line.lower()
                if low.startswith("duty station"):
                    location = line.split(":", 1)[-1].strip()
                elif low.startswith("department"):
                    organization = line.split(":", 1)[-1].strip()
            if not title or not url:
                continue
            out.append(JobPosting(
                source=self.name,
                title=title,
                url=url,
                location=location,
                organization=organization or "United Nations",
                posted_at=pub,
                description=text[:500] if text else None,
            ))
        return out

    def fetch(self) -> list[JobPosting]:
        results: dict[str, JobPosting] = {}
        with httpx.Client(timeout=45, headers=HEADERS, follow_redirects=True) as client:
            try:
                r = client.get(FEED_URL)
                r.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[un-inspira] error fetching {FEED_URL}: {e}")
                return []
            parsed = self._parse(r.text)
            print(f"[un-inspira] fetched {len(parsed)} total items (pre-filter)")
            for p in parsed:
                if relevant(p.location, p.title, p.description):
                    results.setdefault(p.fingerprint, p)
        return list(results.values())
