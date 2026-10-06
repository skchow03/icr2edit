"""Headless integration checks for panel bindings; rendering needs Qt locally."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest
from parameter_model import ParameterModel
from test_parameter_model import binary_helpers


class Control:
    def __init__(self):
        self.current = 0
        self.blocked = False
        self.enabled = True
        self.callback = None
        self.maximum = 0

    def setValue(self, value):
        changed = value != self.current
        self.current = value
        if changed and not self.blocked and self.callback:
            self.callback(value)

    def value(self):
        return self.current

    def blockSignals(self, blocked):
        self.blocked = blocked

    def setEnabled(self, enabled):
        self.enabled = enabled

    def isEnabled(self):
        return self.enabled

    def setMaximum(self, maximum):
        self.maximum = maximum

    def setSingleStep(self, value):
        self.step = value

    def setStyleSheet(self, value):
        self.style = value

    def setToolTip(self, value):
        self.tooltip = value


class EnginePanelTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent
        tree = ast.parse((root / 'torque_graph.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and
                   n.name in {'parameter_id', 'edit_value', 'edit_slider', 'refresh', 'on_model_change', 'reset_defaults'}]
        scope = {}
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'engine bindings', 'exec'), scope)
        Panel = type('Panel', (), {k: v for k, v in scope.items() if callable(v)})
        self.panel = panel = Panel()
        fields = ['torque_coefficient_1', 'torque_coefficient_2', 'torque_adjustment',
                  'rpm_upshift_point', 'rpm_downshift_point', 'rpm_limit',
                  'fuel_consumption_rate', 'durability_coefficient']
        groups = binary_helpers()['load_parameters_by_category'](root / 'parameters.csv')
        params = [p for name, ps in groups.items() if name.startswith('Engine parameters') for p in ps]
        panel.model = ParameterModel()
        panel.model.load(params, {p['Parameter ID']: int(p['Default value']) for p in params})
        self.name = 'Ford'
        panel.engine = SimpleNamespace(currentText=lambda: self.name, count=lambda: 3, setEnabled=lambda _: None)
        panel.FIELDS = [(f, f) for f in fields]
        panel.reset_button = Control()
        panel.inputs = {f: Control() for f in fields}
        panel.sliders = {f: Control() for f in fields}
        panel.slider_ranges = {}
        panel.figure = MagicMock()
        panel.canvas = MagicMock()
        panel.coord_label = MagicMock()
        panel.plot_timer = MagicMock()
        for f in fields:
            panel.inputs[f].callback = lambda value, field=f: panel.edit_value(field, value)
            panel.sliders[f].callback = lambda value, field=f: panel.edit_slider(field, value)
        panel.model.subscribe(panel.on_model_change)
        panel.refresh()

    def test_reset_restores_all_engines_and_preserves_other_edits(self):
        panel = self.panel
        extra = {'Parameter ID': 'other.value', 'Data type': 'UInt16', 'Length': '2', 'Default value': '10'}
        panel.model.parameters['other.value'] = extra
        panel.model.values['other.value'] = panel.model.original['other.value'] = 10
        panel.model.set_value('other.value', 20)
        panel.model.set_value('engine.ford.torque_coefficient_1', 1500)
        panel.model.set_value('engine.honda.rpm_limit', 7000)
        panel.reset_defaults()
        self.assertEqual(panel.model.get_value('engine.ford.torque_coefficient_1'), 1290)
        self.assertEqual(panel.model.get_value('engine.honda.rpm_limit'), 6750)
        self.assertEqual(panel.model.get_value('other.value'), 20)
        self.assertEqual(panel.inputs['torque_coefficient_1'].value(), 1290)

    def test_slider_edit_updates_shared_model(self):
        panel = self.panel
        panel.sliders['torque_coefficient_1'].setValue(750)
        self.assertEqual(panel.model.get_value('engine.ford.torque_coefficient_1'), 1935)
        self.assertEqual(panel.inputs['torque_coefficient_1'].value(), 1935)
        self.assertIn('engine.ford.torque_coefficient_1', panel.model.dirty)

    def test_advanced_edit_and_revert_update_engine_controls(self):
        panel = self.panel
        panel.model.set_value('engine.ford.torque_coefficient_1', 1400)
        self.assertEqual(panel.inputs['torque_coefficient_1'].value(), 1400)
        panel.model.revert()
        self.assertEqual(panel.inputs['torque_coefficient_1'].value(), 1290)
        self.assertFalse(panel.model.dirty)

    def test_engine_switch_and_rpm_conversion(self):
        panel = self.panel
        self.name = 'Honda'
        panel.refresh()
        self.assertEqual(panel.inputs['torque_coefficient_1'].value(), 1180)
        panel.inputs['rpm_limit'].setValue(14001)
        self.assertEqual(panel.model.get_value('engine.honda.rpm_limit'), 7000)
        self.assertEqual(panel.inputs['rpm_limit'].value(), 14000)
        self.assertEqual(panel.model.get_value('engine.ford.rpm_limit'), 6500)

    def test_uint32_range_and_missing_optional_parameter(self):
        panel = self.panel
        self.assertEqual(panel.inputs['torque_adjustment'].maximum, 4294967295)
        panel.inputs['torque_adjustment'].setValue(3000000000)
        self.assertEqual(panel.model.get_value('engine.ford.torque_adjustment'), 3000000000)
        pid = 'engine.ford.durability_coefficient'
        del panel.model.parameters[pid]
        panel.refresh()
        self.assertFalse(panel.inputs['durability_coefficient'].isEnabled())
        self.assertFalse(panel.sliders['durability_coefficient'].isEnabled())


if __name__ == '__main__':
    unittest.main()
