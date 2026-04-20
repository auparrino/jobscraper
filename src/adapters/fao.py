from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# FAO uses Oracle Taleo. Its jobsearch.ftl is a hashbang SPA that populates
# the result list via JS. We navigate and scrape the hydrated DOM.
BASE = "https://jobs.fao.org"
SEARCH_URLS = [
    f"{BASE}/careersection/fao_external/jobsearch.ftl",
]


class FAOAdapter(Adapter):
    name = "fao"

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
                    # FAO's Taleo template renders each opening as an
                    # application.jss link (25 per page).
                    page.wait_for_selector(
                        'a[href*="application.jss"]',
                        timeout=25000,
                    )
                except Exception as e:
                    print(f"[fao] nav error {url}: {e}")
                    continue

                anchors = page.evaluate(
                    """() => {
                        const q = 'a[href*="application.jss"]';
                        return Array.from(document.querySelectorAll(q)).map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            rowText: (a.closest('tr, li, div.joblist-item, div')?.innerText || '').trim().slice(0, 500),
                        }));
                    }"""
                )
                print(f"[fao] {len(anchors)} anchors (pre-filter)")
                for a in anchors:
                    title = a.get("text", "").split("\n")[0].strip()
                    href = a.get("href", "")
                    if not title or len(title) < 5:
                        continue
                    blob = a.get("rowText", "")
                    location = None
                    for line in blob.split("\n"):
                        low = line.lower()
                        if any(k in low for k in ("argentina", "buenos aires", "remote", "home-based")):
                            location = line.strip()
                            break
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location=location,
                        organization="Food and Agriculture Organization",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
