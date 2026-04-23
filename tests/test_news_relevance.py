import unittest

from news_relevance import build_google_rss_query, is_relevant_news_text


class NewsRelevanceTests(unittest.TestCase):
    def test_google_rss_query_prioritizes_stock_name(self):
        query = build_google_rss_query("2330", "台積電", "money.udn.com")

        self.assertIn("台積電", query)
        self.assertIn("site:money.udn.com", query)
        self.assertNotEqual(query.strip(), "2330")

    def test_stock_name_match_is_relevant(self):
        self.assertTrue(is_relevant_news_text("台積電法說會聚焦先進製程", "2330", "台積電"))

    def test_plain_numeric_amount_is_not_relevant(self):
        self.assertFalse(is_relevant_news_text("半導體設備訂單衝上2330億元", "2330", "台積電"))

    def test_parenthesized_stock_code_counts_as_relevant(self):
        self.assertTrue(is_relevant_news_text("外資調高台積電(2330)目標價", "2330", "台積電"))

    def test_tai_tai_variant_is_relevant(self):
        self.assertTrue(is_relevant_news_text("臺積電擴產帶動供應鏈", "2330", "台積電"))


if __name__ == "__main__":
    unittest.main()
