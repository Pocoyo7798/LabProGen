# Action Data Model: license and attribution

The schema files are modified laboratory protocol models licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), separately from the
LabProGen code. The [license text](../LICENSES/CC-BY-4.0.txt) accompanies the model.

## Model contract

`action_data_model.yaml`, version 1.10.0, is the common contract for the editor,
validation, exports and schema map. Its 48 classes include the action hierarchy,
typed separation methods, cells, copolymers and zeolites. Inheritance and mixin
constraints apply to the editor fields and strict validation.

Exports declare `schema_profile: action-data-model` and the schema version.
The application envelope preserves canvas metadata; normalized `LabProcedure`
instances use `protocol_name` and `laboratory_actions`. Old aliases and lossless
structural conversions are accepted during import. Missing required values and
fields without a safe current equivalent require explicit review before export.

Python representations are generated into `labprogen/generated/`; see
[regeneration and model boundaries](../docs/models.md). The schema is preserved
as the authoritative model rather than rewritten to match application code.

## Sources and credits

The model derives from **Hendrik Borgelt's
[dcat-ap-plus-labdata](https://github.com/HendrikBorgelt/dcat-ap-plus-labdata)**,
whose laboratory profile extends **ChemDCAT-AP / DCAT-AP-PLUS**. The upstream
[profile](https://github.com/HendrikBorgelt/dcat-ap-plus-labdata/blob/39baf86ff30bc9d085a3566eac181ca816951807/src/dcat_p_lab/schema/dcat_p_lab.yaml)
and its companion chemical/material profiles declare `CC-BY 4.0`.

ChemDCAT-AP credits **Philip Strömert, Hendrik Borgelt, Mark Doerr and David
Linke**, as recorded in its
[creator metadata](https://github.com/nfdi-de/chem-dcat-ap/blob/fe267c9a0eeecf06833b9d8ae02a6dafed86c1cd/.zenodo.json).
Credit also belongs to the respective ChemDCAT-AP and
[DCAT-AP-PLUS](https://github.com/nfdi-de/dcat-ap-plus) contributors for their
material. These credits do not imply that every named contributor authored every
part of this adapted model or endorses LabProGen.

**Pedro Tavares** adapted, developed and expanded the model for LabProGen,
including local entity metadata, structured measurements and the closed action
model used for export and validation. The schema has been modified from its base;
LabProGen's Git history records the local changes. The project history also
credits **Daniel Pereira Costa** for subsequent ontology mappings and schema
refinements.

The specification named **“Action Data Model Rules and Definitions”** is
attributed to **Hendrik Borgelt's base work** on the basis of provenance
information supplied by the project maintainer. Authorship of a separately
identified version of that document has not been independently verified; this
notice does not assert sole authorship or grant a new license to that document.

## Notices and redistribution

The upstream repositories also contain root software notices, preserved verbatim:

- [dcat-ap-plus-labdata MIT notice](../LICENSES/DCAT-AP-PLUS-Labdata-MIT.txt):
  Copyright (c) 2025 Hendrik Borgelt.
- [ChemDCAT-AP MIT notice](../LICENSES/ChemDCAT-AP-MIT.txt):
  Copyright (c) 2025 Philip Strömert.

These notices do not replace the individual schemas' CC BY 4.0 declarations.
When redistributing the derived schema, retain the attribution, applicable
copyright/license notices and source/license links, indicate that the model was
modified, and avoid implying endorsement. LabProGen's root MIT license does not
replace these conditions.
