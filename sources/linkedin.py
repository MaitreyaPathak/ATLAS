"""
linkedin.py — Scraper for LinkedIn public job search (no login required).

Uses the public search endpoint with keywords targeting our desired roles.
LinkedIn does NOT require auth for search result pages.

Note: LinkedIn aggressively rate-limits; we add delays between requests.
"""

import requests
from bs4 import BeautifulSoup
import time
import re

BASE_URL = "https://www.linkedin.com/jobs/search/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TARGET_QUERIES = [
    "founder associate remote",
    "strategy analyst remote",
    "business analyst remote entry level",
    "growth analyst remote",
    "operations analyst remote",
    "product analyst remote",
    "chief of staff remote",
    "venture associate remote",
]


def _search(session: requests.Session, query: str) -> list[dict]:
    params = {
        "keywords": query,
        "location": "Worldwide",
        "f_WT": "2",      # remote filter
        "f_E": "1,2",     # experience: internship + entry level
        "start": "0",
    }

    try:
        res = session.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
        if res.status_code == 429:
            print(f"  LinkedIn: rate limited on '{query}'")
            return []
        res.raise_for_status()
    except Exception as e:
        print(f"  LinkedIn [{query}]: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    jobs = []

    for card in soup.select("div.base-card"):
        title_el = card.select_one("h3.base-search-card__title")
        company_el = card.select_one("h4.base-search-card__subtitle")
        link_el = card.select_one("a.base-card__full-link")
        location_el = card.select_one("span.job-search-card__location")

        title = title_el.get_text(strip=True) if title_el else ""
        company = company_el.get_text(strip=True) if company_el else "Unknown"
        link = link_el.get("href", "").split("?")[0] if link_el else ""
        location = location_el.get_text(strip=True) if location_el else ""

        if not title or not link:
            continue

        jobs.append({
            "Title": title,
            "Company": company,
            "Link": link,
            "Source": "LinkedIn",
            "Location": location,
        })

    return jobs


def fetch_jobs() -> list[dict]:
    print("Fetching LinkedIn jobs...")

    all_jobs: list[dict] = []
    seen: set[str] = set()

    with requests.Session() as session:
        for i, query in enumerate(TARGET_QUERIES):
            if i > 0:
                time.sleep(2)  # be polite

            results = _search(session, query)
            for job in results:
                link = job["Link"]
                if link and link not in seen:
                    seen.add(link)
                    all_jobs.append(job)

    print(f"  LinkedIn: {len(all_jobs)} jobs")
    return all_jobs
