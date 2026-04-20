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
                    page.wait_for_selector('table tr', timeout=20000)
                except Exception as e:
                    print(f"[emb-uk] nav error {url}: {e}")
                    continue

                # TalentLink renders the result list as a <table>. Each <tr>
                # has a title anchor, a country cell, a job-type cell, etc.
                rows = page.evaluate(
                    """() => {
                        const trs = Array.from(document.querySelectorAll('tr'));
                        return trs.map(tr => {
                            const a = tr.querySelector('a[href]');
                            const cells = Array.from(tr.querySelectorAll('td, th'))
                                .map(c => c.innerText.trim());
                            return {
                                href: a ? a.href : null,
                                title: a ? a.innerText.trim() : '',
                                cells: cells,
                                rowText: tr.innerText.trim().slice(0, 600),
                            };
                        });
                    }"""
                )
                print(f"[emb-uk] {len(rows)} rows (pre-filter)")
                for r in rows:
                    href = r.get("href") or ""
                    title = (r.get("title") or "").split("\n")[0].strip()
                    if not title or len(title) < 6 or not href:
                        continue
                    # Skip nav anchors (the listing URL itself, filter toggles).
                    if href.rstrip("/").endswith("/adv") or "#" in href or "/lang-" not in href:
                        # Job-detail URLs on TalentLink include /lang-XX/.
                        continue
                    cells = r.get("cells") or []
                    location = " · ".join(cells[1:3]) if len(cells) > 2 else None
                    blob = r.get("rowText", "")
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
