"""Static opt-in integration gate: no generator imports or third-party deps."""
import ast
import unittest
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1] / "backend/design/general_engine.py"

class TestASSLGeneratorIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=SOURCE.read_text(encoding="utf-8")
        cls.tree=ast.parse(cls.source,filename=str(SOURCE))
        cls.functions={x.name:x for x in cls.tree.body
                       if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}

    def test_search_flag_is_optional_and_off_by_default(self):
        fn=self.functions["search"]
        names=[x.arg for x in fn.args.kwonlyargs]
        self.assertIn("assl_space_optimize",names)
        default=fn.args.kw_defaults[names.index("assl_space_optimize")]
        self.assertIsInstance(default,ast.Constant)
        self.assertIs(default.value,False)

    def test_generate_flag_is_optional_and_off_by_default(self):
        fn=self.functions["generate_general"]
        names=[x.arg for x in fn.args.kwonlyargs]
        self.assertIn("assl_space_optimize",names)
        default=fn.args.kw_defaults[names.index("assl_space_optimize")]
        self.assertIsInstance(default,ast.Constant)
        self.assertIs(default.value,False)

    def test_search_calls_forward_explicit_flag(self):
        fn=self.functions["generate_general"]
        calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Name) and n.func.id=="search"]
        self.assertGreater(len(calls),0)
        for call in calls:
            self.assertIn("assl_space_optimize",[k.arg for k in call.keywords])

    def test_generator_has_no_default_assl_import(self):
        self.assertTrue(any(
            isinstance(n,ast.If) and
            isinstance(n.test,ast.Name) and n.test.id=="assl_space_optimize"
            for n in ast.walk(self.functions["search"])))
        self.assertNotIn("from assl.space_optimizer import score_layout\n",self.source.split("def search(",1)[0])

if __name__=="__main__":
    unittest.main()
