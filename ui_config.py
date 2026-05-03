from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchPanelConfig:
    hero_title: str
    hero_subtitle: str
    title: str
    placeholder: str
    input_labels: tuple[str, str, str]
    day_range_label: str
    button_label: str
    database_banner_title: str
    database_banner_detail: str
    focus_title: str
    focus_subtitle: str
    hot_symbols: tuple[str, ...]
    show_manual_api_key: bool


def get_mobile_search_panel_config() -> SearchPanelConfig:
    return SearchPanelConfig(
        hero_title="股市新聞爬蟲 AI 分析台",
        hero_subtitle="輸入股票代號，爬取新聞後由 AI 整合分析與建議",
        title="輸入股票代號（最多 3 檔）",
        placeholder="例如 2330、台積電、緯創",
        input_labels=("股票代號 1", "股票代號 2", "股票代號 3"),
        day_range_label="新聞時間窗",
        button_label="開始爬取並 AI 分析",
        database_banner_title="資料庫已就緒｜支援即時新聞爬取",
        database_banner_detail="新聞來源涵蓋超過 50+ 財經媒體與公告站點",
        focus_title="今日股市焦點",
        focus_subtitle="一鍵爬取今日整體市場新聞，AI 分析大盤趨勢與焦點",
        hot_symbols=("2330 台積電", "2317 鴻海", "0050 元大台灣50", "2382 廣達"),
        show_manual_api_key=False,
    )


def resolve_active_api_key(system_api_key: str | None) -> str | None:
    return system_api_key or None
