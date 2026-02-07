# VoiceAccounting Prototype Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 输出语音记账 iOS 应用的 UX/UI 说明与 HTML+Tailwind 原型文件（含 index.html iframe 入口）

**Architecture:** 采用每页独立 HTML 文件（accounting/stats/history/settings），统一 iPhone 15 Pro 尺寸容器样式；入口 index.html 使用 iframe 平铺展示。

**Tech Stack:** HTML, Tailwind CSS (CDN), FontAwesome (CDN), Python (验证脚本)

---

### Task 1: 测试骨架（TDD - RED）

**Files:**
- Create: `tests/verify_prototypes.py`

**Step 1: Write the failing test**

```python
import os
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

if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 tests/verify_prototypes.py`
Expected: FAIL with "missing file"

---

### Task 2: 完整测试集（TDD - RED）

**Files:**
- Modify: `tests/verify_prototypes.py`

**Step 1: Write the failing tests**

```python
import re

def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

class UnitTests(unittest.TestCase):
    def test_tailwind_included(self):
        for path in REQUIRED_FILES:
            html = read(path)
            self.assertIn("tailwindcss", html)

class FunctionalTests(unittest.TestCase):
    def test_accounting_page(self):
        html = read("accounting.html")
        self.assertIn("语音输入", html)
        self.assertIn("手动输入", html)
        self.assertRegex(html, r"本月支出")
```

**Step 2: Run test to verify it fails**

Run: `python3 tests/verify_prototypes.py`
Expected: FAIL (files missing / strings not found)

---

### Task 3: index.html 入口页面

**Files:**
- Create: `index.html`

**Step 1: Write minimal implementation**
实现 iframe 平铺展示 4 个页面，包含说明与设备外观框。

**Step 2: Run tests**

Run: `python3 tests/verify_prototypes.py`
Expected: FAIL（其他页面未实现）

---

### Task 4: 记账页面（accounting.html）

**Files:**
- Create: `accounting.html`

**Step 1: Write minimal implementation**
包含本月支出、语音/手动输入按钮、今日记录列表与手动输入弹窗。

**Step 2: Run tests**

Run: `python3 tests/verify_prototypes.py`
Expected: FAIL（其他页面未实现）

---

### Task 5: 统计页面（stats.html）

**Files:**
- Create: `stats.html`

**Step 1: Write minimal implementation**
包含月/季度/年切换与趋势/分布柱状图。

**Step 2: Run tests**

Run: `python3 tests/verify_prototypes.py`
Expected: FAIL（其他页面未实现）

---

### Task 6: 历史页面（history.html）

**Files:**
- Create: `history.html`

**Step 1: Write minimal implementation**
按天分组显示历史记录。

**Step 2: Run tests**

Run: `python3 tests/verify_prototypes.py`
Expected: FAIL（其他页面未实现）

---

### Task 7: 设置页面（settings.html）

**Files:**
- Create: `settings.html`

**Step 1: Write minimal implementation**
货币单位选择、分类管理、数据管理（导出/清空）。

**Step 2: Run tests**

Run: `python3 tests/verify_prototypes.py`
Expected: PASS

---

### Task 8: 验证与收尾

**Files:**
- Update: `progress.md`
- Create: `verification.md`

**Step 1: Run tests**

Run: `python3 tests/verify_prototypes.py`
Expected: PASS

**Step 2: 记录测试结果与风险**

记录命令输出与验证结论。

