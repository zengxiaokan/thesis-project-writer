from pathlib import Path
import runpy
import unittest


exact_quote = runpy.run_path(str(Path(__file__).with_name("summarize.py")))["exact_quote"]


class RatingEvidenceTests(unittest.TestCase):
    def test_actual_short_quote_is_accepted(self):
        exact_quote("事务提交后发送通知", "正文：事务提交后发送通知，失败保留待处理记录。", "A01/D5")

    def test_missing_or_invented_quote_is_rejected(self):
        for quote in ("自动回滚已提交派工", "", None):
            with self.subTest(quote=quote):
                with self.assertRaises(ValueError):
                    exact_quote(quote, "事务提交后发送通知，失败保留待处理记录。", "A01/C2")
