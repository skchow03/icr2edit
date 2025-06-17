import csv
import os
import struct
from PyQt5 import QtWidgets, QtCore

EXE_VERSIONS = {
    1142371: "dos100",
    1142387: "dos102",
    1247899: "rend102",
    1916928: "windy101",
}

ADDRESS_KEYS = {
    "dos100": "DOS address",
    "dos102": "DOS address",
    "windy101": "Windy address",
    "rend102": "Rendition address",
}


def identify_icr2_version(file_path):
    size = os.path.getsize(file_path)
    return EXE_VERSIONS.get(size)


def load_parameters_by_category(file_path):
    parameters_by_category = {}
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            category = row["Category"].strip()
            if not category:
                continue
            parameters_by_category.setdefault(category, []).append(row)
    return parameters_by_category


def read_value_from_exe(exe_path, address_hex, length):
    try:
        offset = int(address_hex, 16)
    except (ValueError, TypeError):
        return None
    with open(exe_path, "rb") as f:
        f.seek(offset)
        data = f.read(length)
        if len(data) != length:
            return None
        if length == 2:
            return struct.unpack("<H", data)[0]
        if length == 4:
            return struct.unpack("<I", data)[0]
        if length == 1:
            return struct.unpack("<B", data)[0]
        return int.from_bytes(data, "little")


def write_value_to_exe(exe_path, address_hex, length, value):
    try:
        offset = int(address_hex, 16)
    except (ValueError, TypeError):
        return
    with open(exe_path, "rb+") as f:
        f.seek(offset)
        if length == 2:
            f.write(struct.pack("<H", value))
        elif length == 4:
            f.write(struct.pack("<I", value))
        elif length == 1:
            f.write(struct.pack("<B", value))
        else:
            f.write(value.to_bytes(length, "little"))


def filter_parameters(parameters, version):
    address_key = ADDRESS_KEYS.get(version, "Windy address")
    valid = []
    for p in parameters:
        addr = p.get(address_key, "").strip()
        try:
            int(addr, 16)
            valid.append(p)
        except ValueError:
            continue
    return valid


def load_initial_values(parameters, exe_path, version):
    address_key = ADDRESS_KEYS[version]
    current_values = {}
    for i, param in enumerate(parameters):
        address = param[address_key].strip()
        length = int(param["Length"]) if param["Length"].isdigit() else 4
        val = read_value_from_exe(exe_path, address, length)
        current_values[i] = val
    return current_values


class ParameterEditDialog(QtWidgets.QDialog):
    def __init__(self, description, value, min_val, max_val, parent=None):
        super().__init__(parent)
        self.setWindowTitle(description)
        self.value = value

        layout = QtWidgets.QVBoxLayout(self)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        max_slider = min(max_val, 2147483647)
        self.slider.setMinimum(min_val)
        self.slider.setMaximum(max_slider)
        self.slider.setValue(value)

        self.input_box = QtWidgets.QLineEdit(str(value))

        self.slider.valueChanged.connect(self.on_slider_change)
        self.input_box.textChanged.connect(self.on_text_change)

        layout.addWidget(self.slider)
        layout.addWidget(self.input_box)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._min = min_val
        self._max = max_val

    def on_slider_change(self, value):
        self.input_box.setText(str(value))

    def on_text_change(self, text):
        try:
            val = int(text)
        except ValueError:
            return
        if self._min <= val <= self._max:
            self.slider.setValue(val)
            self.value = val


class PhysicsEditorGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICR2 Physics Editor")
        self.resize(800, 600)

        self.exe_path = None
        self.version = None
        self.parameters_by_category = {}
        self.current_values = {}
        self.unsaved_changes = {}

        self.status = self.statusBar()
        self.status.showMessage("No EXE loaded")
        self._create_widgets()

    def update_status(self):
        if not self.exe_path:
            self.status.showMessage("No EXE loaded")
            return
        changed = "modified" if self.unsaved_changes else "saved"
        self.status.showMessage(f"Version: {self.version} - {changed}")

    def _create_widgets(self):
        open_action = QtWidgets.QAction("Open EXE", self)
        open_action.triggered.connect(self.open_exe)
        save_action = QtWidgets.QAction("Save Changes", self)
        save_action.triggered.connect(self.save_all)
        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)

        self.category_list = QtWidgets.QListWidget()
        self.category_list.currentRowChanged.connect(self.on_category_select)
        layout.addWidget(self.category_list, 1)

        self.param_table = QtWidgets.QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(["Description", "Current", "Default"])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.doubleClicked.connect(self.on_double_click)
        layout.addWidget(self.param_table, 3)

    def open_exe(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select EXE", filter="Executables (*.exe)")
        if not path:
            return
        version = identify_icr2_version(path)
        if not version:
            QtWidgets.QMessageBox.critical(self, "Error", "Unrecognized EXE version")
            return
        csv_path = os.path.join(os.path.dirname(__file__), "parameters.csv")
        try:
            params_by_cat = load_parameters_by_category(csv_path)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "Error", "parameters.csv not found")
            return

        self.exe_path = path
        self.version = version
        self.parameters_by_category = params_by_cat
        self.unsaved_changes.clear()
        self.category_list.clear()
        self.category_list.addItems(self.parameters_by_category.keys())
        self.param_table.setRowCount(0)
        self.setWindowTitle(f"ICR2 Physics Editor - {os.path.basename(path)}")
        self.update_status()

    def on_category_select(self, index):
        if self.exe_path is None or index < 0:
            return
        category = self.category_list.item(index).text()
        raw_params = self.parameters_by_category[category]
        valid_params = filter_parameters(raw_params, self.version)
        if category in self.unsaved_changes:
            current_vals = self.unsaved_changes[category][1]
        else:
            current_vals = load_initial_values(valid_params, self.exe_path, self.version)
        self.current_values = current_vals
        self.current_params = valid_params
        self.current_category = category
        self.populate_params()

    def populate_params(self):
        self.param_table.setRowCount(len(self.current_params))
        for i, param in enumerate(self.current_params):
            desc = param["Description"]
            default = param["Default value"]
            cur = self.current_values.get(i, "N/A")
            self.param_table.setItem(i, 0, QtWidgets.QTableWidgetItem(desc))
            self.param_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(cur)))
            self.param_table.setItem(i, 2, QtWidgets.QTableWidgetItem(default))

    def on_double_click(self, index):
        row = index.row()
        if row < 0:
            return
        param = self.current_params[row]
        cur_val = self.current_values.get(row, "N/A")
        data_type = param.get("Data type", "").strip()
        type_bounds = {
            "UInt8": (0, 0xFF),
            "UInt16": (0, 0xFFFF),
            "UInt32": (0, 0xFFFFFFFF),
        }
        min_val, max_val = type_bounds.get(data_type, (0, 0xFFFFFFFF))

        dlg = ParameterEditDialog(param["Description"], int(cur_val), min_val, max_val, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        new_val = dlg.value
        if not (min_val <= new_val <= max_val):
            QtWidgets.QMessageBox.critical(self, "Error", f"Value out of range for {data_type}")
            return
        self.current_values[row] = new_val
        self.param_table.item(row, 1).setText(str(new_val))
        self.unsaved_changes[self.current_category] = (self.current_params, self.current_values.copy())
        self.update_status()

    def save_all(self):
        if not self.unsaved_changes:
            QtWidgets.QMessageBox.information(self, "Info", "No changes to save")
            return
        for cat, (params, values) in self.unsaved_changes.items():
            self.save_changes(params, values)
        self.unsaved_changes.clear()
        self.update_status()
        QtWidgets.QMessageBox.information(self, "Info", "Changes saved")

    def save_changes(self, params, values):
        address_key = ADDRESS_KEYS[self.version]
        for i, param in enumerate(params):
            if i not in values:
                continue
            address = param[address_key].strip()
            length = int(param["Length"]) if param["Length"].isdigit() else 4
            write_value_to_exe(self.exe_path, address, length, values[i])


def main():
    app = QtWidgets.QApplication([])
    gui = PhysicsEditorGUI()
    gui.show()
    app.exec_()


if __name__ == "__main__":
    main()
