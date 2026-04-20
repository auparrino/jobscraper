from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# World Bank Group careers use SAP SuccessFactors hosted at worldbankgroup.csod.com
# plus a front at worldbank.org/en/about/careers. The ATS search endpoint:
BASE = "https://worldbankgroup.csod.com"
SEARCH_URLS = [
    # SuccessFactors Cornerstone career site
    f"{BASE}/ats/careersite/search.aspx?site=1&c=worldbankgroup&keywords=&location=Argentina",
    f"{BASE}/ats/careersite/search.aspx?site=1&c=worldbankgroup&keywords=remote",
    f"{BASE}/ats/careersite/search.aspx?site=1&c=worldbankgroup&keywords=home-based",
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
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"[worldbank] nav error {url}: {e}")
                    continue

                anchors = page.evaluate(
                    """() => {
                        const links = Array.from(document.querySelectorAll('a[href*=\"jobdetails\"], a[href*=\"JobDetail\"], a[href*=\"/job/\"]'));
                        return links.map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            parentText: (a.closest('article, tr, li, div')?.innerText || '').trim().slice(0, 500),
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
