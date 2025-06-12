# ICR2 Physics Editor

A command-line tool for viewing and editing engine and chassis parameters in IndyCar Racing II (WINDY.EXE, INDYCAR.EXE, or CART.EXE). Built for modding the Windows and DOS versions of ICR2 with a retro-style DOS interface.

---

# Version history

- v0.3 - June 1, 2025: redid the interface and added more parameters to edit
- v0.31 - June 3, 2025: added validation check when inputting new values

---


## Features

- View engine and chassis parameter tables in a tabular format
- Add or remove editable parameters using parameters.csv
- Edit any individual parameter by engine/chassis and index
- Save changes directly to the EXE
- Runs entirely in the terminal, with an optional Tkinter-based GUI

---

## Usage

### Prerequisites (for source use)
- Python 3.x

### Running the Editor

Download the precompiled .exe from Releases or run from source:

    python icr2_physedit.py path/to/WINDY.EXE

Or:

    icr2_physedit.exe path/to/INDYCAR.EXE

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
