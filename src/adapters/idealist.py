from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


BASE = "https://www.idealist.org"
# Idealist ships a Next.js app; listings are SSR'd but also hydrate.
# Use their public search URL with location filters.
SEARCH_URLS = [
    # Argentina (country)
    f"{BASE}/en/jobs?searchMode=LOCATION&locationName=Argentina",
    # Remote jobs (their flag)
    f"{BASE}/en/jobs?remote=true",
]


class IdealistAdapter(Adapter):
    name = "idealist"

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
                    print(f"[idealist] nav error {url}: {e}")
                    continue
                try:
                    page.get_by_role("button", name="Accept").click(timeout=2000)
                except Exception:
                    pass

                anchors = page.evaluate(
                    """() => Array.from(document.querySelectorAll('a[href*="/en/nonprofit-job/"], a[href*="/es/empleo-sin-fines-de-lucro/"]'))
                        .map(a => ({
                            href: a.href,
                            text: (a.innerText || '').trim(),
                            parentText: (a.closest('article, li, div')?.innerText || '').trim().slice(0, 500),
                        }))"""
                )
                for a in anchors:
                    title = a.get("text", "").split("\n")[0].strip()
                    href = a.get("href", "")
                    if not title or len(title) < 6 or not href:
                        continue
                    blob = a.get("parentText", "")
                    location = None
                    org = None
                    lines = [ln.strip() for ln in blob.split("\n") if ln.strip()]
                    for ln in lines:
                        low = ln.lower()
                        if any(k in low for k in ("argentina", "buenos aires", "remote", "remoto")):
                            location = ln
                            break
                    if len(lines) >= 2 and lines[0] == title:
                        org = lines[1]
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location=location,
                        organization=org,
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
