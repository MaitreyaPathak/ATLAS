"""
aggregator.py — Discovers and runs all scraper modules in parallel.

Each scraper module must expose a function named fetch_jobs().
All other functions are ignored to keep the interface clean.
"""

import importlib
import pkgutil
import traceback
import sources
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

SCRAPER_TIMEOUT_SECONDS = 120  # per scraper, not total


# ─────────────────────────────────────────────
# SCRAPER DISCOVERY
# ─────────────────────────────────────────────
_SKIP_MODULES = {"aggregator", "scoring", "__init__"}


def load_all_scrapers() -> list[tuple[str, callable]]:
    """
    Auto-discovers all source modules and returns (name, fetch_jobs) pairs.
    Only modules with a fetch_jobs() function are loaded.
    """
    scrapers = []

    for _, module_name, _ in pkgutil.iter_modules(sources.__path__):
        if module_name in _SKIP_MODULES:
            continue

        try:
            module = importlib.import_module(f"sources.{module_name}")
        except Exception:
            print(f"[SKIP] {module_name}: import failed\n{traceback.format_exc()}")
            continue

        if hasattr(module, "fetch_jobs") and callable(module.fetch_jobs):
            scrapers.append((module_name, module.fetch_jobs))
        else:
            # Fallback: pick up any fetch_* function for rapid prototyping
            found = False
            for attr in dir(module):
                if attr.startswith("fetch_") and callable(getattr(module, attr)):
                    scrapers.append((f"{module_name}.{attr}", getattr(module, attr)))
                    found = True
            if not found:
                print(f"[SKIP] {module_name}: no fetch_jobs() or fetch_* function found")

    return scrapers


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────
def _is_valid_job(job: dict) -> bool:
    if not isinstance(job, dict):
        return False
    title = job.get("Title", "").strip()
    link = job.get("Link", "").strip()
    return bool(title) and bool(link) and link.startswith("http")


def clean_jobs(jobs: list) -> list[dict]:
    return [j for j in jobs if _is_valid_job(j)]


# ─────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────
def _normalise_title(title: str) -> str:
    """Strip job-board ref numbers and noise for deduplication.
    e.g. "Operations Analyst - Remote Work | REF#283370" -> "operations analyst remote work"
    """
    import re
    t = title.lower()
    t = re.sub(r"\|?\s*ref#?\d+", "", t)          # REF#12345
    t = re.sub(r"\|?\s*\(ref[:\s]?#?\d+\)", "", t) # (REF: 12345)
    t = re.sub(r"[-|]\s*(remote work|work from home|wfh)\s*$", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def deduplicate(jobs: list[dict]) -> list[dict]:
    """
    Deduplicates by normalised URL (strip query params + trailing slash).
    Also deduplicates by (normalised_title, company) pair to catch:
      - Cross-source reposts
      - Same job posted multiple times with different REF numbers (BairesDev etc.)
    """
    seen_links: set[str] = set()
    seen_title_company: set[tuple] = set()
    unique = []

    for job in jobs:
        link = job.get("Link", "").split("?")[0].rstrip("/").lower()
        title_key = (
            _normalise_title(job.get("Title", "")),
            job.get("Company", "").lower().strip(),
        )

        if link in seen_links:
            continue
        if title_key[0] and title_key in seen_title_company:
            continue

        seen_links.add(link)
        seen_title_company.add(title_key)
        unique.append(job)

    return unique


# ─────────────────────────────────────────────
# PARALLEL FETCH ENGINE
# ─────────────────────────────────────────────
def _run_scraper(name: str, fn: callable) -> list[dict]:
    try:
        print(f"  → Fetching {name}...")
        result = fn()
        jobs = result or []
        print(f"  ✓ {name}: {len(jobs)} jobs")
        return jobs
    except Exception:
        print(f"  ✗ {name} failed:\n{traceback.format_exc()}")
        return []


def fetch_all_jobs(max_workers: int = 6) -> list[dict]:
    scrapers = load_all_scrapers()

    if not scrapers:
        print("[ERROR] No scrapers found. Check your sources/ directory.")
        return []

    print(f"\n{'─'*40}")
    print(f"Running {len(scrapers)} scrapers in parallel...")
    print(f"{'─'*40}\n")

    all_jobs: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_name = {
            executor.submit(_run_scraper, name, fn): name
            for name, fn in scrapers
        }

        for future in as_completed(future_to_name, timeout=SCRAPER_TIMEOUT_SECONDS + 5):
            name = future_to_name[future]
            try:
                jobs = future.result(timeout=SCRAPER_TIMEOUT_SECONDS)
                all_jobs.extend(jobs)
            except TimeoutError:
                print(f"  ✗ {name}: timed out after {SCRAPER_TIMEOUT_SECONDS}s")
            except Exception:
                print(f"  ✗ {name}: unexpected error\n{traceback.format_exc()}")

    all_jobs = clean_jobs(all_jobs)
    all_jobs = deduplicate(all_jobs)

    print(f"\n{'─'*40}")
    print(f"Total unique jobs collected: {len(all_jobs)}")
    print(f"{'─'*40}\n")

    return all_jobs
