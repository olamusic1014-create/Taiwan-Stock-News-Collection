import unittest

from ui_config import get_mobile_search_panel_config, resolve_active_api_key


class UiConfigTests(unittest.TestCase):
    def test_mobile_search_panel_hides_manual_api_key_input(self):
        config = get_mobile_search_panel_config()

        self.assertFalse(config.show_manual_api_key)
        self.assertEqual(config.button_label, "啟動分析")
        self.assertEqual(config.day_range_label, "抓取天數")
        self.assertIn("股票", config.title)

    def test_resolve_active_api_key_only_uses_system_key(self):
        self.assertEqual(resolve_active_api_key("secret-key"), "secret-key")
        self.assertIsNone(resolve_active_api_key(None))
        self.assertIsNone(resolve_active_api_key(""))


if __name__ == "__main__":
    unittest.main()
