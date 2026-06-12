"""
wellfound.py — Scraper for Wellfound (formerly AngelList Talent).

Wellfound blocks headless Playwright with bot detection.
Workaround: use their public sitemap + direct job page requests,
OR use their public RSS/JSON endpoints where available.

Alternative approach: scrape their public "role" pages using
stealth mode (randomised viewport, realistic headers, slow scroll).
"""

import re
import time

BASE_URL = "https://wellfound.com"

ROLE_PATHS = [
    "/role/r/operations",
    "/role/r/business-development", 
    "/role/r/finance",
    "/role/r/product-manager",
    "/role/r/data-analyst",
    "/role/r/marketing",
    "/role/r/operations-manager",
]

_JUNK_RE = re.compile(
    r"^(apply|view|see all|sign up|log in|remote|full.?time|"
    r"part.?time|contract|\d+|save|follow)$",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


def fetch_jobs() -> list[dict]:
    print("Fetching Wellfound jobs...")

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("  Wellfound: playwright not installed — skipping")
        return []

    jobs: list[dict] = []
    seen: set[str] = set()

    try:
        with sync_playwright() as p:
            # Use stealth-like settings to avoid bot detection
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                }
            )

            # Remove webdriver fingerprint
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            for path in ROLE_PATHS:
                page = context.new_page()

                try:
                    page.goto(f"{BASE_URL}{path}", timeout=45_000)
                    page.wait_for_load_state("networkidle", timeout=20_000)

                    # Check if we hit a bot/CAPTCHA page
                    page_text = (page.inner_text("body") or "").lower()
                    if any(x in page_text for x in ["captcha", "blocked", "access denied", "cf-browser"]):
                        print(f"  Wellfound: blocked on {path}")
                        page.close()
                        continue

                except PWTimeout:
                    print(f"  Wellfound: timeout on {path}")
                    page.close()
                    continue

                # Human-like scrolling
                for _ in range(5):
                    page.mouse.wheel(0, 1500 + (_ * 200))
                    page.wait_for_timeout(500 + (_ * 100))

                # Try multiple card selectors
                selectors = [
                    "a[href*='/jobs/']",
                    "[data-test*='job'] a",
                    ".job-listing a",
                    "article a",
                ]

                for selector in selectors:
                    cards = page.query_selector_all(selector)
                    if not cards:
                        continue

                    for card in cards:
                        try:
                            href = card.get_attribute("href") or ""
                            if not href or "/jobs/" not in href:
                                continue

                            full_link = (
                                BASE_URL + href if href.startswith("/") else href
                            ).split("?")[0]

                            if full_link in seen:
                                continue

                            raw = _clean(card.inner_text() or "")
                            lines = [
                                _clean(l) for l in raw.splitlines()
                                if _clean(l) and not _JUNK_RE.match(_clean(l))
                            ]

                            if not lines:
                                continue

                            title = max(lines, key=len) if lines else ""
                            if len(title) < 6:
                                continue

                            company = "Startup"
                            try:
                                parent = card.query_selector("xpath=../..")
                                if parent:
                                    parent_lines = [
                                        _clean(l)
                                        for l in (parent.inner_text() or "").splitlines()
                                        if _clean(l) and _clean(l) != title
                                        and len(_clean(l)) > 2
                                    ]
                                    if parent_lines:
                                        company = parent_lines[0][:80]
                            except Exception:
                                pass

                            seen.add(full_link)
                            jobs.append({
                                "Title": title,
                                "Company": company,
                                "Link": full_link,
                                "Source": "Wellfound",
                                "Location": "Remote",
                            })

                        except Exception:
                            continue

                    if jobs:  # found something with this selector
                        break

                page.close()
                time.sleep(1.5)  # be polite between pages

            browser.close()

    except Exception as e:
        print(f"  Wellfound: error — {e}")
        return []

    print(f"  Wellfound: {len(jobs)} jobs")
    return jobs
