import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .adapters import ALL_ADAPTERS
from .store import Store
from .models import JobPosting


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def render_markdown(new_jobs: list[JobPosting]) -> str:
    if not new_jobs:
        return "# Sin ofertas nuevas\n"
    by_source: dict[str, list[JobPosting]] = {}
    for j in new_jobs:
        by_source.setdefault(j.source, []).append(j)
    lines = [f"# {len(new_jobs)} ofertas nuevas\n"]
    for src, items in sorted(by_source.items()):
        lines.append(f"\n## {src} ({len(items)})\n")
        for j in items:
            meta = " · ".join(filter(None, [j.organization, j.location, j.posted_at]))
            lines.append(f"- [{j.title}]({j.url})" + (f" — {meta}" if meta else ""))
    return "\n".join(lines) + "\n"


def run(only: list[str] | None = None) -> int:
    DATA.mkdir(exist_ok=True)
    store = Store(DATA / "jobs.db")
    all_new: list[JobPosting] = []
    errors: dict[str, str] = {}

    adapters = ALL_ADAPTERS
    if only:
        adapters = [a for a in adapters if a.name in only]

    for adapter in adapters:
        print(f"[{adapter.name}] fetching…", flush=True)
        try:
            jobs = adapter.fetch()
            print(f"[{adapter.name}] got {len(jobs)} listings", flush=True)
            new = store.upsert_many(jobs)
            print(f"[{adapter.name}] {len(new)} new", flush=True)
            all_new.extend(new)
        except Exception as e:
            print(f"[{adapter.name}] FAILED: {e}", flush=True)
            traceback.print_exc()
            errors[adapter.name] = str(e)

    store.close()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = DATA / f"new_jobs_{stamp}.json"
    md_path = DATA / f"new_jobs_{stamp}.md"
    latest_json = DATA / "new_jobs_latest.json"
    latest_md = DATA / "new_jobs_latest.md"

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "new_count": len(all_new),
        "errors": errors,
        "jobs": [j.to_dict() for j in all_new],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md = render_markdown(all_new)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")

    print(f"\n=== DONE: {len(all_new)} new jobs, {len(errors)} adapter errors ===")
    print(f"wrote {json_path.name} and {md_path.name}")
    # Individual adapter errors are recorded in the output JSON and logs;
    # they should not prevent the DB + snapshot from being committed.
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="Run only these adapters by name")
    args = ap.parse_args()
    sys.exit(run(args.only))


if __name__ == "__main__":
    main()
