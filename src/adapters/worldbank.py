from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# World Bank Group careers run on Cornerstone (csod.com). The careersite home
# page renders a job list client-side; each job link is `/requisition/<id>`.
BASE = "https://worldbankgroup.csod.com"
SEARCH_URLS = [
    f"{BASE}/ux/ats/careersite/1/home?c=worldbankgroup",
]


class WorldBankAdapter(Adapter):
    name = "worldbank"

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
                    # SPA hydration is slow; wait for job links to appear.
                    page.wait_for_selector('a[href*="/requisition/"]', timeout=20000)
                except Exception as e:
                    print(f"[worldbank] nav error {url}: {e}")
                    continue

                # Cornerstone renders ~25 jobs in first page. Each card has the
                # title as anchor text and a separate <span> with location.
                cards = page.evaluate(
                    """() => {
                        const links = Array.from(document.querySelectorAll('a[href*="/requisition/"]'));
                        return links.map(a => {
                            const card = a.closest('article, li, div.card, div');
                            return {
                                href: a.href,
                                text: (a.innerText || '').trim(),
                                cardText: (card?.innerText || '').trim().slice(0, 500),
                            };
                        });
                    }"""
                )
                print(f"[worldbank] fetched {len(cards)} card links (pre-filter)")
                seen = set()
                for c in cards:
                    href = c.get("href", "")
                    if href in seen:
                        continue
                    seen.add(href)
                    title = c.get("text", "").split("\n")[0].strip()
                    if not title or len(title) < 4:
                        continue
                    blob = c.get("cardText", "")
                    location = None
                    for line in blob.split("\n"):
                        low = line.strip().lower()
                        if any(k in low for k in ("argentina", "buenos aires", "remote", "home-based")):
                            location = line.strip()
                            break
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location=location,
                        organization="World Bank Group",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
