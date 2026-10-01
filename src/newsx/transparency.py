"""Transparency Page Generator (M1).

Generates a static HTML audit page detailing all registered news and primary sources,
their ownership, funding, regional distribution, and event diversity quotas.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Optional

try:
    from .registry import SourceRegistry, DiversityChecker, DEFAULT_SOURCES_PATH, DEFAULT_RULES_PATH
except ImportError:
    from newsx.registry import SourceRegistry, DiversityChecker, DEFAULT_SOURCES_PATH, DEFAULT_RULES_PATH

DEFAULT_REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "transparency.html"


def generate_transparency_html(registry: SourceRegistry, checker: Optional[DiversityChecker] = None) -> str:
    sources = registry.all_sources()
    primary = [s for s in sources if s.tier.value == "primary"]
    secondary = [s for s in sources if s.tier.value == "secondary"]
    tertiary = [s for s in sources if s.tier.value == "tertiary"]

    quotas = checker._quotas if checker else {}

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"UTF-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        "  <title>Source Transparency Registry — Raw News Extraction</title>",
        "  <style>",
        "    :root {",
        "      --bg: #0f172a; --card-bg: #1e293b; --text: #f8fafc; --text-muted: #94a3b8;",
        "      --border: #334155; --primary: #38bdf8; --success: #4ade80; --warning: #fbbf24;",
        "      --tier1: #3b82f6; --tier2: #10b981; --tier3: #f59e0b;",
        "    }",
        "    body {",
        "      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;",
        "      background-color: var(--bg); color: var(--text); line-height: 1.5; margin: 0; padding: 2rem;",
        "    }",
        "    .container { max-width: 1200px; margin: 0 auto; }",
        "    header { margin-bottom: 2.5rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }",
        "    h1 { font-size: 2rem; margin: 0 0 0.5rem 0; color: #fff; }",
        "    p.subtitle { color: var(--text-muted); font-size: 1.1rem; margin: 0; }",
        "    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2.5rem; }",
        "    .stat-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; }",
        "    .stat-value { font-size: 2rem; font-weight: 700; color: var(--primary); }",
        "    .stat-label { color: var(--text-muted); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em; }",
        "    .section { margin-bottom: 3rem; }",
        "    h2 { font-size: 1.5rem; margin-bottom: 1rem; border-left: 4px solid var(--primary); padding-left: 0.75rem; }",
        "    table { width: 100%; border-collapse: collapse; margin-top: 1rem; background: var(--card-bg); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }",
        "    th, td { padding: 0.85rem 1rem; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.95rem; }",
        "    th { background: #111827; color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.8rem; }",
        "    tr:hover { background: #24344d; }",
        "    .badge { display: inline-block; padding: 0.25rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }",
        "    .badge-primary { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }",
        "    .badge-secondary { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }",
        "    .badge-tertiary { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }",
        "    .source-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 1.25rem; }",
        "    .source-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between; }",
        "    .source-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem; }",
        "    .source-title { font-size: 1.15rem; font-weight: 600; margin: 0; color: #fff; }",
        "    .source-meta { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem; }",
        "    .source-notes { font-size: 0.9rem; color: #cbd5e1; margin-top: 0.5rem; background: #0f172a; padding: 0.6rem; border-radius: 4px; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <div class=\"container\">",
        "    <header>",
        "      <h1>Source Transparency Registry</h1>",
        "      <p class=\"subtitle\">Public, auditable registry of sources, tiers, ownership, funding, and event diversity rules.</p>",
        "    </header>",
        "    <div class=\"stats-grid\">",
        f"      <div class=\"stat-card\"><div class=\"stat-value\">{len(sources)}</div><div class=\"stat-label\">Total Registered Sources</div></div>",
        f"      <div class=\"stat-card\"><div class=\"stat-value\">{len(primary)}</div><div class=\"stat-label\">Primary Sources (Official/Filings)</div></div>",
        f"      <div class=\"stat-card\"><div class=\"stat-value\">{len(secondary)}</div><div class=\"stat-label\">Secondary Sources (Wires/Reporters)</div></div>",
        f"      <div class=\"stat-card\"><div class=\"stat-value\">{len(tertiary)}</div><div class=\"stat-label\">Tertiary (Aggregators/Excluded)</div></div>",
        "    </div>",
    ]

    # Quotas Section
    if quotas:
        html_parts.extend([
            "    <div class=\"section\">",
            "      <h2>Event Diversity Quotas</h2>",
            "      <table>",
            "        <thead>",
            "          <tr>",
            "            <th>Event Type</th>",
            "            <th>Description</th>",
            "            <th>Min Primary</th>",
            "            <th>Min Secondary</th>",
            "            <th>Min Independent Origins</th>",
            "            <th>Min Ownership Entities</th>",
            "            <th>Min Regions</th>",
            "          </tr>",
            "        </thead>",
            "        <tbody>",
        ])
        for ek, q in quotas.items():
            html_parts.append(
                f"          <tr>"
                f"<td><strong>{html.escape(ek)}</strong></td>"
                f"<td>{html.escape(q.description)}</td>"
                f"<td>{q.min_primary_sources}</td>"
                f"<td>{q.min_secondary_sources}</td>"
                f"<td>{q.min_independent_origins}</td>"
                f"<td>{q.min_distinct_ownerships}</td>"
                f"<td>{q.min_distinct_regions}</td>"
                f"</tr>"
            )
        html_parts.extend([
            "        </tbody>",
            "      </table>",
            "    </div>",
        ])

    # Sources Section
    html_parts.extend([
        "    <div class=\"section\">",
        "      <h2>Registered Source Profiles</h2>",
        "      <div class=\"source-grid\">",
    ])

    for s in sources:
        tier_class = f"badge-{s.tier.value}"
        html_parts.append(
            f"        <div class=\"source-card\">"
            f"          <div>"
            f"            <div class=\"source-header\">"
            f"              <h3 class=\"source-title\">{html.escape(s.name)}</h3>"
            f"              <span class=\"badge {tier_class}\">{html.escape(s.tier.value)}</span>"
            f"            </div>"
            f"            <div class=\"source-meta\"><strong>ID:</strong> {html.escape(s.id)} | <strong>Region:</strong> {html.escape(s.region)} | <strong>Medium:</strong> {html.escape(s.medium)}</div>"
            f"            <div class=\"source-meta\"><strong>Ownership:</strong> {html.escape(s.ownership)}</div>"
            f"            <div class=\"source-meta\"><strong>Funding:</strong> {html.escape(s.funding)}</div>"
            f"            <div class=\"source-notes\">{html.escape(s.leaning_notes)}</div>"
            f"          </div>"
            f"          <div style=\"margin-top: 0.75rem; font-size: 0.8rem; color: var(--text-muted);\">"
            f"            Access: {html.escape(s.access_notes)}"
            f"          </div>"
            f"        </div>"
        )

    html_parts.extend([
        "      </div>",
        "    </div>",
        "  </div>",
        "</body>",
        "</html>",
    ])

    return "\n".join(html_parts)


def render_transparency_page(output_path: Optional[Path] = None) -> Path:
    out = output_path or DEFAULT_REPORT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    registry = SourceRegistry()
    checker = DiversityChecker(registry)
    content = generate_transparency_html(registry, checker)
    with out.open("w", encoding="utf-8") as f:
        f.write(content)
    return out


if __name__ == "__main__":
    p = render_transparency_page()
    print(f"Rendered transparency page to {p}")
