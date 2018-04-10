import unittest
from unittest.mock import patch, MagicMock
import skydive_shell
from skydive_shell import gremlin_query_list_string
from skydive.rest.client import RESTClient


class TestCompletions(unittest.TestCase):

    def test_gremlin_completions(self):
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "g"),
            (0, ["."]))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "g.v("),
            (0, []))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "g.v"),
            (-1, ['v(']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "g.v().h"),
            (-1, ['has(']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "g.v().ha"),
            (-2, ['has(']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", "g.v().limit"),
            (0, ['(']))

    def test_gremlin_has_completions(self):
        with patch('skydive.rest.client.RESTClient.lookup',
                   MagicMock(return_value=['Name', 'Contrail'])):
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""), "g.v().has("),
                (0, ['"Contrail"', '"Name"']))
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""), 'g.v().has("Na'),
                (-3, ['"Name"']))

        mockedValues = ['tap01-aaaa', 'tap02-aaaa', 'tap02-bbbb', 'tap1-aaaa']
        exptectedValues = ['"tap01-aaaa"', '"tap02-aaaa"', '"tap02-bbbb"', '"tap1-aaaa"']
        with patch('skydive.rest.client.RESTClient.lookup',
                   return_value=mockedValues):
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""),
                                              'g.v().has("Name",'),
                (0, exptectedValues))
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""),
                                              'g.v().has("Name","tap0'),
                (-5, exptectedValues[0:3]))
            self.assertEqual(
                skydive_shell.get_completions(RESTClient(""),
                                              'g.v().has("Name","tap02'),
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

    def test_find_valid_gremlin_expr(self):
        self.assertEqual(
            skydive_shell.find_valid_gremlin_expr("capture create g.v().has("),
            ('g.v()', 'has('))
        self.assertEqual(
            skydive_shell.find_valid_gremlin_expr("g.v().ha"),
            ('g.v()', 'ha'))
        self.assertEqual(
            skydive_shell.find_valid_gremlin_expr("g.v().has("),
            ('g.v()', 'has('))


if __name__ == '__main__':
    unittest.main()
