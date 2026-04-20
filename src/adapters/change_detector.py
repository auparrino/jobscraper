"""Generic change-detector for static embassy/news pages.

For sources that don't expose structured job listings, we hash the page
body. When the hash changes vs. last run, we emit a single JobPosting-like
item pointing at the page so the user can inspect manually.
"""
from __future__ import annotations

import hashlib
import re

import httpx
from bs4 import BeautifulSoup

from .base import Adapter
from ..models import JobPosting


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}


# (name, url, organization, content_selector_or_None)
# content selector narrows hashing to the main content area to avoid churn
# from header widgets, cookie banners, timestamps, etc.
WATCH_PAGES: list[tuple[str, str, str, str | None]] = [
    ("emb-australia", "https://argentina.embassy.gov.au/baircastellano/jobopportunities.html",
     "Australian Embassy Argentina", "main, #main-content, .main-content"),
    ("emb-ireland", "https://www.ireland.ie/en/argentina/buenosaires/about/job-opportunities/",
     "Embassy of Ireland Argentina", "main, article"),
    ("emb-sweden", "https://www.swedenabroad.se/es/embajada/argentina-buenos-aires/actualidad/noticias/",
     "Embassy of Sweden Argentina", "main, .content, article"),
    ("emb-norway", "https://www.norway.no/es/argentina/",
     "Embassy of Norway Argentina", "main, article"),
    ("emb-japan", "https://www.ar.emb-japan.go.jp/itprtop_es/index.html",
     "Embassy of Japan Argentina", None),
    ("emb-turkey", "https://buenosaires-emb.mfa.gov.tr/Mission/Announcements",
     "Embassy of Türkiye Argentina", None),
    ("emb-korea", "https://www.mofa.go.kr/ar-es/brd/m_6289/list.do",
     "Embassy of Korea Argentina", "main, .board, .content"),
    ("emb-greece", "https://www.mfa.gr/missionsabroad/es/argentina.html",
     "Embassy of Greece Argentina", "main, article, .content"),
]


def _extract_content(html: str, selector: str | None) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    node = None
    if selector:
        for sel in [s.strip() for s in selector.split(",")]:
            node = soup.select_one(sel)
            if node:
                break
    if node is None:
        node = soup.body or soup
    text = node.get_text("\n", strip=True)
    # Collapse runs of whitespace so cosmetic formatting changes don't churn.
    text = re.sub(r"\s+", " ", text)
    return text


class ChangePageAdapter(Adapter):
    """Emits a pseudo-posting keyed by (url, content-hash).

    When the page body changes, a new fingerprint is generated and the Store
    treats it as a "new" job. Title includes the hash prefix so the user can
    tell at a glance when a page has actually changed.
    """

    name = "change-detect"

    def fetch(self) -> list[JobPosting]:
        out: list[JobPosting] = []
        pending: list[tuple[str, str, str, str | None]] = []
        with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
            for entry in WATCH_PAGES:
                key, url, org, selector = entry
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    text = _extract_content(r.text, selector)
                    if not text:
                        raise ValueError("empty content")
                except Exception as e:
                    print(f"[change-detect] {key} httpx failed: {e} — queuing Playwright fallback")
                    pending.append(entry)
                    continue
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
                out.append(JobPosting(
                    source=f"watch-{key}",
                    title=f"[check page] {org} — rev {digest}",
                    url=url,
                    location="Argentina",
                    organization=org,
                    description=text[:400],
                ))
                print(f"[change-detect] {key} ok (rev {digest}, {len(text)} chars)")

        if pending:
            try:
                from playwright.sync_api import sync_playwright
            except Exception as e:
                print(f"[change-detect] Playwright unavailable: {e}")
                return out
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent=HEADERS["User-Agent"], locale="es-AR",
                )
                page = ctx.new_page()
                for key, url, org, selector in pending:
                    try:
                        page.goto(url, wait_until="networkidle", timeout=45000)
                        html = page.content()
                    except Exception as e:
                        print(f"[change-detect] {key} playwright failed: {e}")
                        continue
                    try:
                        text = _extract_content(html, selector)
                    except Exception as e:
                        print(f"[change-detect] {key} parse error: {e}")
                        continue
                    if not text:
                        print(f"[change-detect] {key} empty content after playwright")
                        continue
                    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
                    out.append(JobPosting(
                        source=f"watch-{key}",
                        title=f"[check page] {org} — rev {digest}",
                        url=url,
                        location="Argentina",
                        organization=org,
                        description=text[:400],
                    ))
                    print(f"[change-detect] {key} ok via playwright (rev {digest}, {len(text)} chars)")
                browser.close()
        return out
