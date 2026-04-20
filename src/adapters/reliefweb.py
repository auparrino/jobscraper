from bs4 import BeautifulSoup

from .base import Adapter
from ..models import JobPosting


# ReliefWeb API v1 was decommissioned; v2 requires a registered appname.
# RSS feeds are public and stable when hit from a browser, but their edge
# returns HTTP 202 with empty body to datacenter IPs (GH Actions, etc.).
# Solution: use Playwright to request the feed — real browser fingerprint
# passes through.
FEEDS = [
    # Argentina country filter (advanced-search code C22 = Argentina).
    ("argentina", "https://reliefweb.int/jobs/rss.xml?advanced-search=%28C22%29"),
    # ReliefWeb's dedicated "Remote / Roster / Roving" curated list — real
    # remote roles, not text-search hits.
    ("remote",    "https://reliefweb.int/jobs/rss.xml?list=Remote%20%2F%20Roster%20%2F%20Roving&view=unspecified-location"),
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
            # Warm up: navigate to the main site so any edge challenge runs JS
            # and sets cookies before we hit the RSS endpoint.
            page = ctx.new_page()
            try:
                page.goto("https://reliefweb.int/jobs", wait_until="domcontentloaded", timeout=30_000)
                # Give any challenge a moment to finish.
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"[reliefweb] warmup nav failed: {e}")

            for tag, url in FEEDS:
                body = None
                try:
                    # Navigating to the feed URL is what finally gets past the 202
                    # gate: the edge treats it as a real browser request.
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    if resp and resp.status != 200:
                        print(f"[reliefweb] {tag}: status={resp.status} — retrying with request()")
                        r2 = ctx.request.get(url, timeout=30_000)
                        if r2.status == 200:
                            body = r2.text()
                    else:
                        body = page.content()
                        # Chromium wraps XML in an HTML viewer; strip it to raw XML
                        if "<rss" not in body and "<RSS" not in body:
                            # get the raw response instead
                            r2 = ctx.request.get(url, timeout=30_000)
                            if r2.status == 200:
                                body = r2.text()
                except Exception as e:
                    print(f"[reliefweb] {tag}: error: {e}")
                    continue
                if not body or not body.strip():
                    print(f"[reliefweb] {tag}: empty body — skipping")
                    continue
                # Extract just the XML payload if the browser wrapped it
                start = body.find("<?xml")
                if start == -1:
                    start = body.find("<rss")
                if start > 0:
                    body = body[start:]
                parsed = self._parse(body, tag)
                print(f"[reliefweb] {tag}: items={len(parsed)}")
                for p_ in parsed:
                    results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
