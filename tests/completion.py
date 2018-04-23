import unittest
from unittest.mock import patch, MagicMock
import skydive_shell
from skydive.rest.client import RESTClient


class TestCompletions(unittest.TestCase):

    def test_gremlin_completions(self):
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "G"),
            (0, ["."]))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "G.V("),
            (0, []))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "G.V"),
            (-1, ['V(']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "G.V().H"),
            (-1, ['Has(']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "G.V().Ha"),
            (-2, ['Has(']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "G.V().Limit"),
            (0, ['(']))

    def test_gremlin_has_completions(self):
        with patch('skydive.rest.client.RESTClient.lookup',
                   MagicMock(return_value=['Name', 'Contrail'])):
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""), "G.V().Has("),
                (0, ['"Contrail"', '"Name"']))
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""), 'G.V().Has("Na'),
                (-3, ['"Name"']))

        mockedValues = ['tap01-aaaa', 'tap02-aaaa', 'tap02-bbbb', 'tap1-aaaa']
        exptectedValues = ['"tap01-aaaa"', '"tap02-aaaa"', '"tap02-bbbb"', '"tap1-aaaa"']
        with patch('skydive.rest.client.RESTClient.lookup',
                   return_value=mockedValues):
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""),
                                              'G.V().Has("Name",'),
                (0, exptectedValues))
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""),
                                              'G.V().Has("Name","tap0'),
                (-5, exptectedValues[0:3]))
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""),
                                              'G.V().Has("Name","tap02'),
                (-6, exptectedValues[1:3]))

    def test_capture_completions(self):
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "cap"),
            (-3, ["capture"]))

    def test_set_completions(self):
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "set "),
            (0, ['format']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "set format "),
            (0, ['json', 'pretty']))


class TestFindValidGremlinExpr(unittest.TestCase):
    def test_capture_create(self):
        self.assertEqual(
            skydive_shell.find_valid_gremlin_expr("capture create G.V().Has("),
            ('G.V()', 'Has('))

    def test_capture_gremlin(self):
        self.assertEqual(
            skydive_shell.find_valid_gremlin_expr("G.V().Ha"),
            ('G.V()', 'Ha'))
        self.assertEqual(
            skydive_shell.find_valid_gremlin_expr("G.V().Has("),
            ('G.V()', 'Has('))


if __name__ == '__main__':
    unittest.main()
