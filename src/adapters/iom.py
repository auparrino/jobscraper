from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# IOM (OIM) blocks direct curl (403). Their public vacancies live at
# recruit.iom.int; the root /career page lists openings.
BASE = "https://recruit.iom.int"
SEARCH_URLS = [
    f"{BASE}/",
]


class IOMAdapter(Adapter):
    name = "iom"

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
                    print(f"[iom] nav error {url}: {e}")
                    continue

                anchors = page.evaluate(
                    """() => {
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        return links.map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            rowText: (a.closest('tr, li, article, .card, div')?.innerText || '').trim().slice(0, 500),
                        }));
                    }"""
                )
                print(f"[iom] {len(anchors)} anchors (pre-filter)")
                for a in anchors:
                    href = a.get("href", "")
                    title = a.get("text", "").split("\n")[0].strip()
                    if not title or len(title) < 6:
                        continue
                    low = href.lower()
                    if not any(k in low for k in ("vacanc", "viewvacancy", "job", "position", "career")):
                        continue
                    blob = a.get("rowText", "")
                    location = None
                    for line in blob.split("\n"):
                        ll = line.lower()
                        if any(k in ll for k in ("argentina", "buenos aires", "remote", "home-based")):
                            location = line.strip()
                            break
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location=location,
                        organization="International Organization for Migration",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
