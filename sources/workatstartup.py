"""
workatstartup.py — Scraper for WorkAtAStartup (YC-backed).

Uses Playwright because the page is JS-rendered. We scroll a few
times to trigger lazy-loads, then collect all job links.

Requires: pip install playwright && playwright install chromium
"""

import re

_JUNK_RE = re.compile(
    r"\bjobs\b|jobs in |remote jobs|product jobs|sales jobs|"
    r"marketing jobs|support jobs|operations jobs",
    re.IGNORECASE,
)

BASE_URL = "https://www.workatastartup.com"


def _is_junk(title: str) -> bool:
    return bool(_JUNK_RE.search(title)) or title.lower().endswith("jobs")


def fetch_jobs() -> list[dict]:
    print("Fetching WorkAtStartup jobs...")

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("  WorkAtStartup: playwright not installed — skipping")
        return []

    jobs: list[dict] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            try:
                page.goto(f"{BASE_URL}/jobs", timeout=60_000)
                page.wait_for_load_state("networkidle", timeout=30_000)
            except PWTimeout:
                print("  WorkAtStartup: page load timed out")
                browser.close()
                return []

            # Scroll to load lazy content
            for _ in range(6):
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(800)

            seen: set[str] = set()

            for card in page.query_selector_all("a[href*='/jobs/']"):
                try:
                    title = (card.inner_text() or "").strip()
                    href = card.get_attribute("href") or ""

                    if not title or len(title) < 8:
                        continue
                    if _is_junk(title):
                        continue

                    if not href.startswith("http"):
                        href = BASE_URL + href

                    href = href.split("?")[0]

                    if href in seen:
                        continue
                    seen.add(href)

                    # Try to get company name from a sibling element
                    company = "Startup"
                    parent = card.query_selector("xpath=..")
                    if parent:
                        company_el = parent.query_selector(
                            "[class*='company'], [class*='employer'], [class*='org']"
                        )
                        if company_el:
                            company = (company_el.inner_text() or "Startup").strip()

                    jobs.append({
                        "Title": title,
                        "Company": company,
                        "Link": href,
                        "Source": "WorkAtStartup",
                        "Location": "Remote / Global",
                    })
                except Exception:
                    continue

            browser.close()

    except Exception as e:
        print(f"  WorkAtStartup: error — {e}")
        return []

    print(f"  WorkAtStartup: {len(jobs)} jobs")
    return jobs
