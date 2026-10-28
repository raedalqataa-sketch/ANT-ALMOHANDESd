"""Structural integration tests: ensure guest safety gate stays opt-in and
survives V4 revalidation immediately before DXF/PDF export.
"""
import ast
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'backend/design/general_engine.py'


class TestGuestGeometryGateWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=SOURCE.read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source,filename=str(SOURCE))
        cls.fns={n.name:n for n in cls.tree.body if isinstance(n,ast.FunctionDef)}

    def test_generator_remains_default_off(self):
        node=self.fns['generate_general']
        i=[a.arg for a in node.args.kwonlyargs].index('assl_space_optimize')
        self.assertIsInstance(node.args.kw_defaults[i],ast.Constant)
        self.assertIs(node.args.kw_defaults[i].value,False)

    def test_no_unconditional_guest_qa_import(self):
        head=self.source.split('def generate_general(',1)[0]
        self.assertNotIn('from assl.guest_geometry_qa import generator_check',head)

    def test_guest_quality_check_after_candidate_validator(self):
        body=ast.get_source_segment(self.source,self.fns['generate_general'])
        self.assertIn('trial=candidate_validator(trial)',body)
        self.assertIn('guest_quality_check=generator_check(trial)',body)
        self.assertLess(body.index('trial=candidate_validator(trial)'),body.index('guest_quality_check=generator_check(trial)'))
        self.assertIn("trial['search']['assl_guest_audit_enabled']=True",body)

    def test_final_export_reruns_guest_check_after_v4(self):
        body=ast.get_source_segment(self.source,self.fns['export_general_model'])
        self.assertIn("model['checks']=validate_v4(model,brief)",body)
        self.assertIn('guest_quality_check=generator_check(model)',body)
        self.assertLess(body.index("model['checks']=validate_v4(model,brief)"),
                        body.index('guest_quality_check=generator_check(model)'))
        self.assertLess(body.index('guest_quality_check=generator_check(model)'),
                        body.index("if not model['release']['drawing_export_allowed']"))

    def test_failed_guest_checks_do_block_export(self):
        body=ast.get_source_segment(self.source,self.fns['export_general_model'])
        self.assertIn("if guest_quality_check['status']=='FAIL':",body)
        self.assertIn("model['release'].update(status='BLOCKED',drawing_export_allowed=False)",body)


if __name__=='__main__':
    unittest.main()
