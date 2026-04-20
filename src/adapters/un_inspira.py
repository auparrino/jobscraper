from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


BASE = "https://careers.un.org"
# UN Careers (Inspira) — fully JS-rendered SPA. The search page supports
# filters via URL params: duty station / keyword.
SEARCH_URLS = [
    f"{BASE}/jobSearchDescription?language=en&location=Argentina",
    f"{BASE}/jobSearchDescription?language=en&keyword=remote",
    f"{BASE}/jobSearchDescription?language=en&keyword=home-based",
]


class UNInspiraAdapter(Adapter):
    name = "un-inspira"

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
            page = ctx.new_page()
            for url in SEARCH_URLS:
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    # Inspira does a secondary XHR render after load; give it time.
                    page.wait_for_timeout(2500)
                except Exception as e:
                    print(f"[un-inspira] nav error {url}: {e}")
                    continue

                # UN Inspira renders job cards with links to /jobDetails?...
                anchors = page.evaluate(
                    """() => {
                        const links = Array.from(document.querySelectorAll('a[href*=\"jobDetails\"], a[href*=\"jobId\"]'));
                        return links.map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            parentText: (a.closest('article, tr, li, .job-card, div')?.innerText || '').trim().slice(0, 500),
                        }));
                    }"""
                )
                for a in anchors:
                    title = a.get("text", "").split("\n")[0].strip()
                    href = a.get("href", "")
                    if not title or len(title) < 6:
                        continue
                    blob = a.get("parentText", "")
                    location = None
                    for line in blob.split("\n"):
                        low = line.lower()
                        if any(k in low for k in ("argentina", "buenos aires", "remote", "home-based", "duty station")):
                            location = line.strip()
                            break
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location=location,
                        organization="United Nations (Inspira)",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
