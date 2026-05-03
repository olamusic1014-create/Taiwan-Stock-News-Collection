import unittest

from ui_helpers import (
    build_dashboard_result_markup,
    build_dashboard_theme_css,
    build_report_markup,
    build_source_sections,
    normalize_stock_inputs,
    parse_ai_report,
)


class UiHelpersTests(unittest.TestCase):
    def test_build_source_sections_keeps_clickable_links_per_source(self):
        sections = build_source_sections(
            {
                "鉅亨網": [
                    {"title": "台積電法說會", "link": "https://example.com/a"},
                    {"title": "台積電擴產", "link": "https://example.com/b"},
                ],
                "Yahoo": [],
            }
        )

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["source"], "鉅亨網")
        self.assertEqual(sections[0]["count"], 2)
        self.assertEqual(sections[0]["links"][0]["link"], "https://example.com/a")

    def test_build_report_markup_uses_requested_text_color(self):
        markup = build_report_markup("分析報告")

        self.assertIn("#aeaeae", markup)
        self.assertIn("分析報告", markup)

    def test_normalize_stock_inputs_strips_deduplicates_and_limits(self):
        symbols = normalize_stock_inputs([" 2330 ", "2317", "", "2330", "0050", "2603"])

        self.assertEqual(symbols, ["2330", "2317", "0050"])

    def test_parse_ai_report_extracts_dashboard_sections(self):
        parsed = parse_ai_report(
            "LEVEL: 偏多\n"
            "SUMMARY: 外資回補、權值股帶動指數走強。\n"
            "ANALYSIS: 短線量價同步增溫，但高檔震盪風險仍在。"
        )

        self.assertEqual(parsed["level"], "偏多")
        self.assertIn("外資回補", parsed["summary"])
        self.assertIn("高檔震盪", parsed["analysis"])

    def test_build_dashboard_theme_css_contains_dashboard_primitives(self):
        css = build_dashboard_theme_css()

        self.assertIn(".dashboard-shell", css)
        self.assertIn(".status-banner", css)
        self.assertIn(".symbol-slot", css)
        self.assertIn(".dashboard-card", css)

    def test_build_dashboard_result_markup_renders_cards_and_metrics(self):
        markup = build_dashboard_result_markup(
            stock_name="台積電",
            stock_code="2330",
            report_text=(
                "LEVEL: 偏多\n"
                "SUMMARY: 法說會釋出正向展望，市場聚焦先進製程需求。\n"
                "ANALYSIS: 可留意外資買盤延續性與高檔獲利了結壓力。"
            ),
            news_items=[
                {"title": "台積電法說會優於預期", "source": "鉅亨網"},
                {"title": "外資回補半導體權值股", "source": "經濟日報"},
            ],
            tracked_codes=["2330", "2317", "0050"],
            updated_at="2026/05/03 10:30",
        )

        self.assertIn("最新分析結果", markup)
        self.assertIn("新聞摘要", markup)
        self.assertIn("AI 綜合建議", markup)
        self.assertIn("台積電法說會優於預期", markup)
        self.assertIn("2330 · 2317 · 0050", markup)


if __name__ == "__main__":
    unittest.main()
