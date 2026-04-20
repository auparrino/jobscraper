from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# Global Affairs Canada — LES (Locally Engaged Staff) portal. Uses jQuery
# DataTables that pull JSON; easier to let JS render and scrape the table.
BASE = "https://staffing-les.international.gc.ca"
SEARCH_URLS = [
    f"{BASE}/en/search/?term=argentina",
]


class EmbassyCanadaAdapter(Adapter):
    name = "emb-canada"

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
                locale="en-CA",
            )
            page = ctx.new_page()
            for url in SEARCH_URLS:
                try:
                    page.goto(url, wait_until="networkidle", timeout=45000)
                    page.wait_for_selector('table tbody tr', timeout=15000)
                except Exception as e:
                    print(f"[emb-canada] nav error {url}: {e}")
                    continue

                rows = page.evaluate(
                    """() => {
                        const trs = Array.from(document.querySelectorAll('table tbody tr'));
                        return trs.map(tr => {
                            const a = tr.querySelector('a[href]');
                            const cells = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                            return {
                                href: a ? a.href : null,
                                title: a ? a.innerText.trim() : (cells[0] || ''),
                                cells: cells,
                            };
                        });
                    }"""
                )
                print(f"[emb-canada] {len(rows)} rows (pre-filter)")
                for r in rows:
                    href = r.get("href") or ""
                    title = (r.get("title") or "").split("\n")[0].strip()
                    cells = r.get("cells") or []
                    if not title or len(title) < 4:
                        continue
                    # Columns typically: position | country | city | function | listing | close
                    country = cells[1] if len(cells) > 1 else ""
                    city = cells[2] if len(cells) > 2 else ""
                    location = ", ".join(filter(None, [city, country])) or None
                    blob = " | ".join(cells)
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href) if href else url,
                        location=location,
                        organization="Global Affairs Canada",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
