# ICR2Edit

A tool for viewing and editing engine, chassis and other parameters in IndyCar Racing II (WINDY.EXE, INDYCAR.EXE, or CART.EXE). Built for modding the Windows and DOS versions of ICR2 with a modern Windows interface.

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
- Display and edit signed 16.16 fixed-point parameters as decimal values while
  storing them in their four-byte little-endian representation

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


### Stable parameter IDs and shared editor state

`parameters.csv` now has a required `Parameter ID` column. IDs are permanent:
keep an existing ID when changing a label, category, address, or row order.
New parameters need new unique IDs. Separate binary occurrences have separate
IDs (including `.occurrence_2` suffixes); future linked controls should explicitly
list the IDs they update. An ID does not certify the interpretation of a parameter.

`ParameterModel` owns executable values, staged changes, binary type validation,
and change notifications. Views use `get_value(id)` and `set_value(id, value)`;
subscribe/unsubscribe for live updates. Missing executable-version addresses are
excluded from the model. Changes are written only with the editor's Save action.
Imports prefer `Parameter ID`; older address-and-length CSV exports remain supported.
Unknown IDs do not fall back to potentially unrelated binary locations.

Open an EXE, then choose **Tools → Launch Torque Curve Visualizer**. Select Ford,
Mercedes, or Honda to edit the same staged values as the parameter table. Curves
update live and compare against that engine's stock defaults. RPM controls display
in-game RPM (twice the stored value). Torque remains in arbitrary simulation units;
the plot uses the existing curve formula, not a calibrated dynamometer model.
Chassis and other graphical panels can use this model in future updates.

Run checks with `python -m unittest discover` and `python -m compileall -q .`.
