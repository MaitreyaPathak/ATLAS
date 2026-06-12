"""
remotive.py — Scraper for Remotive API.

Remotive's API ignores `limit` on the base endpoint and caps at ~28 jobs.
To get full coverage, we must hit each category endpoint separately.
We pull ALL categories (scrape everything, filter later).
"""

import requests
from typing import Optional

BASE_URL = "https://remotive.com/api/remote-jobs"
TIMEOUT = 20

# All Remotive categories — scrape all, let scorer filter
ALL_CATEGORIES = [
    "software-dev",
    "customer-support",
    "design",
    "marketing",
    "product",
    "business",
    "data",
    "devops-sysadmin",
    "finance-legal",
    "hr",
    "qa",
    "sales",
    "teaching",
    "writing",
    "all-others",
]


def _fetch_category(session: requests.Session, category: str) -> list[dict]:
    try:
        res = session.get(
            BASE_URL,
            params={"category": category},
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        data = res.json()
        return data.get("jobs", [])
    except Exception as e:
        print(f"  Remotive [{category}]: error — {e}")
        return []


def fetch_jobs() -> list[dict]:
    print("Fetching Remotive jobs...")

    seen_ids: set[int] = set()
    jobs: list[dict] = []

    with requests.Session() as session:
        for category in ALL_CATEGORIES:
            raw = _fetch_category(session, category)

            for job in raw:
                jid = job.get("id")
                if jid in seen_ids:
                    continue
                seen_ids.add(jid)

                title: str = job.get("title", "").strip()
                company: str = job.get("company_name", "Unknown").strip()
                link: Optional[str] = job.get("url", "").strip() or None
                tags: list[str] = job.get("tags", [])
                location: str = job.get("candidate_required_location", "")
                description: str = job.get("description", "")

                if not title or not link:
                    continue

                jobs.append({
                    "Title": title,
                    "Company": company,
                    "Link": link,
                    "Source": "Remotive",
                    "Tags": ", ".join(tags[:5]),
                    "Location": location,
                    "Description": description[:500] if description else "",
                })

    print(f"  Remotive: {len(jobs)} jobs")
    return jobs
