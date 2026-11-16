"""Q2 BUILD 测试：正常输入、异常输入、空数据、字段校验。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
START = "20220101"
END = "20221231"


def load_fixture() -> dict:
    return {
        "daily": pd.read_parquet(FIXTURES / "daily.parquet"),
        "contracts": pd.read_parquet(FIXTURES / "contracts.parquet"),
        "dominant": pd.read_parquet(FIXTURES / "dominant.parquet"),
    }


class ValidateInputTest(unittest.TestCase):
    def test_none_is_allowed(self):
        build.validate_input(None)

    def test_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            build.validate_input([1, 2, 3])

    def test_rejects_unknown_key(self):
        with self.assertRaises(ValueError):
            build.validate_input({"daily": pd.DataFrame(), "foo": pd.DataFrame()})

    def test_rejects_empty_frame(self):
        with self.assertRaises(ValueError):
            build.validate_input({"daily": pd.DataFrame()})

    def test_rejects_missing_columns(self):
        frames = load_fixture()
        frames["daily"] = frames["daily"].drop(columns=["open_interest"])
        with self.assertRaises(ValueError):
            build.validate_input(frames)


class ConfigTest(unittest.TestCase):
    def test_rejects_bad_date(self):
        with self.assertRaises(ValueError):
            build.run(None, {"start_date": "2022-01-01"})

    def test_rejects_unknown_rule(self):
        with self.assertRaises(ValueError):
            build.run(None, {"rules": ["vwap"]})

    def test_rejects_unknown_config_key(self):
        with self.assertRaises(ValueError):
            build.run(None, {"foo": 1})


class RunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = load_fixture()
        cls.result = build.run(cls.frames, {
            "start_date": START,
            "end_date": END,
            "rules": ["fixed"],
            "products": ["RB", "HC"],
            "output_dir": None,
        })

    def test_metrics_shape(self):
        metrics = self.result["metrics"]
        self.assertEqual(len(metrics), 1)
        row = metrics[0]
        for key in ("rule", "annual_return", "annual_vol", "sharpe",
                    "max_drawdown", "roll_count", "trade_count", "turnover_x"):
            self.assertIn(key, row)
        self.assertEqual(row["rule"], "fixed")

    def test_signal_domain(self):
        self.assertTrue(set(self.result["signals"]["signal"].unique()) <= {-1, 0, 1})

    def test_curve_not_empty(self):
        curve = self.result["daily"]["fixed"]
        self.assertGreater(len(curve), 100)
        self.assertTrue(curve["equity"].notna().all())

    def test_production_schema(self):
        frame = build.to_production(self.result)
        self.assertEqual(len(frame), 1)
        expected = {"trade_date", "build_id", "build_name", "target_id",
                    "result_type", "result_value", "result_json",
                    "data_version", "update_time"}
        self.assertEqual(set(frame.columns), expected)
        self.assertEqual(frame.iloc[0]["build_id"], "Q2")
        import json
        json.loads(frame.iloc[0]["result_json"])

    def test_deterministic(self):
        again = build.run(self.frames, {
            "start_date": START, "end_date": END,
            "rules": ["fixed"], "products": ["RB", "HC"],
        })
        self.assertEqual(self.result["metrics"][0], again["metrics"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
