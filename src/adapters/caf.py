from urllib.parse import urljoin

from .base import Adapter, relevant
from ..models import JobPosting


# CAF (Banco de Desarrollo de América Latina) — headquarters in Caracas,
# regional offices including Buenos Aires. The site returns ~800 bytes to
# bare curl (bot wall), so Playwright is needed.
BASE = "https://www.caf.com"
SEARCH_URLS = [
    f"{BASE}/es/oportunidades-laborales/",
    f"{BASE}/en/jobs/",
]


class CAFAdapter(Adapter):
    name = "caf"

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
                locale="es-AR",
            )
            page = ctx.new_page()
            for url in SEARCH_URLS:
                try:
                    page.goto(url, wait_until="networkidle", timeout=45000)
                except Exception as e:
                    print(f"[caf] nav error {url}: {e}")
                    continue

                # Extract all anchors + full page text as fallback blob.
                data = page.evaluate(
                    """() => {
                        const anchors = Array.from(document.querySelectorAll('a[href]'));
                        return {
                            body: (document.body?.innerText || '').slice(0, 8000),
                            anchors: anchors.map(a => ({
                                href: a.href,
                                text: (a.innerText || '').trim(),
                                near: (a.closest('li, article, .card, div')?.innerText || '').trim().slice(0, 400),
                            })),
                        };
                    }"""
                )
                anchors = data.get("anchors", [])
                body = data.get("body", "")
                print(f"[caf] {url} -> {len(anchors)} anchors, body {len(body)} chars")
                for a in anchors:
                    href = a.get("href", "")
                    title = a.get("text", "").split("\n")[0].strip()
                    if not title or len(title) < 6:
                        continue
                    low = href.lower()
                    if not any(k in low for k in ("vacante", "oportun", "job", "career", "position")):
                        continue
                    blob = a.get("near", "") + "\n" + body[:500]
                    p_ = JobPosting(
                        source=self.name,
                        title=title,
                        url=urljoin(BASE, href),
                        location=None,
                        organization="CAF - Banco de Desarrollo de América Latina",
                    )
                    if relevant(p_.location, p_.title, blob):
                        results.setdefault(p_.fingerprint, p_)
            browser.close()
        return list(results.values())
