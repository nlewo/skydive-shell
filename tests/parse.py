import unittest
import skydive_shell

from lark.reconstruct import Reconstructor


class TestParser(unittest.TestCase):

    def test_capture_delete(self):
        skydive_shell.larkParser.parse(
            "capture delete 59e1d836-81b2-4781-46a5-1a423c6486e5")

    def test_capture_list(self):
        skydive_shell.larkParser.parse(
            "capture list")


class TestReconstructor(unittest.TestCase):

    def test_reconstructor(self):
        for expr in ['G.V()',
                     'G.V().Has("Name").Has("Driver").Limit(1)',
                     'G.V().Has("Name").Has("Driver")',
                     'capture create G.V().Has("Name").Has("Driver")',
                     'G.V().Has("Name")']:
            self.assertEqual(expr, self._deconstruct_reconstruct(expr))

    def test_capture_list(self):
        expr = 'capture list'
        self.assertEqual(expr, self._deconstruct_reconstruct(expr))

    def _deconstruct_reconstruct(self, expr):
        tree = skydive_shell.larkParser.parse(expr)
        return Reconstructor(
            skydive_shell.larkParser).reconstruct(tree)


if __name__ == '__main__':
    unittest.main()
