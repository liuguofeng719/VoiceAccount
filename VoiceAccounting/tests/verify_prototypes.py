import os
import re
import unittest

REQUIRED_FILES = [
    "index.html",
    "accounting.html",
    "stats.html",
    "history.html",
    "settings.html",
]


class SmokeTests(unittest.TestCase):
    def test_files_exist(self):
        for path in REQUIRED_FILES:
            self.assertTrue(os.path.exists(path), f"missing file: {path}")


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class UnitTests(unittest.TestCase):
    def test_tailwind_and_icons_included(self):
        for path in REQUIRED_FILES:
            html = read(path)
            self.assertIn("tailwindcss", html)
            self.assertIn("font-awesome", html)

    def test_device_marker_present(self):
        for path in REQUIRED_FILES:
            html = read(path)
            self.assertIn('data-device="iphone-15-pro"', html)


class FunctionalTests(unittest.TestCase):
    def test_accounting_page(self):
        html = read("accounting.html")
        self.assertIn("本月支出", html)
        self.assertIn("语音输入", html)
        self.assertIn("手动输入", html)
        self.assertIn("今日记录", html)
        self.assertRegex(html, r"金额")
        self.assertRegex(html, r"标题")
        self.assertRegex(html, r"时间")
        self.assertRegex(html, r"分类")

    def test_stats_page(self):
        html = read("stats.html")
        self.assertIn("统计", html)
        self.assertIn("月", html)
        self.assertIn("季度", html)
        self.assertIn("年", html)
        self.assertIn("趋势", html)
        self.assertIn("分布", html)

    def test_history_page(self):
        html = read("history.html")
        self.assertIn("历史", html)
        self.assertIn("按天", html)

    def test_settings_page(self):
        html = read("settings.html")
        self.assertIn("设置", html)
        self.assertIn("货币单位", html)
        self.assertIn("分类管理", html)
        self.assertIn("导出CSV", html)
        self.assertIn("清空所有数据", html)


if __name__ == "__main__":
    unittest.main()
