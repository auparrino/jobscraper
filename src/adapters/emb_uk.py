from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# UK FCDO's TalentLink ATS. The advanced-search page SSRs the filter UI
# but fills rows via JS. We need to filter by Argentina after load.
BASE = "https://fcdo.tal.net"
SEARCH_URLS = [
    f"{BASE}/vx/appcentre-ext/candidate/jobboard/vacancy/1/adv/",
]


class EmbassyUKAdapter(Adapter):
    name = "emb-uk"

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
                locale="en-GB",
            )
            page = ctx.new_page()
            for url in SEARCH_URLS:
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    page.wait_for_selector('a[href*="/vacancy/"]', timeout=20000)
                except Exception as e:
                    print(f"[emb-uk] nav error {url}: {e}")
                    continue

                anchors = page.evaluate(
                    """() => {
                        const links = Array.from(document.querySelectorAll('a[href*="/vacancy/"]'));
                        return links.map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            rowText: (a.closest('tr, li, article, .row, div.vacancy')?.innerText || '').trim().slice(0, 600),
                        }));
                    }"""
                )
                print(f"[emb-uk] {len(anchors)} anchors (pre-filter)")
                for a in anchors:
                    href = a.get("href", "")
                    title = a.get("text", "").split("\n")[0].strip()
                    if not title or len(title) < 6:
                        continue
                    # The listing URL itself contains /vacancy/1/adv/ — skip it.
                    if href.rstrip("/").endswith("/adv"):
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
                        organization="UK Foreign, Commonwealth & Development Office",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
