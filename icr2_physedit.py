import csv
import os
import struct
import sys

EXE_VERSIONS = {
    1142371: "dos100",
    1142387: "dos102",
    1247899: "rend102",
    1916928: "windy101"
}

ADDRESS_KEYS = {
    "dos100": "DOS address",
    "dos102": "DOS address",
    "windy101": "Windy address",
    "rend102": "Rendition address"
}

def identify_icr2_version(file_path):
    size = os.path.getsize(file_path)
    print(f"File: {file_path} ({size} bytes)")
    version = EXE_VERSIONS.get(size)
    if version:
        print(f"Detected version: {version}")
    else:
        print("Unknown version (unrecognized file size).")
    return version

def load_parameters_by_category(file_path):
    parameters_by_category = {}
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            category = row['Category'].strip()
            if not category:
                continue
            if category not in parameters_by_category:
                parameters_by_category[category] = []
            parameters_by_category[category].append(row)
    return parameters_by_category

def read_value_from_exe(exe_path, address_hex, length):
    try:
        offset = int(address_hex, 16)
    except (ValueError, TypeError):
        return None
    with open(exe_path, 'rb') as f:
        f.seek(offset)
        data = f.read(length)
        if len(data) != length:
            return None
        if length == 2:
            return struct.unpack('<H', data)[0]
        elif length == 4:
            return struct.unpack('<I', data)[0]
        elif length == 1:
            return struct.unpack('<B', data)[0]
        else:
            return int.from_bytes(data, 'little')
    return None

def write_value_to_exe(exe_path, address_hex, length, value):
    try:
        offset = int(address_hex, 16)
    except (ValueError, TypeError):
        print("Invalid address.")
        return
    with open(exe_path, 'rb+') as f:
        f.seek(offset)
        if length == 2:
            f.write(struct.pack('<H', value))
        elif length == 4:
            f.write(struct.pack('<I', value))
        elif length == 1:
            f.write(struct.pack('<B', value))
        else:
            f.write(value.to_bytes(length, 'little'))

def list_categories(parameters_by_category):
    print("\nAvailable Categories:")
    for i, category in enumerate(parameters_by_category.keys()):
        print(f"[{i}] {category}")
    print("[s] Save all changes")
    print("[q] Quit")
    return list(parameters_by_category.keys())

def filter_parameters(parameters, version):
    address_key = ADDRESS_KEYS.get(version, "Windy address")
    valid_params = []
    for param in parameters:
        address = param.get(address_key, "").strip()
        try:
            int(address, 16)
            valid_params.append(param)
        except ValueError:
            continue
    return valid_params

def list_parameters_with_values(parameters, current_values):
    print("\nParameters in this category:")
    print(f"{'Idx':<4} {'Description':<40} {'Current':>10} {'Default':>10}")
    print("-" * 70)
    for i, param in enumerate(parameters):
        desc = param['Description']
        default_val = param['Default value']
        exe_val = current_values.get(i, "N/A")
        print(f"[{i:<2}] {desc:<40} {exe_val:>10} {default_val:>10}")
    print("[b] Back to category menu")

def prompt_edit_parameter(index, parameters, current_values):
    try:
        param = parameters[index]
        current_val = current_values.get(index)
        desc = param['Description']
        data_type = param.get('Data type', '').strip()

        type_bounds = {
            'UInt8': (0, 0xFF),
            'UInt16': (0, 0xFFFF),
            'UInt32': (0, 0xFFFFFFFF),
        }

        min_val, max_val = type_bounds.get(data_type, (0, 0xFFFFFFFF))

        print(f"\nEditing: {desc}")
        print(f"Current value: {current_val}")
        print(f"Expected type: {data_type} (range: {min_val} to {max_val})")

        raw_input_val = input("Enter new value: ").strip()
        new_val = int(raw_input_val)

        if not (min_val <= new_val <= max_val):
            print(f"Error: Value out of range for {data_type}.")
            return False

        current_values[index] = new_val
        print("Value updated in session.")
        return True

    except ValueError:
        print("Invalid input: please enter a valid integer.")
    except IndexError:
        print("Invalid index.")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return False

def load_initial_values(parameters, exe_path, version):
    address_key = ADDRESS_KEYS[version]
    current_values = {}
    for i, param in enumerate(parameters):
        address = param[address_key].strip()
        length = int(param['Length']) if param['Length'].isdigit() else 4
        val = read_value_from_exe(exe_path, address, length)
        current_values[i] = val
    return current_values

def save_changes_to_exe(parameters, current_values, exe_path, version):
    address_key = ADDRESS_KEYS[version]
    for i, param in enumerate(parameters):
        if i not in current_values:
            continue
        address = param[address_key].strip()
        length = int(param['Length']) if param['Length'].isdigit() else 4
        write_value_to_exe(exe_path, address, length, current_values[i])
    print("Changes saved.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python icr2_physedit.py <path_to_EXE>")
        return

    exe_path = sys.argv[1]
    if not os.path.exists(exe_path):
        print("File not found.")
        return

    version = identify_icr2_version(exe_path)
    if not version:
        return

    parameters_csv = os.path.join(os.path.dirname(__file__), 'parameters.csv')
    try:
        parameters_by_category = load_parameters_by_category(parameters_csv)
    except FileNotFoundError:
        print("File 'parameters.csv' not found.")
        return

    unsaved_changes = {}

    print('ICR2 Car Physics Editor - v0.31')
    print('June 3, 2025')

    while True:
        categories = list_categories(parameters_by_category)
        choice = input("Select an option: ").strip().lower()

        if choice == 'q':
            if unsaved_changes:
                if input("You have unsaved changes. Save now? (y/n): ").strip().lower() == 'y':
                    for cat, (params, values) in unsaved_changes.items():
                        save_changes_to_exe(params, values, exe_path, version)
            break
        elif choice == 's':
            if unsaved_changes:
                for cat, (params, values) in unsaved_changes.items():
                    save_changes_to_exe(params, values, exe_path, version)
                unsaved_changes.clear()
            else:
                print("No changes to save.")
            continue

        try:
            selected_category = categories[int(choice)]
        except (ValueError, IndexError):
            print("Invalid selection.")
            continue

        raw_params = parameters_by_category[selected_category]
        valid_params = filter_parameters(raw_params, version)

        if selected_category in unsaved_changes:
            current_values = unsaved_changes[selected_category][1]
        else:
            current_values = load_initial_values(valid_params, exe_path, version)

        while True:
            list_parameters_with_values(valid_params, current_values)
            action = input("Select a parameter to edit or [b] to go back: ").strip().lower()
            if action == 'b':
                break
            try:
                idx = int(action)
                changed = prompt_edit_parameter(idx, valid_params, current_values)
                if changed:
                    unsaved_changes[selected_category] = (valid_params, current_values.copy())
            except ValueError:
                print("Invalid selection.")

if __name__ == "__main__":
    main()
