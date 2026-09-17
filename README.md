# 🧪 Laboratory Protocol Builder - User Guide

Welcome to the **Laboratory Protocol Builder**, a professional tool designed to help you create, organize, and export chemical laboratory procedures using an intuitive "smart block" system. If it is your first using it, consider answering this [Google Form](https://forms.gle/2RoHZSrXgg8aZRDV6) to give us feedback about your experience.

## 0. Download or Set Up
If you want to use the Interface Directly, download the Windows or Mac version [here](https://ulisboa-my.sharepoint.com/:f:/g/personal/ist187382_tecnico_ulisboa_pt/IgBbEPWlrYx1QJbgrnwBPx4-AYCU74uv_ykpcqADT8ZSn2Q?e=csxmn7).

### Run it as a tool

[uv](https://github.com/astral-sh/uv) can fetch the project from GitHub, build it in a temporary
environment and start it, without installing anything permanently:

```bash
uvx --from git+https://github.com/Pocoyo7798/LabProGen labprogen
```

`--from` names the package to install, `labprogen` the command it provides. Append `@` and a branch,
tag or commit to run a revision other than the default branch:

```bash
uvx --from git+https://github.com/Pocoyo7798/LabProGen@main labprogen
```

To keep the command on your PATH instead of resolving it on every run, install it as a tool:

```bash
uv tool install git+https://github.com/Pocoyo7798/LabProGen
labprogen
```

[pipx](https://github.com/pypa/pipx) installs from git the same way:

```bash
pipx install git+https://github.com/Pocoyo7798/LabProGen
labprogen
```

Each isolated environment carries its own PySide6 build, about 820 MB. The first run downloads it,
later runs reuse the cache.

### Set up for development

Follow these steps to set up a Python virtual environment and run the project.

#### Linux / macOS

```bash
cd /path/to/LabProGen
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python main.py
```

#### Windows (PowerShell)

```powershell
cd C:\path\to\LabProGen
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python main.py
```

If you already have the environment created, activate it with `source .venv/bin/activate` (Linux/macOS) and run `python main.py`.

### Where files are stored

Schemas and the config templates ship inside the `src` package. Editable settings, such as
AIedu credentials and complex action definitions, are written to:

| Runtime | Location |
| --- | --- |
| Checkout | `<project>/config/` |
| Downloaded build | `<folder holding the executable>/config/` |
| `pipx` or `uv` install | `%APPDATA%\LabProGen` (Windows), `~/.config/LabProGen` (Linux), `~/Library/Application Support/LabProGen` (macOS) |

On first run the application copies the packaged templates into that location.

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
1.  **Subproducts**: These are anchored to the *Separate* action. They cannot be moved individually and must have at least one chemical attached before you can export the protocol.
2.  **Chemical Connections**: Chemicals can only be attached to *Add*, *Change Atmosphere*, or *SubProduct Creation* blocks. Trying to attach them to other actions will show a warning message.

---
*User Manual for Laboratory Protocol Builder*
