# Licensing and binary redistribution

## Project code and resources

The original LabProGen code, tests, build scripts, configuration, documentation
and SVG/PNG arrow are licensed under the [MIT License](../LICENSE).
Copyright (c) 2026 Daniel Pereira Costa and Pedro Tavares.

The [derived Action Data Model](../schema/README.md) is licensed separately under
**CC BY 4.0**. Its attribution identifies Hendrik Borgelt's dcat-ap-plus-labdata,
the ChemDCAT-AP / DCAT-AP-PLUS contributors, and Pedro Tavares's adaptations.
The [resource documentation](../resources/README.md) identifies the arrow and
explains how to regenerate its Qt module.

Python archives declare **`MIT AND CC-BY-4.0`**: MIT applies to the original code
and arrow; CC BY 4.0 applies to the derived schema. The expression describes the
archive's contents, not the licenses of dependencies installed separately.
[PyPA metadata specification](https://packaging.python.org/en/latest/specifications/core-metadata/#license-expression).
The root license, upstream notices in `LICENSES/`, and schema/resource/licensing
documentation accompany the Python distributions through `license-files`.

Dependencies retain their own licenses. MIT is
[GPL-compatible](https://www.gnu.org/licenses/license-list.html#Expat), but an MIT
grant for the original code does not waive obligations for a distributed
combination. User protocols, credentials and external service results do not
receive a new license simply because LabProGen processes them.

## PyInstaller releases

**A PyInstaller executable is not entirely MIT.** In particular, the official
LinkML dependency chain includes `rfc3987` (GPLv3+). A successful build does not
establish compliance with redistribution terms. Prepare the following for each
release, using the components actually included on the target platform:

| Components | Distribution requirements |
| --- | --- |
| **GPLv3+ — rfc3987** | Preserve copyright, license and notices; meet the applicable terms for the distributed combination and provide Corresponding Source, including necessary build scripts, by an allowed method. |
| **LGPL — PySide6, Shiboken, Qt and native libraries** | Preserve licenses/notices; provide the libraries' corresponding source and modifications as required; permit debugging/reverse engineering for modifications and effective library replacement/relinking. Check any installation information requirements. Dynamic linking or one-file packaging alone does not demonstrate compliance. |
| **MPL-2.0 — certifi, fqdn** | Preserve notices, explain how to obtain the covered files' Source Code Form, and supply applicable modifications. These are file-level obligations, not an automatic license change for all project code. |
| **Cairo / Graphite2 and other multi-licensed libraries** | Identify the license option used for each distributed component, including LGPL/MPL-1.1 options, and comply with it and the additional notices. |
| **CC BY 4.0 — derived schema** | Include the attribution, source/license links and notices, identify modifications, and provide the license. See the schema attribution. |
| **Apache, MIT, BSD, ISC, CC0 and other third-party material** | Preserve required copyright, license and NOTICE files, including applicable LinkML/OpenAPI notices and third-party material embedded in native libraries. |
| **GCC runtime and PyInstaller bootloader exceptions** | Preserve applicable exception terms. The GCC Runtime Library Exception and PyInstaller Bootloader Exception do not waive other dependencies' obligations. |

Release preparation must include a platform-specific component/license inventory,
the required notices, source delivery or offers, and replacement/relinking
instructions where applicable. Account for components embedded in Qt and native
extensions, not only Python distribution metadata. Windows, macOS and Linux
builds may contain different system libraries and plugins.

`jsonasobj` 1.3.1 has inconsistent license metadata (Apache-2.0 in the license
field, CC0 in its classifier) and no license file in the inspected wheel; confirm
the applicable upstream terms before binary redistribution. The MIT project
license does not resolve that discrepancy or certify existing binary releases.

Primary references:
[GPLv3](https://www.gnu.org/licenses/gpl-3.0.html),
[Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations),
[MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en),
[PyInstaller license and exception](https://pyinstaller.org/en/stable/license.html).
