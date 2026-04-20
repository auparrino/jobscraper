from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# US Department of State — ERA (Electronic Recruitment Application) for
# locally-employed staff at overseas missions. Per-post site for Argentina.
BASE = "https://erajobs.state.gov"
SEARCH_URLS = [
    f"{BASE}/dos-era/arg/vacancysearch/searchVacancies.hms",
]


class EmbassyUSAAdapter(Adapter):
    name = "emb-usa"

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
                    # ERA shows vacancies in a table once loaded.
                    page.wait_for_selector('table, a[href*="vacancyDetail"]', timeout=15000)
                except Exception as e:
                    print(f"[emb-usa] nav error {url}: {e}")
                    continue

                data = page.evaluate(
                    """() => {
                        const trs = Array.from(document.querySelectorAll('tr'));
                        const rows = trs.map(tr => {
                            const a = tr.querySelector('a[href]');
                            const cells = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                            return {
                                href: a ? a.href : null,
                                title: a ? a.innerText.trim() : '',
                                cells: cells,
                            };
                        }).filter(r => r.href);
                        return {
                            rows: rows,
                            bodyText: (document.body?.innerText || '').slice(0, 2000),
                        };
                    }"""
                )
                rows = data.get("rows", [])
                body = data.get("bodyText", "")
                print(f"[emb-usa] {len(rows)} rows; body {len(body)} chars")
                for r in rows:
                    href = r.get("href") or ""
                    title = (r.get("title") or "").split("\n")[0].strip()
                    cells = r.get("cells") or []
                    if not title or len(title) < 4:
                        continue
                    # ERA links look like .../vacancyDetail.hms?... — filter.
                    if "vacancy" not in href.lower():
                        continue
                    blob = " | ".join(cells) + "\n" + body
                    # Buenos Aires implicit (this is the Argentina post site).
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location="Buenos Aires, Argentina",
                        organization="U.S. Embassy Buenos Aires",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
