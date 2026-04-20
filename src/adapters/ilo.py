from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# ILO runs on SAP SuccessFactors at jobs.ilo.org. Listings are JS-rendered.
# /search/?locationsearch=Argentina filters by country server-side.
BASE = "https://jobs.ilo.org"
SEARCH_URLS = [
    f"{BASE}/search/?locationsearch=Argentina",
    f"{BASE}/search/?q=home-based",
    f"{BASE}/search/?q=remote",
]


class ILOAdapter(Adapter):
    name = "ilo"

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
                    page.goto(url, wait_until="networkidle", timeout=45000)
                    page.wait_for_selector('a[href*="/job/"]', timeout=15000)
                except Exception as e:
                    print(f"[ilo] nav error {url}: {e}")
                    continue

                anchors = page.evaluate(
                    """() => {
                        const links = Array.from(document.querySelectorAll('a[href*="/job/"]'));
                        return links.map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            rowText: (a.closest('tr, li, article, div.job')?.innerText || '').trim().slice(0, 400),
                        }));
                    }"""
                )
                print(f"[ilo] {url} -> {len(anchors)} anchors (pre-filter)")
                for a in anchors:
                    title = a.get("text", "").split("\n")[0].strip()
                    href = a.get("href", "")
                    if not title or len(title) < 5 or "/job/" not in href:
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
                        organization="International Labour Organization",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
