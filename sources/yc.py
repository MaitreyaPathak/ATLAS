"""
yc.py — Fast YC Jobs Scraper

Optimized version:
- Uses YC role pages only
- No search-box automation
- Faster page loading
- Less scrolling
- Deduplicates jobs
"""

import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.ycombinator.com"

ROLE_PAGES = [
    "/jobs/role/operations",
    "/jobs/role/product-manager",
    "/jobs/role/sales-manager",
    "/jobs/role/finance",
    "/jobs/role/marketing",
    "/jobs/role/recruiting-hr",
]

_BATCH_RE = re.compile(r"\s*\([WSF]\d{2}\)\s*$")


def _scrape_page(page, url: str, seen: set[str]) -> list[dict]:
    jobs = []

    try:
        page.goto(url, timeout=30000)

        # Much faster than networkidle
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)

    except Exception as e:
        print(f"  YC page failed: {url}")
        print(f"  Error: {e}")
        return []

    # Minimal scrolling
    for _ in range(2):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(250)

    last_company = "YC Startup"

    links = page.query_selector_all("a[href]")

    for a in links:
        try:
            href = a.get_attribute("href") or ""
            text = " ".join((a.inner_text() or "").split())
        except Exception:
            continue

        # Company link
        if href.startswith("/companies/") and "/jobs/" not in href:
            company = _BATCH_RE.sub("", text.split("•")[0]).strip()

            if company:
                last_company = company

            continue

        # Job link
        if "/companies/" in href and "/jobs/" in href:

            title = text.strip()

            if (
                not title
                or len(title) < 3
                or title.lower() == "apply"
            ):
                continue

            full_link = (BASE_URL + href).split("?")[0]

            if full_link in seen:
                continue

            seen.add(full_link)

            jobs.append({
                "Title": title,
                "Company": last_company,
                "Link": full_link,
                "Source": "YC",
                "Location": "Remote / US",
                "Tags": "",
                "Description": ""
            })

    return jobs


def fetch_jobs() -> list[dict]:
    print("Fetching YC jobs...")

    all_jobs = []
    seen = set()

    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )

            page = context.new_page()

            for role_page in ROLE_PAGES:

                url = BASE_URL + role_page

                jobs = _scrape_page(page, url, seen)

                all_jobs.extend(jobs)

                print(
                    f"  {role_page.split('/')[-1]}: "
                    f"{len(jobs)} jobs"
                )

            browser.close()

    except Exception as e:
        print(f"  YC error: {e}")
        return []

    print(f"  YC: {len(all_jobs)} jobs")

    return all_jobs