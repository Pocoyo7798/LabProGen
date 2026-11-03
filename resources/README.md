# Qt resources

`icons/arrow_down_mit.svg` is the editable source for the combo-box arrow.
`icons/arrow_down_mit.png` is its transparent 24×24 rendering. Both are original
LabProGen resources under the [MIT License](../LICENSE), Copyright (c) 2026
Daniel Pereira Costa and Pedro Tavares.

`resources.qrc` includes the PNG as `:/icons/arrow_down_mit.png`.
The committed `labprogen/resources_rc.py` registers it for source, installed and
PyInstaller runs. The interface loads the PNG and does not require SVG support
at runtime.

After modifying the PNG or QRC, regenerate the resource module from the repository
root and commit it together with the source assets:

```bash
uv run pyside6-rcc resources/resources.qrc -o labprogen/resources_rc.py
```
