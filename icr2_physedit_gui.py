import csv
import os
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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
    version = EXE_VERSIONS.get(size)
    return version


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


class PhysicsEditorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ICR2 Physics Editor")

        self.exe_path = None
        self.version = None
        self.parameters_by_category = {}
        self.current_values = {}
        self.unsaved_changes = {}

        self.create_widgets()

    def create_widgets(self):
        # Menu
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open EXE", command=self.open_exe)
        filemenu.add_command(label="Save Changes", command=self.save_all)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        # layout
        left_frame = tk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        right_frame = tk.Frame(self.root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Label(left_frame, text="Categories").pack(anchor="w")
        self.category_list = tk.Listbox(left_frame, height=20)
        self.category_list.pack(fill=tk.Y, expand=True)
        self.category_list.bind("<<ListboxSelect>>", self.on_category_select)

        columns = ("Description", "Current", "Default")
        self.param_tree = ttk.Treeview(
            right_frame, columns=columns, show="headings", selectmode="browse"
        )
        for col in columns:
            self.param_tree.heading(col, text=col)
            self.param_tree.column(col, width=150, anchor="center")
        self.param_tree.pack(fill=tk.BOTH, expand=True)
        self.param_tree.bind("<Double-1>", self.on_double_click)

    def open_exe(self):
        path = filedialog.askopenfilename(title="Select EXE")
        if not path:
            return
        version = identify_icr2_version(path)
        if not version:
            messagebox.showerror("Error", "Unrecognized EXE version")
            return
        csv_path = os.path.join(os.path.dirname(__file__), "parameters.csv")
        try:
            params_by_cat = load_parameters_by_category(csv_path)
        except FileNotFoundError:
            messagebox.showerror("Error", "parameters.csv not found")
            return

        self.exe_path = path
        self.version = version
        self.parameters_by_category = params_by_cat
        self.unsaved_changes.clear()
        self.category_list.delete(0, tk.END)
        for cat in self.parameters_by_category.keys():
            self.category_list.insert(tk.END, cat)
        self.param_tree.delete(*self.param_tree.get_children())
        self.root.title(f"ICR2 Physics Editor - {os.path.basename(path)}")

    def on_category_select(self, event):
        if not self.exe_path:
            return
        selection = self.category_list.curselection()
        if not selection:
            return
        index = selection[0]
        category = self.category_list.get(index)
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
        self.param_tree.delete(*self.param_tree.get_children())
        for i, param in enumerate(self.current_params):
            desc = param["Description"]
            default = param["Default value"]
            cur = self.current_values.get(i, "N/A")
            self.param_tree.insert("", "end", iid=str(i), values=(desc, cur, default))

    def on_double_click(self, event):
        item = self.param_tree.focus()
        if not item:
            return
        idx = int(item)
        param = self.current_params[idx]
        cur_val = self.current_values.get(idx)
        data_type = param.get("Data type", "").strip()

        type_bounds = {
            "UInt8": (0, 0xFF),
            "UInt16": (0, 0xFFFF),
            "UInt32": (0, 0xFFFFFFFF),
        }
        min_val, max_val = type_bounds.get(data_type, (0, 0xFFFFFFFF))

        def commit():
            try:
                new_val = int(entry.get())
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid integer")
                return
            if not (min_val <= new_val <= max_val):
                messagebox.showerror(
                    "Error", f"Value out of range for {data_type}"
                )
                return
            self.current_values[idx] = new_val
            self.param_tree.set(item, column="Current", value=str(new_val))
            self.unsaved_changes[self.current_category] = (
                self.current_params,
                self.current_values.copy(),
            )
            edit_win.destroy()

        edit_win = tk.Toplevel(self.root)
        edit_win.title(param["Description"])
        tk.Label(edit_win, text=f"Current value: {cur_val}").pack(padx=10, pady=5)
        entry = tk.Entry(edit_win)
        entry.insert(0, str(cur_val))
        entry.pack(padx=10, pady=5)
        tk.Button(edit_win, text="OK", command=commit).pack(pady=5)

    def save_all(self):
        if not self.unsaved_changes:
            messagebox.showinfo("Info", "No changes to save")
            return
        for cat, (params, values) in self.unsaved_changes.items():
            self.save_changes(params, values)
        self.unsaved_changes.clear()
        messagebox.showinfo("Info", "Changes saved")

    def save_changes(self, params, values):
        address_key = ADDRESS_KEYS[self.version]
        for i, param in enumerate(params):
            if i not in values:
                continue
            address = param[address_key].strip()
            length = int(param["Length"]) if param["Length"].isdigit() else 4
            write_value_to_exe(self.exe_path, address, length, values[i])


def main():
    root = tk.Tk()
    app = PhysicsEditorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
