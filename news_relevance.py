from __future__ import annotations

import re
from urllib.parse import quote_plus


def normalize_stock_name_variants(stock_name: str) -> set[str]:
    names = {stock_name.strip()}
    if "台" in stock_name:
        names.add(stock_name.replace("台", "臺"))
    if "臺" in stock_name:
        names.add(stock_name.replace("臺", "台"))
    return {name for name in names if name}


def build_google_rss_query(stock_code: str, stock_name: str, site_domain: str) -> str:
    primary_name = stock_name.strip()
    if primary_name:
        return f'"{primary_name}" site:{site_domain}'
    return f'"{stock_code}" site:{site_domain}'


def is_relevant_news_text(text: str, stock_code: str, stock_name: str) -> bool:
    if not text:
        return False

    normalized_text = text.strip()
    if not normalized_text:
        return False

    for variant in normalize_stock_name_variants(stock_name):
        if variant in normalized_text:
            return True

    strong_code_patterns = (
        rf"\({re.escape(stock_code)}\)",
        rf"\b{re.escape(stock_code)}\.TW\b",
        rf"\b{re.escape(stock_code)}\.TWO\b",
        rf"代號\s*{re.escape(stock_code)}",
        rf"股票\s*{re.escape(stock_code)}",
    )
    return any(re.search(pattern, normalized_text, re.IGNORECASE) for pattern in strong_code_patterns)


def build_google_rss_url(stock_code: str, stock_name: str, site_domain: str) -> str:
    query = quote_plus(build_google_rss_query(stock_code, stock_name, site_domain))
    return f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
