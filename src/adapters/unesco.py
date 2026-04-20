from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# UNESCO careers run on Oracle Taleo (careersection URL). Listings hydrate
# after load. The landing page already SSRs a couple; we still need a browser
# to get the full set.
BASE = "https://careers.unesco.org"
SEARCH_URLS = [
    f"{BASE}/careersection/2/jobsearch.ftl",
]


class UNESCOAdapter(Adapter):
    name = "unesco"

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
                    # UNESCO's Taleo build hides the list until cookies are
                    # accepted. Try a few common accept buttons.
                    for sel in (
                        'button:has-text("Accept")',
                        'button:has-text("Accept all")',
                        'button:has-text("Aceptar")',
                    ):
                        try:
                            page.locator(sel).first.click(timeout=1500)
                            page.wait_for_load_state("networkidle", timeout=8000)
                            break
                        except Exception:
                            pass
                    page.wait_for_selector('a[href*="/job/"]', timeout=25000)
                except Exception as e:
                    print(f"[unesco] nav error {url}: {e}")
                    continue

                anchors = page.evaluate(
                    """() => {
                        const links = Array.from(document.querySelectorAll('a[href*="/job/"]'));
                        return links.map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            rowText: (a.closest('tr, li, article, div')?.innerText || '').trim().slice(0, 500),
                        }));
                    }"""
                )
                print(f"[unesco] {len(anchors)} anchors (pre-filter)")
                for a in anchors:
                    title = a.get("text", "").split("\n")[0].strip()
                    href = a.get("href", "")
                    if not title or len(title) < 5 or "/job/" not in href:
                        continue
                    blob = a.get("rowText", "")
                    # UNESCO job slugs embed the location as first segment:
                    # /job/Paris-Junior-Professional-Officer-...
                    slug_loc = None
                    try:
                        slug = href.split("/job/", 1)[1].split("/")[0]
                        slug_loc = slug.split("-", 1)[0].replace("%20", " ")
                    except Exception:
                        pass
                    location = slug_loc
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
                        organization="UNESCO",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
