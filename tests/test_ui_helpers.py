import unittest

from ui_helpers import build_report_markup, build_source_sections


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


if __name__ == "__main__":
    unittest.main()
