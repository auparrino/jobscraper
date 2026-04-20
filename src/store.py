import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable

from .models import JobPosting


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    fingerprint TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    location TEXT,
    posted_at TEXT,
    organization TEXT,
    description TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_many(self, jobs: Iterable[JobPosting]) -> list[JobPosting]:
        """Insert jobs, returning only the ones that are new."""
        now = datetime.now(timezone.utc).isoformat()
        new_jobs: list[JobPosting] = []
        cur = self.conn.cursor()
        for job in jobs:
            fp = job.fingerprint
            cur.execute("SELECT 1 FROM jobs WHERE fingerprint = ?", (fp,))
            exists = cur.fetchone() is not None
            if exists:
                cur.execute(
                    "UPDATE jobs SET last_seen_at = ? WHERE fingerprint = ?",
                    (now, fp),
                )
            else:
                cur.execute(
                    """INSERT INTO jobs
                    (fingerprint, source, title, url, location, posted_at,
                     organization, description, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        fp, job.source, job.title, job.url, job.location,
                        job.posted_at, job.organization, job.description,
                        now, now,
                    ),
                )
                new_jobs.append(job)
        self.conn.commit()
        return new_jobs

    def active_jobs(self, max_days_stale: int = 14) -> list[dict]:
        """Return all jobs last seen within max_days_stale days.

        Older rows stay in the DB for dedup across time but are treated as
        closed postings for UI purposes.
        """
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_days_stale)).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """SELECT fingerprint, source, title, url, location, posted_at,
                      organization, description, first_seen_at, last_seen_at
               FROM jobs
               WHERE last_seen_at >= ?
               ORDER BY first_seen_at DESC""",
            (cutoff,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        self.conn.close()
