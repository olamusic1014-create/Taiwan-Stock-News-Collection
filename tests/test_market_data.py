import unittest

from market_data import merge_market_scan_data


class MarketDataTests(unittest.TestCase):
    def test_merge_market_scan_data_adds_missing_stock_codes(self):
        merged = merge_market_scan_data(
            {"台積電": "2330"},
            {
                "data": [
                    {"d": ["2337", "旺宏", 1000]},
                    {"d": ["3711", "日月光 KY", 900]},
                ]
            },
        )

        self.assertEqual(merged["台積電"], "2330")
        self.assertEqual(merged["旺宏"], "2337")
        self.assertEqual(merged["日月光"], "3711")

    def test_merge_market_scan_data_ignores_incomplete_rows(self):
        merged = merge_market_scan_data(
            {"台積電": "2330"},
            {"data": [{"d": ["2337"]}, {"d": []}]},
        )

        self.assertEqual(merged, {"台積電": "2330"})


if __name__ == "__main__":
    unittest.main()
