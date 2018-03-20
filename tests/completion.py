import unittest
import skydive_shell


class TestCompletions(unittest.TestCase):

    def test_completions(self):
        self.assertEqual(
            skydive_shell.skydive_get_completions("localhost:8182", "g"),
            (0, ["."]))
        self.assertEqual(
            skydive_shell.skydive_get_completions("localhost:8182", "g.v("),
            (0, []))
        self.assertEqual(
            skydive_shell.skydive_get_completions("localhost:8182", "g.v"),
            (-1, ['v(']))

if __name__ == '__main__':
    unittest.main()
