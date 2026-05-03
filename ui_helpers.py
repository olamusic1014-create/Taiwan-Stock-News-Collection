from __future__ import annotations

from html import escape
import re


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


def normalize_stock_inputs(values: list[str], limit: int = 3) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        clean_value = (value or "").strip().upper()
        if not clean_value or clean_value in seen:
            continue
        normalized.append(clean_value)
        seen.add(clean_value)
        if len(normalized) >= limit:
            break

    return normalized


def parse_ai_report(report_text: str) -> dict[str, str]:
    clean_report = re.sub(
        r"(?im)^SCORE:\s*\d+\s*$",
        "",
        report_text or "",
    ).strip()

    def extract(label: str) -> str:
        pattern = (
            rf"(?:\*\*)?{label}(?:\*\*)?\s*:\s*(.+?)"
            r"(?=(?:\n(?:\*\*)?(?:LEVEL|SUMMARY|ANALYSIS)(?:\*\*)?\s*:)|\Z)"
        )
        match = re.search(pattern, clean_report, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip().strip("*")

    level = extract("LEVEL")
    summary = extract("SUMMARY")
    analysis = extract("ANALYSIS")

    fallback = clean_report.replace("\n", " ").strip()
    if not summary:
        summary = fallback
    if not analysis:
        analysis = summary
    if not level:
        level = "觀望"

    return {
        "level": level,
        "summary": summary,
        "analysis": analysis,
        "raw": clean_report,
    }


def build_dashboard_theme_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;800&display=swap');

:root {
    --bg-primary: #040b1b;
    --bg-secondary: #081226;
    --surface-primary: rgba(10, 20, 42, 0.92);
    --surface-secondary: rgba(13, 26, 54, 0.94);
    --surface-highlight: rgba(18, 45, 94, 0.92);
    --border-primary: rgba(84, 132, 235, 0.22);
    --border-strong: rgba(91, 142, 255, 0.42);
    --text-primary: #f8fbff;
    --text-secondary: #a8b7da;
    --text-muted: #7f91b8;
    --accent-blue: #3d8dff;
    --accent-cyan: #4ad5ff;
    --accent-green: #65d98b;
    --accent-amber: #ffbd59;
    --accent-red: #ff7b78;
    --shadow-soft: 0 24px 60px rgba(0, 0, 0, 0.28);
}

.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background:
        radial-gradient(circle at top left, rgba(44, 102, 255, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(72, 214, 255, 0.1), transparent 18%),
        linear-gradient(180deg, #030815 0%, #07111f 46%, #050c18 100%);
    color: var(--text-primary);
    font-family: "Plus Jakarta Sans", "Noto Sans TC", sans-serif;
}

[data-testid="stSidebar"], [data-testid="collapsedControl"] {
    display: none;
}

.block-container {
    max-width: 760px;
    padding-top: 1.5rem;
    padding-bottom: 6.5rem;
}

.dashboard-shell {
    position: relative;
}

.dashboard-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 22px;
}

.hero-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0;
}

.hero-mark {
    width: 68px;
    height: 68px;
    border-radius: 22px;
    display: grid;
    place-items: center;
    background:
        radial-gradient(circle at 30% 30%, rgba(74, 213, 255, 0.38), transparent 30%),
        linear-gradient(160deg, rgba(27, 69, 159, 0.95) 0%, rgba(9, 22, 46, 0.98) 100%);
    border: 1px solid rgba(122, 166, 255, 0.25);
    box-shadow: 0 18px 40px rgba(20, 65, 166, 0.3);
    font-size: 28px;
}

.hero-copy h1 {
    margin: 0 0 6px;
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.04em;
}

.hero-copy p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.95rem;
}

.hero-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--text-secondary);
    font-size: 1.2rem;
}

.hero-action {
    width: 38px;
    height: 38px;
    display: grid;
    place-items: center;
    border-radius: 999px;
    background: rgba(11, 23, 48, 0.8);
    border: 1px solid rgba(84, 132, 235, 0.18);
}

.status-banner,
.dashboard-panel,
.dashboard-card,
.focus-inline-card,
.metric-strip,
.detail-panel {
    background: linear-gradient(180deg, rgba(10, 20, 42, 0.95), rgba(8, 17, 34, 0.96));
    border: 1px solid var(--border-primary);
    box-shadow: var(--shadow-soft);
}

.status-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    border-radius: 18px;
    padding: 18px 20px;
    margin-bottom: 18px;
    overflow: hidden;
}

.status-banner-copy {
    display: flex;
    align-items: center;
    gap: 14px;
}

.status-badge {
    width: 40px;
    height: 40px;
    border-radius: 999px;
    display: grid;
    place-items: center;
    background: rgba(101, 217, 139, 0.18);
    color: var(--accent-green);
    font-size: 1.1rem;
}

.status-banner-title {
    margin: 0 0 4px;
    color: #88f0a9;
    font-size: 1.02rem;
    font-weight: 700;
}

.status-banner-detail {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.88rem;
}

.status-banner-chart {
    min-width: 108px;
    height: 48px;
    border-radius: 14px;
    background:
        radial-gradient(circle at 80% 30%, rgba(101, 217, 139, 0.35), transparent 28%),
        linear-gradient(135deg, rgba(37, 69, 132, 0.3) 0%, rgba(13, 43, 60, 0.55) 100%);
    position: relative;
}

.status-banner-chart::after {
    content: "";
    position: absolute;
    inset: 10px 12px;
    border-bottom: 2px solid rgba(101, 217, 139, 0.45);
    border-right: 2px solid rgba(101, 217, 139, 0.45);
    border-radius: 14px;
    transform: skewX(-20deg);
}

.dashboard-panel {
    border-radius: 24px;
    padding: 20px;
    margin-bottom: 20px;
}

.panel-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 14px;
}

.panel-heading h2 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 700;
}

.panel-heading p {
    margin: 4px 0 0;
    color: var(--text-secondary);
    font-size: 0.82rem;
}

.panel-count {
    color: var(--accent-blue);
    font-size: 0.9rem;
    font-weight: 700;
}

.slot-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 14px;
}

.symbol-slot {
    border-radius: 18px;
    padding: 14px 16px;
    background: linear-gradient(180deg, rgba(17, 30, 60, 0.95), rgba(13, 23, 46, 0.98));
    border: 1px solid rgba(101, 132, 196, 0.2);
}

.symbol-slot-label {
    margin-bottom: 8px;
    color: var(--text-muted);
    font-size: 0.78rem;
}

.symbol-slot-value {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 1.15rem;
    font-weight: 700;
}

.symbol-slot-value span:last-child {
    color: rgba(255, 255, 255, 0.35);
    font-size: 0.9rem;
}

.hot-symbols {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 12px 0 18px;
}

.hot-symbol {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(23, 57, 125, 0.42);
    border: 1px solid rgba(61, 141, 255, 0.28);
    color: #8ec2ff;
    font-size: 0.8rem;
}

.analysis-button-note {
    margin-top: 10px;
    color: var(--text-muted);
    font-size: 0.8rem;
}

div[data-testid="stForm"] {
    background: linear-gradient(180deg, rgba(10, 20, 42, 0.95), rgba(8, 17, 34, 0.96));
    border: 1px solid var(--border-primary);
    border-radius: 24px;
    padding: 20px;
    box-shadow: var(--shadow-soft);
    margin-bottom: 18px;
}

div[data-testid="stTextInput"] label p,
div[data-testid="stSelectSlider"] label p {
    color: var(--text-secondary) !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
}

div[data-testid="stTextInput"] input {
    min-height: 56px;
    border-radius: 18px;
    background: rgba(15, 29, 58, 0.95);
    border: 1px solid rgba(89, 122, 189, 0.25);
    color: var(--text-primary);
    font-size: 1.05rem;
    font-weight: 600;
}

div[data-testid="stTextInput"] input:focus {
    border-color: rgba(74, 213, 255, 0.55);
    box-shadow: 0 0 0 1px rgba(74, 213, 255, 0.35);
}

div[data-testid="stSelectSlider"] [data-baseweb="slider"] {
    padding-top: 4px;
}

div[data-testid="stForm"] button {
    min-height: 56px;
    border-radius: 18px;
    border: 0;
    color: white;
    font-size: 1.12rem;
    font-weight: 800;
    background: linear-gradient(90deg, #31b8ff 0%, #225cff 100%);
    box-shadow: 0 18px 40px rgba(34, 92, 255, 0.32);
}

div[data-testid="stForm"] button:hover {
    background: linear-gradient(90deg, #5bc6ff 0%, #3d72ff 100%);
}

.focus-button-wrapper div[data-testid="stButton"] button {
    min-height: 54px;
    border-radius: 18px;
    border: 1px solid rgba(84, 132, 235, 0.28);
    background: linear-gradient(180deg, rgba(11, 24, 48, 0.95), rgba(7, 16, 30, 0.96));
    color: var(--text-primary);
    font-weight: 800;
    box-shadow: var(--shadow-soft);
}

.focus-button-wrapper div[data-testid="stButton"] button:hover {
    border-color: rgba(74, 213, 255, 0.42);
}

.task-done-wrapper div[data-testid="stButton"] button,
.task-error-wrapper div[data-testid="stButton"] button {
    min-height: 56px;
    border-radius: 16px;
    font-weight: 700;
    color: white;
}

.task-done-wrapper div[data-testid="stButton"] button {
    background: linear-gradient(135deg, rgba(41, 148, 89, 0.95), rgba(14, 113, 79, 0.95));
    border: 1px solid rgba(122, 237, 168, 0.24);
}

.task-error-wrapper div[data-testid="stButton"] button {
    background: linear-gradient(135deg, rgba(148, 49, 72, 0.96), rgba(109, 23, 48, 0.96));
    border: 1px solid rgba(255, 135, 152, 0.22);
}

.focus-inline-card {
    border-radius: 20px;
    padding: 16px 18px;
    margin-top: 16px;
}

.focus-inline-card h3 {
    margin: 0 0 6px;
    font-size: 1.02rem;
}

.focus-inline-card p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.87rem;
}

.task-pill {
    padding: 12px 14px;
    border-radius: 16px;
    text-align: center;
    font-weight: 700;
    border: 1px solid rgba(84, 132, 235, 0.22);
    background: rgba(13, 27, 54, 0.9);
    color: var(--text-primary);
    margin-bottom: 10px;
}

.task-pill.running {
    color: #97dcff;
}

.task-pill.done {
    color: #9ae6a8;
}

.task-pill.error {
    color: #ffb4b2;
}

.dashboard-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin: 24px 0 14px;
}

.dashboard-section-header h2 {
    margin: 0;
    font-size: 1.12rem;
    font-weight: 800;
}

.dashboard-section-header span {
    color: var(--text-muted);
    font-size: 0.8rem;
}

.dashboard-card-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.dashboard-card {
    border-radius: 20px;
    padding: 18px;
}

.dashboard-card h3 {
    margin: 0 0 12px;
    font-size: 1rem;
    font-weight: 700;
}

.dashboard-card p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.7;
    font-size: 0.92rem;
}

.analysis-stock {
    margin-bottom: 10px;
    color: #9fbeff;
    font-size: 0.84rem;
    font-weight: 700;
}

.summary-list {
    margin: 0;
    padding-left: 1.15rem;
    color: var(--text-secondary);
}

.summary-list li {
    margin-bottom: 0.55rem;
    line-height: 1.55;
    font-size: 0.91rem;
}

.dashboard-chip-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin: 14px 0;
}

.metric-chip {
    border-radius: 16px;
    padding: 14px 16px;
    background: rgba(13, 26, 54, 0.95);
    border: 1px solid rgba(84, 132, 235, 0.18);
}

.metric-chip span {
    display: block;
    color: var(--text-muted);
    font-size: 0.78rem;
    margin-bottom: 6px;
}

.metric-chip strong {
    font-size: 1rem;
}

.metric-chip.positive strong {
    color: #7ae6a2;
}

.metric-chip.neutral strong {
    color: #ffd479;
}

.metric-chip.negative strong {
    color: #ff9f9a;
}

.metric-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0;
    border-radius: 20px;
    overflow: hidden;
}

.metric-strip-item {
    padding: 18px;
    border-right: 1px solid rgba(84, 132, 235, 0.14);
}

.metric-strip-item:last-child {
    border-right: 0;
}

.metric-strip-item span {
    display: block;
    color: var(--text-muted);
    font-size: 0.82rem;
    margin-bottom: 10px;
}

.metric-strip-item strong {
    display: block;
    font-size: 1.95rem;
    line-height: 1;
    margin-bottom: 6px;
}

.metric-strip-item small {
    color: var(--text-secondary);
    font-size: 0.82rem;
}

.metric-strip-item.positive strong {
    color: #7ae6a2;
}

.metric-strip-item.neutral strong {
    color: #ffd479;
}

.metric-strip-item.negative strong {
    color: #ff9f9a;
}

.dashboard-empty {
    padding: 24px;
    border-radius: 20px;
    background: rgba(13, 26, 54, 0.9);
    border: 1px dashed rgba(84, 132, 235, 0.26);
    color: var(--text-secondary);
    text-align: center;
}

.detail-panel {
    border-radius: 20px;
    padding: 18px;
    margin-top: 16px;
}

.news-row {
    margin-bottom: 12px;
    padding: 16px;
    border-radius: 16px;
    background: rgba(10, 20, 42, 0.95);
    border: 1px solid rgba(84, 132, 235, 0.18);
    font-size: 0.92rem;
    transition: transform 0.18s ease, border-color 0.18s ease;
}

.news-row:hover {
    transform: translateY(-2px);
    border-color: rgba(74, 213, 255, 0.42);
}

.detail-panel h3 {
    margin-top: 0;
}

.bottom-nav {
    position: fixed;
    left: 50%;
    bottom: 0;
    width: min(760px, calc(100vw - 24px));
    transform: translateX(-50%);
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0;
    padding: 10px 12px 14px;
    border-top: 1px solid rgba(84, 132, 235, 0.2);
    background: rgba(3, 10, 24, 0.92);
    backdrop-filter: blur(20px);
}

.bottom-nav-item {
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.8rem;
}

.bottom-nav-item strong {
    display: block;
    margin-bottom: 6px;
    font-size: 1.1rem;
}

.bottom-nav-item.active {
    color: #70afff;
}

@media (max-width: 760px) {
    .dashboard-topbar,
    .panel-heading,
    .dashboard-section-header {
        flex-direction: column;
        align-items: flex-start;
    }

    .slot-grid,
    .dashboard-card-grid,
    .dashboard-chip-row,
    .metric-strip {
        grid-template-columns: 1fr;
    }

    .metric-strip-item {
        border-right: 0;
        border-bottom: 1px solid rgba(84, 132, 235, 0.14);
    }

    .metric-strip-item:last-child {
        border-bottom: 0;
    }

    .hero-copy h1 {
        font-size: 1.72rem;
    }

    .bottom-nav {
        width: calc(100vw - 12px);
    }
}
</style>
""".strip()


def build_dashboard_status_markup(title: str, detail: str) -> str:
    return (
        "<div class='status-banner'>"
        "  <div class='status-banner-copy'>"
        "    <div class='status-badge'>✓</div>"
        "    <div>"
        f"      <div class='status-banner-title'>{escape(title)}</div>"
        f"      <p class='status-banner-detail'>{escape(detail)}</p>"
        "    </div>"
        "  </div>"
        "  <div class='status-banner-chart' aria-hidden='true'></div>"
        "</div>"
    )


def build_dashboard_result_markup(
    stock_name: str,
    stock_code: str,
    report_text: str,
    news_items: list[dict],
    tracked_codes: list[str] | None = None,
    updated_at: str | None = None,
) -> str:
    parsed = parse_ai_report(report_text)
    level = parsed["level"]
    summary = parsed["summary"]
    analysis = parsed["analysis"]

    metric_class, emotion_score, volatility_label = _sentiment_meta(level, len(news_items))
    safe_stock_name = escape(stock_name or "等待分析")
    safe_stock_code = escape(stock_code or "--")
    safe_updated_at = escape(updated_at or "等待更新")
    safe_watchlist = escape(" · ".join(tracked_codes or [stock_code or "--"]))

    bullet_items = []
    for item in news_items[:4]:
        title = (item.get("title") or "").strip()
        if title:
            bullet_items.append(f"<li>{escape(title)}</li>")
    if not bullet_items:
        bullet_items.append("<li>尚未取得可用新聞，請啟動分析或拉長新聞時間窗。</li>")

    safe_summary = escape(summary).replace("\n", "<br>")
    safe_analysis = escape(analysis).replace("\n", "<br>")

    return (
        "<div class='dashboard-shell'>"
        "  <div class='dashboard-section-header'>"
        "    <h2>最新分析結果</h2>"
        f"    <span>更新時間: {safe_updated_at}</span>"
        "  </div>"
        "  <div class='dashboard-card-grid'>"
        "    <section class='dashboard-card'>"
        f"      <div class='analysis-stock'>{safe_stock_name} · {safe_stock_code}</div>"
        "      <h3>新聞摘要</h3>"
        f"      <p>{safe_summary}</p>"
        f"      <ul class='summary-list'>{''.join(bullet_items)}</ul>"
        "    </section>"
        "    <section class='dashboard-card'>"
        f"      <div class='analysis-stock'>LEVEL: {escape(level)}</div>"
        "      <h3>AI 綜合建議</h3>"
        f"      <p>{safe_analysis}</p>"
        "    </section>"
        "  </div>"
        "  <div class='dashboard-chip-row'>"
        f"    <div class='metric-chip {metric_class}'><span>市場情緒</span><strong>{escape(level)}</strong></div>"
        f"    <div class='metric-chip neutral'><span>風險等級</span><strong>{escape(_risk_label(level))}</strong></div>"
        f"    <div class='metric-chip {metric_class}'><span>波動預期</span><strong>{escape(volatility_label)}</strong></div>"
        "  </div>"
        "  <div class='metric-strip'>"
        "    <div class='metric-strip-item'>"
        f"      <span>新聞數量</span><strong>{len(news_items)}</strong><small>依近期新聞彙整</small>"
        "    </div>"
        f"    <div class='metric-strip-item {metric_class}'>"
        f"      <span>情緒分數</span><strong>{emotion_score}</strong><small>由 LEVEL 與摘要語氣推估</small>"
        "    </div>"
        "    <div class='metric-strip-item'>"
        f"      <span>建議觀察</span><strong>{len(tracked_codes or [stock_code])} 檔</strong><small>{safe_watchlist}</small>"
        "    </div>"
        "  </div>"
        "</div>"
    )


def _sentiment_meta(level: str, news_count: int) -> tuple[str, str, str]:
    level_text = level.strip()
    if any(token in level_text for token in ("多", "樂觀", "強", "回補", "上攻")):
        metric_class = "positive"
        emotion_score = "+0.62"
    elif any(token in level_text for token in ("空", "弱", "出貨", "保守", "下修")):
        metric_class = "negative"
        emotion_score = "-0.41"
    else:
        metric_class = "neutral"
        emotion_score = "+0.08"

    if news_count >= 8:
        volatility_label = "高波動"
    elif news_count >= 4:
        volatility_label = "中性"
    else:
        volatility_label = "低波動"

    return metric_class, emotion_score, volatility_label


def _risk_label(level: str) -> str:
    level_text = level.strip()
    if any(token in level_text for token in ("多", "樂觀", "強")):
        return "中性"
    if any(token in level_text for token in ("空", "弱", "保守", "出貨")):
        return "偏高"
    return "觀察"
