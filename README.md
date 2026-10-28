# 🧪 Laboratory Protocol Builder - User Guide

Welcome to the **Laboratory Protocol Builder**, a professional tool designed to help you create, organize, and export chemical laboratory procedures using an intuitive "smart block" system. If it is your first using it, consider answering this [Google Form](https://forms.gle/2RoHZSrXgg8aZRDV6) to give us feedback about your experience.

## 0. Download or Set Up
If you want to use the Interface Directly, download the Windows or Mac version [here](https://ulisboa-my.sharepoint.com/:f:/g/personal/ist187382_tecnico_ulisboa_pt/IgBbEPWlrYx1QJbgrnwBPx4-AYCU74uv_ykpcqADT8ZSn2Q?e=csxmn7).

### Run without cloning (Windows, Linux and macOS)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Git](https://git-scm.com/downloads), then run:

```bash
uvx --from git+https://github.com/Pocoyo7798/LabProGen labprogen
```

uv installs LabProGen and its Python dependencies in an isolated environment and
opens the graphical editor. A compatible Python can be downloaded automatically
by uv when needed.

For a persistent installation, available from any directory:

```bash
uv tool install git+https://github.com/Pocoyo7798/LabProGen
labprogen
```

If the command is not on your PATH, run `uv tool update-shell` and reopen the
terminal. A published PyPI package is not required for either Git installation.

### Run from the repository (Windows, Linux and macOS)

With uv and Git installed:

```bash
git clone https://github.com/Pocoyo7798/LabProGen.git
cd LabProGen
uv run main.py
```

Alternatively, run `uv run labprogen`. uv reads `pyproject.toml`, creates the
project environment, and installs the dependencies automatically. The committed
`uv.lock` records
the resolved versions for reproducible source runs; `pyproject.toml` remains the
only dependency declaration. pip and uvx resolve the published dependency ranges
independently of that project lockfile.

### Use pip instead of uv

Use Python **3.10–3.14** on a platform supported by PySide6 6.10.2. Python 3.12 is
a suitable choice. From a checkout, on Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/labprogen
```

On Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\labprogen.exe
```

Use `pip install -e .` with the environment's Python instead when developing.
`pip install -r requirements.txt` is also supported from the repository root;
that file delegates to `pyproject.toml`. After installation,
`python -m labprogen` also launches the editor using that environment's Python.

### Desktop and system requirements

Python package managers install the Python dependencies and the Qt libraries
provided by the PySide6 wheels. They do not install operating system libraries
or provide a desktop/display server. Windows, Linux and macOS are supported only
where PySide6 6.10.2 supplies compatible wheels; Python support alone does not
guarantee OS/architecture support.

On Linux, Qt needs graphics drivers, OpenGL/EGL, font libraries and the X11/XCB or
Wayland desktop libraries. Minimal Debian/Ubuntu installations may need packages
such as `libegl1`, `libgl1`, `libxkbcommon-x11-0`, `libxcb-cursor0`,
`libxcb-icccm4`, `libxcb-image0`, `libxcb-keysyms1` and
`libxcb-render-util0`. Package names vary by distribution; see
[Qt platform dependencies](https://doc.qt.io/qt-6.10/linux-requirements.html).
On Windows, missing Microsoft runtime DLLs may require the
[Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
On macOS, use a macOS release and architecture supported by the Qt wheels.
A separate Qt SDK is not required. Internet access is required for the initial
installation, PubChem searches and optional AIedu article generation.

### Configuration and bundled resources

The installed package includes the LinkML schema, default complex actions,
AIedu configuration example, and compiled Qt icon resources. Runtime asset paths
are independent of the directory from which LabProGen is launched.

The editor, export and validation use `action_data_model.yaml` (version 1.10.0),
including its 48 classes. Separation methods have their own typed fields; sieve
operations use `Separate` → `Sieving`, and subproduct collection records the
phase to retain. Addition quantities belong to the chemicals.

Older action/type aliases and unambiguous structures are converted on import.
Incomplete or incompatible records remain editable but must be reviewed before
strict export: for example, choose a retained separation phase, resolve obsolete
polymer fields, or replace a `Dispersion` with an appropriate current entity
without losing its composition. The application does not invent missing values.
Exports retain canvas metadata for round-trip editing;
normalized activities use the schema's `laboratory_actions` relation.
See [schema and attribution](schema/README.md).

Editable configuration is stored in:

| Execution mode | Configuration directory |
| --- | --- |
| Source checkout / editable install | `config/` in the checkout |
| PyInstaller executable | `config/` beside the executable |
| Python / uvx / uv tool installation on Linux | `$XDG_CONFIG_HOME/LabProGen` or `~/.config/LabProGen` |
| Python / uvx / uv tool installation on macOS | `~/Library/Application Support/LabProGen` |
| Python / uvx / uv tool installation on Windows | `%LOCALAPPDATA%\LabProGen` |

Installed runs seed `complex_actions.json` on first launch and preserve subsequent
edits across uvx environments. Optional AIedu credentials can be entered in the
application or supplied through `IAEDU_ENDPOINT`, `IAEDU_API_KEY` and
`IAEDU_CHANNEL_ID`. Private credentials and exported protocols are excluded from
the Python distributions. Source checkouts and executables retain their existing
configuration locations; an executable needs write access to its own folder to
save configuration there.

### Saving complex actions

Native JSON/YAML protocols preserve each explicitly identified complex-action
instance, its ordered members, parameter labels/defaults/editability and the
expanded/collapsed view. The instance is self-contained: importing it does not
require registering the same definition in the local complex-action dictionary.
Nested templates are saved as their materialized member sequence and bindings;
the protocol is not a replacement for exporting the reusable dictionary.

LabProGen's LinkML export envelope also retains this information, separately from
the strict schema instances. Its root `complex_action_groups` object has
`version: 1`, a `groups` list (`group_id`, `name`, `parameters`) and `collapsed`.
Members are identified by `part_of_complex_action`, `complex_group_id`,
`complex_action_name` and `complex_step_index` on the native step/export wrapper.
These fields never become LinkML slots. The member action parameters remain the
source of instance values; grouping metadata describes their presentation.

Older files with explicit member markers can restore their groups. Files with
only a flat sequence remain flat, even when the local dictionary contains a
matching sequence. Dictionary import registers reusable definitions without
matching or grouping existing actions; insert an instance through Add Action.
A dictionary (`complex_action_name`, `steps`, `parameters`) must be opened with
Import Complex Action Dictionary, rather than Import Protocol. Tools that strip
LabProGen envelope metadata cannot preserve
this grouping. Inconsistent groups produce import warnings while retaining their
actions and markers; unsupported metadata versions are rejected before replacing
the open protocol. Additional native scalar-record/list editors use the same
compact Add/edit/remove controls. Quantity editors retain string-valued schema
fields and existing units without automatic conversion.

### Generated data models

The semantic Python models are generated from the LinkML schema and committed in
`labprogen/generated/`. Regenerate them with `uv run --locked python -m tools.generate_models` and check synchronization with the same command followed
by `--check`. See [model architecture and validation](docs/models.md).

### Development and executable builds

From the repository root:

```bash
uv run --extra test python -m pytest
uv run --extra build python -m build
uv run --extra build pyinstaller main.spec
```

`python -m build` produces a wheel and source distribution in `dist/`.
`main.spec` and `rth_fix_metadata.py` retain the existing PyInstaller pipeline,
including LinkML data and metadata collection. Build on each target operating
system; PyInstaller does not cross-compile Windows or macOS executables on Linux.
The spec includes the OpenAPI validators' schema resources, including their
extensionless vocabulary files. It excludes optional console Readline and Qt
Virtual Keyboard from the executable while retaining other desktop input
plugins; normal Python/PySide6 installations are unaffected. The executable does
not provide Qt's on-screen keyboard selected by `QT_IM_MODULE=qtvirtualkeyboard`.

The compiled icon module is committed. See [Qt resources](resources/README.md)
for the regeneration command when modifying the icon or QRC.

### License

The original LabProGen source code is licensed under the [MIT License](LICENSE).
Copyright © 2026 Daniel Pereira Costa and Pedro Tavares. This grant covers their
original code, tests, build scripts, configuration and documentation, subject to
the resource exceptions below. It does not relicense third-party material.

The [derived schema](schema/README.md) is licensed separately under **CC BY 4.0**,
with upstream attribution and identification of the local adaptations. The
[SVG/PNG arrow](resources/README.md) is an original MIT-licensed resource.

Python distribution metadata describes these separate terms with
`MIT AND CC-BY-4.0`: MIT for original code and the arrow, CC BY 4.0 for the
derived schema. Dependencies installed separately retain their own licenses.

**The PyInstaller executable is not licensed entirely under MIT.** It includes
`rfc3987` (GPLv3+), Qt and other LGPL components, MPL components and separately
licensed resources. Binary redistribution compliance remains pending. See the
[licensing scope and distribution requirements](docs/licensing.md).

## Schema map

Browse the data schema interactively, with relation diagrams and every class, slot and option list:

 **[Open the schema map](https://pocoyo7798.github.io/LabProGen/)**

The page is rebuilt and republished automatically by GitHub Actions whenever
`schema/action_data_model.yaml` changes on `main`.

To build it locally:

```bash
uv run python scripts/build_schema_map.py   # writes site/index.html
```


## 1. Overview
This application allows you to build logical flowcharts for experiments. Each block represents either a physical action (e.g., stirring, heating) or a chemical entity (e.g., substances, solutions). The system automatically handles snapping, alignment, and logic rules to ensure your protocol is consistent.

---

## 2. Top Toolbar Functions

There are four main buttons at the top of the interface:

1.  **`+ Add Action`**: Opens a menu to select a new step. Actions are divided into **Elementary Actions** and **Support Actions**.
2.  **`🧪 Add Chemical`**: Opens a menu to add chemical entities (Substances, Solutions, Materials, etc.) to be used as ingredients.
3.  **`📥 Export Protocol`**: Saves your design to a `.json` file. A window will appear allowing you to choose the file name and the destination folder.
4.  **`📂 Import Protocol`**: Loads a previously saved protocol, rebuilding the entire graph, block positions, and settings exactly as they were.

---

## 3. Block Color Scheme

Colors identify the function of each element at a glance:

*   **🟧 Orange**: Represents the **Start (First Block)** of a chain.
*   **🟪 Purple**: Represents **Elementary Actions**.
*   **🟦 Blue**: Represents **Support Actions**.
*   **🟩 Green**: Represents **Chemical Entities**.

---

## 4. Interacting with Blocks

### Drag and Snap
You can move any block freely. When you bring one block close to another, they will "magnetically" snap together:
*   **Horizontal**: Blocks snap side-to-side to create a sequence.
*   **Vertical**: Vertical actions allow a flow to come from above. If you drop a block on the top half of another, it links from above creating a vertical sequence.
*   **Chemicals**: Must be dropped **directly on top** of a compatible action block. They will automatically snap to the bottom (for horizontal actions) or to the left side (for vertical actions).

### Right-Click Menu
Right-clicking a block opens a context menu:
*   **Set Vertical / Set Horizontal**: Changes the direction the block points. This is disabled if the block is currently connected to a chain.
*   **Make it First / Unmark as First**: Defines the block as an entry point. It will turn orange and disconnect from previous blocks. You can have multiple first blocks for different chains.
*   **Add Subproduct Branch**: (Exclusive to the *Separate* action) Creates a secondary vertical output for materials resulting from a separation.
*   **Delete**: Removes the block and automatically repairs the chain.

### Editing Details
**Double-click** any block to open its property form. You can define parameters such as:
*   **Values & Units**: Enter numbers and select units (e.g., °C/°F for temperature, min/h/s for duration, g/mL/mol for chemicals).
*   **Dropdowns**: Choose specific types for stirring or addition methods.

---

## 5. Advanced Features

### Moving Entire Chains (Ctrl + Drag)
*   Dragging a block normally moves only that specific block (it will detach from its chain).
*   Holding the **`Ctrl`** key while dragging a block moves **the entire connected cluster** (everything attached horizontally or vertically) as a single unit.

### Influence System (Badges)
Support actions (like Temperature) affect all blocks that follow them. You will see small colored labels (e.g., **CT1**, **CA1**) in the corners:
*   **Priority**: If a block is influenced by both a horizontal and a vertical chain of the same type, the **horizontal influence takes priority**.

### Navigation
*   **Zoom**: Use the mouse wheel while holding **`Ctrl`**, or use the **`+`** and **`-`** buttons in the top-right corner.
*   **Pan**: Click and hold the **Middle Mouse Button (Scroll Wheel)** on the background to "pull" and navigate through the workspace.

---

## 6. Constraints & Validation
1.  **Subproducts**: These are anchored to the *Separate* action. They cannot be moved individually and must specify the phase to retain before strict export.
2.  **Chemical Connections**: Chemicals can be attached to *Add* and *Continuous Addition* blocks. Continuous addition also offers an inline chemical list in its property form; use one representation per action. Trying to attach them to other actions will show a warning message.

---
*User Manual for Laboratory Protocol Builder*
