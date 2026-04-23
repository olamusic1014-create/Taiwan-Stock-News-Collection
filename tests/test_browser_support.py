import unittest

from browser_support import BrowserStatus, detect_browser_status, get_launch_kwargs


class BrowserSupportTests(unittest.TestCase):
    def test_detect_browser_status_prefers_explicit_executable(self):
        env = {"PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH": "/custom/chromium"}

        status = detect_browser_status(
            env=env,
            path_exists=lambda path: path == "/custom/chromium",
            home="/home/tester",
        )

        self.assertTrue(status.available)
        self.assertEqual(status.executable_path, "/custom/chromium")
        self.assertIn("configured Chromium executable", status.message)

    def test_detect_browser_status_accepts_playwright_cache_without_explicit_path(self):
        status = detect_browser_status(
            env={},
            path_exists=lambda path: path == "/home/tester/.cache/ms-playwright",
            home="/home/tester",
        )

        self.assertTrue(status.available)
        self.assertIsNone(status.executable_path)
        self.assertIn("Playwright browser cache", status.message)

    def test_detect_browser_status_reports_missing_runtime(self):
        status = detect_browser_status(
            env={},
            path_exists=lambda path: False,
            home="/home/tester",
        )

        self.assertFalse(status.available)
        self.assertIsNone(status.executable_path)
        self.assertIn("No Chromium runtime detected", status.message)

    def test_get_launch_kwargs_uses_explicit_executable_when_present(self):
        status = BrowserStatus(
            available=True,
            executable_path="/custom/chromium",
            source="env",
            message="ok",
        )

        self.assertEqual(
            get_launch_kwargs(status),
            {"headless": True, "executable_path": "/custom/chromium"},
        )


if __name__ == "__main__":
    unittest.main()
