# Standard libraries
import csv
import os
import struct
import sys
import json

# PyQt5 for GUI
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QPixmap, QIcon

# ---- Constants and Mappings ----

# Known EXE file sizes and their associated ICR2 versions
EXE_VERSIONS = {
    1142371: "dos100",
    1142387: "dos102",
    1247899: "rend102",
    1916928: "windy101",
}

# Maps ICR2 version names to the CSV address field to use
ADDRESS_KEYS = {
    "dos100": "DOS address",
    "dos102": "DOS address",
    "windy101": "Windy address",
    "rend102": "Rendition address",
}

# JSON file to store last opened folder path
SETTINGS_FILE = "settings.json"

# ---- Utility Functions ----

def load_last_folder():
    """Load last used folder from settings.json (if it exists)."""
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f).get("last_folder", "")
    except Exception:
        return ""

def save_last_folder(folder_path):
    """Save the folder path to settings.json for future sessions."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"last_folder": folder_path}, f)
    except Exception:
        pass

def resource_path(filename):
    """
    Return the full path to a resource file, whether running from
    source or from a PyInstaller-built EXE (with _MEIPASS).
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.abspath(filename)

def identify_icr2_version(file_path):
    """Identify the ICR2 EXE version based on file size."""
    size = os.path.getsize(file_path)
    return EXE_VERSIONS.get(size)

def load_parameters_by_category(file_path):
    """Load and group parameter rows from parameters.csv by category."""
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
    """Read a typed value of `length` bytes from the EXE at hex offset."""
    try:
        offset = int(address_hex, 16)
    except (ValueError, TypeError):
        return None
    with open(exe_path, "rb") as f:
        f.seek(offset)
        data = f.read(length)
        if len(data) != length:
            return None
        if length == 1:
            return struct.unpack("<B", data)[0]
        if length == 2:
            return struct.unpack("<H", data)[0]
        if length == 4:
            return struct.unpack("<I", data)[0]
        return int.from_bytes(data, "little")  # fallback

def write_value_to_exe(exe_path, address_hex, length, value):
    """Write a typed value of `length` bytes to the EXE at hex offset."""
    try:
        offset = int(address_hex, 16)
    except (ValueError, TypeError):
        return
    with open(exe_path, "rb+") as f:
        f.seek(offset)
        if length == 1:
            f.write(struct.pack("<B", value))
        elif length == 2:
            f.write(struct.pack("<H", value))
        elif length == 4:
            f.write(struct.pack("<I", value))
        else:
            f.write(value.to_bytes(length, "little"))

def filter_parameters(parameters, version):
    """Filter out parameters missing a valid address for the current version."""
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
    """Read the current values from the EXE for a list of parameter rows."""
    address_key = ADDRESS_KEYS[version]
    current_values = {}
    for i, param in enumerate(parameters):
        address = param[address_key].strip()
        length = int(param["Length"]) if param["Length"].isdigit() else 4
        val = read_value_from_exe(exe_path, address, length)
        current_values[i] = val
    return current_values

# ---- GUI Dialog for Editing a Single Parameter ----

class ParameterEditDialog(QtWidgets.QDialog):
    """Dialog with a spinbox to edit a numeric parameter."""

    def __init__(self, description, value, min_val, max_val, parent=None):
        super().__init__(parent)
        self.setWindowTitle(description)
        self.value = value

        layout = QtWidgets.QVBoxLayout(self)

        # Description label
        label = QtWidgets.QLabel(f"Enter new value for: {description}")
        layout.addWidget(label)

        # SpinBox setup
        self.spinbox = QtWidgets.QSpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(min(max_val, 2147483647))  # protect from overflow
        self.spinbox.setValue(value)
        self.spinbox.setSingleStep(1)
        self.spinbox.setAccelerated(True)  # allow press-and-hold auto increment
        layout.addWidget(self.spinbox)

        # OK/Cancel button box
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # Update internal value when spinbox changes
        self.spinbox.valueChanged.connect(self.on_value_change)

    def on_value_change(self, val):
        self.value = val


# ---- Main GUI Class ----

class PhysicsEditorGUI(QtWidgets.QMainWindow):
    """Main window for ICR2Edit."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICR2Edit v0.4.1")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.resize(800, 600)

        # State
        self.exe_path = None
        self.version = None
        self.parameters_by_category = {}
        self.current_values = {}
        self.unsaved_changes = {}

        # GUI Setup
        self.status = self.statusBar()
        self.status.showMessage("No EXE loaded")
        self._create_widgets()
        self.show_about()

    def update_status(self):
        """Update window title and status bar based on EXE path and save state."""
        if not self.exe_path:
            self.status.showMessage("No EXE loaded")
            self.setWindowTitle("ICR2Edit v0.4.1")
            return
        changed = "modified" if self.unsaved_changes else "saved"
        base_name = os.path.basename(self.exe_path)
        self.setWindowTitle(f"ICR2Edit v0.4.1 - {base_name} [{self.version}, {changed}]")
        self.status.clearMessage()

    def revert_all_changes(self):
        """Prompt and revert all changes across all categories."""
        if not self.exe_path or not self.parameters_by_category:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Revert All Changes",
            "Are you sure you want to discard ALL unsaved changes\n"
            "and reload parameter values from the EXE?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        self.unsaved_changes.clear()
        self.category_list.clear()
        self.category_list.addItems(self.parameters_by_category.keys())
        self.param_table.setRowCount(0)
        self.current_values.clear()
        self.update_status()
        self.update_category_list_styles()

        # Try to reselect the current category to repopulate the table
        index = self.category_list.currentRow()
        if index >= 0:
            self.on_category_select(index)

        # Restore selection to the first category (or previous if known)
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)  # triggers on_category_select automatically



    def closeEvent(self, event):
        """Prompt to save if there are unsaved changes on exit."""
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
            else:
                event.ignore()
        else:
            event.accept()

    def show_about(self):
        """Display the About dialog with image and info."""
        dialog = QtWidgets.QDialog(self)
        dialog.setFixedWidth(420)
        dialog.setWindowTitle("About ICR2Edit")
        layout = QtWidgets.QVBoxLayout(dialog)

        # Image
        image_label = QtWidgets.QLabel()
        pixmap = QPixmap(resource_path("title.png"))
        if not pixmap.isNull():
            image_label.setPixmap(pixmap.scaledToWidth(400, QtCore.Qt.SmoothTransformation))
            image_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(image_label)

        # Rich text
        text_label = QtWidgets.QLabel()
        text_label.setTextFormat(QtCore.Qt.RichText)
        text_label.setOpenExternalLinks(True)
        text_label.setAlignment(QtCore.Qt.AlignLeft)
        text_label.setWordWrap(True)
        text_label.setText(
            "<b>ICR2Edit v0.4.1</b><br><br>"
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
        """Italicize categories with unsaved changes."""
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            font = item.font()
            font.setItalic(item.text() in self.unsaved_changes)
            item.setFont(font)

    def _create_widgets(self):
        """Builds all menus and layout widgets."""
        # Menubar setup
        open_action = QtWidgets.QAction("&Open .EXE File...\tCtrl+O", self)
        open_action.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_O)
        open_action.triggered.connect(self.open_exe)

        save_action = QtWidgets.QAction("&Save\tCtrl+S", self)
        save_action.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_S)
        save_action.triggered.connect(self.save_all)

        revert_action = QtWidgets.QAction("&Revert\tCtrl+R", self)
        revert_action.setShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_R)
        revert_action.triggered.connect(self.revert_all_changes)


        exit_action = QtWidgets.QAction("E&xit", self)
        exit_action.triggered.connect(self.close)

        about_action = QtWidgets.QAction("&About", self)
        about_action.triggered.connect(self.show_about)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(revert_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)


        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(about_action)

        # Main layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)

        # Category list
        self.category_list = QtWidgets.QListWidget()
        self.category_list.currentRowChanged.connect(self.on_category_select)
        layout.addWidget(self.category_list, 1)

        # Parameter table
        self.param_table = QtWidgets.QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(["Parameter", "Current value", "Default value"])
        header = self.param_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        #self.param_table.doubleClicked.connect(self.on_double_click)
        layout.addWidget(self.param_table, 3)

    def open_exe(self):
        """Open EXE file and load associated parameters."""
        initial_dir = load_last_folder()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select ICR2 .EXE file", initial_dir, "Executables (*.exe)")
        if not path:
            return

        version = identify_icr2_version(path)
        if not version:
            QtWidgets.QMessageBox.critical(self, "Error", "Unrecognized EXE version")
            return

        try:
            params_by_cat = load_parameters_by_category("parameters.csv")
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "Error", "parameters.csv not found")
            return

        # Save state
        self.exe_path = path
        save_last_folder(os.path.dirname(path))
        self.version = version
        self.parameters_by_category = params_by_cat
        self.unsaved_changes.clear()

        # UI update
        self.category_list.clear()
        self.category_list.addItems(self.parameters_by_category.keys())
        self.param_table.setRowCount(0)
        self.update_status()
        self.update_category_list_styles()

    def on_category_select(self, index):
        """When user selects a category, populate the table with its parameters."""
        if self.exe_path is None or index < 0:
            return
        category = self.category_list.item(index).text()
        raw_params = self.parameters_by_category[category]
        valid_params = filter_parameters(raw_params, self.version)
        current_vals = self.unsaved_changes.get(category, (None, None))[1] or load_initial_values(valid_params, self.exe_path, self.version)
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
            cur_val = self.current_values.get(i, 0)
            orig_val = original_values.get(i, 0)

            # Description column (not editable)
            item_desc = QtWidgets.QTableWidgetItem(desc)
            item_desc.setFlags(QtCore.Qt.ItemIsEnabled)
            self.param_table.setItem(i, 0, item_desc)

            # SpinBox for current value
            data_type = param.get("Data type", "").strip()
            type_bounds = {
                "UInt8": (0, 0xFF),
                "UInt16": (0, 0xFFFF),
                "UInt32": (0, 0xFFFFFFFF),
            }
            min_val, max_val = type_bounds.get(data_type, (0, 0xFFFFFFFF))

            spinbox = QtWidgets.QSpinBox()
            spinbox.setMinimum(min_val)
            spinbox.setMaximum(min(max_val, 2147483647))  # UI limit
            spinbox.setValue(cur_val)
            spinbox.setSingleStep(1)
            spinbox.setAccelerated(True)

            # Highlight if changed
            if cur_val != orig_val:
                spinbox.setStyleSheet("background-color: yellow;")

            # Closure to capture index and update current values
            def on_change(val, row=i):
                sender = self.sender()
                if isinstance(sender, QtWidgets.QSpinBox):
                    sender.setStyleSheet("background-color: yellow;")
                self.current_values[row] = val
                self.unsaved_changes[self.current_category] = (
                    self.current_params,
                    self.current_values.copy(),
                )
                self.update_status()
                self.update_category_list_styles()


            spinbox.valueChanged.connect(on_change)
            self.param_table.setCellWidget(i, 1, spinbox)

            # Default value (read-only)
            item_def = QtWidgets.QTableWidgetItem(default)
            item_def.setFlags(QtCore.Qt.ItemIsEnabled)
            self.param_table.setItem(i, 2, item_def)


    def on_double_click(self, index):
        """Edit the selected parameter with a slider/input dialog."""
        row = index.row()
        if row < 0:
            return
        param = self.current_params[row]
        cur_val = self.current_values.get(row, "N/A")
        data_type = param.get("Data type", "").strip()
        type_bounds = {"UInt8": (0, 0xFF), "UInt16": (0, 0xFFFF), "UInt32": (0, 0xFFFFFFFF)}
        min_val, max_val = type_bounds.get(data_type, (0, 0xFFFFFFFF))

        dlg = ParameterEditDialog(param["Description"], int(cur_val), min_val, max_val, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        new_val = dlg.value
        if not (min_val <= new_val <= max_val):
            QtWidgets.QMessageBox.critical(self, "Error", f"Value out of range for {data_type}")
            return

        # Save value and mark as changed
        self.current_values[row] = new_val
        self.param_table.item(row, 1).setText(str(new_val))
        self.param_table.item(row, 1).setBackground(QtCore.Qt.yellow)
        self.unsaved_changes[self.current_category] = (self.current_params, self.current_values.copy())
        self.update_status()
        self.update_category_list_styles()

    def save_all(self):
        """Save all modified values back to EXE."""
        if not self.unsaved_changes:
            QtWidgets.QMessageBox.information(self, "Info", "No changes to save")
            return
        for cat, (params, values) in self.unsaved_changes.items():
            self.save_changes(params, values)
        self.unsaved_changes.clear()
        self.update_status()
        self.update_category_list_styles()
        QtWidgets.QMessageBox.information(self, "Info", "Changes saved")

    def save_changes(self, params, values):
        """Write parameter values to the EXE file."""
        address_key = ADDRESS_KEYS[self.version]
        for i, param in enumerate(params):
            if i not in values:
                continue
            address = param[address_key].strip()
            length = int(param["Length"]) if param["Length"].isdigit() else 4
            write_value_to_exe(self.exe_path, address, length, values[i])

# ---- Application Entry Point ----

def main():
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    gui = PhysicsEditorGUI()
    gui.show()
    app.exec_()

if __name__ == "__main__":
    main()
