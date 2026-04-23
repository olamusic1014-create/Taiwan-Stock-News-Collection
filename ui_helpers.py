from __future__ import annotations

from html import escape


def build_source_sections(data_map: dict[str, list[dict]]) -> list[dict]:
    sections = []
    for source_name, items in data_map.items():
        if not items:
            continue
        links = []
        for item in items:
            title = item.get("title", "").strip()
            if not title:
                continue
            link = item.get("link") or f"https://www.google.com/search?q={title}"
            links.append({"title": title, "link": link})
        if links:
            sections.append({"source": source_name, "count": len(links), "links": links})
    return sections


def build_report_markup(report_text: str) -> str:
    safe_text = escape(report_text or "").replace("\n", "<br>")
    return (
        "<div style='background:#111111;border:1px solid #242424;border-radius:16px;"
        "padding:14px 16px;color:#aeaeae;line-height:1.65;'>"
        f"{safe_text}</div>"
    )
