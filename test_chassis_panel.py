import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest
from chassis_values import aero_summary
from parameter_model import ParameterModel
from test_parameter_model import binary_helpers


class ChassisTests(unittest.TestCase):
    def test_stock_aero_and_changes(self):
        stock = aero_summary(33000, 255, 43691, 33000, 255)
        self.assertEqual(stock['relative_drag'], 100)
        self.assertEqual(stock['relative_downforce'], 100)
        self.assertAlmostEqual(stock['rear_percent'], 66.6667, places=3)
        self.assertAlmostEqual(stock['front_percent'] + stock['rear_percent'], 100)
        edited = aero_summary(16500, 510, 32768, 33000, 255)
        self.assertEqual(edited['relative_drag'], 50)
        self.assertEqual(edited['relative_downforce'], 100)
        self.assertEqual(edited['rear_percent'], 50)

    def setUp(self):
        root = Path(__file__).parent
        tree = ast.parse((root / 'chassis_panel.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and
                   n.name in {'parameter_id', 'edit_value', 'edit_slider'}]
        scope = {}
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'chassis bindings', 'exec'), scope)
        Panel = type('Panel', (), {k: v for k, v in scope.items() if callable(v)})
        self.panel = panel = Panel()
        panel.FIELDS = [('weight', '', 1, 0), ('drag', '', 65536, 5),
                        ('ratio', '', 100, 2), ('rear', '', 655.36, 4)]
        groups = binary_helpers()['load_parameters_by_category'](root / 'parameters.csv')
        params = [p for name, ps in groups.items() if name.startswith('Chassis parameters') for p in ps]
        panel.model = ParameterModel()
        panel.model.load(params, {p['Parameter ID']: int(p['Default value']) for p in params})
        self.mode = 'road_course'
        self.name = 'Lola'
        panel.mode = SimpleNamespace(currentData=lambda: self.mode)
        panel.chassis = SimpleNamespace(currentText=lambda: self.name)
        panel.refresh = MagicMock()
        panel.slider_max = {'drag': 65535, 'rear': 65535}

    def test_mode_routes_edits_without_overwriting_other_preset(self):
        panel = self.panel
        panel.edit_value('drag', .5)
        self.assertEqual(panel.model.get_value('chassis.lola.road_course_body_drag_coefficient'), 32768)
        self.mode = 'speedway'
        panel.edit_value('ratio', 3.25)
        self.assertEqual(panel.model.get_value('chassis.lola.speedway_body_downforce_to_drag_ratio'), 325)
        self.assertEqual(panel.model.get_value('chassis.lola.road_course_body_downforce_to_drag_ratio'), 255)
        self.assertEqual(panel.model.get_value('chassis.lola.speedway_body_drag_coefficient'), 28000)
        self.assertEqual(panel.model.get_value('chassis.lola.road_course_body_drag_coefficient'), 32768)

    def test_shared_distribution_and_chassis_selection(self):
        panel = self.panel
        panel.edit_value('rear', 50)
        self.assertEqual(panel.model.get_value('chassis.lola.body_downforce_rear_distribution'), 32768)
        self.mode = 'speedway'
        self.assertEqual(panel.parameter_id('rear'), 'chassis.lola.body_downforce_rear_distribution')
        self.name = 'Penske'
        panel.edit_value('weight', 8000)
        self.assertEqual(panel.model.get_value('chassis.penske.base_chassis_weight'), 8000)
        self.assertEqual(panel.model.get_value('chassis.lola.base_chassis_weight'), 7500)

    def test_slider_reaches_valid_uint16_limit(self):
        self.panel.edit_slider('drag', 1000)
        self.assertEqual(self.panel.model.get_value('chassis.lola.road_course_body_drag_coefficient'), 65535)


if __name__ == '__main__':
    unittest.main()
