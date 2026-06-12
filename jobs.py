"""
jobs.py — Main entry point for ATLAS.

Usage:
    python jobs.py                  # Run all scrapers
    python jobs.py remotive         # Run single scraper by name
    python jobs.py --no-browser     # Skip Playwright-based scrapers

Output:
    atlas_opportunities.csv       — Full results table
    atlas_dashboard.html          — Clickable, sortable HTML report (open in browser)
"""

import sys
import importlib
import traceback
import pandas as pd
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────
# PATH SETUP — works whether run from project root or elsewhere
# ─────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from sources.aggregator import fetch_all_jobs
from sources.scoring import filter_and_score

BANNER = """
╔══════════════════════════════════════════╗
║                 ATLAS                    ║
║   Job Discovery & Intelligence Engine    ║
╚══════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────────────
# ARGS
# ─────────────────────────────────────────────────────
args = sys.argv[1:]
mode = args[0].lower() if args and not args[0].startswith("--") else "all"
no_browser = "--no-browser" in args


# ─────────────────────────────────────────────────────
# SINGLE SCRAPER RUNNER
# ─────────────────────────────────────────────────────
def run_single(module_name: str) -> list[dict]:
    try:
        module = importlib.import_module(f"sources.{module_name}")
    except ModuleNotFoundError:
        print(f"[ERROR] No scraper named '{module_name}' found in sources/")
        return []
    except Exception:
        print(f"[ERROR] Failed to import sources.{module_name}")
        traceback.print_exc()
        return []

    if hasattr(module, "fetch_jobs"):
        return module.fetch_jobs() or []

    print(f"[ERROR] sources.{module_name} has no fetch_jobs() function")
    return []


# ─────────────────────────────────────────────────────
# HTML REPORT GENERATOR
# ─────────────────────────────────────────────────────
def generate_html_report(df: pd.DataFrame, output_path: str = "atlas_dashboard.html") -> None:
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M")

    rows = ""
    for _, row in df.iterrows():
        score = row.get("Score", 0)
        color = "#22c55e" if score >= 150 else "#f59e0b" if score >= 80 else "#94a3b8"
        rows += f"""
        <tr>
            <td><a href="{row['Link']}" target="_blank">{row['Title']}</a></td>
            <td>{row.get('Company', '—')}</td>
            <td style="color:{color};font-weight:600">{int(score)}</td>
            <td>{row.get('Tags', '—')}</td>
            <td>{row.get('Location', '—')}</td>
            <td><span class="badge">{row.get('Source', '—')}</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ATLAS Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.3rem; color: #f8fafc; }}
  .meta {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; }}
  th {{ background: #334155; padding: 0.7rem 1rem; text-align: left; font-size: 0.78rem;
        text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; cursor: pointer; }}
  th:hover {{ background: #475569; color: #f1f5f9; }}
  td {{ padding: 0.65rem 1rem; border-bottom: 1px solid #334155; font-size: 0.88rem; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #263148; }}
  a {{ color: #60a5fa; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ background: #334155; border-radius: 999px; padding: 0.2rem 0.6rem;
            font-size: 0.75rem; color: #94a3b8; }}
  input {{ background: #1e293b; border: 1px solid #334155; color: #e2e8f0;
           padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.9rem;
           margin-bottom: 1rem; width: 300px; }}
  input::placeholder {{ color: #64748b; }}
</style>
</head>
<body>
  <h1>🎯 ATLAS Dashboard</h1>
  <div class="meta">Generated {timestamp} · {len(df)} jobs found</div>
  <input type="text" id="search" placeholder="Filter by title, company, source…" oninput="filterTable()">
  <table id="jobTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Title ↕</th>
        <th onclick="sortTable(1)">Company ↕</th>
        <th onclick="sortTable(2)">Score ↕</th>
        <th>Tags</th>
        <th>Location</th>
        <th onclick="sortTable(5)">Source ↕</th>
      </tr>
    </thead>
    <tbody id="tableBody">
      {rows}
    </tbody>
  </table>
  <script>
    function filterTable() {{
      const q = document.getElementById('search').value.toLowerCase();
      document.querySelectorAll('#tableBody tr').forEach(row => {{
        row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
      }});
    }}
    function sortTable(col) {{
      const tbody = document.getElementById('tableBody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const dir = tbody.dataset.sortDir === 'asc' ? -1 : 1;
      tbody.dataset.sortDir = dir === 1 ? 'asc' : 'desc';
      rows.sort((a, b) => {{
        const aVal = a.cells[col].innerText.trim();
        const bVal = b.cells[col].innerText.trim();
        const aNum = parseFloat(aVal);
        return isNaN(aNum)
          ? aVal.localeCompare(bVal) * dir
          : (aNum - parseFloat(bVal)) * dir;
      }});
      rows.forEach(r => tbody.appendChild(r));
    }}
  </script>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"  HTML report saved → {output_path}")


# ─────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────
print(BANNER)

if mode == "all":
    jobs = fetch_all_jobs()
else:
    jobs = run_single(mode)

if not jobs:
    print("[INFO] No jobs found. Check your internet connection or scraper logs.")
    sys.exit(0)

# Score and filter
jobs = filter_and_score(jobs)

if not jobs:
    print("[INFO] All jobs were filtered out by the scorer. "
          "Try lowering the score threshold in scoring.py.")
    sys.exit(0)

# Build DataFrame
df = pd.DataFrame(jobs)
for col in ["Tags", "Company", "Source", "Location", "Score"]:
    if col not in df.columns:
        df[col] = "" if col != "Score" else 0
      
# Clean NaN values for display
df = df.fillna("")

# ─── Save outputs ───
df.to_csv("atlas_opportunities.csv", index=False)
print(f"\n  CSV saved → atlas_opportunities.csv")
generate_html_report(df)

# ─── Terminal summary ───
print(f"\n{'═'*50}")
print(f"  Jobs after filtering:  {len(df)}")
print(f"{'─'*50}")
print("\n  Source breakdown:")
print(df["Source"].value_counts().to_string())

print("\n\n  TOP 20 MATCHES")
print(f"{'─'*50}")
display_cols = [c for c in ["Title", "Company", "Score", "Source", "Location"] if c in df.columns]
print(df[display_cols].head(20).to_string(index=False))
print(f"\n{'═'*50}")
print("  Open atlas_dashboard.html in your browser for the full clickable report.")
print(f"{'═'*50}\n")
