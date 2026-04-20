from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


BASE = "https://jobs.iadb.org"
# IDB uses SAP SuccessFactors — listings are JS-rendered. Use Playwright.
# Their search URLs: /search/?locationsearch=Argentina works for country filter.
SEARCH_URLS = [
    f"{BASE}/search/?locationsearch=Argentina",
    f"{BASE}/search/?q=remote",
    f"{BASE}/search/?q=home-based",
]


class IDBAdapter(Adapter):
    name = "idb"

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
                except Exception as e:
                    print(f"[idb] nav error {url}: {e}")
                    continue

                # SuccessFactors renders rows in table.data-row or .joblist-item.
                # Fall back to any anchor under the results container.
                anchors = page.evaluate(
                    """() => {
                        const rows = Array.from(document.querySelectorAll('a.jobTitle-link, tr.data-row a, .job-link, a[href*=\"/job/\"]'));
                        return rows.map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            parentText: (a.closest('tr, li, article')?.innerText || '').trim().slice(0, 400),
                        }));
                    }"""
                )
                for a in anchors:
                    title = a.get("text", "").split("\n")[0].strip()
                    href = a.get("href", "")
                    if not title or len(title) < 6 or "/job/" not in href:
                        continue
                    blob = a.get("parentText", "")
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
                        organization="Inter-American Development Bank",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
