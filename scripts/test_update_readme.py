#!/usr/bin/env python3
"""Tests for the README updater helpers."""
import importlib
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

README = """# 阿里云数据库内核月报分类整理

# MySQL
| 分类 | 标题  |
|---|---|
| 参数故事 | [timed_mutexes](http://mysql.taobao.org/monthly/2014/08/01/) |

# PostgreSQL
| 分类 | 标题  |
|---|---|
| 特性分析 | [Replication Slot](http://mysql.taobao.org/monthly/2015/02/03/) |
"""


class TimeoutTest(unittest.TestCase):
    def test_timeout_is_configurable(self):
        os.environ["MONTHLY_TIMEOUT"] = "2.5"
        try:
            module = importlib.reload(importlib.import_module("update_readme"))
        finally:
            del os.environ["MONTHLY_TIMEOUT"]
        self.assertEqual(module.TIMEOUT, 2.5)

    def test_default_timeout(self):
        os.environ.pop("MONTHLY_TIMEOUT", None)
        module = importlib.reload(importlib.import_module("update_readme"))
        self.assertEqual(module.TIMEOUT, 10)


class CoveredMonthsTest(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("update_readme")

    def test_reads_months_from_article_links(self):
        self.assertEqual(
            self.module.covered_months(README),
            {(2014, 8), (2015, 2)},
        )

    def test_ignores_the_scheme(self):
        content = "| [a](https://mysql.taobao.org/monthly/2024/11/01/) |"
        self.assertEqual(self.module.covered_months(content), {(2024, 11)})

    def test_does_not_confuse_short_months(self):
        content = "| [a](http://mysql.taobao.org/monthly/2024/01/01/) |"
        self.assertEqual(self.module.covered_months(content), {(2024, 1)})
        self.assertNotIn((2024, 1), self.module.covered_months(
            "| [a](http://mysql.taobao.org/monthly/2024/11/01/) |"
        ))

    def test_extracts_article_urls_once(self):
        links = self.module.existing_articles(README)
        self.assertIn("http://mysql.taobao.org/monthly/2014/08/01/", links)
        self.assertEqual(len(links), 2)


class InsertRowsTest(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("update_readme")

    def test_inserts_rows_under_the_matching_category(self):
        rows = ["| 参数故事 | [new](http://mysql.taobao.org/monthly/2024/11/01/) |"]
        updated = self.module.insert_rows(README, "MySQL", rows)
        self.assertIn("timed_mutexes", updated)
        self.assertIn("2024/11/01/", updated)
        # The row belongs to the MySQL table, not to the PostgreSQL one.
        mysql, _, postgresql = updated.partition("# PostgreSQL")
        self.assertIn("2024/11/01/", mysql)
        self.assertNotIn("2024/11/01/", postgresql)

    def test_ignores_unknown_categories(self):
        updated = self.module.insert_rows(README, "Redis", ["| x | [y](z) |"])
        self.assertEqual(updated, README)

    def test_repeated_header_only_receives_rows_once(self):
        content = README + "\n# Redis\n| 分类 | 标题  |\n|---|---|\n"
        rows = ["| 参数故事 | [new](http://mysql.taobao.org/monthly/2024/11/01/) |"]
        updated = self.module.insert_rows(content, "MySQL", rows)
        self.assertEqual(updated.count("2024/11/01/"), 1)


if __name__ == "__main__":
    unittest.main()
