# ICR2Edit

A command-line tool for viewing and editing engine, chassis and other parameters in IndyCar Racing II (WINDY.EXE, INDYCAR.EXE, or CART.EXE). Built for modding the Windows and DOS versions of ICR2 with a modern Windows interface.

---

# Version history

- v0.5.2 - August 3, 2025: Added support for signed integers
- v0.5.1 - July 22, 2025: Added support for DOS32A Rendition version
- v0.4 - July 1, 2025: Added GUI, general improvements
- v0.3 - June 1, 2025: redid the interface and added more parameters to edit
- v0.31 - June 3, 2025: added validation check when inputting new values

---


## Features

- View engine and chassis parameter tables in a tabular format
- Add or remove editable parameters using parameters.csv
- Edit any individual parameter by engine/chassis and index
- Save changes directly to the EXE

---

## Usage

### Prerequisites (for source use)
- Python 3.x

### Running the Editor

Download the precompiled .exe from Releases or run from source:

    python icr2edit.py

Or:

    icr2edit.exe

---

## EXE Compatibility

The editor determines version by file size and uses version-specific hardcoded offsets.

---

## License

MIT License

---

## Credits

Created by SK Chow. This is a fan-made tool and is not affiliated with the original developers.
