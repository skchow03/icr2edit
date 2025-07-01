import csv
import os
import struct
import sys
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QPixmap, QIcon
import json


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

SETTINGS_FILE = "settings.json"

def load_last_folder():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f).get("last_folder", "")
    except Exception:
        return ""

def save_last_folder(folder_path):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"last_folder": folder_path}, f)
    except Exception:
        pass


def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.abspath(filename)


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
        self.setWindowTitle("ICR2Edit v0.4")
        self.resize(800, 600)

        self.setWindowIcon(QIcon(resource_path("icon.ico")))  # or .ico


        self.exe_path = None
        self.version = None
        self.parameters_by_category = {}
        self.current_values = {}
        self.unsaved_changes = {}

        self.status = self.statusBar()
        self.status.showMessage("No EXE loaded")
        self._create_widgets()
        self.show_about()

    def update_status(self):
        if not self.exe_path:
            self.status.showMessage("No EXE loaded")
            self.setWindowTitle("ICR2Edit v0.4")
            return
        changed = "modified" if self.unsaved_changes else "saved"
        base_name = os.path.basename(self.exe_path)
        title = f"ICR2Edit v0.4 - {base_name} [{self.version}, {changed}]"
        self.setWindowTitle(title)
        self.status.clearMessage()


    def closeEvent(self, event):
        if self.unsaved_changes:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before exiting?",
                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Save,
            )

            if reply == QtWidgets.QMessageBox.Save:
                self.save_all()
                event.accept()
            elif reply == QtWidgets.QMessageBox.Discard:
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()

    def show_about(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setFixedWidth(420)

        dialog.setWindowTitle("About ICR2Edit")
        layout = QtWidgets.QVBoxLayout(dialog)

        # Load and resize image
        image_label = QtWidgets.QLabel()
        pixmap = QPixmap(resource_path("title.png"))

        if not pixmap.isNull():
            scaled = pixmap.scaledToWidth(400, QtCore.Qt.SmoothTransformation)
            image_label.setPixmap(scaled)
            image_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(image_label)

        # Rich text label
        text_label = QtWidgets.QLabel()
        text_label.setTextFormat(QtCore.Qt.RichText)
        text_label.setOpenExternalLinks(True)
        text_label.setAlignment(QtCore.Qt.AlignLeft)
        text_label.setWordWrap(True)

        text_label.setText(
            "<b>ICR2Edit v0.4</b><br><br>"
            "A physics parameter editor for IndyCar Racing II.<br>"
            "Supports DOS, Windows, and Rendition EXEs.<br><br>"
            "Created by SK Chow.<br><br>"
            "<a href='https://github.com/skchow03/icr2_physedit'>GitHub Repository</a><br>"
            "<a href='https://icr2.net/forum/showthread.php?tid=1428'>ICR2 Forum Thread</a><br><br>"
            "<i><b>Disclaimer:</b> Use at your own risk. This tool directly modifies your ICR2 EXE file, which "
            "can lead to crashes or unexpected behavior. Always back up your EXE and any important data before use.</i>"
        )
        layout.addWidget(text_label)

        # OK button
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec_()





    def update_category_list_styles(self):
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            category = item.text()
            font = item.font()
            font.setItalic(category in self.unsaved_changes)
            item.setFont(font)


    def _create_widgets(self):
        open_action = QtWidgets.QAction("&Open .EXE File...\tCtrl+O", self)
        open_action.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_O)
        open_action.triggered.connect(self.open_exe)
        save_action = QtWidgets.QAction("&Save\tCtrl+S", self)
        save_action.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_S)
        save_action.triggered.connect(self.save_all)
        exit_action = QtWidgets.QAction("E&xit", self)
        exit_action.triggered.connect(self.close)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        help_menu = self.menuBar().addMenu("&Help")

        about_action = QtWidgets.QAction("&About", self)
        about_action.triggered.connect(self.show_about)

        help_menu.addAction(about_action)


        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)

        self.category_list = QtWidgets.QListWidget()
        self.category_list.currentRowChanged.connect(self.on_category_select)
        layout.addWidget(self.category_list, 1)

        self.param_table = QtWidgets.QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(["Parameter", "Current value", "Default value"])

        header = self.param_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)        # Parameter column expands
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Current value fits content
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Default value fits content

        self.param_table.doubleClicked.connect(self.on_double_click)
        layout.addWidget(self.param_table, 3)

    def open_exe(self):

        initial_dir = load_last_folder()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select ICR2 .EXE file",
            initial_dir,
            "Executables (*.exe)"
        )



        if not path:
            return
        version = identify_icr2_version(path)
        if not version:
            QtWidgets.QMessageBox.critical(self, "Error", "Unrecognized EXE version")
            return
        csv_path = os.path.abspath("parameters.csv")

        try:
            params_by_cat = load_parameters_by_category(csv_path)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "Error", "parameters.csv not found")
            return

        self.exe_path = path

        save_last_folder(os.path.dirname(path))


        self.version = version
        self.parameters_by_category = params_by_cat
        self.unsaved_changes.clear()
        self.category_list.clear()
        self.category_list.addItems(self.parameters_by_category.keys())
        self.param_table.setRowCount(0)
        self.update_status()
        self.update_category_list_styles()


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
        original_values = load_initial_values(self.current_params, self.exe_path, self.version)

        for i, param in enumerate(self.current_params):
            desc = param["Description"]
            default = param["Default value"]
            cur_val = self.current_values.get(i, "N/A")
            orig_val = original_values.get(i, "N/A")

            item_desc = QtWidgets.QTableWidgetItem(desc)
            item_cur = QtWidgets.QTableWidgetItem(str(cur_val))
            item_def = QtWidgets.QTableWidgetItem(default)

            # Highlight if changed in this session
            if cur_val != orig_val:
                item_cur.setBackground(QtCore.Qt.yellow)

            self.param_table.setItem(i, 0, item_desc)
            self.param_table.setItem(i, 1, item_cur)
            self.param_table.setItem(i, 2, item_def)



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
        self.param_table.item(row, 1).setBackground(QtCore.Qt.yellow)
        self.unsaved_changes[self.current_category] = (self.current_params, self.current_values.copy())
        self.update_status()
        self.update_category_list_styles()


    def save_all(self):
        if not self.unsaved_changes:
            QtWidgets.QMessageBox.information(self, "Info", "No changes to save")
            return
        for cat, (params, values) in self.unsaved_changes.items():
            self.save_changes(params, values)
        self.unsaved_changes.clear()
        self.update_status()
        QtWidgets.QMessageBox.information(self, "Info", "Changes saved")
        self.update_category_list_styles()


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
    app.setWindowIcon(QIcon(resource_path("icon.ico"))
)
    gui = PhysicsEditorGUI()
    gui.show()
    app.exec_()


if __name__ == "__main__":
    main()