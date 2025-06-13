import csv
import os
import struct

from PyQt5 import QtCore, QtWidgets

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
        elif length == 4:
            return struct.unpack("<I", data)[0]
        elif length == 1:
            return struct.unpack("<B", data)[0]
        else:
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


numbounds = {
    "UInt8": (0, 0xFF),
    "UInt16": (0, 0xFFFF),
    "UInt32": (0, 0xFFFFFFFF),
}


class PhysicsEditorWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICR2 Physics Editor")

        self.exe_path = None
        self.version = None
        self.parameters_by_category = {}
        self.current_category = None
        self.current_params = []
        self.current_values = {}
        self.unsaved_changes = {}

        self.setup_ui()

    def setup_ui(self):
        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_act = QtWidgets.QAction("Open EXE", self)
        save_act = QtWidgets.QAction("Save Changes", self)
        exit_act = QtWidgets.QAction("Exit", self)
        file_menu.addAction(open_act)
        file_menu.addAction(save_act)
        file_menu.addSeparator()
        file_menu.addAction(exit_act)
        open_act.triggered.connect(self.open_exe)
        save_act.triggered.connect(self.save_all)
        exit_act.triggered.connect(self.close)

        # Central widgets
        splitter = QtWidgets.QSplitter()
        self.setCentralWidget(splitter)

        self.category_list = QtWidgets.QListWidget()
        splitter.addWidget(self.category_list)
        self.category_list.currentRowChanged.connect(self.category_changed)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Description", "Current", "Default"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.edit_value)
        splitter.addWidget(self.table)
        splitter.setSizes([150, 600])

    def open_exe(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select EXE")
        if not path:
            return
        version = identify_icr2_version(path)
        if not version:
            QtWidgets.QMessageBox.warning(self, "Error", "Unrecognized EXE version")
            return
        csv_path = os.path.join(os.path.dirname(__file__), "parameters.csv")
        try:
            params = load_parameters_by_category(csv_path)
        except FileNotFoundError:
            QtWidgets.QMessageBox.warning(self, "Error", "parameters.csv not found")
            return

        self.exe_path = path
        self.version = version
        self.parameters_by_category = params
        self.unsaved_changes.clear()
        self.category_list.clear()
        for cat in self.parameters_by_category.keys():
            self.category_list.addItem(cat)
        self.table.setRowCount(0)
        self.setWindowTitle(f"ICR2 Physics Editor - {os.path.basename(path)}")

    def category_changed(self, row):
        if row < 0 or not self.exe_path:
            return
        category = self.category_list.item(row).text()
        raw_params = self.parameters_by_category[category]
        valid_params = filter_parameters(raw_params, self.version)
        if category in self.unsaved_changes:
            current_vals = self.unsaved_changes[category][1]
        else:
            current_vals = load_initial_values(valid_params, self.exe_path, self.version)
        self.current_category = category
        self.current_params = valid_params
        self.current_values = current_vals
        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(len(self.current_params))
        for i, param in enumerate(self.current_params):
            desc = QtWidgets.QTableWidgetItem(param["Description"])
            cur = QtWidgets.QTableWidgetItem(str(self.current_values.get(i, "N/A")))
            default = QtWidgets.QTableWidgetItem(param["Default value"])
            self.table.setItem(i, 0, desc)
            self.table.setItem(i, 1, cur)
            self.table.setItem(i, 2, default)

    def edit_value(self, item):
        row = item.row()
        param = self.current_params[row]
        cur_val = self.current_values.get(row)
        data_type = param.get("Data type", "").strip()
        min_v, max_v = numbounds.get(data_type, (0, 0xFFFFFFFF))
        new_val, ok = QtWidgets.QInputDialog.getInt(
            self,
            param["Description"],
            "Enter new value:",
            value=cur_val if cur_val is not None else 0,
            min=min_v,
            max=max_v,
        )
        if ok:
            self.current_values[row] = new_val
            self.table.item(row, 1).setText(str(new_val))
            self.unsaved_changes[self.current_category] = (
                self.current_params,
                self.current_values.copy(),
            )

    def save_all(self):
        if not self.unsaved_changes:
            QtWidgets.QMessageBox.information(self, "Info", "No changes to save")
            return
        for cat, (params, values) in self.unsaved_changes.items():
            self.save_changes(params, values)
        self.unsaved_changes.clear()
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
    window = PhysicsEditorWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
