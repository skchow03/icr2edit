# ICR2 Physics Editor

A command-line tool for viewing and editing engine and chassis parameters in IndyCar Racing II (WINDY.EXE, INDYCAR.EXE, or CART.EXE). Built for modding the Windows and DOS versions of ICR2 with a retro-style DOS interface.

---

## Features

- View engine and chassis parameter tables in a tabular format
- Edit any individual parameter by engine/chassis and index
- Reset all values to original stock defaults (hardcoded)
- Save changes directly to the EXE
- Automatically creates a .bak backup of the EXE upon load
- No GUI required — runs entirely in the terminal

---

## Usage

### Prerequisites (for source use)
- Python 3.x

### Running the Editor

Download the precompiled .exe from Releases or run from source:

    python icr2_physedit.py path/to/WINDY.EXE

Or:

    icr2_physedit.exe path/to/INDYCAR.EXE

Upon launch, you’ll see a table display and a menu like:

    --- MENU ---
    [1] Edit engine value
    [2] Edit chassis value
    [3] Reset to default
    [4] Save changes
    [5] Quit

---

## EXE Compatibility

Version       | File Name     | Detected As
------------- | ------------- | ------------
Windows 1.0.1 | WINDY.EXE     | windy101
DOS 1.0.0     | INDYCAR.EXE   | dos100
DOS 1.0.2     | INDYCAR.EXE   | dos102
Rendition     | CART.EXE      | rend102

The editor determines version by file size and uses version-specific hardcoded offsets.

---

## Building the EXE (Optional)

To create a standalone .exe from the source:

    pip install pyinstaller
    pyinstaller --onefile --console icr2_physedit.py

Your .exe will appear in the dist/ folder.

---

## License

MIT License

---

## Credits

Created by SK Chow. This is a fan-made tool and is not affiliated with the original developers.
