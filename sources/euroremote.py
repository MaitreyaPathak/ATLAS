"""
euroremote.py — Scraper for EuroRemoteJobs.

Uses requests + BeautifulSoup. Extracts job title and company name
from the job card structure, not just the link text.
"""

import requests
from bs4 import BeautifulSoup, Tag
import re

BASE_URL = "https://euremotejobs.com"
JOBS_URL = f"{BASE_URL}/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Category/listing pages — not individual job posts
_JUNK_PATTERNS = re.compile(
    r"\bjobs\b|\bremote jobs\b|jobs in |product jobs|sales jobs|"
    r"marketing jobs|support jobs|operations jobs",
    re.IGNORECASE,
)


def _is_junk(title: str) -> bool:
    return bool(_JUNK_PATTERNS.search(title))


def _absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE_URL + href


def fetch_jobs() -> list[dict]:
    print("Fetching EuroRemote jobs...")

    try:
        res = requests.get(JOBS_URL, headers=HEADERS, timeout=20)
        res.raise_for_status()
    except Exception as e:
        print(f"  EuroRemote: request failed — {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    seen: set[str] = set()
    jobs: list[dict] = []

    for a in soup.select("a[href*='/job/']"):
        href = a.get("href", "").strip()
        if not href:
            continue

        href = _absolute(href).split("?")[0]
        if href in seen:
            continue

        # Try to get a clean title — prefer a heading inside the card
        title_el = a.find(["h2", "h3", "h4", "span"])
        title = title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)
        title = title.strip()

        if not title or len(title) < 8:
            continue
        if _is_junk(title):
            continue

        seen.add(href)

        # Try to find company name in nearby elements
        company = "Unknown"
        parent = a.parent
        if parent:
            company_el = parent.find(class_=re.compile(r"company|employer|org", re.I))
            if company_el:
                company = company_el.get_text(strip=True)

        jobs.append({
            "Title": title,
            "Company": company,
            "Link": href,
            "Source": "EuroRemote",
            "Location": "Europe / Remote",
        })

    print(f"  EuroRemote: {len(jobs)} jobs")
    return jobs
