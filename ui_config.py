from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchPanelConfig:
    title: str
    placeholder: str
    day_range_label: str
    button_label: str
    show_manual_api_key: bool


def get_mobile_search_panel_config() -> SearchPanelConfig:
    return SearchPanelConfig(
        title="輸入股票代號或名稱",
        placeholder="例如 2330、台積電、緯創",
        day_range_label="抓取天數",
        button_label="啟動分析",
        show_manual_api_key=False,
    )


def resolve_active_api_key(system_api_key: str | None) -> str | None:
    return system_api_key or None
