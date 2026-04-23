from __future__ import annotations


def merge_market_scan_data(base_stock_dict: dict[str, str], scan_payload: dict) -> dict[str, str]:
    merged = dict(base_stock_dict)
    for item in scan_payload.get("data", []):
        row = item.get("d", [])
        if len(row) < 2:
            continue
        code = str(row[0]).strip()
        name = str(row[1]).replace("KY", "").strip()
        if code and name:
            merged[name] = code
    return merged
