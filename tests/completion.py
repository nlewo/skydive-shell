import unittest
import skydive_shell


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

    def test_set_completions(self):
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", ":set "),
            (0, ['format']))
        self.assertEqual(
            skydive_shell.get_completions("localhost:8182", ":set format "),
            (0, ['json', 'pretty']))

    def test_find_valid_expr(self):
        self.assertEqual(
            skydive_shell.find_valid_expr("capture create g.v().has("),
            ('g.v()', 'has('))
        self.assertEqual(
            skydive_shell.find_valid_expr("g.v().has("),
            ('g.v()', 'has('))


if __name__ == '__main__':
    unittest.main()
