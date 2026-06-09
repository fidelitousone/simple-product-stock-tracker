import json
import os
import tempfile
import unittest
from unittest import mock

import check_stock

FIXTURES = os.path.join(os.path.dirname(__file__), "tests", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


class ParseStockFixtureTests(unittest.TestCase):
    """parse_stock against real captured Store API payloads."""

    def test_in_stock_fixture(self):
        self.assertIs(check_stock.parse_stock(load_fixture("in_stock.json")), True)

    def test_out_of_stock_fixture(self):
        self.assertIs(check_stock.parse_stock(load_fixture("out_of_stock.json")), False)


class ParseStockEdgeCaseTests(unittest.TestCase):
    """The 'unknown' invariant: anything ambiguous must resolve to None."""

    def test_plain_dict_true(self):
        self.assertIs(check_stock.parse_stock({"is_in_stock": True}), True)

    def test_plain_dict_false(self):
        self.assertIs(check_stock.parse_stock({"is_in_stock": False}), False)

    def test_list_wrapped(self):
        self.assertIs(check_stock.parse_stock([{"is_in_stock": True}]), True)

    def test_empty_list_is_unknown(self):
        self.assertIsNone(check_stock.parse_stock([]))

    def test_missing_key_is_unknown(self):
        self.assertIsNone(check_stock.parse_stock({}))

    def test_non_dict_is_unknown(self):
        self.assertIsNone(check_stock.parse_stock("x"))
        self.assertIsNone(check_stock.parse_stock(None))

    def test_truthiness_coercion(self):
        self.assertIs(check_stock.parse_stock({"is_in_stock": 1}), True)
        self.assertIs(check_stock.parse_stock({"is_in_stock": 0}), False)


class ShouldNotifyTests(unittest.TestCase):
    """Rising-edge rule: alert only when newly in stock."""

    def test_first_ever_in_stock(self):
        self.assertTrue(check_stock.should_notify(True, None))

    def test_rising_edge_from_out_of_stock(self):
        self.assertTrue(check_stock.should_notify(True, False))

    def test_already_in_stock_no_repeat(self):
        self.assertFalse(check_stock.should_notify(True, True))

    def test_out_of_stock_never_alerts(self):
        self.assertFalse(check_stock.should_notify(False, None))
        self.assertFalse(check_stock.should_notify(False, False))
        self.assertFalse(check_stock.should_notify(False, True))


class StateRoundTripTests(unittest.TestCase):
    """save_state then load_previous should return what was written."""

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            with mock.patch.object(check_stock, "STATE_FILE", path):
                check_stock.save_state(True)
                self.assertIs(check_stock.load_previous(), True)
                check_stock.save_state(False)
                self.assertIs(check_stock.load_previous(), False)

    def test_missing_file_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "does_not_exist.json")
            with mock.patch.object(check_stock, "STATE_FILE", path):
                self.assertIsNone(check_stock.load_previous())


if __name__ == "__main__":
    unittest.main()
