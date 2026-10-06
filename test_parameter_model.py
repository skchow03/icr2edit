import ast
import csv
from pathlib import Path
import tempfile
import unittest
from parameter_model import ParameterModel
from fixed_point import *
import struct

ROOT = Path(__file__).parent


def binary_helpers():
    # Exercise the editor's actual binary codec without importing its Qt GUI.
    tree = ast.parse((ROOT / 'icr2edit.py').read_text())
    names = {'is_fixed_16_16', 'read_value_from_exe', 'write_value_to_exe',
             'load_initial_values', 'filter_parameters', 'load_parameters_by_category'}
    module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
    scope = dict(globals(), FIXED_16_16_TYPES={'16.16', 'fixed16.16', 'fixed16_16'},
                 ADDRESS_KEYS={'dos102': 'DOS address', 'windy101': 'Windy address'})
    exec(compile(module, str(ROOT / 'icr2edit.py'), 'exec'), scope)
    return scope


class ParameterModelTests(unittest.TestCase):
    def setUp(self):
        self.params = [dict({'Parameter ID': 'engine.ford.torque_coefficient_1', 'Length': '2',
                            'Data type': 'UInt16', 'DOS address': '4', 'Windy address': '8'}),
                       {'Parameter ID': 'engine.condition', 'Length': '4', 'Data type': 'Fixed16.16'}]
        self.model = ParameterModel()
        self.model.load(self.params, {'engine.ford.torque_coefficient_1': 1290, 'engine.condition': 150.0})

    def test_change_notification_and_revert(self):
        events = []
        self.model.subscribe(events.append)
        pid = self.params[0]['Parameter ID']
        self.model.set_value(pid, 1300)
        self.assertEqual(self.model.dirty, {pid})
        self.assertEqual(events, [pid])
        self.model.revert()
        self.assertEqual(self.model.get_value(pid), 1290)
        self.assertFalse(self.model.dirty)

    def test_preserves_other_staged_values(self):
        self.model.set_value('engine.condition', 149)
        self.model.set_value(self.params[0]['Parameter ID'], 1400)
        self.assertEqual(self.model.get_value('engine.condition'), 149)
        self.assertEqual(len(self.model.dirty), 2)

    def test_return_to_original_clears_dirty(self):
        pid = self.params[0]['Parameter ID']
        self.model.set_value(pid, 1400)
        self.model.set_value(pid, 1290)
        self.assertFalse(self.model.dirty)

    def test_storage_validation(self):
        pid = self.params[0]['Parameter ID']
        for invalid in (-1, 65536, 1.5, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.model.set_value(pid, invalid)
        self.assertEqual(self.model.get_value(pid), 1290)

    def test_fixed_point_quantization(self):
        self.model.set_value('engine.condition', 150.123456)
        self.assertEqual(self.model.get_value('engine.condition'), decode_fixed_16_16(encode_fixed_16_16(150.123456)))

    def test_save_and_unsubscribe(self):
        events = []
        callback = events.append
        self.model.subscribe(callback)
        self.model.set_value('engine.condition', 149)
        self.model.mark_saved()
        self.assertFalse(self.model.dirty)
        self.model.unsubscribe(callback)
        self.model.set_value('engine.condition', 148)
        self.assertEqual(len(events), 2)

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            self.model.load([self.params[0], self.params[0]], self.model.values)

    def test_registry_survives_reordering_and_label_changes(self):
        pid = self.params[0]['Parameter ID']
        self.params[0]['Description'] = 'Renamed'
        self.model.load(list(reversed(self.params)), self.model.values)
        self.assertEqual(self.model.get_value(pid), 1290)

    def test_binary_roundtrip_across_versions(self):
        helper = binary_helpers()
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'\0' * 16); f.flush()
            param = self.params[0]
            helper['write_value_to_exe'](f.name, '4', 2, 1290, 'UInt16')
            helper['write_value_to_exe'](f.name, '8', 2, 1236, 'UInt16')
            for version, expected in [('dos102', 1290), ('windy101', 1236)]:
                values = helper['load_initial_values']([param], f.name, version)
                self.assertEqual(values, {param['Parameter ID']: expected})
                self.model.load([param], values)
                self.model.set_value(param['Parameter ID'], 1400)
                address = helper['ADDRESS_KEYS'][version]
                helper['write_value_to_exe'](f.name, param[address], 2, self.model.get_value(param['Parameter ID']), 'UInt16')
                self.assertEqual(helper['load_initial_values']([param], f.name, version)[param['Parameter ID']], 1400)
            self.assertEqual(Path(f.name).read_bytes()[:4], b'\0' * 4)

    def test_actual_csv_column_mapping(self):
        helper = binary_helpers()
        groups = helper['load_parameters_by_category'](ROOT / 'parameters.csv')
        ford = {p['Parameter ID']: p for p in groups['Engine parameters Ford']}
        coefficient = ford['engine.ford.torque_coefficient_1']
        self.assertEqual(coefficient['DOS address'], 'F9CE4')
        self.assertEqual(coefficient['Windy address'], 'DD32C')
        self.assertEqual(coefficient['Rendition address'], '115414')
        self.assertEqual(coefficient['Length'], '2')
        self.assertEqual(coefficient['Data type'], 'UInt16')
        self.assertEqual(coefficient['Default value'], '1290')
        self.assertEqual(coefficient['Description'], 'Torque coefficient 1')

    def test_missing_column_and_shifted_type_rejected(self):
        helper = binary_helpers()
        source = (ROOT / 'parameters.csv').read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.csv'
            path.write_text(source.replace('DOS address,Windy address,', 'DOS address,', 1))
            with self.assertRaisesRegex(ValueError, 'missing columns'):
                helper['load_parameters_by_category'](path)
            path.write_text(source.replace(',2,UInt16,6290,', ',2,2,6290,', 1))
            with self.assertRaisesRegex(ValueError, 'Invalid data type'):
                helper['load_parameters_by_category'](path)

    def test_actual_csv_unique_ids_and_engine_bindings(self):
        helper = binary_helpers()
        groups = helper['load_parameters_by_category'](ROOT / 'parameters.csv')
        params = [p for ps in groups.values() for p in ps]
        ids = [p['Parameter ID'] for p in params]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn('Category', groups)
        for engine in ('ford', 'mercedes', 'honda'):
            for field in ('torque_coefficient_1', 'torque_coefficient_2', 'torque_adjustment',
                          'rpm_upshift_point', 'rpm_downshift_point', 'rpm_limit'):
                self.assertIn(f'engine.{engine}.{field}', ids)
        self.assertGreater(len(params), 200)


class ImportExportTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        tree = ast.parse((ROOT / 'icr2edit.py').read_text())
        editor = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PhysicsEditorGUI')
        methods = [n for n in editor.body if isinstance(n, ast.FunctionDef) and
                   n.name in {'import_parameter_values', 'export_selected_parameters', 'save_changes'}]
        scope = binary_helpers()
        scope['QtWidgets'] = SimpleNamespace(QFileDialog=MagicMock(), QMessageBox=MagicMock())
        scope['parse_parameter_value'] = lambda value, typ: float(value) if typ == 'Fixed16.16' else int(value)
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'editor methods', 'exec'), scope)
        self.scope = scope
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = str(Path(self.temp.name) / 'values.csv')
        params = [{'Parameter ID': 'engine.ford.torque_coefficient_1', 'Category': 'Engine',
                   'DOS address': '4', 'Windy address': '8', 'Rendition address': '', 'Length': '2', 'Data type': 'UInt16'},
                  {'Parameter ID': 'engine.ford.torque_coefficient_2', 'Category': 'Engine',
                   'DOS address': '6', 'Windy address': 'a', 'Rendition address': '', 'Length': '2', 'Data type': 'UInt16'}]
        model = ParameterModel()
        model.load(params, {params[0]['Parameter ID']: 1290, params[1]['Parameter ID']: 8675})
        self.editor = SimpleNamespace(parameters_by_category={'Engine': params}, model=model,
            version='dos102', current_category=None, unsaved_changes={}, checked_parameters={'Engine': {0, 1}},
            update_status=lambda: None, update_category_list_styles=lambda: None)
        scope['QtWidgets'].QFileDialog.getOpenFileName.return_value = (self.file, '')
        scope['QtWidgets'].QFileDialog.getSaveFileName.return_value = (self.file, '')

    def test_id_import_preserves_unrelated_edit_and_ignores_unknown_id(self):
        model = self.editor.model
        model.set_value('engine.ford.torque_coefficient_2', 9000)
        Path(self.file).write_text('Parameter ID,DOS address,Windy address,Rendition address,Length,Value\n'
            'engine.ford.torque_coefficient_1,FFFF,FFFF,,2,1400\n'
            'unknown,6,a,,2,1000\n')
        self.scope['import_parameter_values'](self.editor)
        self.assertEqual(model.get_value('engine.ford.torque_coefficient_1'), 1400)
        self.assertEqual(model.get_value('engine.ford.torque_coefficient_2'), 9000)

    def test_legacy_import_and_id_export(self):
        Path(self.file).write_text('DOS address,Windy address,Rendition address,Length,Value\n4,8,,2,1400\n')
        self.scope['import_parameter_values'](self.editor)
        self.scope['export_selected_parameters'](self.editor)
        with open(self.file) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]['Parameter ID'], 'engine.ford.torque_coefficient_1')
        self.assertEqual(rows[0]['Value'], '1400')
        self.assertEqual(rows[1]['Value'], '8675')

    def test_save_writes_only_dirty_locations(self):
        self.editor.exe_path = str(Path(self.temp.name) / 'test.exe')
        Path(self.editor.exe_path).write_bytes(bytes(range(16)))
        before = Path(self.editor.exe_path).read_bytes()
        self.editor.model.set_value('engine.ford.torque_coefficient_1', 1400)
        params = self.editor.parameters_by_category['Engine']
        self.scope['save_changes'](self.editor, params, self.editor.model.values_for(params))
        after = Path(self.editor.exe_path).read_bytes()
        self.assertEqual(after[4:6], struct.pack('<H', 1400))
        self.assertEqual(after[:4], before[:4])
        self.assertEqual(after[6:], before[6:])


if __name__ == '__main__':
    unittest.main()
