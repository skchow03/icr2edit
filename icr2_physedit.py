import os
import struct
from copy import deepcopy
import sys
import shutil


class ChassisParam:
    def __init__(self, values):
        if len(values) != 6:
            raise ValueError("Each chassis must have exactly 6 parameters.")
        self.params = values

    def __getitem__(self, index):
        return self.params[index]

    def __setitem__(self, index, value):
        self.params[index] = value

    def __repr__(self):
        return f"ChassisParam({self.params})"


class EngineParam:
    def __init__(self, values):
        if len(values) != 8:
            raise ValueError("Each engine must have exactly 8 parameters.")
        self.params = values

    def __getitem__(self, index):
        return self.params[index]

    def __setitem__(self, index, value):
        self.params[index] = value

    def __repr__(self):
        return f"EngineParam({self.params})"

def parse_hex_pattern_to_int_list(hex_string):
    """Convert hex pattern string to list of 4-byte unsigned ints (little endian)"""
    raw = bytes.fromhex(hex_string)
    if len(raw) % 4 != 0:
        raise ValueError("Hex pattern length is not a multiple of 4.")
    return [struct.unpack('<I', raw[i:i+4])[0] for i in range(0, len(raw), 4)]


def save_table_to_file(file_path, offset, table):
    with open(file_path, 'rb+') as f:
        f.seek(offset)
        for entry in table:
            for val in entry.params:
                f.write(struct.pack('<I', val))

def edit_value(table, label):
    try:
        entity = int(input(f"Select {label} index (0–2): "))
        param = int(input(f"Select parameter index: "))
        value = int(input("Enter new value: "))
        table[entity][param] = value
        print(f"{label} {entity} param {param} updated to {value}.")
    except (ValueError, IndexError):
        print("Invalid input.")


def load_chassis_table(file_path, offset):
    count = 3 * 6  # 3 chassis * 6 params each
    flat_values = read_4byte_ints(file_path, offset, count, signed=False)
    return [ChassisParam(flat_values[i*6:(i+1)*6]) for i in range(3)]


def load_engine_table(file_path, offset):
    count = 3 * 8  # 3 engines * 8 params each
    flat_values = read_4byte_ints(file_path, offset, count, signed=False)
    return [EngineParam(flat_values[i*8:(i+1)*8]) for i in range(3)]

def identify_icr2_version(file_path):
    size = os.path.getsize(file_path)
    print(f"File: {file_path} ({size} bytes)")
    if size == 1142371:
        print ('DOS version 1.0.0')
        return "dos100"
    elif size == 1142387:
        print ('DOS version 1.0.2')
        return "dos102"
    elif size == 1247899:
        print ('Rendition version 1.0.2-RN1 Build #61')
        return "rend102"
    elif size == 1916928:
        print ('Windows version 1.0.1')
        return "windy101"
    else:
        print ('Unknown version (unrecognized file size)')
        return False # Unknown version (unrecognized file size)

def hex_string_to_bytes(hex_string):
    """Convert a hex string like '92 18 00 00' into bytes"""
    return bytes.fromhex(hex_string)

def find_pattern_in_file(file_path, hex_string, pattern_name):
    """Search for the given hex string in the binary file"""
    pattern = hex_string_to_bytes(hex_string)
    with open(file_path, 'rb') as f:
        data = f.read()
    index = data.find(pattern)
    if index != -1:
        print(f"{pattern_name} found at file offset: 0x{index:X}")
    else:
        print("Pattern not found.")

def read_4byte_ints(file_path, offset, count, signed=False):
    """Reads 'count' 4-byte integers from 'file_path' starting at 'offset'."""
    int_format = '<i' if signed else '<I'  # little-endian
    results = []

    with open(file_path, 'rb') as f:
        f.seek(offset)
        for _ in range(count):
            bytes_read = f.read(4)
            if len(bytes_read) < 4:
                raise ValueError("Unexpected end of file")
            value = struct.unpack(int_format, bytes_read)[0]
            results.append(value)

    return results

def print_table(label, table, param_count, entity_label="Engine"):
    print(f"\n{label}:")
    
    # Header
    col_width = 12
    header = f"{'Param':<6}" + "".join([f"{f'{entity_label} {i}':>{col_width}}" for i in range(len(table))])
    print(header)
    print("-" * len(header))
    
    # Rows
    for param_index in range(param_count):
        row = f"[{param_index}]".ljust(6)
        for entity in table:
            row += f"{entity[param_index]:>{col_width}}"
        print(row)



engine_pattern = (
    "92 18 00 00 64 19 00 00 3C 0F 00 00 0A 05 00 00 "
    "E3 21 00 00 00 00 00 00 64 19 00 00 00 00 12 00 "
    "92 18 00 00 64 19 00 00 3C 0F 00 00 D4 04 00 00 "
    "74 20 00 00 80 84 1E 00 64 19 00 00 00 00 12 00 "
    "92 18 00 00 5E 1A 00 00 04 10 00 00 9C 04 00 00 "
    "D5 1D 00 00 40 42 0F 00 5E 1A 00 00 00 00 12 00"
)

chassis_pattern = (
    "4C 1D 00 00 E8 80 00 00 60 6D 00 00 "
    "FF 00 00 00 04 01 00 00 AB AA 00 00 "
    "7E 1D 00 00 E8 80 00 00 60 6D 00 00 "
    "FF 00 00 00 04 01 00 00 AB AA 00 00 "
    "7E 1D 00 00 E8 80 00 00 60 6D 00 00 "
    "FF 00 00 00 04 01 00 00 AB AA 00 00 "
)

EXE_TABLE_OFFSETS = {
    "windy101": {
        "engine_param": 0xDD320,
        "chassis_param": 0xDD38C
    },
    "dos100": {
        "engine_param": 0xF9CD8,
        "chassis_param": 0xF9D44
    },
    "dos102": {
        "engine_param": 0xF9CD8,
        "chassis_param": 0xF9D44
    },
    "rend102": {
        "engine_param": 0x115408,
        "chassis_param": 0x115474
    }
}

# Build default tables from engine_pattern and chassis_pattern
engine_defaults_flat = parse_hex_pattern_to_int_list(engine_pattern)
chassis_defaults_flat = parse_hex_pattern_to_int_list(chassis_pattern)

engine_table_default = [EngineParam(engine_defaults_flat[i*8:(i+1)*8]) for i in range(3)]
chassis_table_default = [ChassisParam(chassis_defaults_flat[i*6:(i+1)*6]) for i in range(3)]

if len(sys.argv) < 2:
    print("Usage: icr2_physedit.exe <path_to_exe>")
    exit(1)

file_path = sys.argv[1]

print ('ICR2 Car Physics Editor - v0.1')
print ('May 6, 2025')

# Backup file
backup_path = file_path + ".bak"
if not os.path.exists(backup_path):
    shutil.copyfile(file_path, backup_path)
    print(f"Backup created: {backup_path}")
else:
    print(f"Backup already exists: {backup_path}")

version = identify_icr2_version(file_path)

if version and version in EXE_TABLE_OFFSETS:
    offsets = EXE_TABLE_OFFSETS[version]
    engine_offset = offsets.get("engine_param")
    chassis_offset = offsets.get("chassis_param")

    if engine_offset is not None:
        engine_table = load_engine_table(file_path, engine_offset)      

    else:
        print("Engine parameter offset not found for this version.")

    if chassis_offset is not None:
        chassis_table = load_chassis_table(file_path, chassis_offset)
        

    else:
        print("Chassis parameter offset not found for this version.")

else:
    print("Unrecognized or unsupported EXE version.")

while True:
    print_table("Engine Parameters", engine_table, 8, "Engine")
    print_table("Chassis Parameters", chassis_table, 6, "Chassis")

    print("\n--- MENU ---")
    print("[1] Edit engine value")
    print("[2] Edit chassis value")
    print("[3] Reset to default")
    print("[4] Save changes")
    print("[5] Quit")
    choice = input("Select an option: ")

    if choice == '1':
        edit_value(engine_table, "Engine")
    elif choice == '2':
        edit_value(chassis_table, "Chassis")
    elif choice == '3':
        engine_table = deepcopy(engine_table_default)
        chassis_table = deepcopy(chassis_table_default)
        print("Tables reset to default values.")
    elif choice == '4':
        save_table_to_file(file_path, engine_offset, engine_table)
        save_table_to_file(file_path, chassis_offset, chassis_table)
        print("Changes saved.")
    elif choice == '5':
        print("Exiting.")
        break
    else:
        print("Invalid selection.")
