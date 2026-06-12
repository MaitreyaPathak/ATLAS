"""
scoring.py — Filter and rank jobs by relevance.

Two-stage filtering:
  1. Title filter  — fast reject/score based on job title
  2. Description filter — reject jobs requiring too much experience
     (only runs if Description field is present)
"""

import re

# ─────────────────────────────────────────────
# HARD-REJECT: engineering / technical roles
# ─────────────────────────────────────────────
BLOCK_KEYWORDS = [
    "engineer", "engineering", "developer", "programmer",
    "software", "backend", "frontend", "full stack", "fullstack",
    "devops", "sre", "architect", "machine learning", "ml engineer",
    "ai engineer", "data scientist", "research scientist",
    "technical product manager", "product owner",
    "scrum master", "project manager",
    "technical", "qa", "quality assurance", "security", "network",
    "infrastructure", "cloud", "platform", "embedded",
    "firmware", "hardware", "robotics",
]

# ─────────────────────────────────────────────
# SENIORITY BLOCK: too senior for fresh grad
# ─────────────────────────────────────────────
SENIORITY_BLOCK = [
    "senior", "sr.", "staff", "principal", "lead",
    "manager", "director", "head of", "vp", "vice president", "chief",
    "c-level", "cto", "coo", "cmo", "cfo", "ceo",
]

# ─────────────────────────────────────────────
# TARGET ROLES — scored by relevance
# ─────────────────────────────────────────────
PRIORITY_KEYWORDS = [
    # Founder's office — dream tier
    ("founder's associate",   120),
    ("founders associate",    120),
    ("founder's office",      120),
    ("founders office",       120),
    ("founder associate",     120),
    ("founding associate",    120),
    ("chief of staff",        110),

    # Strategy
    ("strategy associate",    100),
    ("strategic associate",   100),
    ("strategy analyst",      100),
    ("business strategy",      95),
    ("strategy",               85),
    ("strategic",              85),

    # Business / ops analyst
    ("business analyst",       90),
    ("operations analyst",     90),
    ("product analyst",        90),
    ("growth analyst",         90),
    ("data analyst",           85),
    ("financial analyst",      80),

    # Product associates (non-technical)
    ("product associate",      90),
    ("product manager",        70),

    # Growth
    ("growth associate",       90),
    ("growth hacker",          80),
    ("growth",                 70),

    # Operations
    ("business operations",    85),
    ("revenue operations",     80),
    ("revops",                 80),
    ("operations associate",   80),
    ("operations",             65),

    # Generalist / associate roles
    ("generalist",             75),
    ("business development",   70),
    ("bd associate",           80),
    ("venture associate",      90),
    ("investor relations",     70),
    ("investment analyst",     85),
    ("management consultant",  80),
    ("consultant",             60),
    ("associate",              50),

    # Misc high-signal titles
    ("customer success",       55),
    ("customer operations",    55),
    ("business transformation",55),
    ("program associate",      60),
    ("research associate",     60),
    ("policy associate",       60),
]

# ─────────────────────────────────────────────
# FRESHER SIGNALS — bonus points
# ─────────────────────────────────────────────
FRESHER_SIGNALS = [
    "intern", "internship", "graduate", "entry level",
    "entry-level", "junior", "early career", "new grad",
    "fresh graduate", "0-1 year", "0-2 year",
]

# ─────────────────────────────────────────────
# SOURCE QUALITY BONUS
# ─────────────────────────────────────────────
SOURCE_BONUS = {
    "YC": 15,
    "WorkAtStartup": 15,
    "Wellfound": 10,
}

# ─────────────────────────────────────────────
# DESCRIPTION: EXPERIENCE BLOCKERS
# Regex patterns that indicate too much experience required.
# Matches things like "5+ years", "5-7 years", "minimum 4 years".
# ─────────────────────────────────────────────
_EXP_PATTERN = re.compile(
    r"(\b[3-9]\d*\+?\s*(?:to|-)\s*\d*\s*years?"   # "3-5 years", "4+ to 6 years"
    r"|\b[3-9]\d*\+\s*years?"                       # "3+ years", "5+ years"
    r"|\bminimum\s+(?:of\s+)?[3-9]\d*\s*years?"    # "minimum of 4 years"
    r"|\bat\s+least\s+[3-9]\d*\s*years?"            # "at least 5 years"
    r"|\b[3-9]\d*\s*years?\s+of\s+experience"       # "4 years of experience"
    r"|\b(?:senior|staff|principal)\s+level)",       # explicit seniority in description
    re.IGNORECASE,
)

# Hard phrases in descriptions that always mean overqualified
_DESC_BLOCK_PHRASES = [
    "proven track record of",
    "10+ years",
    "decade of experience",
    "managed a team of",
    "p&l responsibility",
    "board-level",
]


def _contains(text: str, phrase: str) -> bool:
    """Word-boundary aware phrase match."""
    pattern = r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])"
    return bool(re.search(pattern, text))


def is_blocked(title: str) -> bool:
    t = title.lower()
    for word in BLOCK_KEYWORDS:
        if _contains(t, word):
            return True
    return False


def is_too_senior(title: str) -> bool:
    t = title.lower()
    for word in SENIORITY_BLOCK:
        if _contains(t, word):
            return True
    return False


def description_blocks(description: str) -> bool:
    """
    Returns True if the job description signals the role requires
    too much experience for a 0-2 year candidate.
    """
    if not description:
        return False  # no description = give benefit of the doubt

    desc = description.lower()

    # Regex: 3+ years / 5-7 years / minimum 4 years etc.
    if _EXP_PATTERN.search(desc):
        return True

    # Hard phrases
    for phrase in _DESC_BLOCK_PHRASES:
        if phrase in desc:
            return True

    return False


def score_job(job: dict) -> int:
    title = job.get("Title", "").lower().strip()

    if not title:
        return -999

    if is_blocked(title):
        return -999

    if is_too_senior(title):
        return -999

    # Take the HIGHEST matching keyword score (not additive).
    # "customer operations" (55) + "operations" (65) = 120 would inflate generic titles.
    # Best single-match wins.
    best_score = -1
    for keyword, points in PRIORITY_KEYWORDS:
        if _contains(title, keyword) and points > best_score:
            best_score = points

    if best_score < 0:
        return -999

    score = best_score

    # Fresher bonus
    for word in FRESHER_SIGNALS:
        if _contains(title, word):
            score += 20

    # Remote bonus
    if "remote" in title:
        score += 10

    # Source quality bonus
    source = job.get("Source", "")
    score += SOURCE_BONUS.get(source, 0)

    return score


def filter_and_score(jobs: list[dict]) -> list[dict]:
    results = []

    for job in jobs:
        score = score_job(job)
        if score < 50:
            continue

        # Stage 2: description check (only if description was scraped)
        if description_blocks(job.get("Description", "")):
            continue

        job = dict(job)  # don't mutate original
        job["Score"] = score
        results.append(job)

    results.sort(key=lambda x: x["Score"], reverse=True)
    return results
