from urllib.parse import urljoin

from .base import Adapter
from ..models import JobPosting


BASE = "https://www.impactpool.org"
# Impactpool renders listings client-side; we use Playwright.
SEARCH_URLS = [
    f"{BASE}/jobs?countries=Argentina",
    f"{BASE}/jobs?remote=true",
]


class ImpactpoolAdapter(Adapter):
    name = "impactpool"

    def fetch(self) -> list[JobPosting]:
        # Import here so the module is optional (avoid Playwright startup cost
        # if this adapter is disabled).
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
                    print(f"[impactpool] nav error {url}: {e}")
                    continue

                # Try to accept cookie banner if present
                try:
                    page.get_by_role("button", name="Accept").click(timeout=2000)
                except Exception:
                    pass

                # Extract job anchors in DOM after hydration
                anchors = page.evaluate(
                    """() => Array.from(document.querySelectorAll('a[href*="/job/"]'))
                        .map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            parentText: (a.closest('article, li, div')?.innerText || '').trim().slice(0, 500),
                        }))"""
                )
                for a in anchors:
                    title = a.get("text", "").split("\n")[0].strip()
                    href = a.get("href", "")
                    if not title or len(title) < 8 or not href:
                        continue
                    blob = a.get("parentText", "")
                    # Try to pluck a location line
                    location = None
                    for line in blob.split("\n"):
                        if any(k in line.lower() for k in ("argentina", "buenos", "remote", "home-based")):
                            location = line.strip()
                            break
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location=location,
                    )
                    results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
