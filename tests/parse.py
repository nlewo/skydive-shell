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
        for expr in ['g.v()',
                     'g.v().has("Name").has("Driver").limit(1)',
                     'g.v().has("Name").has("Driver")',
                     'capture create g.v().has("Name").has("Driver")',
                     'g.v().has("Name")']:
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
