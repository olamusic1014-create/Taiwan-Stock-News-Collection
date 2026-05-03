import unittest
from pathlib import Path

from ui_helpers import (
    build_dashboard_loading_markup,
    build_dashboard_input_overlay_markup,
    build_dashboard_result_markup,
    build_dashboard_status_markup,
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

    def test_build_dashboard_theme_css_centers_input_panel_and_keeps_inputs_full_width(self):
        css = build_dashboard_theme_css()

        self.assertIn("margin: 0 auto 18px;", css)
        self.assertIn("max-width: 720px;", css)
        self.assertIn('div[data-testid="stTextInput"] {\n    width: 100%;', css)
        self.assertIn("justify-content: center;", css)
        self.assertIn("text-align: center;", css)

    def test_build_dashboard_theme_css_drops_non_functional_decorative_classes(self):
        css = build_dashboard_theme_css()

        self.assertNotIn(".hero-actions", css)
        self.assertNotIn(".hero-action", css)
        self.assertNotIn(".status-banner-chart", css)
        self.assertNotIn(".bottom-nav", css)

    def test_build_dashboard_theme_css_uses_inset_stock_input_style_reference(self):
        css = build_dashboard_theme_css()

        self.assertIn('[data-baseweb="base-input"] {', css)
        self.assertIn("box-shadow: inset 2px 5px 10px", css)
        self.assertIn(':focus-within {', css)
        self.assertIn("background-color: rgba(245, 248, 255, 0.98) !important;", css)
        self.assertNotIn("transform: scale(1.05);", css)

    def test_build_dashboard_theme_css_rebuilds_stock_input_shell_for_overlay_text(self):
        css = build_dashboard_theme_css()

        self.assertIn(".stock-input-overlay {", css)
        self.assertIn("margin-top: -80px;", css)
        self.assertIn("margin-bottom: -80px;", css)
        self.assertIn("pointer-events: none;", css)
        self.assertIn("opacity: 1;", css)
        self.assertIn(".stock-input-overlay-value {", css)
        self.assertIn("font-size: 1.89rem !important;", css)
        self.assertIn("transform: translateY(-6px);", css)
        self.assertIn("color: transparent !important;", css)
        self.assertIn("-webkit-text-fill-color: transparent !important;", css)
        self.assertIn("caret-color: var(--text-primary);", css)
        self.assertIn("text-align: center !important;", css)
        self.assertIn('div[data-testid="stElementContainer"]:has(div[data-testid="stTextInput"]:focus-within) + div[data-testid="stElementContainer"] .stock-input-overlay {', css)

    def test_build_dashboard_theme_css_reveals_grey_native_text_on_focus(self):
        css = build_dashboard_theme_css()

        self.assertIn('div[data-testid="stTextInput"] input:focus {', css)
        self.assertIn("color: #787878 !important;", css)
        self.assertIn("-webkit-text-fill-color: #787878 !important;", css)
        self.assertIn("caret-color: #787878;", css)
        self.assertIn("opacity: 0;", css)
        self.assertIn("input::selection {", css)

    def test_build_dashboard_theme_css_keeps_native_placeholder_hidden_while_editing(self):
        css = build_dashboard_theme_css()

        self.assertIn(
            'div[data-testid="stTextInput"] input:focus::placeholder {\n'
            "    color: transparent !important;\n"
            "    -webkit-text-fill-color: transparent !important;",
            css,
        )

    def test_build_dashboard_theme_css_includes_animated_loading_bar_styles(self):
        css = build_dashboard_theme_css()

        self.assertIn(".analysis-loading-track {", css)
        self.assertIn("mix-blend-mode: difference;", css)
        self.assertIn("-webkit-box-reflect: below 1px", css)
        self.assertIn("@keyframes gradientAnimation", css)
        self.assertIn("width: var(--loading-progress, 0%);", css)

    def test_build_dashboard_input_overlay_markup_renders_escaped_value(self):
        markup = build_dashboard_input_overlay_markup("<2330>", "2330")

        self.assertIn("stock-input-overlay", markup)
        self.assertIn("stock-input-overlay-value", markup)
        self.assertIn("&lt;2330&gt;", markup)
        self.assertNotIn("is-placeholder", markup)

    def test_build_dashboard_input_overlay_markup_uses_placeholder_style_when_empty(self):
        markup = build_dashboard_input_overlay_markup("", "2330")

        self.assertIn(">2330<", markup)
        self.assertIn("is-placeholder", markup)

    def test_build_dashboard_status_markup_keeps_only_copy_without_chart_stub(self):
        markup = build_dashboard_status_markup("資料庫已就緒", "支援即時新聞爬取")

        self.assertIn("status-banner-copy", markup)
        self.assertNotIn("status-banner-chart", markup)

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

    def test_app_places_market_focus_section_above_task_and_result_sections(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        focus_index = app_source.index("# 今日股市焦點 區塊")
        tasks_index = app_source.index("# 繪製 Task Slots 按鈕列")
        result_index = app_source.index("# 顯示目前選取的報告")

        self.assertLess(focus_index, tasks_index)
        self.assertLess(focus_index, result_index)

    def test_app_renders_stock_input_overlay_after_text_input(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("build_dashboard_input_overlay_markup(", app_source)

    def test_app_uses_loading_markup_for_running_analysis_state(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("build_dashboard_loading_markup(", app_source)

    def test_app_starts_with_blank_stock_inputs_and_no_native_placeholder_copy(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('st.session_state.last_inputs = ["", "", ""]', app_source)
        self.assertIn('default_inputs = list(st.session_state.get("last_inputs", ["", "", ""]))[:3]', app_source)
        self.assertIn('placeholder=""', app_source)
        self.assertNotIn('["2330", "2317", "0050"]', app_source)

    def test_build_dashboard_loading_markup_renders_clamped_progress_bar(self):
        markup = build_dashboard_loading_markup(
            stock_name="台積電",
            stock_code="2330",
            progress=142,
        )

        self.assertIn("台積電", markup)
        self.assertIn("2330", markup)
        self.assertIn("抓取資料中....", markup)
        self.assertIn("100%", markup)
        self.assertIn("--loading-progress: 100%;", markup)


if __name__ == "__main__":
    unittest.main()
