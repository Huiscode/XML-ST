# DUT / dataType Support in xml_st_converter.py

**Date**: 2026-02-21

## Feature Name and Purpose

Extended the PLCopen XML parser to handle **DUT (Data Unit Type)** exports (structs, enums, aliases), in addition to the existing POU support. Previously, files containing only `dataType` elements (e.g. `ST_BatchMetadata.xml`) raised `"No POUs found in the XML file."`.

## Key Design Decisions

- **Additive, not breaking**: POU extraction is unchanged. DUT extraction runs as a second pass on `dataTypes/dataType` nodes.
- **Same extraction pattern**: DUTs store their plain-text ST in `addData/data[@name='...interfaceasplaintext']/InterfaceAsPlainText/xhtml`, identical to the POU pattern. Reuses `get_xhtml_text()`.
- **Unified error**: The `ValueError` now fires only when **both** POUs and DUTs yield nothing, giving a single accurate message.

## Functions Introduced

| Function | Location | Purpose |
|---|---|---|
| `extract_datatype(datatype_element)` | `xml_st_converter.py:112` | Pulls `InterfaceAsPlainText` xhtml from a single `dataType` element |

## Changes to Existing Functions

| Function | Change |
|---|---|
| `parse_xml_file()` | Now searches both `.//plc:pous/plc:pou` and `.//plc:dataTypes/plc:dataType`; combines results; updated error message |

## Known Limitations / Future Considerations

- If a DUT has no `InterfaceAsPlainText` node (e.g. auto-generated primitives), it is silently skipped. This is intentional — the plain-text representation is optional in the schema.
- Enums and aliases use the same extraction path; no special handling needed currently.

## How to Test Manually

1. Run `python xml_st_converter.py`
2. Open `ST_BatchMetadata.xml` — should display the full `TYPE ST_BatchMetadata : STRUCT ... END_TYPE` block.
3. Open `FB_TrendManager.xml` (POU) — should still work as before.
4. Open a file with both POUs and DUTs — both should appear, POUs first.
