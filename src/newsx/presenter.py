"""Brief Presenters and Multi-Format Renderers (Milestone 7).

Provides Markdown, HTML, and Terminal renderers for synthesized event briefs
with complete drill-down provenance, side-by-side dispute comparisons, and source audits.
"""

from __future__ import annotations

import html
from typing import Optional

from newsx.schemas import Brief, BriefFact, ConfidenceTier, DisputedPoint, SourceTier, TimelineEntry


class MarkdownBriefRenderer:
    """Renders structured event briefs into GitHub-flavored Markdown."""

    def render(self, brief: Brief) -> str:
        lines: list[str] = []

        # Title & Metadata
        lines.append(f"# {brief.neutral_headline}")
        lines.append("")
        lines.append(f"> **Event ID**: `{brief.event_id}`  ")
        lines.append(f"> **Diversity Compliance**: {'✅ COMPLIANT' if brief.diversity_compliant else '⚠️ DEFICIENT'}  ")
        if brief.diversity_deficiencies:
            for d in brief.diversity_deficiencies:
                lines.append(f"> - ⚠️ *{d}*  ")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. Core Facts
        lines.append("## 1. Core Verified Facts")
        lines.append("")
        if not brief.core_facts:
            lines.append("*No Tier 1 or Tier 2 corroborated facts established yet.*")
        else:
            for fact in brief.core_facts:
                tier_badge = "🟢 **[Tier 1: Primary Confirmed]**" if fact.tier == ConfidenceTier.PRIMARY_CONFIRMED else "🔵 **[Tier 2: Corroborated]**"
                speaker_str = f" (*Attributed to: {fact.attribution_speaker}{' (anonymous)' if fact.attribution_anonymous else ''}*)" if fact.attribution_speaker else ""
                lines.append(f"- {tier_badge}{speaker_str} {fact.text}")

                # Provenance details
                src_list = ", ".join(f"`{s}`" for s in fact.supporting_source_ids)
                lines.append(f"  - **Sources ({fact.independent_source_count} independent origin(s))**: {src_list}")
                if fact.original_text and fact.original_text != fact.text:
                    lines.append(f"  - **Original Wording**: *\"{fact.original_text}\"*")
                if fact.changes:
                    change_notes = "; ".join(f"[{c.category}] '{c.original_span}' -> '{c.replacement}' ({c.rationale})" for c in fact.changes)
                    lines.append(f"  - **Neutralization Adjustments**: {change_notes}")
                if fact.item_urls:
                    url_links = " | ".join(f"[Source Link]({u})" for u in fact.item_urls[:3])
                    lines.append(f"  - **Links**: {url_links}")
                lines.append("")

        # 2. Disputed Points
        lines.append("## 2. Disputed Points (Side-by-Side Comparison)")
        lines.append("")
        if not brief.disputed_points:
            lines.append("*No conflicting claims or direct contradictions identified across reporting.*")
        else:
            for dp in brief.disputed_points:
                if isinstance(dp, DisputedPoint):
                    lines.append(f"### ⚡ Dispute: {dp.topic}")
                    lines.append(f"*{dp.explanation}*")
                    lines.append("")
                    lines.append("| Position / Claim | Sources | Attribution | Original Text |")
                    lines.append("| :--- | :--- | :--- | :--- |")
                    for f in dp.claims:
                        src_str = ", ".join(f"`{s}`" for s in f.supporting_source_ids)
                        speaker = f.attribution_speaker or "Direct Reporting"
                        if f.attribution_anonymous:
                            speaker += " *(anon)*"
                        orig = f.original_text.replace("|", "\\|") if f.original_text else f.text.replace("|", "\\|")
                        clean = f.text.replace("|", "\\|")
                        lines.append(f"| **{clean}** | {src_str} | {speaker} | *\"{orig}\"* |")
                    lines.append("")
                else:
                    lines.append(f"- ⚡ {dp}")
                    lines.append("")

        # 3. Single-Source Facts
        if brief.single_source_facts:
            lines.append("## 3. Single-Source Context (Tier 3)")
            lines.append("")
            for fact in brief.single_source_facts:
                src_list = ", ".join(f"`{s}`" for s in fact.supporting_source_ids)
                speaker_str = f" (*Attributed: {fact.attribution_speaker}*)" if fact.attribution_speaker else ""
                lines.append(f"- 🟡 **[Tier 3: Single Source]**{speaker_str} {fact.text} *(Source: {src_list})*")
            lines.append("")

        # 4. Unknowns / Unverified Assertions
        lines.append("## 4. Known Unknowns & Reporting Gaps")
        lines.append("")
        if not brief.unknowns:
            lines.append("*No outstanding reporting gaps flagged.*")
        else:
            for unk in brief.unknowns:
                lines.append(f"- ❓ {unk}")
        lines.append("")

        # 5. Timeline
        lines.append("## 5. Event Chronology")
        lines.append("")
        if not brief.timeline:
            lines.append("*No structured timestamps identified.*")
        else:
            for item in brief.timeline:
                if isinstance(item, TimelineEntry):
                    srcs = f" *(via {', '.join(item.source_ids)})*" if item.source_ids else ""
                    lines.append(f"- **{item.timestamp_str}**: {item.description}{srcs}")
                else:
                    lines.append(f"- {item}")
        lines.append("")

        # 6. Source Ledger Audit
        lines.append("## 6. Source Transparency & Origin Audit")
        lines.append("")
        lines.append("| Source ID | Name | Tier | Independent Origin | Republished / Syndicated From |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for src in brief.source_ledger:
            tier_label = src.tier.value.upper()
            ind_label = "✅ Yes (Origin)" if src.independent_origin else "🔄 Syndicated Copy"
            repub_str = f"`{src.republished_from}`" if src.republished_from else "—"
            lines.append(f"| `{src.source_id}` | {src.name} | **{tier_label}** | {ind_label} | {repub_str} |")
        lines.append("")

        return "\n".join(lines)


class HtmlBriefRenderer:
    """Renders a standalone, responsive HTML brief with interactive drill-down drawers."""

    def render(self, brief: Brief) -> str:
        esc = html.escape

        core_facts_html = ""
        if not brief.core_facts:
            core_facts_html = "<p class='empty-state'>No Tier 1 or Tier 2 corroborated facts established yet.</p>"
        else:
            for fact in brief.core_facts:
                is_p1 = fact.tier == ConfidenceTier.PRIMARY_CONFIRMED
                badge_class = "tier-badge tier-1" if is_p1 else "tier-badge tier-2"
                badge_text = "Tier 1: Primary Confirmed" if is_p1 else "Tier 2: Corroborated"
                speaker_html = f"<span class='speaker-tag'>Attributed to: <strong>{esc(fact.attribution_speaker)}</strong>{' <em>(anon)</em>' if fact.attribution_anonymous else ''}</span>" if fact.attribution_speaker else ""
                sources_str = ", ".join(esc(s) for s in fact.supporting_source_ids)

                drill_down_html = f"""
                <details class="drill-down">
                    <summary>View Provenance & Original Text ({fact.independent_source_count} independent origin(s))</summary>
                    <div class="drill-content">
                        <p><strong>Sources:</strong> {sources_str}</p>
                        <p><strong>Original Raw Passage:</strong> <em>"{esc(fact.original_text or fact.text)}"</em></p>
                """
                if fact.changes:
                    drill_down_html += "<strong>Neutralization Edits:</strong><ul>"
                    for c in fact.changes:
                        drill_down_html += f"<li>[{esc(c.category)}] <code>{esc(c.original_span)}</code> &rarr; <code>{esc(c.replacement)}</code> <em>({esc(c.rationale)})</em></li>"
                    drill_down_html += "</ul>"

                if fact.item_urls:
                    drill_down_html += "<p><strong>Source URLs:</strong> " + " | ".join(f'<a href="{esc(u)}" target="_blank">{esc(u)}</a>' for u in fact.item_urls[:3]) + "</p>"

                drill_down_html += """
                    </div>
                </details>
                """

                core_facts_html += f"""
                <div class="fact-card">
                    <div class="fact-header">
                        <span class="{badge_class}">{badge_text}</span>
                        {speaker_html}
                    </div>
                    <div class="fact-text">{esc(fact.text)}</div>
                    {drill_down_html}
                </div>
                """

        # Disputed points HTML
        disputes_html = ""
        if not brief.disputed_points:
            disputes_html = "<p class='empty-state'>No conflicting claims or direct contradictions identified across reporting.</p>"
        else:
            for dp in brief.disputed_points:
                if isinstance(dp, DisputedPoint):
                    table_rows = ""
                    for f in dp.claims:
                        src_str = ", ".join(esc(s) for s in f.supporting_source_ids)
                        speaker = esc(f.attribution_speaker or "Direct Reporting")
                        if f.attribution_anonymous:
                            speaker += " <em>(anon)</em>"
                        table_rows += f"""
                        <tr>
                            <td><strong>{esc(f.text)}</strong></td>
                            <td><code>{src_str}</code></td>
                            <td>{speaker}</td>
                            <td><em>"{esc(f.original_text or f.text)}"</em></td>
                        </tr>
                        """
                    disputes_html += f"""
                    <div class="dispute-card">
                        <h3>⚡ {esc(dp.topic)}</h3>
                        <p class="dispute-expl">{esc(dp.explanation)}</p>
                        <table class="data-table">
                            <thead>
                                <tr><th>Position / Claim</th><th>Sources</th><th>Attribution</th><th>Original Text</th></tr>
                            </thead>
                            <tbody>
                                {table_rows}
                            </tbody>
                        </table>
                    </div>
                    """
                else:
                    disputes_html += f"<div class='dispute-card'><p>⚡ {esc(str(dp))}</p></div>"

        # Timeline HTML
        timeline_html = ""
        if not brief.timeline:
            timeline_html = "<p class='empty-state'>No chronological timestamps extracted.</p>"
        else:
            timeline_html = "<div class='timeline-container'>"
            for item in brief.timeline:
                if isinstance(item, TimelineEntry):
                    src_tag = f"<span class='timeline-src'>[{', '.join(esc(s) for s in item.source_ids)}]</span>" if item.source_ids else ""
                    timeline_html += f"""
                    <div class="timeline-item">
                        <div class="timeline-time">{esc(item.timestamp_str)}</div>
                        <div class="timeline-desc">{esc(item.description)} {src_tag}</div>
                    </div>
                    """
                else:
                    timeline_html += f"<div class='timeline-item'><div class='timeline-desc'>{esc(str(item))}</div></div>"
            timeline_html += "</div>"

        # Source Ledger Table
        ledger_rows = ""
        for src in brief.source_ledger:
            tier_class = f"badge-{src.tier.value}"
            ind_text = "✅ Independent Origin" if src.independent_origin else "🔄 Syndicated Copy"
            repub_text = f"<code>{esc(src.republished_from)}</code>" if src.republished_from else "—"
            ledger_rows += f"""
            <tr>
                <td><code>{esc(src.source_id)}</code></td>
                <td>{esc(src.name)}</td>
                <td><span class="badge {tier_class}">{esc(src.tier.value.upper())}</span></td>
                <td>{ind_text}</td>
                <td>{repub_text}</td>
            </tr>
            """

        # Compliance Banner
        comp_class = "status-pass" if brief.diversity_compliant else "status-warn"
        comp_title = "Source Diversity Quotas Satisfied" if brief.diversity_compliant else "Diversity Notice"
        defic_items = "".join(f"<li>{esc(d)}</li>" for d in brief.diversity_deficiencies)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(brief.neutral_headline)} - Neutral Event Brief</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --border: #334155;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #38bdf8;
            --tier1: #10b981;
            --tier2: #3b82f6;
            --tier3: #f59e0b;
            --tier4: #ef4444;
            --radius: 8px;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem 1rem;
        }}
        .container {{ max-width: 960px; margin: 0 auto; }}
        header {{ margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }}
        h1 {{ font-size: 2rem; color: #fff; margin-bottom: 0.5rem; }}
        .meta-bar {{ display: flex; gap: 1rem; flex-wrap: wrap; color: var(--text-muted); font-size: 0.9rem; margin-top: 0.5rem; }}
        .status-banner {{ padding: 0.75rem 1rem; border-radius: var(--radius); margin-bottom: 2rem; font-size: 0.95rem; }}
        .status-pass {{ background: rgba(16, 185, 129, 0.15); border: 1px solid var(--tier1); color: #6ee7b7; }}
        .status-warn {{ background: rgba(245, 158, 11, 0.15); border: 1px solid var(--tier3); color: #fcd34d; }}
        h2 {{ font-size: 1.4rem; color: var(--primary); margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
        .fact-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.25rem; margin-bottom: 1rem; }}
        .fact-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }}
        .tier-badge {{ padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold; text-transform: uppercase; }}
        .tier-1 {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid var(--tier1); }}
        .tier-2 {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid var(--tier2); }}
        .speaker-tag {{ color: var(--text-muted); font-size: 0.85rem; }}
        .fact-text {{ font-size: 1.05rem; font-weight: 500; margin-bottom: 0.75rem; }}
        details.drill-down {{ background: rgba(0,0,0,0.2); border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.9rem; }}
        details summary {{ cursor: pointer; color: var(--primary); font-weight: 500; }}
        .drill-content {{ margin-top: 0.75rem; color: var(--text-muted); line-height: 1.5; }}
        .dispute-card {{ background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: var(--radius); padding: 1.25rem; margin-bottom: 1.5rem; }}
        .dispute-card h3 {{ color: #f87171; margin-bottom: 0.5rem; }}
        .dispute-expl {{ font-size: 0.9rem; color: var(--text-muted); margin-bottom: 1rem; font-style: italic; }}
        .data-table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; font-size: 0.9rem; }}
        .data-table th, .data-table td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }}
        .data-table th {{ background: rgba(0,0,0,0.3); color: var(--text-muted); }}
        .badge {{ padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }}
        .badge-primary {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
        .badge-secondary {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; }}
        .timeline-container {{ border-left: 2px solid var(--primary); padding-left: 1.5rem; margin-left: 0.5rem; }}
        .timeline-item {{ position: relative; margin-bottom: 1.25rem; }}
        .timeline-item::before {{ content: ""; position: absolute; left: -1.85rem; top: 0.35rem; width: 10px; height: 10px; border-radius: 50%; background: var(--primary); }}
        .timeline-time {{ font-weight: bold; color: var(--primary); font-size: 0.9rem; }}
        .timeline-desc {{ font-size: 0.95rem; }}
        .timeline-src {{ color: var(--text-muted); font-size: 0.85rem; }}
        .empty-state {{ color: var(--text-muted); font-style: italic; padding: 1rem 0; }}
        a {{ color: var(--primary); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{esc(brief.neutral_headline)}</h1>
            <div class="meta-bar">
                <span>Event ID: <code>{esc(brief.event_id)}</code></span>
                <span>Sources: {len(brief.source_ledger)}</span>
                <span>Generated by Antigravity NewsX</span>
            </div>
        </header>

        <div class="status-banner {comp_class}">
            <strong>{comp_title}</strong>
            {"<ul>" + defic_items + "</ul>" if defic_items else ""}
        </div>

        <section>
            <h2>1. Core Verified Facts</h2>
            {core_facts_html}
        </section>

        <section>
            <h2>2. Disputed Points</h2>
            {disputes_html}
        </section>

        <section>
            <h2>3. Event Chronology</h2>
            {timeline_html}
        </section>

        <section>
            <h2>4. Source Transparency & Origin Audit</h2>
            <table class="data-table">
                <thead>
                    <tr><th>Source ID</th><th>Name</th><th>Tier</th><th>Independent Origin</th><th>Syndication</th></tr>
                </thead>
                <tbody>
                    {ledger_rows}
                </tbody>
            </table>
        </section>
    </div>
</body>
</html>
"""


class ConsoleBriefRenderer:
    """Renders ANSI formatted brief for terminal output."""

    def render(self, brief: Brief) -> str:
        lines: list[str] = []
        lines.append("=" * 78)
        lines.append(f"  EVENT BRIEF: {brief.neutral_headline}")
        lines.append("=" * 78)
        lines.append(f"Event ID: {brief.event_id} | Diversity: {'COMPLIANT' if brief.diversity_compliant else 'DEFICIENT'}")
        lines.append("-" * 78)

        lines.append("\n[1. CORE VERIFIED FACTS]")
        if not brief.core_facts:
            lines.append("  (No corroborated core facts)")
        for fact in brief.core_facts:
            tag = "[Tier 1: PRIMARY]" if fact.tier == ConfidenceTier.PRIMARY_CONFIRMED else "[Tier 2: CORROBORATED]"
            speaker = f" [Attributed: {fact.attribution_speaker}]" if fact.attribution_speaker else ""
            lines.append(f"  * {tag}{speaker} {fact.text}")
            lines.append(f"    - Sources: {', '.join(fact.supporting_source_ids)} ({fact.independent_source_count} ind. origin(s))")

        if brief.disputed_points:
            lines.append("\n[2. DISPUTED POINTS]")
            for dp in brief.disputed_points:
                if isinstance(dp, DisputedPoint):
                    lines.append(f"  * DISPUTE: {dp.topic}")
                    for f in dp.claims:
                        lines.append(f"    - [{', '.join(f.supporting_source_ids)}]: {f.text}")

        if brief.timeline:
            lines.append("\n[3. TIMELINE]")
            for item in brief.timeline:
                if isinstance(item, TimelineEntry):
                    lines.append(f"  * {item.timestamp_str}: {item.description}")

        lines.append("\n" + "=" * 78)
        return "\n".join(lines)
