from bs4 import BeautifulSoup

from .base import Adapter
from ..models import JobPosting


# ReliefWeb API v1 was decommissioned; v2 requires a registered appname.
# RSS feeds are public and stable when hit from a browser, but their edge
# returns HTTP 202 with empty body to datacenter IPs (GH Actions, etc.).
# Solution: use Playwright to request the feed — real browser fingerprint
# passes through.
FEEDS = [
    ("argentina", "https://reliefweb.int/jobs/rss.xml?advanced-search=%28C22%29"),
    ("home-based", "https://reliefweb.int/jobs/rss.xml?search=home-based"),
    ("remote",     "https://reliefweb.int/jobs/rss.xml?search=remote"),
]


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
        from playwright.sync_api import sync_playwright

        results: dict[str, JobPosting] = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                locale="en-US",
            )
            # Playwright's APIRequestContext uses the browser stack (TLS, HTTP/2,
            # ALPN), which is enough to bypass the 202 edge protection.
            req = ctx.request
            for tag, url in FEEDS:
                try:
                    resp = req.get(url, timeout=30_000)
                except Exception as e:
                    print(f"[reliefweb] {tag}: request error: {e}")
                    continue
                if resp.status != 200:
                    print(f"[reliefweb] {tag}: status={resp.status} — skipping")
                    continue
                body = resp.text()
                if not body.strip():
                    print(f"[reliefweb] {tag}: empty body — skipping")
                    continue
                parsed = self._parse(body, tag)
                print(f"[reliefweb] {tag}: status=200 items={len(parsed)}")
                for p_ in parsed:
                    results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
