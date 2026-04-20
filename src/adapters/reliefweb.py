import httpx
from datetime import datetime, timezone

from .base import Adapter
from ..models import JobPosting


API_URL = "https://api.reliefweb.int/v1/jobs"
APPNAME = "jobscraper-ar"


class ReliefWebAdapter(Adapter):
    """ReliefWeb has a proper public API. We query twice:
    1. Jobs in country=Argentina
    2. Jobs flagged as home-based/remote (experiential.name = 'Home-based')
    The API returns structured JSON; no HTML parsing needed.
    Docs: https://apidoc.reliefweb.int/
    """
    name = "reliefweb"

    def _query(self, body: dict) -> list[dict]:
        params = {"appname": APPNAME}
        with httpx.Client(timeout=30) as client:
            r = client.post(API_URL, params=params, json=body)
            r.raise_for_status()
            return r.json().get("data", [])

    def _to_posting(self, item: dict) -> JobPosting:
        f = item.get("fields", {})
        country_names = [c.get("name") for c in f.get("country", []) if c.get("name")]
        city_names = [c.get("name") for c in f.get("city", []) if c.get("name")]
        location = ", ".join(city_names + country_names) or None
        orgs = [s.get("name") for s in f.get("source", []) if s.get("name")]
        return JobPosting(
            source=self.name,
            title=f.get("title", "").strip(),
            url=f.get("url_alias") or f.get("url") or "",
            location=location,
            posted_at=f.get("date", {}).get("created"),
            organization=", ".join(orgs) or None,
            description=None,
            raw=f,
        )

    def fetch(self) -> list[JobPosting]:
        results: dict[str, JobPosting] = {}

        # Query 1: Argentina-located roles
        body_ar = {
            "limit": 200,
            "sort": ["date.created:desc"],
            "fields": {
                "include": ["title", "url_alias", "url", "date.created",
                            "country", "city", "source", "type", "theme"]
            },
            "filter": {
                "field": "country.iso3",
                "value": "arg",
            },
        }
        for item in self._query(body_ar):
            p = self._to_posting(item)
            results[p.fingerprint] = p

        # Query 2: home-based (ReliefWeb uses theme or experiential in some datasets;
        # simplest cross-cutting trick is a text query on title/body)
        body_remote = {
            "limit": 200,
            "sort": ["date.created:desc"],
            "fields": {
                "include": ["title", "url_alias", "url", "date.created",
                            "country", "city", "source", "type"]
            },
            "query": {
                "value": "home-based OR remote OR \"home based\"",
                "fields": ["title", "body"],
                "operator": "AND",
            },
        }
        for item in self._query(body_remote):
            p = self._to_posting(item)
            results.setdefault(p.fingerprint, p)

        return list(results.values())
