import unittest
import skydive_shell

from lark.reconstruct import Reconstructor


class TestParser(unittest.TestCase):

    def test_capture_delete(self):
        skydive_shell.larkParser.parse(
            "capture delete 59e1d836-81b2-4781-46a5-1a423c6486e5")


class TestReconstructor(unittest.TestCase):

    def test_reconstructor(self):
        for expr in ['g.v()',
                     'g.v().has("Name").has("Driver").limit(1)',
                     'g.v().has("Name").has("Driver")',
                     'capture create g.v().has("Name").has("Driver")',
                     'g.v().has("Name")']:

            tree = skydive_shell.larkParser.parse(expr)
            new_expr = Reconstructor(
                skydive_shell.larkParser).reconstruct(tree)
            self.assertEqual(expr, new_expr)


if __name__ == '__main__':
    unittest.main()
