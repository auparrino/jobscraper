import httpx
from bs4 import BeautifulSoup

from .base import Adapter
from ..models import JobPosting


# ReliefWeb API v1 was decommissioned; v2 requires an approved appname (manual
# registration). RSS feeds are public and stable. We use two feeds:
#   - Argentina country feed (advanced-search C22 = Argentina)
#   - a text-search feed for home-based / remote roles
# Feed URL pattern: https://reliefweb.int/jobs/rss.xml?<filters>
FEEDS = [
    ("argentina", "https://reliefweb.int/jobs/rss.xml?advanced-search=%28C22%29"),
    ("home-based", "https://reliefweb.int/jobs/rss.xml?search=home-based"),
    ("remote",     "https://reliefweb.int/jobs/rss.xml?search=remote"),
]

HEADERS = {
    "User-Agent": "jobscraper-ar/1.0 (+https://github.com/auparrino/jobscraper)",
}


class ReliefWebAdapter(Adapter):
    name = "reliefweb"

    def _parse(self, xml: str, tag: str) -> list[JobPosting]:
        soup = BeautifulSoup(xml, "xml")
        out: list[JobPosting] = []
        for item in soup.find_all("item"):
            title = (item.title.text if item.title else "").strip()
            url = (item.link.text if item.link else "").strip()
            pub = (item.pubDate.text if item.pubDate else None)
            desc_html = (item.description.text if item.description else "")
            # Description HTML contains the org + country + city in <p>Country: ...</p>
            meta_soup = BeautifulSoup(desc_html, "lxml")
            text = meta_soup.get_text("\n", strip=True)
            location = None
            organization = None
            for line in text.split("\n"):
                low = line.lower()
                if low.startswith("country:"):
                    location = line.split(":", 1)[1].strip()
                elif low.startswith("organization:") or low.startswith("source:"):
                    organization = line.split(":", 1)[1].strip()
                elif low.startswith("city:") and not location:
                    location = line.split(":", 1)[1].strip()
            if not title or not url:
                continue
            out.append(JobPosting(
                source=self.name,
                title=title,
                url=url,
                location=location,
                organization=organization,
                posted_at=pub,
                raw={"feed": tag},
            ))
        return out

    def fetch(self) -> list[JobPosting]:
        results: dict[str, JobPosting] = {}
        with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            for tag, url in FEEDS:
                try:
                    r = client.get(url)
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[reliefweb] error fetching {tag} ({url}): {e}")
                    continue
                for p in self._parse(r.text, tag):
                    results.setdefault(p.fingerprint, p)
        return list(results.values())
